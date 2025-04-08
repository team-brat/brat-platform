import requests
import uuid
import json
import base64
from datetime import datetime
from decimal import Decimal
API_BASE_URL = "https://zf42ytba0m.execute-api.us-east-2.amazonaws.com/dev"
RECEIVING_ORDERS_ENDPOINT = f"{API_BASE_URL}/receiving-orders"

TEST_ORDER_ID = None

def generate_test_order():
    """Generate test data using the legacy format (which we know works)"""
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

def generate_new_structure_test_data():
    """Generate test data in the new structure format"""
    # For testing with small files, use actual simple base64
    sample_base64 = base64.b64encode(b"Test document content").decode('utf-8')
    
    return {
        "request_details": {
            "scheduled_date": datetime.now().strftime("%Y-%m-%d"),
            "supplier_name": "Acme Corp",
            "supplier_number": "SUP-001",
            "po_number": f"PO-{uuid.uuid4().hex[:8]}",
            "contact_name": "John Doe",
            "contact_phone": "010-9876-5432",
            "responsible_person": "Jane Smith",
            "notes": "Created with new structure"
        },
        "sku_information": {
            "sku_name": "Widget A",
            "sku_number": "SKU-12345",
            "quantity": 15,
            "serial_or_barcode": "ABC123456789",
            "length": "20.5",
            "width": "15.0",
            "height": "10.0",
            "depth": "5.0",
            "volume": "3000",
            "weight": "2.5",
            "notes": "Handle with care"
        },
        "shipment_information": {
            "shipment_number": "SHIP-9988",
            "truck_number": "TRUCK-11",
            "driver_contact_info": "+82-10-1234-5678"
        },
        "documents": {
            "invoice": {
                "file_name": "invoice.pdf",
                "content_type": "application/pdf",
                "file_content": sample_base64
            },
            "bill_of_entry": {
                "file_name": "bill.pdf",
                "content_type": "application/pdf",
                "file_content": sample_base64
            },
            "airway_bill": {
                "file_name": "airwaybill.pdf",
                "content_type": "application/pdf",
                "file_content": sample_base64
            }
        },
        "user_id": "api_test_user"
    }

def print_result(name, response):
    print(f"\n--- {name} ---")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2))
    except:
        print(response.text)

def test_create_order_legacy():
    """Test creating an order with the legacy format"""
    global TEST_ORDER_ID
    print("\n[1] Create Receiving Order (Legacy Format)")
    
    payload = generate_test_order()
    response = requests.post(RECEIVING_ORDERS_ENDPOINT, json=payload)
    print_result("Create Receiving Order (Legacy)", response)
    
    if response.status_code == 201:
        TEST_ORDER_ID = response.json()["order"]["order_id"]
        return True
    return False

def test_create_order_new_structure():
    """Test creating an order with the new structure format"""
    global TEST_ORDER_ID
    print("\n[1] Create Receiving Order (New Structure)")
    
    payload = generate_new_structure_test_data()
    response = requests.post(RECEIVING_ORDERS_ENDPOINT, json=payload)
    print_result("Create Receiving Order (New Structure)", response)
    
    if response.status_code == 201:
        response_data = response.json()
        if "order" in response_data:
            TEST_ORDER_ID = response_data["order"]["order_id"]
        elif "order_id" in response_data:
            TEST_ORDER_ID = response_data["order_id"]
        return True
    return False

def test_get_order():
    print(f"\n[2] Get Receiving Order: {TEST_ORDER_ID}")
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
    print("\n[5] Update Order Status to IN_PROGRESS")
    response = requests.put(f"{RECEIVING_ORDERS_ENDPOINT}/{TEST_ORDER_ID}/status", json={
        "status": "IN_PROGRESS",
        "user_id": "api_test_user",
        "notes": "Changing status for test"
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
    supplier_id = "SUPP-123"  # Use the supplier ID from our legacy structure
    response = requests.get(f"{RECEIVING_ORDERS_ENDPOINT}?supplier_id={supplier_id}")
    print_result(f"Filter by supplier_id ({supplier_id})", response)

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
    # First try the new structure format
    created_with_new = test_create_order_new_structure()
    
    # If the new structure fails, fall back to legacy format
    if not created_with_new:
        print("\n⚠️ New structure format failed, falling back to legacy format")
        created_with_legacy = test_create_order_legacy()
        if not created_with_legacy:
            print("❌ Both new structure and legacy formats failed to create an order.")
            return
    
    if TEST_ORDER_ID:
        print(f"\n✅ Successfully created order with ID: {TEST_ORDER_ID}")
        test_get_order()
        test_update_order_info()
        test_list_orders()
        test_filtering_by_supplier()
        test_status_update()
        test_document_verification()
        test_invalid_status_update()
        test_receive_order()
        test_delete_order()
        test_missing_fields_on_create()
    else:
        print("❌ TEST_ORDER_ID not set. Create order failed.")


if __name__ == "__main__":
    run_all_tests()