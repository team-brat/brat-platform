import json
import boto3
import os
from datetime import datetime
import uuid
import base64
from decimal import Decimal  # Decimal import 추가

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')

# 환경 변수
INVENTORY_TABLE = os.environ.get('INVENTORY_TABLE')


# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # Decimal을 float로 변환
        return super(DecimalEncoder, self).default(obj)


def lambda_handler(event, context):
    """빈 관리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event, cls=DecimalEncoder)}")
        
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
                }, cls=DecimalEncoder)
            }
        
        # 직접 호출
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Bin service executed directly',
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

def get_bins(event):
    """빈 목록 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        zone = query_params.get('zone')
        status = query_params.get('status')
        
        table = dynamodb.Table(INVENTORY_TABLE)
        
        # 필터 표현식 생성
        filter_expression = None
        expression_values = {}
        expression_names = {}
        
        # 필터 조건 설정
        if zone:
            filter_expression = "#zone = :zone"
            expression_values[':zone'] = zone
            expression_names['#zone'] = 'zone'
            
        if status:
            if filter_expression:
                filter_expression += " AND #status = :status"
            else:
                filter_expression = "#status = :status"
            expression_values[':status'] = status
            expression_names['#status'] = 'status'
        
        # DynamoDB 스캔
        if filter_expression:
            response = table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names
            )
        else:
            response = table.scan()
        
        bins = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'bins': bins}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting bins: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting bins: {str(e)}"}, cls=DecimalEncoder)
        }

def get_bin(bin_id):
    """특정 빈 조회"""
    try:
        table = dynamodb.Table(INVENTORY_TABLE)
        response = table.get_item(Key={'bin_id': bin_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Bin not found'}, cls=DecimalEncoder)
            }
        
        bin_data = response['Item']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(bin_data, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting bin: {str(e)}"}, cls=DecimalEncoder)
        }

def get_bin_status(event):
    """빈 상태 통계 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        zone = query_params.get('zone')
        
        table = dynamodb.Table(INVENTORY_TABLE)
        response = table.scan()
        
        bins = response.get('Items', [])
        
        # 전체 통계 계산
        total_bins = len(bins)
        occupied_bins = sum(1 for bin_item in bins if bin_item.get('status') == 'OCCUPIED')
        empty_bins = total_bins - occupied_bins
        utilization = (occupied_bins / total_bins * 100) if total_bins > 0 else 0
        
        # 존별 통계 계산
        zones = {}
        for bin_item in bins:
            bin_zone = bin_item.get('zone')
            if bin_zone not in zones:
                zones[bin_zone] = {'total': 0, 'occupied': 0, 'empty': 0}
            
            zones[bin_zone]['total'] += 1
            if bin_item.get('status') == 'OCCUPIED':
                zones[bin_zone]['occupied'] += 1
            else:
                zones[bin_zone]['empty'] += 1
        
        # 존별 활용률 계산
        for zone_key, zone_data in zones.items():
            zone_data['utilization'] = (zone_data['occupied'] / zone_data['total'] * 100) if zone_data['total'] > 0 else 0
        
        status = {
            'total_bins': total_bins,
            'occupied': occupied_bins,
            'empty': empty_bins,
            'utilization': utilization,
            'zones': zones
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
            'body': json.dumps({'status': status}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting bin status: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting bin status: {str(e)}"}, cls=DecimalEncoder)
        }

def create_bin(event):
    """새 빈 생성"""
    try:
        body = json.loads(event.get('body', '{}'))
        zone = body.get('zone')
        aisle = body.get('aisle')
        rack = body.get('rack')
        level = body.get('level')
        
        # 누락된 필드 확인
        missing_fields = []
        if not zone:
            missing_fields.append('zone')
        if not aisle:
            missing_fields.append('aisle')
        if not rack:
            missing_fields.append('rack')
        if not level:
            missing_fields.append('level')
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': '필수 정보가 누락되었습니다. 다음 필드를 제공해주세요: ' + ', '.join(missing_fields),
                    'missing_fields': missing_fields,
                    'example': {
                        'zone': 'A',
                        'aisle': '01',
                        'rack': '02',
                        'level': '03'
                    }
                }, cls=DecimalEncoder)
            }
            
        # 입력값 검증
        validation_errors = []
        
        if zone and not isinstance(zone, str):
            validation_errors.append('zone은 문자열이어야 합니다')
        
        if aisle and not isinstance(aisle, str):
            validation_errors.append('aisle은 문자열이어야 합니다')
        
        if rack and not isinstance(rack, str):
            validation_errors.append('rack은 문자열이어야 합니다')
        
        if level and not isinstance(level, str):
            validation_errors.append('level은 문자열이어야 합니다')
        
        if validation_errors:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': '입력값이 올바르지 않습니다: ' + '; '.join(validation_errors)
                }, cls=DecimalEncoder)
            }
            
        # 빈 ID 생성
        bin_id = f"{zone}-{aisle}-{rack}-{level}"
        timestamp = int(datetime.now().timestamp())
        
        table = dynamodb.Table(INVENTORY_TABLE)
        
        # 중복 확인
        response = table.get_item(Key={'bin_id': bin_id})
        if 'Item' in response:
            return {
                'statusCode': 409,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({
                    'message': f'이미 존재하는 빈 ID입니다: {bin_id}',
                    'bin': response['Item']
                }, cls=DecimalEncoder)
            }
        
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
        
        # DynamoDB에 저장
        table.put_item(Item=new_bin)
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'bin': new_bin,
                'message': '빈이 성공적으로 생성되었습니다'
            }, cls=DecimalEncoder)
        }
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'message': '올바른 JSON 형식이 아닙니다',
                'example': {
                    'zone': 'A',
                    'aisle': '01',
                    'rack': '02',
                    'level': '03'
                }
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error creating bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"빈 생성 중 오류가 발생했습니다: {str(e)}"}, cls=DecimalEncoder)
        }
        
def update_bin(bin_id, event):
    """빈 정보 업데이트"""
    try:
        body = json.loads(event.get('body', '{}'))
        product_id = body.get('product_id')
        quantity = body.get('quantity')
        status = body.get('status')
        
        table = dynamodb.Table(INVENTORY_TABLE)
        
        # 기존 빈 확인
        response = table.get_item(Key={'bin_id': bin_id})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Bin not found'}, cls=DecimalEncoder)
            }
        
        existing_bin = response['Item']
        timestamp = int(datetime.now().timestamp())
        
        # 상태 결정
        if status is None:
            if product_id and (quantity is None or quantity > 0):
                status = 'OCCUPIED'
            elif quantity == 0 or product_id is None:
                status = 'EMPTY'
            else:
                status = existing_bin.get('status', 'EMPTY')
        
        # 업데이트 표현식 생성
        update_expression = "SET updated_at = :timestamp"
        expression_values = {':timestamp': timestamp}
        
        if status:
            update_expression += ", #status = :status"
            expression_values[':status'] = status
        
        if product_id is not None:
            update_expression += ", product_id = :product_id"
            expression_values[':product_id'] = product_id
        
        if quantity is not None:
            update_expression += ", quantity = :quantity"
            expression_values[':quantity'] = quantity
        
        # DynamoDB 업데이트
        table.update_item(
            Key={'bin_id': bin_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames={'#status': 'status'} if status else {}
        )
        
        # 업데이트된 항목 반환
        response = table.get_item(Key={'bin_id': bin_id})
        updated_bin = response['Item']
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'bin': updated_bin,
                'message': 'Bin updated successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error updating bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error updating bin: {str(e)}"}, cls=DecimalEncoder)
        }

def delete_bin(bin_id):
    """빈 삭제"""
    try:
        table = dynamodb.Table(INVENTORY_TABLE)
        
        # 기존 빈 확인
        response = table.get_item(Key={'bin_id': bin_id})
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Bin not found'}, cls=DecimalEncoder)
            }
        
        # DynamoDB에서 삭제
        table.delete_item(Key={'bin_id': bin_id})
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Bin deleted successfully'}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error deleting bin: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting bin: {str(e)}"}, cls=DecimalEncoder)
        }