import requests
import base64
import json
import os
import uuid
from datetime import datetime

# API configuration
API_URL = "https://qh9g1unehb.execute-api.us-east-2.amazonaws.com/dev"
DOCUMENT_ENDPOINT = f"{API_URL}/documents"

# Create a test file if it doesn't exist
def create_test_file(filename="test_invoice.txt"):
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            f.write(f"Test Invoice\nGenerated: {datetime.now().isoformat()}\n")
        print(f"Created test file: {filename}")
    return filename

def encode_file(filename):
    """Read file and encode to base64"""
    with open(filename, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def test_document_api():
    # Generate a unique order ID for testing
    order_id = f"TEST-ORDER-{uuid.uuid4()}"
    document_id = None
    test_file = create_test_file()
    
    print(f"\n=== Testing Document API with Order ID: {order_id} ===\n")
    
    # Step 1: Upload a document
    print("1. Testing document upload...")
    upload_payload = {
        "order_id": order_id,
        "document_type": "INVOICE",
        "file_name": os.path.basename(test_file),
        "content_type": "text/plain",
        "file_content": encode_file(test_file),
        "user_id": "api_test_user"
    }
    
    response = requests.post(DOCUMENT_ENDPOINT, json=upload_payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 201:
        result = response.json()
        document_id = result["document"]["document_id"]
        print(f"Upload successful! Document ID: {document_id}")
        print(json.dumps(result, indent=2))
    else:
        print(f"Upload failed: {response.text}")
        return
    
    # Step 2: List all documents
    print("\n2. Testing document list...")
    response = requests.get(DOCUMENT_ENDPOINT)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Found {result['count']} documents")
    else:
        print(f"List failed: {response.text}")
    
    # Step 3: List documents by order ID
    print(f"\n3. Testing document list by order ID: {order_id}")
    response = requests.get(f"{DOCUMENT_ENDPOINT}?order_id={order_id}")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Found {result['count']} documents for order {order_id}")
        print(json.dumps(result, indent=2))
    else:
        print(f"List by order failed: {response.text}")
    
    # Step 4: Get document details
    if document_id:
        print(f"\n4. Testing get document: {document_id}")
        response = requests.get(f"{DOCUMENT_ENDPOINT}/{document_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("Document details:")
            print(json.dumps(result, indent=2))
            
            # Try downloading the document
            if "download_url" in result:
                print(f"\nDocument download URL: {result['download_url']}")
                print("(You can copy this URL to download the document)")
        else:
            print(f"Get document failed: {response.text}")
    
    # Step 5: Delete the document
    if document_id:
        print(f"\n5. Testing delete document: {document_id}")
        response = requests.delete(f"{DOCUMENT_ENDPOINT}/{document_id}")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("Document deleted successfully!")
        else:
            print(f"Delete failed: {response.text}")
    
    print("\n=== Document API Testing Complete ===")

if __name__ == "__main__":
    test_document_api()