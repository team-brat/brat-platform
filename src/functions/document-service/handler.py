import boto3
import os
import json
import uuid

# AWS 서비스 클라이언트
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# 환경 변수
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET', 'wms-documents-dev')
METADATA_TABLE = os.environ.get('METADATA_TABLE', 'wms-document-metadata-dev')

def lambda_handler(event, context):
    try:
        # API Gateway에서 전달된 이벤트 처리
        print("Received event:", json.dumps(event))
        
        # 간단한 응답 반환 (테스트용)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Document processor function executed successfully',
                'input': event
            })
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f"Error: {str(e)}"
            })
        }
