import boto3
import uuid
from datetime import datetime

# 리전은 명시, 자격은 환경변수에서 가져옴
dynamodb = boto3.resource('dynamodb', region_name='us-east-2')

# ✅ 실제 테이블 이름 반영
RECEIVING_ORDER_TABLE = 'wms-receiving-orders-dev'
RECEIVING_ITEM_TABLE = 'wms-receiving-items-dev'

now = int(datetime.now().timestamp())

def create_order(order_id, status='PENDING'):
    print(f"Creating order: {order_id} with status: {status}")
    order_table = dynamodb.Table(RECEIVING_ORDER_TABLE)
    order_table.put_item(Item={
        'order_id': order_id,
        'status': status,
        'created_at': now,
        'updated_at': now
    })

from decimal import Decimal

def create_item(item_id, order_id, product_name):
    print(f"Creating item: {item_id} for order_id: {order_id}")
    item_table = dynamodb.Table(RECEIVING_ITEM_TABLE)
    item_table.put_item(Item={
        'item_id': item_id,
        'order_id': order_id,
        'product_name': product_name,
        'expected_qty': Decimal('10'),
        'sku_number': 'TESTSKU',
        'serial_or_barcode': 'SN12345',
        'length': Decimal('10'),
        'width': Decimal('5'),
        'height': Decimal('3'),
        'depth': Decimal('2'),
        'volume': Decimal('300'),
        'weight': Decimal('1.5'),
        'notes': 'Test item',
        'created_at': now,
        'updated_at': now
    })

if __name__ == "__main__":
    valid_order_id = "test-valid-order"
    valid_item_id = "test-valid-item"
    create_order(valid_order_id, status="PENDING")
    create_item(valid_item_id, valid_order_id, "Valid Product")

    invalid_order_id = "non-existent-order"
    invalid_item_id = "item-with-invalid-order"
    create_item(invalid_item_id, invalid_order_id, "Invalid Order Item")

    completed_order_id = "completed-order-id"
    completed_item_id = "item-with-completed-order"
    create_order(completed_order_id, status="COMPLETED")
    create_item(completed_item_id, completed_order_id, "Completed Order Item")

    print("\n🎉 Dummy data created!")
    print("Use these IDs in your tests:")
    print(f"VALID_ORDER_ID = '{valid_order_id}'")
    print(f"VALID_ITEM_ID = '{valid_item_id}'")
    print(f"ITEM_WITH_INVALID_ORDER = '{invalid_item_id}'")
    print(f"COMPLETED_ORDER_ID = '{completed_order_id}'")
    print(f"ITEM_WITH_COMPLETED_ORDER = '{completed_item_id}'")
