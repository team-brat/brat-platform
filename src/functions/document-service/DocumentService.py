import json
import boto3
import os
import uuid
import base64
from datetime import datetime
from decimal import Decimal

# AWS 서비스 클라이언트
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
events = boto3.client('events')

# 환경 변수
DOCUMENT_METADATA_TABLE = os.environ.get('DOCUMENT_METADATA_TABLE')
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET')

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """문서 처리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 문서 목록 조회
            if http_method == 'GET' and path == '/documents':
                return get_documents(event)
            
            # 특정 문서 조회
            elif http_method == 'GET' and path.startswith('/documents/') and path_params.get('document_id'):
                return get_document(path_params['document_id'])
            
            # 문서 업로드
            elif http_method == 'POST' and path == '/documents':
                return upload_document(event)
            
            # 문서 삭제
            elif http_method == 'DELETE' and path.startswith('/documents/') and path_params.get('document_id'):
                return delete_document(path_params['document_id'])
            
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
                'message': 'Document service executed directly',
                'event': event
            }, cls=DecimalEncoder)
        }
            
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting document: {str(e)}"}, cls=DecimalEncoder)
        }

def publish_event(event_detail, detail_type, source='wms.document-service'):
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

def get_documents(event):
    """문서 목록 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        order_id = query_params.get('order_id')
        
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        
        if order_id:
            # 특정 주문의 문서 조회
            # GSI 필요: order_id-index
            response = table.query(
                IndexName='order_id-index',
                KeyConditionExpression='order_id = :order_id',
                ExpressionAttributeValues={
                    ':order_id': order_id
                }
            )
        else:
            # 모든 문서 스캔 (프로덕션에서는 권장하지 않음)
            response = table.scan()
            
        documents = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'documents': documents,
                'count': len(documents)
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting documents: {str(e)}"}, cls=DecimalEncoder)
        }

def get_document(document_id):
    """특정 문서 조회"""
    try:
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)

        response = table.get_item(Key={'document_id': document_id})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }

        document = response['Item']

        # S3에서 문서 URL 생성 (임시 URL)
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': DOCUMENT_BUCKET,
                'Key': document['s3_key']
            },
            ExpiresIn=3600  # 1시간 유효
        )

        document['download_url'] = presigned_url

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(document, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error getting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting document: {str(e)}"}, cls=DecimalEncoder)
        }

def upload_document(event):
    """문서 업로드"""
    try:
        body = json.loads(event.get('body', '{}'))
        
        # 필수 필드 검증
        required_fields = ['order_id', 'document_type', 'file_name', 'content_type', 'file_content']
        missing_fields = [field for field in required_fields if field not in body]
        
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Missing required fields: {", ".join(missing_fields)}'}, cls=DecimalEncoder)
            }
            
        # 문서 유형 검증
        valid_types = ['INVOICE', 'BILL_OF_ENTRY', 'AIRWAY_BILL']
        document_type = body.get('document_type')
        
        if document_type not in valid_types:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Invalid document type. Must be one of: {", ".join(valid_types)}'}, cls=DecimalEncoder)
            }
            
        # 파일 내용 디코딩
        file_content = body.get('file_content')
        try:
            decoded_content = base64.b64decode(file_content)
        except:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Invalid file content. Must be base64 encoded.'}, cls=DecimalEncoder)
            }
            
        # 문서 ID 및 기타 메타데이터 생성
        document_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        file_name = body.get('file_name')
        file_extension = file_name.split('.')[-1] if '.' in file_name else ''
        
        # S3 키 생성
        s3_key = f"{body.get('order_id')}/{document_type.lower()}/{document_id}.{file_extension}"
        
        # S3에 업로드
        s3.put_object(
            Bucket=DOCUMENT_BUCKET,
            Key=s3_key,
            Body=decoded_content,
            ContentType=body.get('content_type')
        )
        
        # 메타데이터 저장
        document_metadata = {
            'document_id': document_id,
            'order_id': body.get('order_id'),
            'document_type': document_type,
            's3_key': s3_key,
            'file_name': file_name,
            'content_type': body.get('content_type'),
            'upload_date': timestamp,
            'uploader': body.get('user_id', 'system'),
            'verification_status': 'PENDING',
            'verification_notes': ''
        }
        
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        table.put_item(Item=document_metadata)
        
        # 문서 업로드 이벤트 발행
        event_detail = {
            'document_id': document_id,
            'order_id': body.get('order_id'),
            'document_type': document_type,
            'timestamp': timestamp
        }
        
        publish_event(event_detail, 'DocumentUploaded')
        
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'document': document_metadata,
                'message': 'Document uploaded successfully'
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error uploading document: {str(e)}"}, cls=DecimalEncoder)
        }


    """문서 삭제"""
    try:
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        
        # 문서 메타데이터 조회
        response = table.get_item(
            Key={
                'document_id': document_id
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }
            
        document = response['Item']
        s3_key = document['s3_key']
        
        # S3에서 파일 삭제
        s3.delete_object(
            Bucket=DOCUMENT_BUCKET,
            Key=s3_key
        )
        
        # DynamoDB에서 메타데이터 삭제
        table.delete_item(
            Key={
                'document_id': document_id
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Document deleted successfully'
            }, cls=DecimalEncoder)
        }

def delete_document(document_id):
    """문서 삭제"""
    try:
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        
        # 문서 메타데이터 조회
        response = table.get_item(
            Key={
                'document_id': document_id
            }
        )
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }
            
        document = response['Item']
        s3_key = document['s3_key']
        
        # S3에서 파일 삭제
        s3.delete_object(
            Bucket=DOCUMENT_BUCKET,
            Key=s3_key
        )
        
        # DynamoDB에서 메타데이터 삭제
        table.delete_item(
            Key={
                'document_id': document_id
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'message': 'Document deleted successfully'
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting document: {str(e)}"}, cls=DecimalEncoder)
        }
