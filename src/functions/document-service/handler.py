import json
import boto3
import os
import uuid
from datetime import datetime

# AWS 서비스 초기화
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

# 환경 변수
DOCUMENT_BUCKET = os.environ.get('DOCUMENT_BUCKET')
METADATA_TABLE = os.environ.get('METADATA_TABLE')

def lambda_handler(event, context):
    """문서 처리 Lambda 핸들러"""
    try:
        # HTTP 메서드와 경로 파싱
        http_method = event.get('httpMethod')
        path = event.get('path', '')
        
        # 문서 목록 조회
        if http_method == 'GET' and not path.endswith('/upload'):
            return get_documents(event)
        
        # 문서 상세 조회
        elif http_method == 'GET' and '/documents/' in path and not path.endswith('/documents/'):
            document_id = path.split('/documents/')[1]
            return get_document(document_id)
        
        # 문서 업로드
        elif http_method == 'POST' and path.endswith('/upload'):
            return upload_document(event)
        
        # 문서 삭제
        elif http_method == 'DELETE' and '/documents/' in path:
            document_id = path.split('/documents/')[1]
            return delete_document(document_id)
        
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

def get_documents(event):
    """문서 목록 조회"""
    table = dynamodb.Table(METADATA_TABLE)
    
    # 쿼리 파라미터 처리
    query_params = event.get('queryStringParameters', {}) or {}
    filter_expr = None
    
    if query_params.get('type'):
        filter_expr = "document_type = :type"
        expr_values = {":type": query_params.get('type')}
        response = table.scan(FilterExpression=filter_expr, ExpressionAttributeValues=expr_values)
    else:
        response = table.scan()
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'documents': response.get('Items', [])})
    }

def get_document(document_id):
    """문서 상세 조회"""
    table = dynamodb.Table(METADATA_TABLE)
    response = table.get_item(Key={'document_id': document_id})
    
    if 'Item' not in response:
        return {
            'statusCode': 404,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'Document not found'})
        }
    
    metadata = response['Item']
    
    # S3에서 미리 서명된 URL 생성
    presigned_url = s3.generate_presigned_url(
        'get_object',
        Params={'Bucket': DOCUMENT_BUCKET, 'Key': metadata['s3_path']},
        ExpiresIn=3600
    )
    
    metadata['download_url'] = presigned_url
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(metadata)
    }

def upload_document(event):
    """문서 업로드"""
    # API Gateway에서 전달된 바이너리 데이터 처리
    # Base64 인코딩된 데이터를 디코딩
    import base64
    
    try:
        body = json.loads(event.get('body', '{}'))
        file_content = body.get('file')
        filename = body.get('filename')
        document_type = body.get('document_type', 'general')
        
        if not file_content or not filename:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Missing file or filename'})
            }
        
        # Base64 디코딩
        file_content_decoded = base64.b64decode(file_content)
        
        # 고유 문서 ID 생성
        document_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        
        # S3에 파일 업로드
        s3_path = f"documents/{document_type}/{document_id}/{filename}"
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
                'document_type': document_type,
                's3_path': s3_path,
                'size': len(file_content_decoded),
                'status': 'ACTIVE'
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
        print(f"Upload error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f"Upload error: {str(e)}"})
        }

def delete_document(document_id):
    """문서 삭제"""
    try:
        # 메타데이터 조회
        table = dynamodb.Table(METADATA_TABLE)
        response = table.get_item(Key={'document_id': document_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'message': 'Document not found'})
            }
        
        # S3에서 파일 삭제
        s3_path = response['Item']['s3_path']
        s3.delete_object(Bucket=DOCUMENT_BUCKET, Key=s3_path)
        
        # 메타데이터에서 상태 변경 (소프트 삭제)
        table.update_item(
            Key={'document_id': document_id},
            UpdateExpression="set #status = :status",
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'DELETED'}
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
        print(f"Delete error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': f"Delete error: {str(e)}"})
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
        'txt': 'text/plain'
    }
    return content_types.get(ext, 'application/octet-stream')