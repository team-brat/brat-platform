import json
import boto3
import os
import uuid
import base64
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Attr, And
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
events = boto3.client('events', region_name='us-east-2')

# 환경 변수
RECEIVING_ORDER_TABLE = os.environ.get('RECEIVING_ORDER_TABLE', 'wms-receiving-orders-dev-wms-storage-stack')
RECEIVING_ITEM_TABLE = os.environ.get('RECEIVING_ITEM_TABLE', 'wms-receiving-items-dev-wms-storage-stack')
RECEIVING_HISTORY_TABLE = os.environ.get('RECEIVING_HISTORY_TABLE', 'wms-receiving-history-dev-wms-storage-stack')
DOCUMENT_METADATA_TABLE = os.environ.get('DOCUMENT_METADATA_TABLE', 'wms-document-metadata-dev-wms-storage-stack')
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET', 'wms-documents-dev-242201288894-wms-storage-stack ')

# 표준 응답 헤더
COMMON_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
}

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def safe_decimal(value, default=0):
    """None도 안전하게 Decimal로 변환"""
    try:
        if value is None:
            return Decimal(str(default))
        return Decimal(str(value))
    except Exception:
        return Decimal(str(default))

def lambda_handler(event, context):
    """입고 주문 처리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        print(f"Using tables: Order={RECEIVING_ORDER_TABLE}, Item={RECEIVING_ITEM_TABLE}, History={RECEIVING_HISTORY_TABLE}, Doc={DOCUMENT_METADATA_TABLE}")
        
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 입고 주문 목록 조회
            if http_method == 'GET' and path == '/receiving-orders':
                return get_receiving_orders(event)
            
            # 입고 주문 생성
            elif http_method == 'POST' and path == '/receiving-orders':
                return create_receiving_order(event)
            
            # OPTIONS 메서드 처리 (CORS)
            elif http_method == 'OPTIONS':
                return {
                    'statusCode': 200,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({})
                }
            
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

#def publish_event(event_detail, detail_type, source='wms.receiving-service'):
#    """EventBridge에 이벤트 발행"""
#    try:
#        response = events.put_events(
#            Entries=[
#                {
#                    'Source': source,
#                    'DetailType': detail_type,
#                    'Detail': json.dumps(event_detail, cls=DecimalEncoder),
#                    'EventBusName': 'default'  # Add this line
#                }
#            ]
#        )
#        print(f"Event published: {response}")
#        return response
#    except Exception as e:
#        print(f"Error publishing event: {str(e)}")
#        return None

def publish_event(event_detail, detail_type, source='wms.receiving-service'):
    """EventBridge에 이벤트 발행 - 디버깅을 위해 비활성화"""
    print(f"EventBridge 이벤트 발행 비활성화됨: {detail_type}")
    return None  # 이벤트 발행 스킵
    
def upload_document(order_id, document_info, user_id):
    """문서 업로드 처리"""
    try:
        document_type = document_info.get('document_type')
        file_name = document_info.get('file_name')
        content_type = document_info.get('content_type')
        file_content = document_info.get('file_content')
        
        if not all([document_type, file_name, content_type, file_content]):
            print(f"Missing required document fields for {document_type}")
            return None
            
        # 문서 ID 및 기타 메타데이터 생성
        document_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        file_extension = file_name.split('.')[-1] if '.' in file_name else ''
        
        # S3 키 생성
        s3_key = f"{order_id}/{document_type.lower()}/{document_id}.{file_extension}"
        
        # 파일 내용 디코딩
        try:
            decoded_content = base64.b64decode(file_content)
        except Exception as e:
            print(f"Error decoding file content for {document_type}: {str(e)}")
            return None
            
        # S3에 업로드
        s3.put_object(
            Bucket=DOCUMENT_BUCKET,
            Key=s3_key,
            Body=decoded_content,
            ContentType=content_type
        )
        
        # 메타데이터 저장
        document_metadata = {
            'document_id': document_id,
            'order_id': order_id,
            'document_type': document_type,
            's3_key': s3_key,
            'file_name': file_name,
            'content_type': content_type,
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
            'document_type': document_type,
            'timestamp': timestamp
        }
        
        publish_event(event_detail, 'DocumentUploaded', 'wms.document-service')
        
        return {
            'document_id': document_id,
            'document_type': document_type,
            'file_name': file_name,
            'upload_status': 'COMPLETE'
        }
    except Exception as e:
        print(f"Error uploading document {document_type}: {str(e)}")
        return None

def create_receiving_order(event):
    """입고 주문 생성"""
    try:
        body = json.loads(event.get('body', '{}'))
        request_details = body.get('request_details', {})
        sku_information = body.get('sku_information', {})
        shipment_information = body.get('shipment_information', {})
        documents = body.get('documents', [])
        user_id = body.get('user_id', 'system')

        # 필수 필드 검증
        required_fields = [
            (request_details, 'scheduled_date', '입고 예정일이 필요합니다.'),
            (request_details, 'supplier_name', '공급업체 이름이 필요합니다.'),
            (request_details, 'supplier_number', '공급업체 번호가 필요합니다.'),
            (request_details, 'sku_name', 'SKU 이름이 필요합니다.'),
            (request_details, 'sku_number', 'SKU 번호가 필요합니다.'),
            (shipment_information, 'shipment_number', '배송 번호가 필요합니다.')
        ]
        for field_obj, field_name, error_msg in required_fields:
            if not field_obj.get(field_name):
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': error_msg}, cls=DecimalEncoder)
                }

        # 필수 문서 체크
        required_doc_types = ['INVOICE', 'BILL_OF_ENTRY', 'AIRWAY_BILL']
        doc_types_found = [doc.get('document_type', '').upper() for doc in documents]
        missing_docs = [doc_type for doc_type in required_doc_types if doc_type not in doc_types_found]
        if missing_docs:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': f'필수 문서가 누락되었습니다: {", ".join(missing_docs)}'}, cls=DecimalEncoder)
            }

        order_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())

        # 입고 예정일 처리
        scheduled_date = request_details.get('scheduled_date')
        try:
            if 'T' in scheduled_date:
                scheduled_date_timestamp = int(datetime.fromisoformat(scheduled_date).timestamp())
            else:
                scheduled_date_timestamp = int(datetime.fromisoformat(f"{scheduled_date}T00:00:00").timestamp())
        except (ValueError, TypeError):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': '잘못된 날짜 형식입니다. YYYY-MM-DD 또는 ISO 형식을 사용하세요.'}, cls=DecimalEncoder)
            }

        order_data = {
            'order_id': order_id,
            'po_number': request_details.get('po_number', f'PO-{timestamp}'),
            'supplier_id': request_details.get('supplier_number'),
            'supplier_name': request_details.get('supplier_name'),
            'sku_name': request_details.get('sku_name'),
            'sku_number': request_details.get('sku_number'),
            'barcode': request_details.get('barcode', ''),
            'scheduled_date': Decimal(str(scheduled_date_timestamp)),
            'status': 'SCHEDULED',
            'notes': request_details.get('notes', ''),
            'shipment_number': shipment_information.get('shipment_number'),
            'truck_number': shipment_information.get('truck_number', ''),
            'driver_contact': shipment_information.get('driver_contact', ''),
            'verification_status': 'PENDING',
            'created_at': Decimal(str(timestamp)),
            'updated_at': Decimal(str(timestamp))
        }

        item_id = str(uuid.uuid4())
        item_data = {
            'item_id': item_id,
            'order_id': order_id,
            'product_name': request_details.get('sku_name', ''),
            'sku_number': request_details.get('sku_number', ''),
            'expected_qty': Decimal('1'),
            'serial_or_barcode': request_details.get('barcode', ''),
            'length': safe_decimal(sku_information.get('length')),
            'width': safe_decimal(sku_information.get('width')),
            'height': safe_decimal(sku_information.get('height')),
            'depth': safe_decimal(sku_information.get('depth')),
            'volume': safe_decimal(sku_information.get('volume')),
            'weight': safe_decimal(sku_information.get('weight')),
            'created_at': Decimal(str(timestamp)),
            'updated_at': Decimal(str(timestamp))
        }

        dynamodb.Table(RECEIVING_ORDER_TABLE).put_item(Item=order_data)
        dynamodb.Table(RECEIVING_ITEM_TABLE).put_item(Item=item_data)

        # 문서 업로드
        uploaded_documents = []
        for doc in documents:
            result = upload_document(order_id, doc, user_id)
            if result:
                uploaded_documents.append(result)

        # 이력 기록
        history_data = {
            'history_id': str(uuid.uuid4()),
            'order_id': order_id,
            'timestamp': Decimal(str(timestamp)),
            'event_type': 'ORDER_CREATED',
            'previous_status': None,
            'new_status': 'IN_PROCESS',
            'user_id': user_id,
            'notes': '입고 주문 생성 완료'
        }
        dynamodb.Table(RECEIVING_HISTORY_TABLE).put_item(Item=history_data)

        # 응답
        return {
            'statusCode': 201,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'order': {
                    **order_data,
                    'scheduled_date_iso': scheduled_date,
                    'created_at_iso': datetime.fromtimestamp(timestamp).isoformat(),
                    'updated_at_iso': datetime.fromtimestamp(timestamp).isoformat(),
                    'dimensions': {
                        'length': sku_information.get('length'),
                        'width': sku_information.get('width'),
                        'height': sku_information.get('height'),
                        'depth': sku_information.get('depth'),
                        'volume': sku_information.get('volume'),
                        'weight': sku_information.get('weight')
                    }
                },
                'documents': uploaded_documents,
                'message': '입고 주문 및 문서가 성공적으로 생성되었습니다.'
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error creating receiving order: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"입고 주문 생성 중 오류가 발생했습니다: {str(e)}"}, cls=DecimalEncoder)
        }

def get_receiving_orders(event):
    """입고 주문 목록 전체 조회 (필터 없이)"""
    try:
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        response = table.scan()  # ✅ 조건 없이 전체 조회
        items = response.get('Items', [])

        # 결과 포맷팅
        formatted_items = []
        for item in items:
            formatted_item = {
                'order_id': item.get('order_id'),
                'supplier_name': item.get('supplier_name'),
                'supplier_id': item.get('supplier_id'),
                'sku_name': item.get('sku_name'),
                'sku_id': item.get('sku_number'),
                'serial_barcode': item.get('barcode', ''),
                'status': item.get('status', 'IN_PROCESS'),
                'created_at': item.get('created_at'),
                'grn_number': item.get('grn_number', '')
            }

            if 'scheduled_date' in item:
                formatted_item['received_date'] = datetime.fromtimestamp(item['scheduled_date']).strftime('%Y-%m-%d')
            if 'created_at' in item:
                formatted_item['created_at_iso'] = datetime.fromtimestamp(item['created_at']).isoformat()

            formatted_items.append(formatted_item)

        # 정렬
        formatted_items.sort(key=lambda x: x.get('received_date', ''), reverse=True)

        # 메타데이터 구성
        meta = {}
        if formatted_items:
            dates = [item.get('received_date') for item in formatted_items if 'received_date' in item]
            if dates:
                meta['date_range'] = {
                    'from': min(dates),
                    'to': max(dates)
                }

        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'orders': formatted_items,
                'count': len(formatted_items),
                'meta': meta
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting receiving orders: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error getting receiving orders: {str(e)}"}, cls=DecimalEncoder)
        }
