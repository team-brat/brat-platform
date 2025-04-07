# handler.py
# 이 파일은 자동 생성되었습니다.

def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'
                },
        'body': 'Hello from bin-service'
    }
