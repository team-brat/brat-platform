import requests
import json
import base64
import uuid
from datetime import datetime

# API 기본 설정
API_BASE_URL = "https://zf42ytba0m.execute-api.us-east-2.amazonaws.com/dev"
HEADERS = {
    'Content-Type': 'application/json'
}

def pretty_print_response(title, response):
    """응답을 예쁘게 출력"""
    print(f"\n===== {title} =====")
    print(f"상태 코드: {response.status_code}")
    try:
        json_response = response.json()
        print(json.dumps(json_response, indent=2, ensure_ascii=False))
    except:
        print(response.text)
    print("=" * (14 + len(title)))

def encode_file_to_base64(file_path):
    """파일을 Base64로 인코딩"""
    try:
        with open(file_path, 'rb') as file:
            file_content = file.read()
            return base64.b64encode(file_content).decode('utf-8')
    except Exception as e:
        print(f"파일 인코딩 오류: {str(e)}")
        return None

def create_test_files():
    """테스트용 임시 파일 생성"""
    files = {}
    # 인보이스 파일 생성
    with open('test_invoice.txt', 'w') as f:
        f.write(f"테스트 인보이스\n생성일: {datetime.now().isoformat()}")
    files['invoice'] = 'test_invoice.txt'
    
    # 통관 서류 파일 생성
    with open('test_bill_of_entry.txt', 'w') as f:
        f.write(f"테스트 통관 서류\n생성일: {datetime.now().isoformat()}")
    files['bill_of_entry'] = 'test_bill_of_entry.txt'
    
    # 항공 화물 서류 파일 생성
    with open('test_airway_bill.txt', 'w') as f:
        f.write(f"테스트 항공 화물 서류\n생성일: {datetime.now().isoformat()}")
    files['airway_bill'] = 'test_airway_bill.txt'
    
    return files

def test_create_receiving_order():
    """입고 주문 생성 테스트"""
    print("\n🔶 입고 주문 생성 테스트 시작")
    
    # 테스트 파일 생성 및 인코딩
    test_files = create_test_files()
    documents = {}
    for doc_type, file_path in test_files.items():
        encoded_content = encode_file_to_base64(file_path)
        if encoded_content:
            documents[doc_type] = {
                "file_name": file_path,
                "content_type": "text/plain",
                "file_content": encoded_content,
                "document_type": doc_type.upper()
            }
    
    # 테스트 요청 데이터 생성
    request_data = {
        "request_details": {
            "scheduled_date": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "supplier_name": "테스트 공급업체",
            "supplier_number": "SUP-TEST-001",
            "sku_name": "테스트 상품",
            "sku_number": "SKU-TEST-001",
            "barcode": "BC-TEST-00123456789"
        },
        "sku_information": {
            "length": 50.5,
            "width": 30.2,
            "height": 10.0,
            "depth": 5.0,
            "volume": 7625.5,
            "weight": 2.3
        },
        "shipment_information": {
            "shipment_number": "SHIP-TEST-001",
            "truck_number": "TRUCK-TEST-123",
            "driver_contact": "010-1234-5678"
        },
        "documents": documents,
        "user_id": "api_test_user"
    }
    
    # API 호출
    response = requests.post(
        f"{API_BASE_URL}/receiving-orders",
        headers=HEADERS,
        data=json.dumps(request_data)
    )
    
    pretty_print_response("입고 주문 생성 결과", response)
    
    if response.status_code == 201:
        try:
            return response.json()['order']['order_id']
        except:
            print("응답에서 order_id를 찾을 수 없습니다.")
    
    return None

def test_get_receiving_orders(order_id=None):
    """입고 주문 목록 조회 테스트"""
    print("\n🔶 입고 주문 목록 조회 테스트 시작")
    
    # 기본 조회 (필터 없음)
    url = f"{API_BASE_URL}/receiving-orders"
    response = requests.get(url, headers=HEADERS)
    pretty_print_response("입고 주문 목록 조회 결과", response)
    
    # 특정 주문으로 필터링 (있는 경우)
    if order_id:
        filtered_url = f"{API_BASE_URL}/receiving-orders?order_id={order_id}"
        response = requests.get(filtered_url, headers=HEADERS)
        pretty_print_response(f"주문 ID {order_id} 필터링 결과", response)
    
    # 상태별 필터링
    status_url = f"{API_BASE_URL}/receiving-orders?status=IN_PROCESS"
    response = requests.get(status_url, headers=HEADERS)
    pretty_print_response("IN_PROCESS 상태 주문 조회 결과", response)
    
    # 날짜 범위 필터링
    today = datetime.now().strftime("%Y-%m-%d")
    date_url = f"{API_BASE_URL}/receiving-orders?from_date={today}"
    response = requests.get(date_url, headers=HEADERS)
    pretty_print_response(f"{today} 이후 주문 조회 결과", response)

def run_all_tests():
    """모든 테스트 실행"""
    print("\n🔷 WMS API 테스트 시작 🔷")
    
    # 입고 주문 생성 테스트
    order_id = test_create_receiving_order()
    
    # 입고 주문 목록 조회 테스트
    test_get_receiving_orders(order_id)
    
    print("\n🔷 WMS API 테스트 완료 🔷")

if __name__ == "__main__":
    # API 엔드포인트 수정
    API_BASE_URL = input("API 엔드포인트를 입력하세요 (기본값: https://your-api-endpoint.execute-api.region.amazonaws.com/dev): ")
    if not API_BASE_URL:
        API_BASE_URL = "https://your-api-endpoint.execute-api.region.amazonaws.com/dev"
    
    run_all_tests()