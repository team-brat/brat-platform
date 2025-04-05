import requests
import uuid
import json
from datetime import datetime

API_BASE_URL = "https://qh9g1unehb.execute-api.us-east-2.amazonaws.com/dev"
RECEIVING_ORDERS_ENDPOINT = f"{API_BASE_URL}/receiving-orders"

TEST_ORDER_ID = None

def generate_test_order():
    return {
        "supplier_id": "SUPP-123",
        "supplier_name": "Sample Supplier",
        "scheduled_date": datetime.now().isoformat(),
        "items": [
            {
                "product_name": "Widget A",
                "sku_number": "WIDGET-A-001",
                "expected_qty": 10
            }
        ],
        "shipment_number": "SHIP-TEST-001",
        "contact_name": "Alice",
        "contact_phone": "010-1111-2222",
        "responsible_person": "Bob",
        "notes": "Created from test script",
        "truck_number": "TRUCK-999",
        "driver_contact": "010-0000-0000",
        "user_id": "api_test_user"
    }

def print_result(name, response):
    print(f"\n--- {name} ---")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)

def test_create_order():
    global TEST_ORDER_ID
    print("\n[1] Create Receiving Order")
    payload = generate_test_order()
    response = requests.post(RECEIVING_ORDERS_ENDPOINT, json=payload)
    print_result("Create Receiving Order", response)
    if response.status_code == 201:
        TEST_ORDER_ID = response.json()["order"]["order_id"]

def test_get_order():
    print("\n[2] Get Receiving Order")
    response = requests.get(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}")
    print_result("Get Receiving Order", response)

def test_update_order_info():
    print("\n[3] Update Order Info (notes, status, scheduled_date)")
    response = requests.put(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}", json={
        "notes": "Updated via script",
        "scheduled_date": datetime.now().isoformat(),
        "status": "SCHEDULED"
    })
    print_result("Update Order Info", response)

def test_list_orders():
    print("\n[4] List All Orders (no filter)")
    response = requests.get(RECEIVING_ORDERS_ENDPOINT)
    print_result("List All Orders", response)

def test_status_update():
    print("\n[5] Update Order Status to COMPLETED")
    response = requests.put(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}/status", json={
        "status": "IN_PROGRESS",
        "user_id": "api_test_user",
        "notes": "Completing order for test"
    })
    print_result("Update Order Status", response)

def test_receive_order():
    print("\n[6] Process Receiving (confirm actual receiving)")
    response = requests.post(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}/receive", json={
        "received_items": [],
        "user_id": "api_test_user"
    })
    print_result("Process Receiving", response)

def test_delete_order():
    print("\n[7] Attempt to Delete Completed Order")
    response = requests.delete(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}")
    print_result("Delete Order", response)
def test_filtering_by_supplier():
    print("\n[8] Filtering Orders by supplier_id")
    response = requests.get(f"{RECEIVING_ORDERS_ENDPOINT}?supplier_id=SUPP-123")
    print_result("Filter by supplier_id", response)

def test_invalid_status_update():
    print("\n[9] Invalid Status Update (bad value)")
    response = requests.put(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}/status", json={
        "status": "FINISHED",  # invalid
        "user_id": "api_test_user"
    })
    print_result("Invalid Status Update", response)

def test_missing_fields_on_create():
    print("\n[10] Create Order with Missing Fields")
    incomplete_payload = {
        "supplier_name": "Incomplete Supplier",
        "scheduled_date": datetime.now().isoformat()
        # missing 'supplier_id', 'items', etc.
    }
    response = requests.post(RECEIVING_ORDERS_ENDPOINT, json=incomplete_payload)
    print_result("Create Order with Missing Fields", response)

def test_document_verification():
    print("\n[11] Document Verification: POST /receiving-orders/{order_id}/documents/verify")

    endpoint = f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}/documents/verify"
    payload = {
        "user_id": "api_test_user",
        "verification_results": [
            {
                "document_id": "doc-1234",
                "result": "APPROVED",
                "notes": "Looks good",
                "discrepancies": ""
            },
            {
                "document_id": "doc-5678",
                "result": "DECLINED",
                "notes": "Missing signature",
                "discrepancies": "No company stamp"
            }
        ]
    }
    
    response = requests.post(endpoint, json=payload)
    print_result("Document Verification", response)


def run_all_tests():
    test_create_order()
    if TEST_ORDER_ID:
        test_get_order()
        test_update_order_info()
        test_list_orders()
        test_filtering_by_supplier()
        test_status_update()
        test_document_verification()  # ⬅️ 여기로 이동
        test_invalid_status_update()
        test_receive_order()
        test_delete_order()
        test_missing_fields_on_create()
    else:
        print("❌ TEST_ORDER_ID not set. Create order failed.")


if __name__ == "__main__":
    run_all_tests()
