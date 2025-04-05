#!/usr/bin/env python3
import os
import shutil
import sys

def create_service_structure():
    # 기본 디렉토리 경로 (프로젝트 루트 디렉토리에서 실행한다고 가정)
    base_dir = "src/functions"
    
    # 현재 모든 서비스 파일이 있는 디렉토리
    source_dir = os.path.join(base_dir, "receiving-order-service")
    
    # 서비스 및 해당 파일 매핑
    services = {
        "document-service": ["DocumentService.py"],
        "bin-service": ["handler.py"],  # handler.py가 존재한다고 가정
        "receiving-order-service": ["ReceivingOrderService.py"],
        "receiving-item-service": ["ReceivingItemService.py"],
        "supplier-service": ["SupplierService.py"],
        "verification-service": ["VerificationService.py"],
        "eventbridge-integration": ["EventBridgeIntegrationService.py"]
    }
    
    # requirements.txt 기본 내용
    default_requirements = {
        "document-service": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2"
        ],
        "bin-service": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2"
        ],
        "receiving-order-service": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2",
            "uuid==1.30"
        ],
        "receiving-item-service": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2",
            "uuid==1.30"
        ],
        "supplier-service": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2"
        ],
        "verification-service": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2"
        ],
        "eventbridge-integration": [
            "boto3==1.24.0",
            "botocore==1.27.0",
            "python-dateutil==2.8.2"
        ]
    }
    
    print(f"서비스 디렉토리 구조 생성 및 파일 이동을 시작합니다...")
    
    # 각 서비스별 디렉토리 생성 및 파일 이동
    for service, files in services.items():
        service_dir = os.path.join(base_dir, service)
        
        # 디렉토리가 이미 존재하는지 확인
        if not os.path.exists(service_dir):
            print(f"디렉토리 생성: {service_dir}")
            os.makedirs(service_dir, exist_ok=True)
        else:
            print(f"디렉토리가 이미 존재합니다: {service_dir}")
        
        # Python 파일 이동
        for file in files:
            source_file = os.path.join(source_dir, file)
            target_file = os.path.join(service_dir, file)
            
            if os.path.exists(source_file):
                # 이미 대상 파일이 존재하는지 확인
                if not os.path.exists(target_file):
                    print(f"파일 복사: {source_file} -> {target_file}")
                    shutil.copy2(source_file, target_file)
                else:
                    print(f"대상 파일이 이미 존재합니다: {target_file}")
            else:
                print(f"경고: 소스 파일을 찾을 수 없습니다: {source_file}")
                # 파일이 없는 경우 빈 파일 생성 (선택적)
                print(f"빈 파일 생성: {target_file}")
                with open(target_file, 'w') as f:
                    f.write(f"# {file}\n# 이 파일은 자동 생성되었습니다.\n\ndef lambda_handler(event, context):\n    return {{\n        'statusCode': 200,\n        'body': 'Hello from {service}'\n    }}\n")
        
        # requirements.txt 파일 생성
        req_file = os.path.join(service_dir, "requirements.txt")
        if not os.path.exists(req_file):
            print(f"requirements.txt 생성: {req_file}")
            with open(req_file, 'w') as f:
                for req in default_requirements.get(service, []):
                    f.write(f"{req}\n")
        else:
            print(f"requirements.txt가 이미 존재합니다: {req_file}")
    
    print("작업 완료!")

if __name__ == "__main__":
    # 실행전 경고 표시
    print("이 스크립트는 프로젝트 구조를 변경합니다.")
    print("실행 전에 코드를 백업하는 것을 권장합니다.")
    
    response = input("계속 진행하시겠습니까? (y/n): ")
    if response.lower() == 'y':
        create_service_structure()
    else:
        print("작업을 취소했습니다.")