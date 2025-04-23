import boto3
import json
import uuid
from datetime import datetime
import time

# 설정
SUPPLIER_TABLE = 'wms-suppliers-dev'
RECEIVING_HISTORY_TABLE = 'wms-receiving-history-dev'
REGION = 'us-east-2'  # 지역 설정

# DynamoDB 리소스 초기화
dynamodb = boto3.resource('dynamodb', region_name=REGION)
supplier_table = dynamodb.Table(SUPPLIER_TABLE)
history_table = dynamodb.Table(RECEIVING_HISTORY_TABLE)

# 타임스탬프 생성 함수
def iso_to_timestamp(iso_date):
    """ISO 날짜 문자열을 Unix timestamp로 변환"""
    dt = datetime.fromisoformat(iso_date)
    return int(dt.timestamp())

# 더미 데이터 로드
def load_dummy_data(file_path='dummy_suppliers.json'):
    """JSON 파일에서 더미 데이터 로드"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File {file_path} not found, using hardcoded data")
        return [
            {
                "supplierName": "Fashion World",
                "supplierNumber": "SUP123",
                "skuName": "Winter Jacket",
                "skuNumber": "SKU9876",
                "barcode": "BC12345678",
                "contact": "010-1111-1111",
                "inbound": [
                    { "date": "2025-01-20", "sku": "SKU9876", "qty": 150 },
                    { "date": "2025-01-22", "sku": "SKU9876", "qty": 50 },
                    { "date": "2025-01-25", "sku": "SKU9876", "qty": 10 }
                ],
                "outbound": [
                    { "date": "2025-02-05", "sku": "SKU9876", "qty": 50 },
                    { "date": "2025-02-05", "sku": "SKU9876", "qty": 20 }
                ]
            },
            {
                "supplierName": "Denim Co",
                "supplierNumber": "SUP456", 
                "skuName": "Slim Fit Jeans",
                "skuNumber": "SKU5432",
                "barcode": "BC87654321",
                "contact": "010-2222-2222",
                "inbound": [
                    { "date": "2025-01-21", "sku": "SKU5432", "qty": 200 },
                    { "date": "2025-01-21", "sku": "SKU5432", "qty": 100 }
                ],
                "outbound": [
                    { "date": "2025-02-06", "sku": "SKU5432", "qty": 80 }
                ]
            },
            {
                "supplierName": "Cotton Kings",
                "supplierNumber": "SUP789",
                "skuName": "Cotton T-Shirt",
                "skuNumber": "SKU1234",
                "barcode": "BC98765432",
                "contact": "010-3333-3333",
                "inbound": [
                    { "date": "2025-01-22", "sku": "SKU1234", "qty": 300 }
                ],
                "outbound": [
                    { "date": "2025-02-07", "sku": "SKU1234", "qty": 120 }
                ]
            }
        ]

# 공급업체 데이터 생성 및 저장
def create_suppliers(suppliers_data):
    """더미 공급업체 데이터를 DynamoDB에 저장"""
    created_suppliers = []
    timestamp = int(datetime.now().timestamp())
    
    for supplier in suppliers_data:
        supplier_id = str(uuid.uuid4())
        
        # 공급업체 정보 구성
        supplier_data = {
            'supplier_id': supplier_id,
            'supplier_name': supplier.get('supplierName'),
            'contact_phone': supplier.get('contact', '000-0000-0000'),
            'contact_email': f"{supplier.get('supplierNumber')}@example.com",
            'contact_name': f"{supplier.get('supplierName')} Contact",
            'responsible_person': f"{supplier.get('supplierName')} Manager",
            'address': f"{supplier.get('supplierName')} Headquarters, Seoul",
            'status': 'ACTIVE',
            'created_at': timestamp,
            'updated_at': timestamp
        }
        
        try:
            # DynamoDB에 공급업체 정보 저장
            supplier_table.put_item(Item=supplier_data)
            print(f"✅ Created supplier: {supplier.get('supplierName')} (ID: {supplier_id})")
            
            # 입고/출고 이력 생성
            create_history_records(supplier_id, supplier)
            
            created_suppliers.append(supplier_id)
        except Exception as e:
            print(f"❌ Error creating supplier {supplier.get('supplierName')}: {str(e)}")
    
    return created_suppliers

# 입고/출고 이력 생성
def create_history_records(supplier_id, supplier_data):
    """공급업체의 입고/출고 이력을 생성"""
    
    # 입고 이력 생성
    for inbound in supplier_data.get('inbound', []):
        history_id = str(uuid.uuid4())
        timestamp = iso_to_timestamp(inbound.get('date'))
        
        history_data = {
            'history_id': history_id,
            'order_id': supplier_id,  # 공급업체 ID를 주문 ID로 사용
            'timestamp': timestamp,
            'event_type': 'RECEIVING_COMPLETED',
            'product_name': supplier_data.get('skuName', 'Unknown Product'),
            'quantity': inbound.get('qty', 0)
        }
        
        try:
            history_table.put_item(Item=history_data)
            print(f"  ↳ Added inbound history: {inbound.get('date')} - {inbound.get('qty')} units")
        except Exception as e:
            print(f"❌ Error creating inbound history: {str(e)}")
    
    # 출고 이력 생성
    for outbound in supplier_data.get('outbound', []):
        history_id = str(uuid.uuid4())
        timestamp = iso_to_timestamp(outbound.get('date'))
        
        history_data = {
            'history_id': history_id,
            'order_id': supplier_id,  # 공급업체 ID를 주문 ID로 사용
            'timestamp': timestamp,
            'event_type': 'DISPATCH_COMPLETED',
            'product_name': supplier_data.get('skuName', 'Unknown Product'),
            'quantity': outbound.get('qty', 0)
        }
        
        try:
            history_table.put_item(Item=history_data)
            print(f"  ↳ Added outbound history: {outbound.get('date')} - {outbound.get('qty')} units")
        except Exception as e:
            print(f"❌ Error creating outbound history: {str(e)}")

# 메인 실행 함수
def main():
    print("🚀 Starting supplier dummy data creation...")
    
    # 더미 데이터 로드
    suppliers_data = load_dummy_data()
    print(f"📋 Loaded {len(suppliers_data)} supplier records")
    
    # 사용자 확인
    confirmation = input(f"⚠️ This will create {len(suppliers_data)} suppliers and their history records in DynamoDB. Proceed? (y/n): ")
    if confirmation.lower() != 'y':
        print("❌ Operation cancelled")
        return
    
    # 공급업체 생성
    created_suppliers = create_suppliers(suppliers_data)
    
    print(f"\n✅ Successfully created {len(created_suppliers)} suppliers with their history records")
    print("🏁 Dummy data creation completed!")

from decimal import Decimal

# Decimal 타입을 float으로 직렬화할 수 있게 도와주는 JSON 인코더
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)

# 조회용 테스트 함수들
def get_all_suppliers():
    """모든 공급업체 조회"""
    response = supplier_table.scan()
    return response.get('Items', [])

def get_supplier_by_id(supplier_id):
    """특정 공급업체 조회"""
    response = supplier_table.get_item(Key={'supplier_id': supplier_id})
    return response.get('Item', {})

def get_inbound_history_by_supplier(supplier_id):
    """공급업체 입고 이력 조회 (GSI 필요)"""
    response = history_table.query(
        IndexName='order-time-index',  # 실제 인덱스 이름으로 변경 필요
        KeyConditionExpression='order_id = :oid',
        FilterExpression='event_type = :etype',
        ExpressionAttributeValues={
            ':oid': supplier_id,
            ':etype': 'RECEIVING_COMPLETED'
        }
    )
    return response.get('Items', [])

def get_outbound_history_by_supplier(supplier_id):
    """공급업체 출고 이력 조회 (GSI 필요)"""
    response = history_table.query(
        IndexName='order-time-index',  # 실제 인덱스 이름으로 변경 필요
        KeyConditionExpression='order_id = :oid',
        FilterExpression='event_type = :etype',
        ExpressionAttributeValues={
            ':oid': supplier_id,
            ':etype': 'DISPATCH_COMPLETED'
        }
    )
    return response.get('Items', [])

# 자동 테스트 실행 함수
def run_all_tests():
    print("\n🔍 [TEST] 전체 공급업체 목록 조회")
    all_suppliers = get_all_suppliers()
    print(f"총 {len(all_suppliers)}개 공급업체 조회됨")

    if all_suppliers:
        test_supplier = all_suppliers[0]
        supplier_id = test_supplier['supplier_id']
        
        print(f"\n🔍 [TEST] ID {supplier_id} 공급업체 상세 조회")
        detailed = get_supplier_by_id(supplier_id)
        print(json.dumps(detailed, indent=2, ensure_ascii=False, cls=DecimalEncoder))

        print(f"\n📦 [TEST] ID {supplier_id} 입고 이력 조회")
        inbound = get_inbound_history_by_supplier(supplier_id)
        print(json.dumps(inbound, indent=2, ensure_ascii=False, cls=DecimalEncoder))

        print(f"\n📤 [TEST] ID {supplier_id} 출고 이력 조회")
        outbound = get_outbound_history_by_supplier(supplier_id)
        print(json.dumps(outbound, indent=2, ensure_ascii=False, cls=DecimalEncoder))
    else:
        print("⚠️ 테스트할 공급업체가 없습니다.")


# 메인 실행 뒤 테스트 수행
if __name__ == "__main__":
    main()
    run_all_tests()
