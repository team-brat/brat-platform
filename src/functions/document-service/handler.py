# src/functions/document-service/handler.py
import json
import boto3
import os
import uuid
from datetime import datetime

# AWS 서비스 클라이언트
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# 환경 변수
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET')
METADATA_TABLE = os.environ.get('METADATA_TABLE')

def lambda_handler(event, context):
    """문서 처리 Lambda 핸들러"""
    try:
        # API Gateway에서 호출한 경우
        if 'httpMethod' in event:
            http_method = event['httpMethod']
            
            # 문서 목록 조회
            if http_method == 'GET':
                return get_documents()
            
            # 문서 업로드
            elif http_method == 'POST' and event.get('path', '').endswith('/upload'):
                return upload_document(event)
        
        # S3 이벤트로 호출된
        elif 'Records' in event and 's3' in event['Records'][0]:
            return process_document(event)
            
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

def get_documents():
    """문서 목록 조회"""
    table = dynamodb.Table(METADATA_TABLE)
    response = table.scan()
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'  # CORS 설정
        },
        'body': json.dumps({'documents': response.get('Items', [])})
    }

def upload_document(event):
    """문서 업로드"""
    # 이 함수에서는 API Gateway에서 전달된 파일을 처리하고 S3에 업로드
    # 실제 구현은 API Gateway 바이너리 지원과 Base64 인코딩 처리 필요
    # 간소화를 위해 구현 생략
    
    document_id = str(uuid.uuid4())
    upload_path = f"uploads/{datetime.now().strftime('%Y-%m-%d')}/{document_id}"
    
    # 메타데이터 저장
    table = dynamodb.Table(METADATA_TABLE)
    table.put_item(
        Item={
            'document_id': document_id,
            'timestamp': int(datetime.now().timestamp()),
            'status': 'PROCESSING',
            'filename': 'sample.pdf',  # 실제로는 업로드된 파일명
            's3_path': upload_path
        }
    )
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'document_id': document_id,
            'message': 'Document uploaded successfully'
        })
    }

def process_document(event):
    """S3에 업로드된 문서 처리"""
    # S3 이벤트에서 버킷과 키 추출
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    # 문서 ID 추출 (S3 키에서)
    document_id = key.split('/')[-1]
    
    # 처리 로직 (OCR, 분류 등) 구현 부분
    # ...
    
    # 처리 결과 저장
    table = dynamodb.Table(METADATA_TABLE)
    table.update_item(
        Key={'document_id': document_id},
        UpdateExpression='SET #status = :status, processed_at = :time',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': 'COMPLETED',
            ':time': int(datetime.now().timestamp())
        }
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Document processed successfully'})
    }