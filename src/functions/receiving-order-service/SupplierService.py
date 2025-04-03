import json
import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')

# 환경 변수
SUPPLIER_TABLE = os.environ.get('SUPPLIER_TABLE')
RECEIVING_HISTORY_TABLE = os.environ.get('RECEIVING_HISTORY_TABLE')

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """공급업체 관리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 공급업체 목록 조회
            if http_method == 'GET' and path == '/suppliers':
                return get_suppliers(event)
            
            # 특정 공급업체 조회
            elif http_method == 'GET' and path.startswith('/suppliers/') and path_params.get('supplier_id'):
                return get_supplier(path_params['supplier_id'])
            
            # 공급업체 생성
            elif http_method == 'POST' and path == '/suppliers':
                return create_supplier(event)
            
            # 공급업체 업데이트
            elif http_method == 'PUT' and path.startswith('/suppliers/') and path_params.get('supplier_id'):
                return update_supplier(event, path_params['supplier_id'])
                
            # 공급업체 삭제
            elif http_method == 'DELETE' and path.startswith('/suppliers/') and path_params.get('supplier_id'):
                return delete_supplier(path_params['supplier_id'])
                
            # 공급업체 입고 이력 조회
            elif http_method == 'GET' and path.startswith('/suppliers/') and path_params.get('supplier_id') and path.endswith('/inbound-history'):
                return get_supplier_inbound_history(path_params['supplier_id'])
                
            # 공급업체 출고 이력 조회
            elif http_method == 'GET' and path.startswith('/suppliers/') and path_params.get('supplier_id') and path.endswith('/outbound-history'):
                return get_supplier_outbound_history(path_params['supplier_id'])
            
            # 기본 응답
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
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
                'message': 'Supplier service executed directly',
                'event': event
            }, cls=DecimalEncoder)
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def get_suppliers(event):
    """공급업체 목록 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        supplier_name = query_params.get('supplier_name')
        
        table = dynamodb.Table(SUPPLIER_TABLE)
        
        if supplier_name:
            # 공급업체 이름으로 필터링 (GSI 필요)
            response = table.scan(
                FilterExpression='contains(supplier_name, :name)',
                ExpressionAttributeValues={
                    ':name': supplier_name
                }
            )
        else:
            # 모든 공급업체 조회
            response = table.scan()
            
        suppliers = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'suppliers': suppliers,
                'count': len(suppliers)
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting suppliers: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting suppliers: {str(e)}"}, cls=DecimalEncoder)
        }

def get_supplier(supplier_id):
    """특정 공급업체 조회"""
    try:
        table = dynamodb.Table(SUPPLIER_TABLE)
        
        response = table.get_item(
            Key={
                'supplier_id': supplier_id
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Supplier not found'}, cls=DecimalEncoder)
            }
            
        supplier = response['Item']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(supplier, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting supplier: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting supplier: {str(e)}"}, cls=DecimalEncoder)
        }

def create_supplier(event):
    """공급업체 생성"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 필수 필드 검증
        required_fields = ['supplier_name', 'contact_name', 'contact_phone']
        missing_fields = [field for field in required_fields if field not in body]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing required fields: {", ".join(missing_fields)}'}, cls=DecimalEncoder)
            }
            
        # 공급업체 ID 생성 및 타임스탬프
        supplier_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # 공급업체 데이터 생성
        supplier_data = {
            'supplier_id': supplier_id,
            'supplier_name': body.get('supplier_name'),
            'contact_name': body.get('contact_name'),
            'contact_phone': body.get('contact_phone'),
            'responsible_person': body.get('responsible_person', ''),
            'address': body.get('address', ''),
            'email': body.get('email', ''),
            'status': 'ACTIVE',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        # DynamoDB에 저장
        table = dynamodb.Table(SUPPLIER_TABLE)
        table.put_item(Item=supplier_data)
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'supplier': supplier_data,
                'message': 'Supplier created successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error creating supplier: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error creating supplier: {str(e)}"}, cls=DecimalEncoder)
        }

def update_supplier(event, supplier_id):
    """공급업체 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 기존 공급업체 조회
        table = dynamodb.Table(SUPPLIER_TABLE)
        response = table.get_item(Key={'supplier_id': supplier_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Supplier not found'}, cls=DecimalEncoder)
            }
            
        # 변경 항목 준비
        update_expression = "set updated_at = :time"
        expression_values = {
            ':time': int(datetime.now().timestamp())
        }
        
        # 업데이트 가능한 필드
        update_fields = {
            'supplier_name': 'sname',
            'contact_name': 'cname',
            'contact_phone': 'cphone',
            'responsible_person': 'resperson',
            'address': 'addr',
            'email': 'email',
            'status': 'status'
        }
        
        for field, short in update_fields.items():
            if field in body:
                update_expression += f", {field} = :{short}"
                expression_values[f':{short}'] = body[field]
        
        # DynamoDB 업데이트
        table.update_item(
            Key={'supplier_id': supplier_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW"
        )

        # 업데이트된 공급업체 조회
        response = table.get_item(Key={'supplier_id': supplier_id})
        updated_supplier = response['Item']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'supplier': updated_supplier,
                'message': 'Supplier updated successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error updating supplier: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error updating supplier: {str(e)}"}, cls=DecimalEncoder)
        }

def delete_supplier(supplier_id):
    """공급업체 삭제"""
    try:
        table = dynamodb.Table(SUPPLIER_TABLE)
        
        # 기존 공급업체 조회
        response = table.get_item(Key={'supplier_id': supplier_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Supplier not found'}, cls=DecimalEncoder)
            }
            
        # 소프트 삭제 (상태만 변경)
        table.update_item(
            Key={'supplier_id': supplier_id},
            UpdateExpression="set #status = :status, updated_at = :time",
            ExpressionAttributeValues={
                ':status': 'DELETED',
                ':time': int(datetime.now().timestamp())
            },
            ExpressionAttributeNames={'#status': 'status'}
        )
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Supplier deleted successfully'}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error deleting supplier: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting supplier: {str(e)}"}, cls=DecimalEncoder)
        }

def get_supplier_inbound_history(supplier_id):
    """공급업체 입고 이력 조회"""
    try:
        # 공급업체 존재 확인
        supplier_table = dynamodb.Table(SUPPLIER_TABLE)
        supplier_response = supplier_table.get_item(Key={'supplier_id': supplier_id})
        
        if 'Item' not in supplier_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Supplier not found'}, cls=DecimalEncoder)
            }
            
        # 이력 조회
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        
        # 주문에서 supplier_id로 필터링 (GSI 필요)
        # DynamoDB에서는 직접 조인이 불가능하므로, 별도 조회 후 애플리케이션에서 조합
        query_params = {'supplier_id': supplier_id, 'event_type': 'RECEIVING_COMPLETED'}
        
        # GSI가 있는 경우:
        response = history_table.query(
            IndexName='supplier_id-index',
            KeyConditionExpression='supplier_id = :sid',
            FilterExpression='event_type = :type',
            ExpressionAttributeValues={
                ':sid': supplier_id,
                ':type': 'RECEIVING_COMPLETED'
            }
        )
        
        history_items = response.get('Items', [])
        
        # 날짜 포맷팅 추가
        for item in history_items:
            if 'timestamp' in item:
                item['timestamp_iso'] = datetime.fromtimestamp(item['timestamp']).isoformat()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'history': history_items,
                'count': len(history_items)
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting supplier outbound history: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting supplier outbound history: {str(e)}"}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting supplier inbound history: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting supplier inbound history: {str(e)}"}, cls=DecimalEncoder)
        }

def get_supplier_outbound_history(supplier_id):
    """공급업체 출고 이력 조회"""
    try:
        # 공급업체 존재 확인
        supplier_table = dynamodb.Table(SUPPLIER_TABLE)
        supplier_response = supplier_table.get_item(Key={'supplier_id': supplier_id})
        
        if 'Item' not in supplier_response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Supplier not found'}, cls=DecimalEncoder)
            }
            
        # 이력 조회
        history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)
        
        # 주문에서 supplier_id로 필터링 (GSI 필요)
        query_params = {'supplier_id': supplier_id, 'event_type': 'DISPATCH_COMPLETED'}
        
        # GSI가 있는 경우:
        response = history_table.query(
            IndexName='supplier_id-index',
            KeyConditionExpression='supplier_id = :sid',
            FilterExpression='event_type = :type',
            ExpressionAttributeValues={
                ':sid': supplier_id,
                ':type': 'DISPATCH_COMPLETED'
            }
        )
        
        history_items = response.get('Items', [])
        
        # 날짜 포맷팅 추가
        for item in history_items:
            if 'timestamp' in item:
                item['timestamp_iso'] = datetime.fromtimestamp(item['timestamp']).isoformat()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'history': history_items,
                'count': len(history_items)
            }, cls=DecimalEncoder)
        }