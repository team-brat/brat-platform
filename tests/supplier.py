import requests
import json
import uuid
import boto3
from datetime import datetime
import time

# ✅ 설정값 수정
API_BASE_URL = "https://zf42ytba0m.execute-api.us-east-2.amazonaws.com/dev"
DYNAMODB_HISTORY_TABLE = "wms-receiving-history-dev"
GSI_NAME = "order-time-index"  # GSI 이름 (기본값)

dynamodb = boto3.resource("dynamodb")
history_table = dynamodb.Table(DYNAMODB_HISTORY_TABLE)

def pretty(res):
    print(f"[{res.status_code}] {res.request.method} {res.url}")
    try:
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    except:
        print(res.text)
    print("=" * 60)

def create_supplier():
    payload = {
        "supplier_name": "Test Supplier",
        "contact_email": "test@supplier.com",
        "contact_phone": "010-1234-5678",
        "contact_name": "홍길동",
        "responsible_person": "담당자",
        "address": "서울시 강남구"
    }
    res = requests.post(API_BASE_URL, json=payload)
    pretty(res)
    return res.json().get("supplier", {}).get("supplier_id")

def get_all_suppliers():
    res = requests.get(API_BASE_URL)
    pretty(res)

def get_supplier(supplier_id):
    res = requests.get(f"{API_BASE_URL}/{supplier_id}")
    pretty(res)

def update_supplier(supplier_id):
    payload = {
        "supplier_name": "Updated Supplier",
        "contact_email": "update@supplier.com",
        "status": "INACTIVE"
    }
    res = requests.put(f"{API_BASE_URL}/{supplier_id}", json=payload)
    pretty(res)

def insert_mock_history(supplier_id):
    now = int(datetime.now().timestamp())
    entries = [
        {
            'history_id': str(uuid.uuid4()),
            'order_id': supplier_id,
            'timestamp': now,
            'event_type': 'RECEIVING_COMPLETED',
            'product_name': '입고 테스트 상품',
            'quantity': 50
        },
        {
            'history_id': str(uuid.uuid4()),
            'order_id': supplier_id,
            'timestamp': now + 60,
            'event_type': 'DISPATCH_COMPLETED',
            'product_name': '출고 테스트 상품',
            'quantity': 20
        }
    ]

    for entry in entries:
        history_table.put_item(Item=entry)
        print(f"✔️ Inserted mock event: {entry['event_type']}")

def get_inbound_history(supplier_id):
    res = requests.get(f"{API_BASE_URL}/{supplier_id}/inbound-history")
    pretty(res)

def get_outbound_history(supplier_id):
    res = requests.get(f"{API_BASE_URL}/{supplier_id}/outbound-history")
    pretty(res)

def delete_supplier(supplier_id):
    res = requests.delete(f"{API_BASE_URL}/{supplier_id}")
    pretty(res)

def check_deleted_supplier(supplier_id):
    res = requests.get(f"{API_BASE_URL}/{supplier_id}")
    pretty(res)

def run_full_test():
    print("🔄 Creating Supplier...")
    supplier_id = create_supplier()
    if not supplier_id:
        print("❌ Supplier creation failed.")
        return

    print("📋 Getting All Suppliers...")
    get_all_suppliers()

    print("🔍 Getting Supplier Info...")
    get_supplier(supplier_id)

    print("✏️ Updating Supplier Info...")
    update_supplier(supplier_id)

    print("📥 Inserting Mock Inbound/Outbound History...")
    insert_mock_history(supplier_id)
    time.sleep(1)

    print("📦 Getting Inbound History...")
    get_inbound_history(supplier_id)

    print("🚚 Getting Outbound History...")
    get_outbound_history(supplier_id)

    print("🗑️ Deleting Supplier...")
    delete_supplier(supplier_id)

    print("❓ Checking Deleted Supplier...")
    check_deleted_supplier(supplier_id)

if __name__ == "__main__":
    run_full_test()
