import json
import boto3
import os
import uuid
from datetime import datetime
import base64
from decimal import Decimal  # Decimal import 추가

# AWS 서비스 클라이언트
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# JSON 인코더 클래스 정의
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)  # Decimal을 float로 변환
        return super(DecimalEncoder, self).default(obj)

# 환경 변수
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET')
METADATA_TABLE = os.environ.get('METADATA_TABLE')

def lambda_handler(event, context):
    """문서 처리 Lambda 핸들러"""
    try:
        print(f"Received event: {json.dumps(event)}")
        print(f"Event keys: {list(event.keys())}")
        # 이벤트에 httpMethod가 있는지 확인
        has_http_method = 'httpMethod' in event
        print(f"Has httpMethod: {has_http_method}")
        
        # httpMethod가 있을 경우 관련 정보 출력
        if has_http_method:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            print(f"HTTP Method: {http_method}")
            print(f"Path: {path}")
            print(f"Path Parameters: {path_params}")
        
        # API Gateway 프록시 통합
        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}
            
            # 문서 목록 조회
            if http_method == 'GET' and path == '/documents':
                return get_documents(event)
            
            # 특정 문서 조회
            elif http_method == 'GET' and path.startswith('/documents/') and path_params.get('document_id') and path_params.get('timestamp'):
                return get_document(path_params['document_id'], path_params['timestamp'])

            
            # 문서 업로드
            elif http_method == 'POST' and path == '/documents/upload':
                return upload_document(event)
                
            # 문서 삭제
            elif http_method == 'DELETE' and path_params.get('document_id') and path_params.get('timestamp'):
                return delete_document(path_params['document_id'], path_params['timestamp'])

                
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
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }
def get_documents(event):
    """모든 문서 목록 조회"""
    try:
        table = dynamodb.Table(METADATA_TABLE)
        
        # 파라미터 파싱
        query_params = event.get('queryStringParameters', {}) or {}
        document_type = query_params.get('document_type')
        status = query_params.get('status', 'ACTIVE')  # 기본값으로 활성 문서만 조회
        
        # 필터 표현식 생성
        filter_expression = "attribute_exists(document_id)"
        expression_values = {}
        
        # 상태 필터
        if status:
            filter_expression += " AND #status = :status"
            expression_values[':status'] = status
        
        # 문서 타입 필터
        if document_type:
            filter_expression += " AND document_type = :doctype"
            expression_values[':doctype'] = document_type

        # DynamoDB 스캔 실행
        if expression_values:
            response = table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames={'#status': 'status'} if status else {}
            )
        else:
            response = table.scan()
        
        # 결과 정렬
        items = sorted(response.get('Items', []), key=lambda x: x.get('updated_at', 0), reverse=True)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'documents': items,
                'count': len(items)
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting documents: {str(e)}"}, cls=DecimalEncoder)
        }

def get_document(document_id, timestamp):
    """복합 키로 특정 문서 조회"""
    try:
        table = dynamodb.Table(METADATA_TABLE)

        # timestamp는 DynamoDB에서 Number 타입으로 저장되어 있으므로 변환
        response = table.get_item(
            Key={
                'document_id': document_id,
                'timestamp': int(float(timestamp))
            }
        )

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }

        document = response['Item']

        # S3 미리 서명된 URL 생성
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
            'body': json.dumps(document, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error getting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error getting document: {str(e)}"}, cls=DecimalEncoder)
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
                'body': json.dumps({'message': 'Title is required'}, cls=DecimalEncoder)
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
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error creating document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error creating document: {str(e)}"}, cls=DecimalEncoder)
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
                'body': json.dumps({'message': 'File content and filename are required'}, cls=DecimalEncoder)
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
                'body': json.dumps({'message': f'Invalid file content: {str(e)}'}, cls=DecimalEncoder)
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
                    'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
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
            }, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error uploading document: {str(e)}"}, cls=DecimalEncoder)
        }

def delete_document(document_id, timestamp):
    """복합 키(document_id + timestamp)로 문서 soft delete"""
    try:
        table = dynamodb.Table(METADATA_TABLE)

        # S3 경로를 확인하기 위해 먼저 문서 조회
        response = table.get_item(
            Key={
                'document_id': document_id,
                'timestamp': int(float(timestamp))
            }
        )

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }

        item = response['Item']

        # S3 객체 삭제
        if 's3_path' in item:
            s3.delete_object(Bucket=DOCUMENT_BUCKET, Key=item['s3_path'])

        # DynamoDB soft delete (status = DELETED)
        table.update_item(
            Key={
                'document_id': document_id,
                'timestamp': int(float(timestamp))
            },
            UpdateExpression="set #status = :status, updated_at = :time",
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'DELETED',
                ':time': int(datetime.now().timestamp())
            }
        )

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': 'Document deleted successfully'}, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'message': f"Error deleting document: {str(e)}"}, cls=DecimalEncoder)
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