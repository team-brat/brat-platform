import json
import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')
events = boto3.client('events')

# 환경 변수
VERIFICATION_RESULT_TABLE = os.environ.get('VERIFICATION_RESULT_TABLE')
DOCUMENT_METADATA_TABLE = os.environ.get('DOCUMENT_METADATA_TABLE')
RECEIVING_ORDER_TABLE = os.environ.get('RECEIVING_ORDER_TABLE')

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """검증 처리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 검증 결과 조회
            if http_method == 'GET' and path == '/verification-results':
                return get_verification_results(event)
            
            # 문서 검증 제출
            elif http_method == 'POST' and path.startswith('/receiving-orders/') and path_params.get('order_id') and path.endswith('/documents/verify'):
                return verify_documents(event, path_params['order_id'])
                
            # 기본 응답
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
                },
                'body': json.dumps({
                    'message': 'Endpoint not found',
                    'path': path,
                    'method': http_method
                }, cls=DecimalEncoder)
            }
        
        # EventBridge 이벤트 처리
        if 'source' in event and event['source'] == 'wms.document-service':
            if event['detail-type'] == 'DocumentUploaded':
                # 문서 업로드 이벤트 처리
                return handle_document_uploaded(event['detail'])

        # 직접 호출
        return {
            'statusCode': 200,
            'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
                },
            'body': json.dumps({
                'message': 'Verification service executed directly',
                'event': event
            }, cls=DecimalEncoder)
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
                },
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def get_verification_results(event):
    """검증 결과 목록 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        order_id = query_params.get('order_id')
        
        table = dynamodb.Table(VERIFICATION_RESULT_TABLE)
        
        if order_id:
            # 특정 주문의 검증 결과 조회
            # GSI 필요: order_id-index
            response = table.query(
                IndexName='order_id-index',
                KeyConditionExpression='order_id = :order_id',
                ExpressionAttributeValues={
                    ':order_id': order_id
                }
            )
        else:
            # 전체 결과 스캔 (프로덕션에서는 권장하지 않음)
            response = table.scan()
            
        results = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'results': results,
                'count': len(results)
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting verification results: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting verification results: {str(e)}"}, cls=DecimalEncoder)
        }

def verify_documents(event, order_id):
    """문서 검증 결과 제출"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 필수 필드 검증
        if 'verification_results' not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Missing verification_results field'}, cls=DecimalEncoder)
            }
        
        verification_results = body.get('verification_results', [])
        
        # 입고 주문 조회
        order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        order_response = order_table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in order_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Receiving order not found'}, cls=DecimalEncoder)
            }
            
        # 기존 주문 정보
        existing_order = order_response['Item']
        
        # 주문 상태 검증
        if existing_order.get('status') in ['COMPLETED', 'CANCELLED', 'DELETED']:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Cannot verify documents for order in {existing_order.get("status")} status'}, cls=DecimalEncoder)
            }
        
        # 문서 조회 및 검증 상태 업데이트
        document_table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        verification_table = dynamodb.Table(VERIFICATION_RESULT_TABLE)
        
        timestamp = int(datetime.now().timestamp())
        overall_result = 'APPROVED'  # 기본값
        saved_results = []
        
        for result in verification_results:
            document_id = result.get('document_id')
            verification_result = result.get('result', 'DECLINED')
            notes = result.get('notes', '')
            
            # 검증 결과가 DECLINED면 전체 결과도 DECLINED
            if verification_result == 'DECLINED':
                overall_result = 'DECLINED'
            
            # 문서 메타데이터 업데이트
            document_table.update_item(
                Key={'document_id': document_id},
                UpdateExpression="set verification_status = :status, verification_notes = :notes",
                ExpressionAttributeValues={
                    ':status': verification_result,
                    ':notes': notes
                }
            )
            
            # 검증 결과 저장
            verification_id = str(uuid.uuid4())
            verification_data = {
                'verification_id': verification_id,
                'order_id': order_id,
                'document_id': document_id,
                'verification_type': 'DOCUMENT',
                'result': verification_result,
                'verifier': body.get('user_id', 'system'),
                'verification_date': timestamp,
                'notes': notes,
                'discrepancies': result.get('discrepancies', '')
            }
            
            verification_table.put_item(Item=verification_data)
            saved_results.append(verification_data)
        
        # 주문 상태 업데이트
        new_verification_status = overall_result
        order_table.update_item(
            Key={'order_id': order_id},
            UpdateExpression="set verification_status = :status, updated_at = :time",
            ExpressionAttributeValues={
                ':status': new_verification_status,
                ':time': timestamp
            }
        )
        
        # 이벤트 발행
        event_detail = {
            'order_id': order_id,
            'verification_status': new_verification_status,
            'timestamp': timestamp
        }
        
        publish_event(event_detail, 'DocumentVerificationCompleted')
        
        # 문서 검증이 승인되면 InspectionPassed 이벤트 발행
        if new_verification_status == 'APPROVED':
            inspection_event = {
                'order_id': order_id,
                'supplier_id': existing_order.get('supplier_id'),
                'timestamp': timestamp
            }
            publish_event(inspection_event, 'InspectionPassed')
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'verification_status': new_verification_status,
                'results': saved_results,
                'message': 'Document verification completed'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error verifying documents: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error verifying documents: {str(e)}"}, cls=DecimalEncoder)
        }

def handle_document_uploaded(detail):
    """문서 업로드 이벤트 처리"""
    try:
        document_id = detail.get('document_id')
        order_id = detail.get('order_id')
        
        # 주문의 모든 문서 조회
        document_table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        response = document_table.query(
            IndexName='order_id-index',
            KeyConditionExpression='order_id = :order_id',
            ExpressionAttributeValues={
                ':order_id': order_id
            }
        )
        
        documents = response.get('Items', [])
        
        # 문서 유형별 카운트
        document_types = {}
        for doc in documents:
            doc_type = doc.get('document_type')
            document_types[doc_type] = document_types.get(doc_type, 0) + 1
        
        # 필요한 모든 문서가 업로드되었는지 확인
        required_types = ['INVOICE', 'BILL_OF_ENTRY', 'AIRWAY_BILL']
        all_documents_uploaded = all(document_types.get(doc_type, 0) > 0 for doc_type in required_types)
        
        if all_documents_uploaded:
            # 모든 문서가 업로드되었으면 이벤트 발행
            event_detail = {
                'order_id': order_id,
                'document_count': len(documents),
                'timestamp': int(datetime.now().timestamp())
            }
            
            publish_event(event_detail, 'AllDocumentsUploaded')
            
            # 주문 상태 업데이트 - 필요에 따라
            order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
            order_table.update_item(
                Key={'order_id': order_id},
                UpdateExpression="set documents_status = :status, updated_at = :time",
                ExpressionAttributeValues={
                    ':status': 'READY_FOR_VERIFICATION',
                    ':time': int(datetime.now().timestamp())
                }
            )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Document upload event processed',
                'all_documents_uploaded': all_documents_uploaded
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error handling document uploaded event: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def publish_event(event_detail, detail_type, source='wms.verification-service'):
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