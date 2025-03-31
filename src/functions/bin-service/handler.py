import json
import boto3
import os
from datetime import datetime
import uuid

# AWS 서비스 초기화
dynamodb = boto3.resource('dynamodb')

# 환경 변수
INVENTORY_TABLE = os.environ.get('INVENTORY_TABLE')

def lambda_handler(event, context):
    """창고 빈 관리 Lambda 핸들러"""
    try:
        # HTTP 메서드와 경로 파싱
        http_method = event.get('httpMethod')
        path = event.get('path', '')
        
        # 빈 목록 조회
        if http_method == 'GET' and path.endswith('/bins'):
            return get_bins(event)
        
        # 빈 상세 조회
        elif http_method == 'GET' and '/bins/' in path and not path.endswith('/bins/'):
            bin_id = path.split('/bins/')[1].split('/')[0]
            return get_bin(bin_id)
        
        # 빈 생성
        elif http_method == 'POST' and path.endswith('/bins'):
            return create_bin(event)
        
        # 빈 할당 업데이트
        elif http_method == 'PUT' and '/bins/' in path and '/assign' in path:
            bin_id = path.split('/bins/')[1].split('/')[0]
            return assign_bin(bin_id, event)
        
        # 빈 삭제
        elif http_method == 'DELETE' and '/bins/' in path:
            bin_id = path.split('/bins/')[1].split('/')[0]
            return delete_bin(bin_id)
        
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'Unsupported operation'})
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f"Error: {str(e)}"})
        }

def get_bins(event):
    """빈 목록 조회"""
    table = dynamodb.Table(INVENTORY_TABLE)
    
    # 쿼리 파라미터 처리
    query_params = event.get('queryStringParameters', {}) or {}
    filter_expr = None
    expr_values = {}
    
    # 여러 필터 조건 구성
    if query_params.get('zone'):
        filter_expr = "bin_zone = :zone"
        expr_values[":zone"] = query_params.get('zone')
    
    if query_params.get('status'):
        if filter_expr:
            filter_expr += " AND bin_status = :status"
        else:
            filter_expr = "bin_status = :status"
        expr_values[":status"] = query_params.get('status')
    
    # 필터가 있으면 적용, 없으면 전체 스캔
    if filter_expr:
        response = table.scan(
            FilterExpression=filter_expr,
            ExpressionAttributeValues=expr_values
        )
    else:
        response = table.scan()
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'bins': response.get('Items', [])})
    }

def get_bin(bin_id):
    """빈 상세 조회"""
    table = dynamodb.Table(INVENTORY_TABLE)
    response = table.get_item(Key={'bin_id': bin_id})
    
    if 'Item' not in response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'Bin not found'})
        }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(response['Item'])
    }

def create_bin(event):
    """빈 생성"""
    try:
        body = json.loads(event.get('body', '{}'))
        zone = body.get('zone')
        aisle = body.get('aisle')
        rack = body.get('rack')
        level = body.get('level')
        
        if not zone or not aisle or not rack or not level:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Missing required bin attributes'})
            }
        
        # 빈 ID 생성 (형식: ZONE-AISLE-RACK-LEVEL)
        bin_id = f"{zone}-{aisle}-{rack}-{level}"
        
        # 이미 존재하는지 확인
        table = dynamodb.Table(INVENTORY_TABLE)
        response = table.get_item(Key={'bin_id': bin_id})
        
        if 'Item' in response:
            return {
                'statusCode': 409,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Bin already exists'})
            }
        
        # 빈 추가
        timestamp = int(datetime.now().timestamp())
        table.put_item(
            Item={
                'bin_id': bin_id,
                'bin_zone': zone,
                'bin_aisle': aisle,
                'bin_rack': rack,
                'bin_level': level,
                'bin_status': 'EMPTY',
                'product_id': None,
                'quantity': 0,
                'created_at': timestamp,
                'updated_at': timestamp
            }
        )
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'bin_id': bin_id,
                'message': 'Bin created successfully'
            })
        }
    except Exception as e:
        print(f"Create bin error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f"Create bin error: {str(e)}"})
        }

def assign_bin(bin_id, event):
    """빈 할당 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        product_id = body.get('product_id')
        quantity = body.get('quantity', 0)
        
        if product_id is None:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Missing product_id'})
            }
        
        # 빈 존재 확인
        table = dynamodb.Table(INVENTORY_TABLE)
        response = table.get_item(Key={'bin_id': bin_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Bin not found'})
            }
        
        # 빈 상태 업데이트
        timestamp = int(datetime.now().timestamp())
        status = 'OCCUPIED' if quantity > 0 else 'EMPTY'
        
        table.update_item(
            Key={'bin_id': bin_id},
            UpdateExpression="set product_id = :pid, quantity = :qty, bin_status = :status, updated_at = :time",
            ExpressionAttributeValues={
                ':pid': product_id if quantity > 0 else None,
                ':qty': quantity,
                ':status': status,
                ':time': timestamp
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'bin_id': bin_id,
                'product_id': product_id,
                'quantity': quantity,
                'status': status,
                'message': 'Bin assignment updated successfully'
            })
        }
    except Exception as e:
        print(f"Assign bin error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f"Assign bin error: {str(e)}"})
        }

def delete_bin(bin_id):
    """빈 삭제"""
    try:
        # 빈 존재 확인
        table = dynamodb.Table(INVENTORY_TABLE)
        response = table.get_item(Key={'bin_id': bin_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Bin not found'})
            }
        
        # 상품이 할당된 경우 삭제 불가
        bin_data = response['Item']
        if bin_data.get('bin_status') == 'OCCUPIED' and bin_data.get('quantity', 0) > 0:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Cannot delete bin with assigned inventory'})
            }
        
        # 빈 삭제
        table.delete_item(Key={'bin_id': bin_id})
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Bin deleted successfully'})
        }
    except Exception as e:
        print(f"Delete bin error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f"Delete bin error: {str(e)}"})
        }