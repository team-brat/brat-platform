import json
import boto3
import os
import uuid
from datetime import datetime
import base64

# AWS 서비스 클라이언트
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# 환경 변수
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET')
METADATA_TABLE = os.environ.get('METADATA_TABLE')

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
            elif http_method == 'GET' and '/documents/' in path and path_params.get('document_id'):
                return get_document(path_params.get('document_id'))
            
            # 문서 업로드
            elif http_method == 'POST' and path == '/documents/upload':
                return upload_document(event)
                
            # 문서 삭제
            elif http_method == 'DELETE' and '/documents/' in path and path_params.get('document_id'):
                return delete_document(path_params.get('document_id'))
                
            # 새 문서 생성 (메타데이터만)
            elif http_method == 'POST' and path == '/documents':
                return create_document(event)
            
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
                'message': 'Document service executed directly',
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

def get_documents(event):
    """문서 목록 조회"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        doc_type = query_params.get('type')
        
        table = dynamodb.Table(METADATA_TABLE)
        
        if doc_type:
            # 문서 유형별 필터링
            response = table.scan(
                FilterExpression="document_type = :dtype",
                ExpressionAttributeValues={':dtype': doc_type}
            )
        else:
            # 전체 문서 조회
            response = table.scan()
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'documents': response.get('Items', [])})
        }
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting documents: {str(e)}"})
        }

def get_document(document_id):
    """특정 문서 조회"""
    try:
        table = dynamodb.Table(METADATA_TABLE)
        response = table.get_item(Key={'document_id': document_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'})
            }
        
        document = response['Item']
        
        # S3 미리 서명된 URL 생성 (30분 유효)
        if 's3_path' in document:
            presigned_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': DOCUMENT_BUCKET, 'Key': document['s3_path']},
                ExpiresIn=1800
            )
            document['download_url'] = presigned_url
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(document)
        }
    except Exception as e:
        print(f"Error getting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting document: {str(e)}"})
        }

def create_document(event):
    """문서 메타데이터 생성"""
    try:
        body = json.loads(event.get('body', '{}'))
        title = body.get('title')
        doc_type = body.get('document_type', 'general')
        
        if not title:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Title is required'})
            }
            
        document_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # DynamoDB에 메타데이터 저장
        table = dynamodb.Table(METADATA_TABLE)
        table.put_item(
            Item={
                'document_id': document_id,
                'timestamp': timestamp,
                'title': title,
                'document_type': doc_type,
                'status': 'PENDING',
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
                'document_id': document_id,
                'message': 'Document metadata created successfully'
            })
        }
    except Exception as e:
        print(f"Error creating document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error creating document: {str(e)}"})
        }

def upload_document(event):
    """문서 업로드"""
    try:
        body = json.loads(event.get('body', '{}'))
        file_content = body.get('file')
        filename = body.get('filename')
        document_id = body.get('document_id')
        
        if not file_content or not filename:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'File content and filename are required'})
            }
        
        # Base64 디코딩
        try:
            # Base64 패딩 확인
            padding = 4 - (len(file_content) % 4)
            if padding:
                file_content += '=' * padding
                
            file_content_decoded = base64.b64decode(file_content)
        except Exception as e:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': f'Invalid file content: {str(e)}'})
            }
        
        # 신규 업로드면 ID 생성
        if not document_id:
            document_id = str(uuid.uuid4())
            timestamp = int(datetime.now().timestamp())
            
            # S3에 파일 업로드
            s3_path = f"documents/{document_id}/{filename}"
            s3.put_object(
                Bucket=DOCUMENT_BUCKET,
                Key=s3_path,
                Body=file_content_decoded,
                ContentType=get_content_type(filename)
            )
            
            # 메타데이터 저장
            table = dynamodb.Table(METADATA_TABLE)
            table.put_item(
                Item={
                    'document_id': document_id,
                    'timestamp': timestamp,
                    'filename': filename,
                    's3_path': s3_path,
                    'size': len(file_content_decoded),
                    'status': 'ACTIVE',
                    'document_type': 'uploaded',
                    'created_at': timestamp,
                    'updated_at': timestamp
                }
            )
        else:
            # 기존 문서 업데이트
            timestamp = int(datetime.now().timestamp())
            
            # 기존 메타데이터 조회
            table = dynamodb.Table(METADATA_TABLE)
            response = table.get_item(Key={'document_id': document_id})
            
            if 'Item' not in response:
                return {
                    'statusCode': 404,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'message': 'Document not found'})
                }
                
            item = response['Item']
            
            # S3에 파일 업로드
            s3_path = f"documents/{document_id}/{filename}"
            s3.put_object(
                Bucket=DOCUMENT_BUCKET,
                Key=s3_path,
                Body=file_content_decoded,
                ContentType=get_content_type(filename)
            )
            
            # 메타데이터 업데이트
            table.update_item(
                Key={'document_id': document_id},
                UpdateExpression="set filename = :fname, s3_path = :path, size = :size, status = :status, updated_at = :time",
                ExpressionAttributeValues={
                    ':fname': filename,
                    ':path': s3_path,
                    ':size': len(file_content_decoded),
                    ':status': 'ACTIVE',
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
                'document_id': document_id,
                'message': 'Document uploaded successfully'
            })
        }
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error uploading document: {str(e)}"})
        }

def delete_document(document_id):
    """문서 삭제"""
    try:
        table = dynamodb.Table(METADATA_TABLE)
        response = table.get_item(Key={'document_id': document_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'})
            }
            
        item = response['Item']
        
        # S3에서 파일 삭제
        if 's3_path' in item:
            s3.delete_object(Bucket=DOCUMENT_BUCKET, Key=item['s3_path'])
        
        # 메타데이터에서 상태 변경 (소프트 삭제)
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression="set #status = :status, updated_at = :time",
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'DELETED',
                ':time': int(datetime.now().timestamp())
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'message': 'Document deleted successfully'})
        }
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting document: {str(e)}"})
        }

def get_content_type(filename):
    """파일 확장자에 따른 Content-Type 반환"""
    ext = filename.lower().split('.')[-1]
    content_types = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'txt': 'text/plain',
        'csv': 'text/csv'
    }
    return content_types.get(ext, 'application/octet-stream')