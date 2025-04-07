import json
import boto3
import os
import uuid
from datetime import datetime
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')

# 환경 변수
RECEIVING_ITEM_TABLE = os.environ.get('RECEIVING_ITEM_TABLE')
RECEIVING_ORDER_TABLE = os.environ.get('RECEIVING_ORDER_TABLE')

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

# 공통 CORS 헤더 정의
def get_cors_headers():
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
    }

def lambda_handler(event, context):
    """입고 품목 관리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            query_params = event.get('queryStringParameters', {}) or {}
            
            # 주문별 품목 목록 조회
            if http_method == 'GET' and path == '/receiving-items' and 'order_id' in query_params:
                return get_items_by_order(query_params['order_id'])
            
            # 특정 품목 조회
            elif http_method == 'GET' and path.startswith('/receiving-items/') and path_params.get('item_id'):
                return get_item(path_params['item_id'])
            
            # 품목 업데이트
            elif http_method == 'PUT' and path.startswith('/receiving-items/') and path_params.get('item_id'):
                return update_item(event, path_params['item_id'])
                
            # 품목 일괄 추가
            elif http_method == 'POST' and path == '/receiving-items/batch':
                return batch_add_items(event)
            
            # 기본 응답
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({
                    'message': 'Endpoint not found',
                    'path': path,
                    'method': http_method
                }, cls=DecimalEncoder)
            }
        
        # 직접 호출
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'message': 'Receiving item service executed directly',
                'event': event
            }, cls=DecimalEncoder)
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def get_items_by_order(order_id):
    """주문별 품목 목록 조회"""
    try:
        # 주문 존재 확인
        order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        order_response = order_table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in order_response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Receiving order not found'}, cls=DecimalEncoder)
            }
        
        # 품목 조회
        table = dynamodb.Table(RECEIVING_ITEM_TABLE)
        
        # order_id로 인덱스 쿼리
        response = table.query(
            IndexName='order_id-index',
            KeyConditionExpression='order_id = :oid',
            ExpressionAttributeValues={
                ':oid': order_id
            }
        )
        
        items = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'items': items,
                'count': len(items)
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting items by order: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': f"Error getting items by order: {str(e)}"}, cls=DecimalEncoder)
        }

def get_item(item_id):
    """특정 품목 조회"""
    try:
        table = dynamodb.Table(RECEIVING_ITEM_TABLE)
        
        response = table.get_item(
            Key={
                'item_id': item_id
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Item not found'}, cls=DecimalEncoder)
            }
            
        item = response['Item']
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps(item, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting item: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': f"Error getting item: {str(e)}"}, cls=DecimalEncoder)
        }

def update_item(event, item_id):
    """품목 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 기존 품목 조회
        table = dynamodb.Table(RECEIVING_ITEM_TABLE)
        response = table.get_item(Key={'item_id': item_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Item not found'}, cls=DecimalEncoder)
            }
            
        existing_item = response['Item']
        
        # 주문 확인
        order_id = existing_item.get('order_id')
        order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        order_response = order_table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in order_response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Associated order not found'}, cls=DecimalEncoder)
            }
            
        existing_order = order_response['Item']
        
        # 주문 상태 확인 (완료된 주문의 품목은 수정 불가)
        if existing_order.get('status') in ['COMPLETED', 'CANCELLED', 'DELETED']:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': f'Cannot update item for order in {existing_order.get("status")} status'}, cls=DecimalEncoder)
            }
            
        # 변경 항목 준비
        update_expression = "set updated_at = :time"
        expression_values = {
            ':time': int(datetime.now().timestamp())
        }
        
        # 업데이트 가능한 필드
        update_fields = {
            'product_name': 'pname',
            'sku_number': 'sku',
            'expected_qty': 'eqty',
            'received_qty': 'rqty',
            'serial_or_barcode': 'serial',
            'length': 'len',
            'width': 'wid',
            'height': 'hei',
            'depth': 'dep',
            'volume': 'vol',
            'weight': 'wei',
            'notes': 'notes'
        }
        
        for field, short in update_fields.items():
            if field in body:
                update_expression += f", {field} = :{short}"
                expression_values[f':{short}'] = body[field]
        
        # DynamoDB 업데이트
        table.update_item(
            Key={'item_id': item_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ReturnValues="ALL_NEW"
        )

        # 업데이트된 품목 조회
        response = table.get_item(Key={'item_id': item_id})
        updated_item = response['Item']
        
        return {
            'statusCode': 200,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'item': updated_item,
                'message': 'Item updated successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error updating item: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': f"Error updating item: {str(e)}"}, cls=DecimalEncoder)
        }

def batch_add_items(event):
    """품목 일괄 추가"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 필수 필드 검증
        required_fields = ['order_id', 'items']
        missing_fields = [field for field in required_fields if field not in body]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': f'Missing required fields: {", ".join(missing_fields)}'}, cls=DecimalEncoder)
            }
            
        order_id = body.get('order_id')
        items = body.get('items', [])
        
        if not isinstance(items, list) or len(items) == 0:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Items must be a non-empty array'}, cls=DecimalEncoder)
            }
            
        # 주문 확인
        order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
        order_response = order_table.get_item(Key={'order_id': order_id})
        
        if 'Item' not in order_response:
            return {
                'statusCode': 404,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': 'Receiving order not found'}, cls=DecimalEncoder)
            }
            
        existing_order = order_response['Item']
        
        # 주문 상태 확인
        if existing_order.get('status') in ['COMPLETED', 'CANCELLED', 'DELETED']:
            return {
                'statusCode': 400,
                'headers': get_cors_headers(),
                'body': json.dumps({'message': f'Cannot add items to order in {existing_order.get("status")} status'}, cls=DecimalEncoder)
            }
            
        # 품목 추가
        table = dynamodb.Table(RECEIVING_ITEM_TABLE)
        timestamp = int(datetime.now().timestamp())
        added_items = []
        
        for item in items:
            item_id = str(uuid.uuid4())
            
            # 필수 필드 확인
            if not all(k in item for k in ['product_name', 'expected_qty']):
                return {
                    'statusCode': 400,
                    'headers': get_cors_headers(),
                    'body': json.dumps({'message': 'Each item must have product_name and expected_qty'}, cls=DecimalEncoder)
                }
                
            # 품목 데이터
            item_data = {
                'item_id': item_id,
                'order_id': order_id,
                'product_name': item.get('product_name'),
                'sku_number': item.get('sku_number', 'UNKNOWN'),
                'expected_qty': item.get('expected_qty'),
                'serial_or_barcode': item.get('serial_or_barcode', ''),
                'length': item.get('length', 0),
                'width': item.get('width', 0),
                'height': item.get('height', 0),
                'depth': item.get('depth', 0),
                'volume': item.get('volume', 0),
                'weight': item.get('weight', 0),
                'notes': item.get('notes', ''),
                'created_at': timestamp,
                'updated_at': timestamp
            }
            
            # DynamoDB에 저장
            table.put_item(Item=item_data)
            added_items.append(item_data)
        
        return {
            'statusCode': 201,
            'headers': get_cors_headers(),
            'body': json.dumps({
                'items': added_items,
                'count': len(added_items),
                'message': 'Items added successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error adding items: {str(e)}")
        return {
            'statusCode': 500,
            'headers': get_cors_headers(),
            'body': json.dumps({'message': f"Error adding items: {str(e)}"}, cls=DecimalEncoder)
        }