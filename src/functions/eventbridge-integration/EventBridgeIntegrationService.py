import json
import boto3
import os
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')
lambda_client = boto3.client('lambda')
events = boto3.client('events')

# 환경 변수
RECEIVING_ORDER_TABLE = os.environ.get('RECEIVING_ORDER_TABLE')
RECEIVING_HISTORY_TABLE = os.environ.get('RECEIVING_HISTORY_TABLE')
TECHNICAL_QUERY_FUNCTION = os.environ.get('TECHNICAL_QUERY_FUNCTION')
BINNING_FUNCTION = os.environ.get('BINNING_FUNCTION')

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """이벤트 처리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # EventBridge 이벤트 처리
        if 'source' in event and 'detail-type' in event:
            source = event['source']
            detail_type = event['detail-type']
            detail = event.get('detail', {})
            
            # 이벤트 유형에 따른 처리
            if source == 'wms.receiving-service':
                if detail_type == 'ReceivingCompleted':
                    return handle_receiving_completed(detail)
            
            elif source == 'wms.verification-service':
                if detail_type == 'InspectionPassed':
                    return handle_inspection_passed(detail)
                elif detail_type == 'DocumentVerificationCompleted':
                    return handle_document_verification(detail)
            
            # 기타 이벤트 처리
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Processed {source} {detail_type} event',
                    'detail': detail
                }, cls=DecimalEncoder)
            }
        
        # DynamoDB 스트림 이벤트 처리
        if 'Records' in event and event['Records']:
            for record in event['Records']:
                # DynamoDB 스트림 레코드
                if record.get('eventSource') == 'aws:dynamodb':
                    return handle_dynamodb_stream(record)
                
        # 직접 호출
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'EventBridge integration service executed directly',
                'event': event
            }, cls=DecimalEncoder)
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def handle_receiving_completed(detail):
    """입고 완료 이벤트 처리"""
    try:
        order_id = detail.get('order_id')
        
        if not order_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing order_id in event detail'}, cls=DecimalEncoder)
            }
            
        # 기술 검사 서비스 호출 (Lambda 함수)
        if TECHNICAL_QUERY_FUNCTION:
            try:
                response = lambda_client.invoke(
                    FunctionName=TECHNICAL_QUERY_FUNCTION,
                    InvocationType='Event',  # 비동기 호출
                    Payload=json.dumps({
                        'action': 'start_inspection',
                        'order_id': order_id
                    }, cls=DecimalEncoder)
                )
                print(f"Invoked technical query function: {response}")
            except Exception as lambda_error:
                print(f"Error invoking technical query function: {str(lambda_error)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Receiving completed event processed',
                'order_id': order_id
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error handling receiving completed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error handling receiving completed: {str(e)}"}, cls=DecimalEncoder)
        }

def handle_inspection_passed(detail):
    """검수 통과 이벤트 처리"""
    try:
        order_id = detail.get('order_id')
        
        if not order_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing order_id in event detail'}, cls=DecimalEncoder)
            }
            
        # GRN 발행 이벤트 생성
        grn_event = {
            'order_id': order_id,
            'timestamp': detail.get('timestamp')
        }
        
        publish_event(grn_event, 'GRNIssued', 'wms.technical-service')
        
        # Binning 서비스 호출 (Lambda 함수)
        if BINNING_FUNCTION:
            try:
                response = lambda_client.invoke(
                    FunctionName=BINNING_FUNCTION,
                    InvocationType='Event',  # 비동기 호출
                    Payload=json.dumps({
                        'action': 'start_binning',
                        'order_id': order_id
                    }, cls=DecimalEncoder)
                )
                print(f"Invoked binning function: {response}")
            except Exception as lambda_error:
                print(f"Error invoking binning function: {str(lambda_error)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Inspection passed event processed',
                'order_id': order_id
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error handling inspection passed: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error handling inspection passed: {str(e)}"}, cls=DecimalEncoder)
        }

def handle_document_verification(detail):
    """문서 검증 완료 이벤트 처리"""
    try:
        order_id = detail.get('order_id')
        verification_status = detail.get('verification_status')
        
        if not order_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': 'Missing order_id in event detail'}, cls=DecimalEncoder)
            }
            
        # 문서 검증 결과에 따른 처리
        if verification_status == 'APPROVED':
            # 검증 승인 시 처리 로직
            # 이미 InspectionPassed 이벤트가 발행되었으므로 추가 작업 불필요
            pass
        elif verification_status == 'DECLINED':
            # 검증 거부 시 처리 로직
            # 입고 주문 상태 업데이트
            order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
            order_table.update_item(
                Key={'order_id': order_id},
                UpdateExpression="set #status = :status",
                ExpressionAttributeValues={
                    ':status': 'REJECTED'
                },
                ExpressionAttributeNames={'#status': 'status'}
            )
            
            # 거부 이벤트 발행
            rejection_event = {
                'order_id': order_id,
                'reason': 'Document verification declined',
                'timestamp': detail.get('timestamp')
            }
            
            publish_event(rejection_event, 'ReceivingRejected', 'wms.verification-service')
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Document verification event processed',
                'order_id': order_id,
                'status': verification_status
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error handling document verification: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error handling document verification: {str(e)}"}, cls=DecimalEncoder)
        }

def handle_dynamodb_stream(record):
    """DynamoDB 스트림 이벤트 처리"""
    try:
        event_name = record.get('eventName')
        
        # 변경 유형에 따른 처리
        if event_name == 'MODIFY':
            # 수정 이벤트 처리
            new_image = record.get('dynamodb', {}).get('NewImage', {})
            old_image = record.get('dynamodb', {}).get('OldImage', {})
            
            # DynamoDB 데이터를 Python 형식으로 변환
            new_data = convert_dynamodb_to_python(new_image)
            old_data = convert_dynamodb_to_python(old_image)
            
            table_name = record.get('eventSourceARN', '').split('/')[1]
            
            # 입고 주문 테이블 이벤트 처리
            if table_name == RECEIVING_ORDER_TABLE:
                # 상태 변경 감지
                if 'status' in new_data and 'status' in old_data:
                    new_status = new_data['status']
                    old_status = old_data['status']
                    
                    if new_status != old_status:
                        # 상태 변경에 따른 이벤트 발행
                        handle_order_status_change(new_data, old_status, new_status)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'DynamoDB stream event {event_name} processed'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error handling DynamoDB stream: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error handling DynamoDB stream: {str(e)}"}, cls=DecimalEncoder)
        }

def handle_order_status_change(order_data, old_status, new_status):
    """입고 주문 상태 변경 처리"""
    order_id = order_data.get('order_id')
    
    # 특정 상태 변경에 따른 이벤트 발행
    if new_status == 'COMPLETED' and old_status != 'COMPLETED':
        # 입고 완료 이벤트 발행
        event_detail = {
            'order_id': order_id,
            'supplier_id': order_data.get('supplier_id'),
            'timestamp': order_data.get('updated_at')
        }
        
        publish_event(event_detail, 'ReceivingCompleted', 'wms.receiving-service')
    
    elif new_status == 'REJECTED' and old_status != 'REJECTED':
        # 입고 거부 이벤트 발행
        event_detail = {
            'order_id': order_id,
            'reason': 'Order status changed to REJECTED',
            'timestamp': order_data.get('updated_at')
        }
        
        publish_event(event_detail, 'ReceivingRejected', 'wms.receiving-service')

def convert_dynamodb_to_python(dynamodb_data):
    """DynamoDB 데이터를 Python 형식으로 변환"""
    if not dynamodb_data:
        return {}
        
    result = {}
    
    for key, value in dynamodb_data.items():
        for data_type, data_value in value.items():
            if data_type == 'S':
                result[key] = data_value
            elif data_type == 'N':
                result[key] = Decimal(data_value)
            elif data_type == 'BOOL':
                result[key] = data_value
            elif data_type == 'NULL':
                result[key] = None
            elif data_type == 'M':
                result[key] = convert_dynamodb_to_python(data_value)
            elif data_type == 'L':
                result[key] = [convert_dynamodb_to_python(item) for item in data_value]
    
    return result

def publish_event(event_detail, detail_type, source='wms.event-service'):
    """EventBridge에 이벤트 발행"""
    try:
        response = events.put_events(
            Entries=[
                {
                    'Source': source,
                    'DetailType': detail_type,
                    'Detail': json.dumps(event_detail, cls=DecimalEncoder)
                }
            ]
        )
        print(f"Event published: {response}")
        return response
    except Exception as e:
        print(f"Error publishing event: {str(e)}")
        return None