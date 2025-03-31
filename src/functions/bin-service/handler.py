# src/functions/bin-service/handler.py
import json
import boto3
import os
from datetime import datetime

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')

# 환경 변수
INVENTORY_TABLE = os.environ.get('INVENTORY_TABLE', 'wms-inventory-dev')

def lambda_handler(event, context):
    """창고 빈 관리 Lambda 핸들러"""
    try:
        # API Gateway에서 호출한 경우
        if 'httpMethod' in event:
            http_method = event['httpMethod']
            path = event.get('path', '')
            
            # 빈 추천
            if http_method == 'POST' and '/bins/recommend' in path:
                body = json.loads(event.get('body', '{}'))
                return recommend_bin(body)
            
            # 빈 상태 조회
            elif http_method == 'GET' and '/bins/status' in path:
                return get_bin_status(event)
                
            # 빈 할당 업데이트
            elif http_method == 'PUT' and '/bins/' in path and '/assign' in path:
                body = json.loads(event.get('body', '{}'))
                bin_id = path.split('/')[2]  # /bins/{bin_id}/assign 형식에서 추출
                return update_bin_assignment(bin_id, body)
        
        return {
            'statusCode': 400,
            'body': json.dumps({'message': 'Unsupported request'})
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'message': f"Error: {str(e)}"})
        }

def recommend_bin(request_data):
    """최적 빈 위치 추천"""
    product_id = request_data.get('product_id')
    quantity = request_data.get('quantity', 1)
    
    # 간단한 추천 로직 - 실제로는 더 복잡한 알고리즘 적용 필요
    # 여기서는 단순 예시로 고정 빈 반환
    recommended_bins = [
        {
            'bin_id': 'A-01-02-03',
            'zone': 'A',
            'aisle': '01',
            'rack': '02',
            'level': '03',
            'score': 0.92,
            'reason': '상품 회전율과 접근성 기준 최적 위치'
        }
    ]
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'recommended_bins': recommended_bins,
            'product_id': product_id,
            'timestamp': int(datetime.now().timestamp())
        })
    }

def get_bin_status(event):
    """빈 상태 조회"""
    # 쿼리 파라미터 추출
    query_params = event.get('queryStringParameters', {}) or {}
    zone = query_params.get('zone')
    utilization = query_params.get('utilization')
    
    # 여기서는 샘플 데이터 반환
    bins = [
        {
            'bin_id': 'A-01-02-03',
            'zone': 'A',
            'status': 'OCCUPIED',
            'product_id': 'PROD-12345',
            'quantity': 5,
            'last_updated': '2023-03-30T14:25:30Z'
        },
        {
            'bin_id': 'A-01-02-04',
            'zone': 'A',
            'status': 'EMPTY',
            'product_id': None,
            'quantity': 0,
            'last_updated': '2023-03-29T10:15:22Z'
        }
    ]
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'bins': bins})
    }

def update_bin_assignment(bin_id, request_data):
    """빈 할당 업데이트"""
    product_id = request_data.get('product_id')
    quantity = request_data.get('quantity', 0)
    
    # 실제로는 DynamoDB 업데이트 필요
    # 여기서는 성공 응답만 반환
    
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
            'status': 'ASSIGNED',
            'timestamp': int(datetime.now().timestamp())
        })
    }