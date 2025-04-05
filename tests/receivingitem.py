import requests
import json

BASE_URL = "https://qh9g1unehb.execute-api.us-east-2.amazonaws.com/dev"
HEADERS = {'Content-Type': 'application/json'}

def print_response(title, response):
    print(f"\n📌 {title}")
    print("Status Code:", response.status_code)
    try:
        print("Response:", json.dumps(response.json(), indent=2))
    except Exception:
        print("Raw Response:", response.text)

# GET /receiving-items
def test_get_items_by_order_success(order_id):
    response = requests.get(f"{BASE_URL}/receiving-items", params={"order_id": order_id})
    print_response("GET /receiving-items (Valid Order ID)", response)

def test_get_items_by_order_invalid():
    response = requests.get(f"{BASE_URL}/receiving-items", params={"order_id": "non-existent-order"})
    print_response("GET /receiving-items (Invalid Order ID)", response)

# GET /receiving-items/{item_id}
def test_get_single_item_success(item_id):
    response = requests.get(f"{BASE_URL}/receiving-items/{item_id}")
    print_response("GET /receiving-items/{item_id} (Valid)", response)

def test_get_single_item_invalid():
    response = requests.get(f"{BASE_URL}/receiving-items/invalid-item-id")
    print_response("GET /receiving-items/{item_id} (Invalid)", response)

# PUT /receiving-items/{item_id}
def test_update_item_success(item_id):
    payload = {
        "product_name": "Updated by test",
        "expected_qty": 50,
        "notes": "Note updated"
    }
    response = requests.put(f"{BASE_URL}/receiving-items/{item_id}", data=json.dumps(payload), headers=HEADERS)
    print_response("PUT /receiving-items/{item_id} (Valid)", response)

def test_update_item_not_found():
    payload = {"product_name": "Test", "expected_qty": 10}
    response = requests.put(f"{BASE_URL}/receiving-items/not-exist-item", data=json.dumps(payload), headers=HEADERS)
    print_response("PUT /receiving-items/{item_id} (Item Not Found)", response)

def test_update_item_order_missing(item_id):
    # item_id must point to an item with invalid order_id
    payload = {"product_name": "Test", "expected_qty": 10}
    response = requests.put(f"{BASE_URL}/receiving-items/{item_id}", data=json.dumps(payload), headers=HEADERS)
    print_response("PUT /receiving-items/{item_id} (Order Not Found)", response)

def test_update_item_order_completed(item_id):
    # item_id must point to an item whose order status is COMPLETED
    payload = {"product_name": "Fail Expected", "expected_qty": 20}
    response = requests.put(f"{BASE_URL}/receiving-items/{item_id}", data=json.dumps(payload), headers=HEADERS)
    print_response("PUT /receiving-items/{item_id} (Order is COMPLETED)", response)

# POST /receiving-items/batch
def test_batch_add_items_success(order_id):
    payload = {
        "order_id": order_id,
        "items": [
            {"product_name": "Product A", "expected_qty": 5},
            {"product_name": "Product B", "expected_qty": 3, "sku_number": "SKU-002"}
        ]
    }
    response = requests.post(f"{BASE_URL}/receiving-items/batch", data=json.dumps(payload), headers=HEADERS)
    print_response("POST /receiving-items/batch (Valid)", response)

def test_batch_add_items_missing_order_id():
    payload = {
        "items": [{"product_name": "Missing Order", "expected_qty": 5}]
    }
    response = requests.post(f"{BASE_URL}/receiving-items/batch", data=json.dumps(payload), headers=HEADERS)
    print_response("POST /receiving-items/batch (Missing order_id)", response)

def test_batch_add_items_empty_items(order_id):
    payload = {
        "order_id": order_id,
        "items": []
    }
    response = requests.post(f"{BASE_URL}/receiving-items/batch", data=json.dumps(payload), headers=HEADERS)
    print_response("POST /receiving-items/batch (Empty items)", response)

def test_batch_add_items_missing_fields(order_id):
    payload = {
        "order_id": order_id,
        "items": [{"product_name": "No qty"}]  # expected_qty missing
    }
    response = requests.post(f"{BASE_URL}/receiving-items/batch", data=json.dumps(payload), headers=HEADERS)
    print_response("POST /receiving-items/batch (Missing item fields)", response)

def test_batch_add_items_order_completed(order_id):
    payload = {
        "order_id": order_id,
        "items": [{"product_name": "Should fail", "expected_qty": 3}]
    }
    response = requests.post(f"{BASE_URL}/receiving-items/batch", data=json.dumps(payload), headers=HEADERS)
    print_response("POST /receiving-items/batch (Order is COMPLETED)", response)

# Lambda 직접 호출 테스트용
def test_direct_lambda_event():
    payload = {"some": "value"}
    print("\n📌 Direct Lambda Execution Test")
    print("This should be tested through `lambda_handler(event, context)` directly in AWS or unittest mock.")

# ✅ 테스트 실행
if __name__ == "__main__":
    # test dummy
    VALID_ORDER_ID = "test-valid-order"
    VALID_ITEM_ID = "test-valid-item"
    ITEM_WITH_INVALID_ORDER = "item-with-invalid-order"
    COMPLETED_ORDER_ID = "completed-order-id"
    ITEM_WITH_COMPLETED_ORDER = "item-with-completed-order"


    # GET tests
    test_get_items_by_order_success(VALID_ORDER_ID)
    test_get_items_by_order_invalid()

    test_get_single_item_success(VALID_ITEM_ID)
    test_get_single_item_invalid()

    # PUT tests
    test_update_item_success(VALID_ITEM_ID)
    test_update_item_not_found()
    test_update_item_order_missing(ITEM_WITH_INVALID_ORDER)
    test_update_item_order_completed(ITEM_WITH_COMPLETED_ORDER)

    # POST tests
    test_batch_add_items_success(VALID_ORDER_ID)
    test_batch_add_items_missing_order_id()
    test_batch_add_items_empty_items(VALID_ORDER_ID)
    test_batch_add_items_missing_fields(VALID_ORDER_ID)
    test_batch_add_items_order_completed(COMPLETED_ORDER_ID)

    # Optional: test_direct_lambda_event()
