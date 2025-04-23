import requests
import json

BASE_URL = "https://zf42ytba0m.execute-api.us-east-2.amazonaws.com/dev"

def pretty(res):
    print(f"[{res.status_code}] {res.request.method} {res.url}")
    try:
        print(json.dumps(res.json(), indent=2, ensure_ascii=False))
    except:
        print(res.text)
    print("=" * 60)

def get_verification_results(order_id=None):
    url = f"{BASE_URL}/verification-results"
    if order_id:
        url += f"?order_id={order_id}"
    res = requests.get(url)
    pretty(res)

def submit_verification(order_id, document_id):
    url = f"{BASE_URL}/receiving-orders/{order_id}/documents/verify"
    
    payload = {
        "user_id": "suhyeon",
        "verification_results": [
            {
                "document_id": document_id,
                "result": "APPROVED",
                "notes": "서류 이상 없음",
                "discrepancies": ""
            }
        ]
    }
    res = requests.post(url, json=payload)
    pretty(res)

if __name__ == "__main__":
    # ✅ 여기에 실제 사용 가능한 order_id, document_id를 넣어주세요
    test_order_id = "aa40771c-089b-410f-ac4f-4901fd402d40"         # 예: "9f9d8c13-xxxx-..."
    test_document_id = "doc-5678"             # 예: "doc-0001"
    
    get_verification_results()
    submit_verification(test_order_id, test_document_id)
    get_verification_results(test_order_id)
