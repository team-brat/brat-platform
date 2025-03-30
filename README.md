# WMS Project
A serverless backend implementation of a Warehouse Management System (WMS).

## Project Structure

- `src/functions/`: Lambda function code
  - `document-service/`: Document processing service
  - `bin-service/`:  Warehouse bin management service
- `infrastructure/`: CloudFormation templates
- `buildspec.yml`: AWS CodeBuild build specification
- src/functions/: Lambda function code

## Local Development Setup

- 1. Install required tools: pip install -r requirements.txt
- 2. Configure AWS profile: aws configure

## Deployment
This project is automatically deployed through AWS CodePipeline.
When changes are pushed to the GitHub repository, the build and deployment process is triggered automatically.



# WMS 프로젝트

창고 관리 시스템(WMS)의 서버리스 백엔드 구현입니다.

## 프로젝트 구조

- `src/functions/`: Lambda 함수 코드
  - `document-service/`: 문서 처리 서비스
  - `bin-service/`: 창고 빈 관리 서비스
- `infrastructure/`: CloudFormation 템플릿
- `buildspec.yml`: AWS CodeBuild 빌드 스펙

## 로컬 개발 환경 설정

1. 필요 도구 설치: pip install -r requirements.txt
2. AWS 프로필 설정: aws configure

## 배포

이 프로젝트는 AWS CodePipeline을 통해 자동으로 배포됩니다. 
GitHub 저장소에 변경사항을 푸시하면 자동으로 빌드 및 배포가 이루어집니다.


