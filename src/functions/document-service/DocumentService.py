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

# 공통 헤더
COMMON_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
}

def lambda_handler(event, context):
    try:
        print(f"Received event: {json.dumps(event)}")

        if 'httpMethod' in event:
            http_method = event.get('httpMethod')
            path = event.get('path', '')
            path_params = event.get('pathParameters', {}) or {}

            if http_method == 'GET' and path == '/documents':
                return get_documents(event)
            elif http_method == 'GET' and path.startswith('/documents/') and path_params.get('document_id'):
                return get_document(path_params['document_id'])
            elif http_method == 'POST' and path == '/documents':
                return upload_document(event)
            elif http_method == 'DELETE' and path.startswith('/documents/') and path_params.get('document_id'):
                return delete_document(path_params['document_id'])

            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Endpoint not found', 'path': path, 'method': http_method}, cls=DecimalEncoder)
            }

        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': 'Document service executed directly', 'event': event}, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error: {str(e)}"}, cls=DecimalEncoder)
        }

def get_documents(event):
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        order_id = query_params.get('order_id')
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)

        if order_id:
            response = table.query(
                IndexName='order_id-index',
                KeyConditionExpression='order_id = :order_id',
                ExpressionAttributeValues={':order_id': order_id}
            )
        else:
            response = table.scan()

        documents = response.get('Items', [])

        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'documents': documents, 'count': len(documents)}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error getting documents: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error getting documents: {str(e)}"}, cls=DecimalEncoder)
        }

def get_document(document_id):
    try:
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        response = table.get_item(Key={'document_id': document_id})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }

        document = response['Item']
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': DOCUMENT_BUCKET, 'Key': document['s3_key']},
            ExpiresIn=3600
        )

        document['download_url'] = presigned_url

        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps(document, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error getting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error getting document: {str(e)}"}, cls=DecimalEncoder)
        }

def upload_document(event):
    try:
        body = json.loads(event.get('body', '{}'))
        required_fields = ['order_id', 'document_type', 'file_name', 'content_type', 'file_content']
        missing_fields = [field for field in required_fields if field not in body]

        if missing_fields:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': f'Missing required fields: {", ".join(missing_fields)}'}, cls=DecimalEncoder)
            }

        valid_types = ['INVOICE', 'BILL_OF_ENTRY', 'AIRWAY_BILL']
        document_type = body.get('document_type')

        if document_type not in valid_types:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': f'Invalid document type. Must be one of: {", ".join(valid_types)}'}, cls=DecimalEncoder)
            }

        try:
            decoded_content = base64.b64decode(body.get('file_content'))
        except:
            return {
                'statusCode': 400,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Invalid file content. Must be base64 encoded.'}, cls=DecimalEncoder)
            }

        document_id = str(uuid.uuid4())
        timestamp = int(datetime.now().timestamp())
        file_name = body.get('file_name')
        file_extension = file_name.split('.')[-1] if '.' in file_name else ''
        s3_key = f"{body.get('order_id')}/{document_type.lower()}/{document_id}.{file_extension}"

        s3.put_object(Bucket=DOCUMENT_BUCKET, Key=s3_key, Body=decoded_content, ContentType=body.get('content_type'))

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

        event_detail = {
            'document_id': document_id,
            'order_id': body.get('order_id'),
            'document_type': document_type,
            'timestamp': timestamp
        }
        publish_event(event_detail, 'DocumentUploaded')

        return {
            'statusCode': 201,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'document': document_metadata, 'message': 'Document uploaded successfully'}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error uploading document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error uploading document: {str(e)}"}, cls=DecimalEncoder)
        }

def delete_document(document_id):
    try:
        table = dynamodb.Table(DOCUMENT_METADATA_TABLE)
        response = table.get_item(Key={'document_id': document_id})

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'headers': COMMON_HEADERS,
                'body': json.dumps({'message': 'Document not found'}, cls=DecimalEncoder)
            }

        document = response['Item']
        s3.delete_object(Bucket=DOCUMENT_BUCKET, Key=document['s3_key'])
        table.delete_item(Key={'document_id': document_id})

        return {
            'statusCode': 200,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': 'Document deleted successfully'}, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error deleting document: {str(e)}")
        return {
            'statusCode': 500,
            'headers': COMMON_HEADERS,
            'body': json.dumps({'message': f"Error deleting document: {str(e)}"}, cls=DecimalEncoder)
        }

def publish_event(event_detail, detail_type, source='wms.document-service'):
    try:
        response = events.put_events(
            Entries=[{
                'Source': source,
                'DetailType': detail_type,
                'Detail': json.dumps(event_detail, cls=DecimalEncoder)
            }]
        )
        print(f"Event published: {response}")
        return response
    except Exception as e:
        print(f"Error publishing event: {str(e)}")
        return None
