import json
import boto3
import os
import uuid
import base64
from datetime import datetime
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
events = boto3.client('events')

# 환경 변수
RECEIVING_ORDER_TABLE = os.environ.get('RECEIVING_ORDER_TABLE')
RECEIVING_ITEM_TABLE = os.environ.get('RECEIVING_ITEM_TABLE')
RECEIVING_HISTORY_TABLE = os.environ.get('RECEIVING_HISTORY_TABLE')
DOCUMENT_METADATA_TABLE = os.environ.get('DOCUMENT_METADATA_TABLE', 'wms-document-metadata-dev')
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET', 'wms-documents-dev-242201288894')

# 표준 응답 헤더
COMMON_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': 'http://localhost:3000',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Credentials': 'true'
}

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """입고 주문 처리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 입고 주문 목록 조회
            if http_method == 'GET' and path == '/receiving-orders':
                return get_receiving_orders(event)
            
            # 특정 입고 주문 조회
            elif http_method == 'GET' and path.startswith('/receiving-orders/') and path_params.get('order_id'):
                return get_receiving_order(path_params['order_id'])
            
            # 입고 주문 생성
            elif http_method == 'POST' and path == '/receiving-orders':
                return create_receiving_order(event)
            
            # 입고 주문 업데이트 (상태 변경 등)
            elif http_method == 'PUT' and path.startswith('/receiving-orders/') and path_params.get('order_id'):
                return update_receiving_order(event, path_params['order_id'])
                
            # 입고 주문 삭제
            elif http_method == 'DELETE' and path.startswith('/receiving-orders/') and path_params.get('order_id'):
                return delete_receiving_order(path_params['order_id'])
                
            # 입고 처리 (실제 입고 확정)
            elif http_method == 'POST' and path.startswith('/receiving-orders/') and path_params.get('order_id') and path.endswith('/receive'):
                return process_receiving(event, path_params['order_id'])

            # 상태 업데이트
            elif http_method == 'PUT' and path.startswith('/receiving-orders/') and path_params.get('order_id') and path.endswith('/status'):
                return update_order_status(event, path_params['order_id'])
            
            # 기본 응답
            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({
                    'message': 'Endpoint not found',
                    'path': path,
                    'method': http_method
                }, cls=DecimalEncoder)
            }
        
        # 직접 호출
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Receiving order service executed directly',
                'event': event
            }, cls=DecimalEncoder)
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def publish_event(event_detail, detail_type, source='wms.receiving-service'):
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

def upload_document(order_id, doc_type, file_info, user_id):
    """문서 업로드 처리"""
    try:
        if not all(key in file_info for key in ['file_name', 'content_type', 'file_content']):
            print(f"Missing required document fields for {doc_type}")
            return None
            
        # 문서 ID 및 기타 메타데이터 생성
        document_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        file_name = file_info.get('file_name')
        file_extension = file_name.split('.')[-1] if '.' in file_name else ''
        
        # S3 키 생성
        s3_key = f"{order_id}/{doc_type.lower()}/{document_id}.{file_extension}"
        
        # 파일 내용 디코딩
        file_content = file_info.get('file_content')
        if file_content == "<base64-encoded-content>":
            # 테스트용 샘플 내용
            decoded_content = b"Sample document content for testing"
        else:
            try:
                decoded_content = base64.b64decode(file_content)
            except Exception as e:
                print(f"Error decoding file content for {doc_type}: {str(e)}")
                return None
            
        # S3에 업로드
        s3.put_object(
            Bucket=DOCUMENT_BUCKET,
            Key=s3_key,
            Body=decoded_content,
            ContentType=file_info.get('content_type')
        )
        
        # 메타데이터 저장
        document_metadata = {
            'document_id': document_id,
            'order_id': order_id,
            'document_type': doc_type.upper(),
            's3_key': s3_key,
            'file_name': file_name,
            'content_type': file_info.get('content_type'),
            'upload_date': timestamp,
            'uploader': user_id,
            'verification_status': 'PENDING',
            'verification_notes': ''
        }
        
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        table.put_item(Item=document_metadata)
        
        # 문서 업로드 이벤트 발행
        event_detail = {
            'document_id': document_id,
            'order_id': order_id,
            'document_type': doc_type.upper(),
            'timestamp': timestamp
        }
        
        publish_event(event_detail, 'DocumentUploaded', 'wms.document-service')
        
        return document_id
    except Exception as e:
        print(f"Error uploading document {doc_type}: {str(e)}")
        return None

def create_receiving_order(event):
    """입고 주문 생성 - 새로운 구조 지원"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 새로운 구조 확인 (request_details, sku_information, shipment_information)
        is_new_structure = all(key in body for key in ['request_details', 'sku_information', 'shipment_information'])
        
        if is_new_structure:
            # 새 구조 처리
            return create_receiving_order_new_structure(body)
        else:
            # 이전 구조 처리 (하위 호환성 유지)
            return create_receiving_order_legacy(body)
            
    except Exception as e:
        print(f"Error creating receiving order: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error creating receiving order: {str(e)}"}, cls=DecimalEncoder)
        }

def create_receiving_order_new_structure(body):
    """새로운 구조의 입고 주문 생성"""
    try:
        # 필요한 섹션 추출
        request_details = body.get('request_details', {})
        sku_info = body.get('sku_information', {})
        shipment_info = body.get('shipment_information', {})
        documents = body.get('documents', {})
        user_id = body.get('user_id', 'system')
        
        # 필수 필드 검증
        if not request_details.get('scheduled_date'):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Missing scheduled_date in request_details'}, cls=DecimalEncoder)
            }
            
        if not (request_details.get('supplier_name') and request_details.get('supplier_number')):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Missing supplier information in request_details'}, cls=DecimalEncoder)
            }
            
        if not sku_info.get('sku_number'):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Missing sku_number in sku_information'}, cls=DecimalEncoder)
            }
            
        if not shipment_info.get('shipment_number'):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Missing shipment_number in shipment_information'}, cls=DecimalEncoder)
            }
            
        # 주문 ID 생성 및 타임스탬프
        order_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # 날짜 변환
        scheduled_date = request_details.get('scheduled_date')
        try:
            # 날짜 형식 확인 (YYYY-MM-DD 또는 ISO 형식)
            if 'T' in scheduled_date:  # ISO 형식 (YYYY-MM-DDTHH:MM:SS)
                scheduled_date_timestamp = int(datetime.fromisoformat(scheduled_date).timestamp())
            else:  # YYYY-MM-DD 형식
                scheduled_date_timestamp = int(datetime.fromisoformat(f"{scheduled_date}T00:00:00").timestamp())
        except (ValueError, TypeError):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Invalid scheduled_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS) or YYYY-MM-DD'}, cls=DecimalEncoder)
            }
            
        # 주문 데이터 생성
        order_data = {
            'order_id': order_id,
            'po_number': request_details.get('po_number', f'PO-{timestamp}'),
            'supplier_id': request_details.get('supplier_number'),
            'supplier_name': request_details.get('supplier_name'),
            'contact_name': request_details.get('contact_name', ''),
            'contact_phone': request_details.get('contact_phone', ''),
            'responsible_person': request_details.get('responsible_person', ''),
            'scheduled_date': scheduled_date_timestamp,
            'status': 'SCHEDULED',
            'notes': request_details.get('notes', ''),
            'shipment_number': shipment_info.get('shipment_number'),
            'truck_number': shipment_info.get('truck_number', ''),
            'driver_contact': shipment_info.get('driver_contact_info', ''),
            'verification_status': 'PENDING',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # DynamoDB에 주문 저장
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        table.put_item(Item=order_data)
        
        # 입고 품목 저장 (SKU 정보 기반)
        item_id = str(uuid.uuid4())
        item_data = {
            'item_id': item_id,
            'order_id': order_id,
            'product_name': sku_info.get('sku_name', ''),
            'sku_number': sku_info.get('sku_number', ''),
            'expected_qty': sku_info.get('quantity', 1),  # 수량 기본값 1
            'serial_or_barcode': sku_info.get('serial_or_barcode', ''),
            'length': sku_info.get('length', 0),
            'width': sku_info.get('width', 0),
            'height': sku_info.get('height', 0),
            'depth': sku_info.get('depth', 0),
            'volume': sku_info.get('volume', 0),
            'weight': sku_info.get('weight', 0),
            'notes': sku_info.get('notes', ''),
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        items_table = dynamodb.Table(RECEIVING_ITEM_TABLE)
        items_table.put_item(Item=item_data)
        
        # 문서 업로드 처리
        uploaded_docs = {}
        document_types = ['invoice', 'bill_of_entry', 'airway_bill']
        
        for doc_type in document_types:
            if doc_type in documents:
                doc_id = upload_document(order_id, doc_type, documents[doc_type], user_id)
                if doc_id:
                    uploaded_docs[doc_type] = doc_id
        
        # 이력 기록
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        history_id = str(uuid.uuid4())
        history_data = {
            'history_id': history_id,
            'order_id': order_id,
            'timestamp': timestamp,
            'event_type': 'ORDER_CREATED',
            'previous_status': None,
            'new_status': 'SCHEDULED',
            'user_id': user_id,
            'notes': 'Receiving order created with new structure'
        }
        history_table.put_item(Item=history_data)
        
        # ISO 형식의 날짜 추가 (응답용)
        order_data['scheduled_date_iso'] = request_details.get('scheduled_date')
        order_data['created_at_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        order_data['updated_at_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        
        # SKU 및 문서 정보 추가 (응답용)
        response_data = {
            'order': order_data,
            'item': item_data,
            'documents': uploaded_docs,
            'message': 'Receiving order created successfully'
        }
        
        return {
            'statusCode': 201,
            'headers': COMMON_HEADERS,
            'body': json.dumps(response_data, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error creating receiving order with new structure: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error creating receiving order: {str(e)}"}, cls=DecimalEncoder)
        }

def create_receiving_order_legacy(body):
    """기존 구조의 입고 주문 생성 (하위 호환성)"""
    try:
        # 필수 필드 검증
        required_fields = ['supplier_id', 'supplier_name', 'scheduled_date', 'items', 'shipment_number']
        missing_fields = [field for field in required_fields if field not in body]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': f'Missing required fields: {", ".join(missing_fields)}'}, cls=DecimalEncoder)
            }
        
        # 주문 ID 생성 및 타임스탬프
        order_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # ISO 형식의 날짜를 타임스탬프로 변환
        scheduled_date = body.get('scheduled_date')
        try:
            scheduled_date_timestamp = int(datetime.fromisoformat(scheduled_date).timestamp())
        except (ValueError, TypeError):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Invalid scheduled_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}, cls=DecimalEncoder)
            }
        
        # 주문 데이터 생성
        order_data = {
            'order_id': order_id,
            'po_number': body.get('po_number', f'PO-{timestamp}'),
            'supplier_id': body.get('supplier_id'),
            'supplier_name': body.get('supplier_name'),
            'contact_name': body.get('contact_name'),
            'contact_phone': body.get('contact_phone'),
            'responsible_person': body.get('responsible_person'),
            'scheduled_date': scheduled_date_timestamp,
            'status': 'SCHEDULED',
            'notes': body.get('notes', ''),
            'shipment_number': body.get('shipment_number'),
            'truck_number': body.get('truck_number'),
            'driver_contact': body.get('driver_contact'),
            'verification_status': 'PENDING',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # DynamoDB에 주문 저장
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        table.put_item(Item=order_data)
        
        # 입고 품목 저장
        items = body.get('items', [])
        for item in items:
            item_id = str(uuid.uuid4())
            item_data = {
                'item_id': item_id,
                'order_id': order_id,
                'product_name': item.get('product_name'),
                'sku_number': item.get('sku_number'),
                'expected_qty': item.get('expected_qty'),
                'serial_or_barcode': item.get('serial_or_barcode', ''),
                'length': item.get('length', 0),
                'width': item.get('width', 0),
                'height': item.get('height', 0),
                'depth': item.get('depth', 0),
                'volume': item.get('volume', 0),
                'weight': item.get('weight', 0),
                'created_at': timestamp,
                'updated_at': timestamp
            }
            
            items_table = dynamodb.Table(RECEIVING_ITEM_TABLE)
            items_table.put_item(Item=item_data)
        
        # 이력 기록
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        history_id = str(uuid.uuid4())
        history_data = {
            'history_id': history_id,
            'order_id': order_id,
            'timestamp': timestamp,
            'event_type': 'ORDER_CREATED',
            'previous_status': None,
            'new_status': 'SCHEDULED',
            'user_id': body.get('user_id', 'system'),
            'notes': 'Receiving order created'
        }
        history_table.put_item(Item=history_data)
        
        # ISO 형식의 날짜 추가 (응답용)
        order_data['scheduled_date_iso'] = scheduled_date
        order_data['created_at_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        order_data['updated_at_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        
        return {
            'statusCode': 201,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'order': order_data,
                'message': 'Receiving order created successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error creating receiving order with legacy structure: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error creating receiving order: {str(e)}"}, cls=DecimalEncoder)
        }

def process_receiving(event, order_id):
    """입고 처리 (실제 입고 확정)"""
    try:
        body = json.loads(event.get('body', '{}'))
        received_items = body.get('received_items', [])
        
        # 기존 주문 조회
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        response = table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Receiving order not found'}, cls=DecimalEncoder)
            }
            
        existing_order = response['Item']
        
        # 상태 제한 (취소된 주문은 입고 처리 불가)
        if existing_order.get('status') in ['CANCELLED', 'DELETED']:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Cannot process a cancelled or deleted receiving order'}, cls=DecimalEncoder)
            }
            
        # 이미 완료된 주문이면 중복 처리 방지
        if existing_order.get('status') == 'COMPLETED':
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Receiving order has already been completed'}, cls=DecimalEncoder)
            }
            
        # 입고 처리 로직 구현...
        timestamp = int(datetime.now().timestamp())
        
        # 입고 주문 업데이트
        table.update_item(
            Key={'order_id': order_id},
            UpdateExpression="set #status = :status, updated_at = :time, received_at = :rtime, verification_status = :vstat",
            ExpressionAttributeValues={
                ':status': 'COMPLETED',
                ':time': timestamp,
                ':rtime': timestamp,
                ':vstat': 'COMPLETED'
            },
            ExpressionAttributeNames={'#status': 'status'}
        )
        
        # GRN 번호 생성
        grn_number = f"GRN-{timestamp}-{order_id[:8]}"
        
        # 이력 기록
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        history_id = str(uuid.uuid4())
        history_data = {
            'history_id': history_id,
            'order_id': order_id,
            'timestamp': timestamp,
            'event_type': 'RECEIVING_COMPLETED',
            'previous_status': existing_order.get('status'),
            'new_status': 'COMPLETED',
            'user_id': body.get('user_id', 'system'),
            'notes': f'Receiving completed with GRN: {grn_number}'
        }
        history_table.put_item(Item=history_data)
        
        # 이벤트 발행
        event_detail = {
            'order_id': order_id,
            'supplier_id': existing_order.get('supplier_id'),
            'supplier_name': existing_order.get('supplier_name'),
            'timestamp': timestamp,
            'grn_number': grn_number
        }
        
        publish_event(event_detail, 'ReceivingCompleted')
        
        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'order_id': order_id,
                'status': 'COMPLETED',
                'grn_number': grn_number,
                'message': 'Receiving completed successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error processing receiving: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error processing receiving: {str(e)}"}, cls=DecimalEncoder)
        }

def update_order_status(event, order_id):
    """주문 상태 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        new_status = body.get('status')
        
        if not new_status:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Status is required'}, cls=DecimalEncoder)
            }
            
        valid_statuses = ['SCHEDULED', 'IN_PROGRESS', 'COMPLETED', 'REJECTED']
        if new_status not in valid_statuses:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, cls=DecimalEncoder)
            }
        
        # 기존 주문 조회
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        response = table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Receiving order not found'}, cls=DecimalEncoder)
            }
            
        existing_order = response['Item']
        previous_status = existing_order.get('status')
        
        # 상태 변경 불가 케이스
        if previous_status == 'DELETED':
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Cannot update status of a deleted order'}, cls=DecimalEncoder)
            }
            
        timestamp = int(datetime.now().timestamp())
        
        # 주문 상태 업데이트
        table.update_item(
            Key={'order_id': order_id},
            UpdateExpression="set #status = :status, updated_at = :time",
            ExpressionAttributeValues={
                ':status': new_status,
                ':time': timestamp
            },
            ExpressionAttributeNames={'#status': 'status'}
        )
        
        # 이력 기록
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        history_id = str(uuid.uuid4())
        history_data = {
            'history_id': history_id,
            'order_id': order_id,
            'timestamp': timestamp,
            'event_type': 'STATUS_CHANGED',
            'previous_status': previous_status,
            'new_status': new_status,
            'user_id': body.get('user_id', 'system'),
            'notes': body.get('notes', f'Status changed from {previous_status} to {new_status}')
        }
        history_table.put_item(Item=history_data)
        
        # 상태가 특정 값일 때 이벤트 발행
        if new_status == 'COMPLETED':
            event_detail = {
                'order_id': order_id,
                'supplier_id': existing_order.get('supplier_id'),
                'timestamp': timestamp
            }
            publish_event(event_detail, 'ReceivingCompleted')
        
        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'order_id': order_id,
                'previous_status': previous_status,
                'status': new_status,
                'message': 'Status updated successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error updating order status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error updating order status: {str(e)}"}, cls=DecimalEncoder)
        }

def update_receiving_order(event, order_id):
    """입고 주문 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 기존 주문 조회
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        response = table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Receiving order not found'}, cls=DecimalEncoder)
            }
            
        existing_order = response['Item']
        
        # 상태 변경 제한 (완료된 주문은 변경 불가)
        if existing_order.get('status') == 'COMPLETED':
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Cannot update a completed receiving order'}, cls=DecimalEncoder)
            }
            
        # 변경 항목 준비
        update_expression = "set updated_at = :time"
        expression_values = {
            ':time': int(datetime.now().timestamp())
        }
        
        # 스케줄 날짜 업데이트
        if 'scheduled_date' in body:
            try:
                # ISO 형식의 날짜 문자열을 timestamp로 변환
                scheduled_date_timestamp = int(datetime.fromisoformat(body['scheduled_date']).timestamp())
                update_expression += ", scheduled_date = :sdate"
                expression_values[':sdate'] = scheduled_date_timestamp
            except (ValueError, TypeError):
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': 'Invalid scheduled_date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'}, cls=DecimalEncoder)
                }
        
        # 상태 업데이트
        if 'status' in body:
            valid_statuses = ['SCHEDULED', 'CONFIRMED', 'IN_PROGRESS', 'CANCELLED']
            if body['status'] not in valid_statuses:
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}, cls=DecimalEncoder)
                }
            update_expression += ", #status = :status"
            expression_values[':status'] = body['status']
        
        # 기타 필드 업데이트
        update_fields = {
            'supplier_name': 'sname',
            'contact_name': 'cname',
            'contact_phone': 'cphone',
            'responsible_person': 'resperson',
            'notes': 'notes',
            'po_number': 'ponum'
        }
        
        for field, short in update_fields.items():
            if field in body:
                update_expression += f", {field} = :{short}"
                expression_values[f':{short}'] = body[field]
        
        # 품목 업데이트 (전체 대체)
        if 'items' in body:
            items = body['items']
            # 품목 데이터 검증
            if not isinstance(items, list) or len(items) == 0:
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': 'Items must be a non-empty array'}, cls=DecimalEncoder)
                }
                
            for item in items:
                if not all(k in item for k in ['item_id', 'product_name', 'expected_qty']):
                    return {
                        'statusCode': 400,
                        'headers': COMMON_HEADERS,
                        'body': json.dumps({'message': 'Each item must have item_id, product_name, and expected_qty'}, cls=DecimalEncoder)
                    }
            
            update_expression += ", items = :items"
            expression_values[':items'] = items
        
        # DynamoDB 업데이트
        expression_names = {'#status': 'status'} if 'status' in body else {}

        table.update_item(
            Key={'order_id': order_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues="ALL_NEW"
        )

        # 업데이트된 주문 조회
        response = table.get_item(Key={'order_id': order_id})
        updated_order = response['Item']

        # 날짜 변환 (Timestamp → ISO 문자열)
        if 'scheduled_date' in updated_order and isinstance(updated_order['scheduled_date'], (int, float)):
            updated_order['scheduled_date_iso'] = datetime.fromtimestamp(updated_order['scheduled_date']).isoformat()
        if 'created_at' in updated_order and isinstance(updated_order['created_at'], (int, float)):
            updated_order['created_at_iso'] = datetime.fromtimestamp(updated_order['created_at']).isoformat()
        if 'updated_at' in updated_order and isinstance(updated_order['updated_at'], (int, float)):
            updated_order['updated_at_iso'] = datetime.fromtimestamp(updated_order['updated_at']).isoformat()
        if 'received_at' in updated_order and isinstance(updated_order['received_at'], (int, float)):
            updated_order['received_at_iso'] = datetime.fromtimestamp(updated_order['received_at']).isoformat()
            
        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'order': updated_order,
                'message': 'Receiving order updated successfully'
            }, cls=DecimalEncoder)
        }