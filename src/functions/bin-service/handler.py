import json
import boto3
import os
from datetime import datetime
import uuid

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')

# 환경 변수
INVENTORY_TABLE = os.environ.get('INVENTORY_TABLE')

def lambda_handler(event, context):
    """빈 관리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 빈 목록 조회
            if http_method == 'GET' and path == '/bins':
                return get_bins(event)
            
            # 특정 빈 조회
            elif http_method == 'GET' and '/bins/' in path and path_params.get('bin_id'):
                return get_bin(path_params.get('bin_id'))
            
            # 빈 상태 조회
            elif http_method == 'GET' and path == '/bins/status':
                return get_bin_status(event)
                
            # 새 빈 생성
            elif http_method == 'POST' and path == '/bins':
                return create_bin(event)
                
            # 빈 정보 업데이트
            elif http_method == 'PUT' and '/bins/' in path and path_params.get('bin_id'):
                return update_bin(path_params.get('bin_id'), event)
                
            # 빈 삭제
            elif http_method == 'DELETE' and '/bins/' in path and path_params.get('bin_id'):
                return delete_bin(path_params.get('bin_id'))
            
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
                })
            }
        
        # 직접 호출
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Bin service executed directly',
                'event': event
            })
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error: {str(e)}"})
        }

def get_bins(event):
    """빈 목록 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        zone = query_params.get('zone')
        status = query_params.get('status')
        
        # TODO: DynamoDB에서 실제 데이터 조회
        # 더미 데이터 반환
        bins = [
            {
                'bin_id': 'A-01-01',
                'zone': 'A',
                'aisle': '01',
                'rack': '01',
                'level': '01',
                'status': 'EMPTY',
                'created_at': 1680221456,
                'updated_at': 1680221456
            },
            {
                'bin_id': 'A-01-02',
                'zone': 'A',
                'aisle': '01',
                'rack': '01',
                'level': '02',
                'status': 'OCCUPIED',
                'product_id': 'PROD-12345',
                'quantity': 10,
                'created_at': 1680221456,
                'updated_at': 1680224456
            }
        ]
        
        # 필터링
        if zone:
            bins = [b for b in bins if b['zone'] == zone]
        if status:
            bins = [b for b in bins if b['status'] == status]
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'bins': bins})
        }
    except Exception as e:
        print(f"Error getting bins: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting bins: {str(e)}"})
        }

def get_bin(bin_id):
    """특정 빈 조회"""
    try:
        # TODO: DynamoDB에서 실제 데이터 조회
        # 더미 데이터 반환
        if bin_id == 'A-01-01':
            bin_data = {
                'bin_id': 'A-01-01',
                'zone': 'A',
                'aisle': '01',
                'rack': '01',
                'level': '01',
                'status': 'EMPTY',
                'created_at': 1680221456,
                'updated_at': 1680221456
            }
        elif bin_id == 'A-01-02':
            bin_data = {
                'bin_id': 'A-01-02',
                'zone': 'A',
                'aisle': '01',
                'rack': '01',
                'level': '02',
                'status': 'OCCUPIED',
                'product_id': 'PROD-12345',
                'quantity': 10,
                'created_at': 1680221456,
                'updated_at': 1680224456
            }
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Bin not found'})
            }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(bin_data)
        }
    except Exception as e:
        print(f"Error getting bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting bin: {str(e)}"})
        }

def get_bin_status(event):
    """빈 상태 통계 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        zone = query_params.get('zone')
        
        # TODO: DynamoDB에서 실제 데이터 조회
        # 더미 데이터 반환
        status = {
            'total_bins': 50,
            'occupied': 35,
            'empty': 15,
            'utilization': 70,
            'zones': {
                'A': {'total': 20, 'occupied': 15, 'empty': 5, 'utilization': 75},
                'B': {'total': 30, 'occupied': 20, 'empty': 10, 'utilization': 67}
            }
        }
        
        # 특정 구역만 필터링
        if zone and zone in status['zones']:
            filtered_status = {
                'total_bins': status['zones'][zone]['total'],
                'occupied': status['zones'][zone]['occupied'],
                'empty': status['zones'][zone]['empty'],
                'utilization': status['zones'][zone]['utilization'],
                'zone': zone
            }
            status = filtered_status
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'status': status})
        }
    except Exception as e:
        print(f"Error getting bin status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting bin status: {str(e)}"})
        }

def create_bin(event):
    """새 빈 생성"""
    try:
        body = json.loads(event.get('body', '{}'))
        zone = body.get('zone')
        aisle = body.get('aisle')
        rack = body.get('rack')
        level = body.get('level')
        
        if not zone or not aisle or not rack or not level:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Zone, aisle, rack, and level are required'})
            }
            
        # 빈 ID 생성
        bin_id = f"{zone}-{aisle}-{rack}-{level}"
        timestamp = int(datetime.now().timestamp())
        
        # TODO: DynamoDB에 실제 저장
        
        new_bin = {
            'bin_id': bin_id,
            'zone': zone,
            'aisle': aisle,
            'rack': rack,
            'level': level,
            'status': 'EMPTY',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'bin': new_bin,
                'message': 'Bin created successfully'
            })
        }
    except Exception as e:
        print(f"Error creating bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error creating bin: {str(e)}"})
        }

def update_bin(bin_id, event):
    """빈 정보 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        product_id = body.get('product_id')
        quantity = body.get('quantity')
        status = body.get('status')
        
        # TODO: 실제 DynamoDB에서 빈 확인 및 업데이트
        
        # 더미 응답
        updated_bin = {
            'bin_id': bin_id,
            'product_id': product_id,
            'quantity': quantity,
            'status': status or ('OCCUPIED' if product_id and quantity > 0 else 'EMPTY'),
            'updated_at': int(datetime.now().timestamp())
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'bin': updated_bin,
                'message': 'Bin updated successfully'
            })
        }
    except Exception as e:
        print(f"Error updating bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error updating bin: {str(e)}"})
        }

def delete_bin(bin_id):
    """빈 삭제"""
    try:
        # TODO: 실제 DynamoDB에서 빈 확인 및 삭제
        
        # 더미 응답
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Bin deleted successfully'})
        }
    except Exception as e:
        print(f"Error deleting bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting bin: {str(e)}"})
        }