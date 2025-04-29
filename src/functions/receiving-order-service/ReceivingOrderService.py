import json
import boto3
import os
import uuid
import base64
from datetime import datetime
from decimal import Decimal
from boto3.dynamodb.conditions import Attr, And

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
    """안전하게 Decimal 값으로 변환"""
    try:
        return Decimal(str(value))
    except:
        return Decimal(str(default))

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
    """입고 주문 생성 - UI에 맞게 구현"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # UI 구조에 맞게 필드 추출
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
        
        # 문서 검증
        required_doc_types = ['INVOICE', 'BILL_OF_ENTRY', 'AIRWAY_BILL']
        doc_types_found = [doc.get('document_type', '').upper() for doc in documents]
        
        missing_docs = [doc_type for doc_type in required_doc_types if doc_type not in doc_types_found]
        if missing_docs:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': f'필수 문서가 누락되었습니다: {", ".join(missing_docs)}'}, cls=DecimalEncoder)
            }
        
        # 주문 ID 생성 및 타임스탬프
        order_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # 입고 예정일 변환
        scheduled_date = request_details.get('scheduled_date')
        try:
            if 'T' in scheduled_date:  # ISO 형식
                scheduled_date_timestamp = int(datetime.fromisoformat(scheduled_date).timestamp())
            else:  # YYYY-MM-DD 형식
                scheduled_date_timestamp = int(datetime.fromisoformat(f"{scheduled_date}T00:00:00").timestamp())
        except (ValueError, TypeError):
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': '잘못된 날짜 형식입니다. YYYY-MM-DD 또는 ISO 형식을 사용하세요.'}, cls=DecimalEncoder)
            }
        
        # 주문 데이터 생성
        order_data = {
            'order_id': order_id,
            'po_number': request_details.get('po_number', f'PO-{timestamp}'),
            'supplier_id': request_details.get('supplier_number'),
            'supplier_name': request_details.get('supplier_name'),
            'sku_name': request_details.get('sku_name'),
            'sku_number': request_details.get('sku_number'),
            'barcode': request_details.get('barcode', ''),
            'scheduled_date': scheduled_date_timestamp,
            'status': 'SCHEDULED',
            'notes': request_details.get('notes', ''),
            'shipment_number': shipment_information.get('shipment_number'),
            'truck_number': shipment_information.get('truck_number', ''),
            'driver_contact': shipment_information.get('driver_contact', ''),
            'verification_status': 'PENDING',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # DynamoDB에 주문 저장
        order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        order_table.put_item(Item=order_data)
        
        # SKU 정보 저장
        item_id = str(uuid.uuid4())
        item_data = {
            'item_id': item_id,
            'order_id': order_id,
            'product_name': request_details.get('sku_name', ''),
            'sku_number': request_details.get('sku_number', ''),
            'expected_qty': 1,  # 기본값
            'serial_or_barcode': request_details.get('barcode', ''),
            'length': safe_decimal(sku_information.get('length', 0)),
            'width': safe_decimal(sku_information.get('width', 0)),
            'height': safe_decimal(sku_information.get('height', 0)),
            'depth': safe_decimal(sku_information.get('depth', 0)),
            'volume': safe_decimal(sku_information.get('volume', 0)),
            'weight': safe_decimal(sku_information.get('weight', 0)),
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        items_table = dynamodb.Table(RECEIVING_ITEM_TABLE)
        items_table.put_item(Item=item_data)
        
        # 문서 업로드 처리
        uploaded_documents = []
        for document in documents:
            upload_result = upload_document(order_id, document, user_id)
            if upload_result:
                uploaded_documents.append(upload_result)
        
        if len(uploaded_documents) != len(documents):
            # 일부 문서 업로드 실패 - 이미 생성된 주문 및 문서 롤백 고려 가능
            print(f"Warning: Some documents failed to upload. Uploaded {len(uploaded_documents)} of {len(documents)}")
        
        # 이력 기록
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        history_id = str(uuid.uuid4())
        history_data = {
            'history_id': history_id,
            'order_id': order_id,
            'timestamp': timestamp,
            'event_type': 'ORDER_CREATED',
            'previous_status': None,
            'new_status': 'IN_PROCESS',
            'user_id': user_id,
            'notes': '입고 주문 생성 완료'
        }
        history_table.put_item(Item=history_data)
        
        # 응답용 데이터 준비
        order_data['scheduled_date_iso'] = scheduled_date
        order_data['created_at_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        order_data['updated_at_iso'] = datetime.fromtimestamp(timestamp).isoformat()
        
        # 차원 정보 포맷팅
        dimensions = {
            'length': sku_information.get('length'),
            'width': sku_information.get('width'),
            'height': sku_information.get('height'),
            'depth': sku_information.get('depth'),
            'volume': sku_information.get('volume'),
            'weight': sku_information.get('weight')
        }
        
        # 응답 생성
        return {
            'statusCode': 201,
            'headers': COMMON_HEADERS,
            'body': json.dumps({
                'order': {
                    **order_data,
                    'dimensions': dimensions
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


    """입고 주문 목록 조회"""
    try:
        # 파라미터 파싱
        query_params = event.get('queryStringParameters', {}) or {}
        supplier_id = query_params.get('supplier_id')
        status = query_params.get('status')
        from_date = query_params.get('from_date')
        to_date = query_params.get('to_date')
        
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        
        # 필터 표현식 생성
        filter_expressions = []
        expression_values = {}
        expression_names = {}
        
        # 공급업체 필터
        if supplier_id:
            filter_expressions.append('supplier_id = :supplier')
            expression_values[':supplier'] = supplier_id
        
        # 상태 필터
        if status:
            filter_expressions.append('#status = :status')
            expression_values[':status'] = status
            expression_names['#status'] = 'status'
        
        # 날짜 범위 필터
        if from_date:
            try:
                from_timestamp = int(datetime.fromisoformat(from_date).timestamp())
                filter_expressions.append('scheduled_date >= :from')
                expression_values[':from'] = from_timestamp
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}, cls=DecimalEncoder)
                }
        
        if to_date:
            try:
                to_timestamp = int(datetime.fromisoformat(to_date).timestamp())
                filter_expressions.append('scheduled_date <= :to')
                expression_values[':to'] = to_timestamp
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}, cls=DecimalEncoder)
                }
        
        # DynamoDB 쿼리 실행
        if filter_expressions:
            filter_expression = ' AND '.join(filter_expressions)
            
            if expression_names:
                response = table.scan(
                    FilterExpression=filter_expression,
                    ExpressionAttributeValues=expression_values,
                    ExpressionAttributeNames=expression_names
                )
            else:
                response = table.scan(
                    FilterExpression=filter_expression,
                    ExpressionAttributeValues=expression_values
                )
        else:
            response = table.scan()
        
        # 결과 정렬 및 가공
        items = response.get('Items', [])
        
        # ISO 날짜 형식 추가 및 포맷팅
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
            
            # 날짜 처리
            if 'scheduled_date' in item:
                formatted_item['received_date'] = datetime.fromtimestamp(item['scheduled_date']).strftime('%Y-%m-%d')
            if 'created_at' in item:
                formatted_item['created_at_iso'] = datetime.fromtimestamp(item['created_at']).isoformat()
                
            formatted_items.append(formatted_item)
        
        # 날짜 기준 내림차순 정렬
        formatted_items.sort(key=lambda x: x.get('received_date', ''), reverse=True)
        
        # 메타데이터 정보
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

def get_receiving_orders(event):
    """입고 주문 목록 조회"""
    try:
        # 파라미터 파싱
        query_params = event.get('queryStringParameters', {}) or {}
        supplier_id = query_params.get('supplier_id')
        status = query_params.get('status')
        from_date = query_params.get('from_date')
        to_date = query_params.get('to_date')
        
        table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        
        # 필터 표현식 생성
        filter_expressions = []

        # 공급업체 필터
        if supplier_id:
            filter_expressions.append(Attr('supplier_id').eq(supplier_id))

        # 상태 필터
        if status:
            filter_expressions.append(Attr('status').eq(status))

        # 날짜 범위 필터
        if from_date:
            try:
                from_timestamp = int(datetime.fromisoformat(from_date).timestamp())
                filter_expressions.append(Attr('scheduled_date').gte(from_timestamp))
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}, cls=DecimalEncoder)
                }

        if to_date:
            try:
                to_timestamp = int(datetime.fromisoformat(to_date).timestamp())
                filter_expressions.append(Attr('scheduled_date').lte(to_timestamp))
            except ValueError:
                return {
                    'statusCode': 400,
                    'headers': COMMON_HEADERS,
                    'body': json.dumps({'message': 'Invalid date format. Use ISO format (YYYY-MM-DD)'}, cls=DecimalEncoder)
                }

        # DynamoDB 쿼리 실행
        if filter_expressions:
            response = table.scan(
                FilterExpression=And(*filter_expressions)
            )
        else:
            response = table.scan()
        
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

        # 날짜 기준 내림차순 정렬
        formatted_items.sort(key=lambda x: x.get('received_date', ''), reverse=True)

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
