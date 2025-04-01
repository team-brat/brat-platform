#!/bin/bash
# WMS API 테스트 스크립트

# API 기본 URL
API_URL="https://vxl6odjqg7.execute-api.us-east-2.amazonaws.com/dev"

# 콘솔 출력 색상 설정
GREEN="\033[0;32m"
RED="\033[0;31m"
BLUE="\033[0;34m"
RESET="\033[0m"

echo -e "${BLUE}===== WMS API 테스트 시작 =====${RESET}\n"

# -------------- 빈(Bins) API 테스트 --------------

# 1. 빈 생성 테스트
echo -e "${BLUE}===== 1. 빈 생성 테스트 =====${RESET}"
BIN_RESPONSE=$(curl -s -X POST "${API_URL}/bins" \
  -H "Content-Type: application/json" \
  -d '{"zone":"A","aisle":"01","rack":"02","level":"03"}')
echo "$BIN_RESPONSE"
echo

# 2. 빈 생성 테스트 (실패케이스)
echo -e "${BLUE}===== 2. 빈 생성 테스트 (실패케이스) =====${RESET}"
BIN_RESPONSE=$(curl -s -X POST "${API_URL}/bins" \
  -H "Content-Type: application/json" \
  -d '{"aisle":"01","rack":"02","level":"03"}')
echo "$BIN_RESPONSE"
echo

# 3. 빈 목록 조회 테스트
echo -e "${BLUE}===== 3. 빈 목록 조회 테스트 =====${RESET}"
curl -s -X GET "${API_URL}/bins"
echo

# 4. 특정 빈 조회 테스트
echo -e "${BLUE}===== 4. 특정 빈 조회 테스트 =====${RESET}"
curl -s -X GET "${API_URL}/bins/A-01-02-03"
echo

# 5. 빈 상태 조회 테스트
echo -e "${BLUE}===== 5. 빈 상태 조회 테스트 =====${RESET}"
curl -s -X GET "${API_URL}/bins/status"
echo

# 6. 빈 정보 업데이트 테스트
echo -e "${BLUE}===== 6. 빈 정보 업데이트 테스트 =====${RESET}"
curl -s -X PUT "${API_URL}/bins/A-01-02-03" \
  -H "Content-Type: application/json" \
  -d '{"product_id":"PROD-12345","quantity":10,"status":"OCCUPIED"}'
echo

# 7. 업데이트된 빈 확인
echo -e "${BLUE}===== 7. 업데이트된 빈 확인 =====${RESET}"
curl -s -X GET "${API_URL}/bins/A-01-02-03"
echo

# 8. 빈 삭제 테스트
echo -e "${BLUE}===== 8. 빈 삭제 테스트 =====${RESET}"
curl -s -X DELETE "${API_URL}/bins/A-01-02-03"
echo

# 9. 삭제 확인 테스트
echo -e "${BLUE}===== 9. 삭제 확인 테스트 =====${RESET}"
curl -s -X GET "${API_URL}/bins/A-01-02-03"
echo


# -------------- 문서(Documents) API 테스트 --------------

# 10. 문서 목록 조회 테스트
echo -e "${BLUE}===== 10. 문서 목록 조회 테스트 =====${RESET}"
curl -s -X GET "${API_URL}/documents"
echo

# 11. 문서 메타데이터 생성 테스트
echo -e "${BLUE}===== 11. 문서 메타데이터 생성 테스트 =====${RESET}"
DOC_META_RESPONSE=$(curl -s -X POST "${API_URL}/documents" \
  -H "Content-Type: application/json" \
  -d '{"title":"테스트 문서","document_type":"report"}')
echo "$DOC_META_RESPONSE"
META_DOC_ID=$(echo "$DOC_META_RESPONSE" | jq -r '.document_id')
echo -e "생성된 문서 메타데이터 ID: ${GREEN}$META_DOC_ID${RESET}"
echo

# 12. 문서 업로드 테스트
echo -e "${BLUE}===== 12. 문서 업로드 테스트 =====${RESET}"
UPLOAD_RESPONSE=$(curl -s -X POST "${API_URL}/documents/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "filename":"test.txt",
    "file":"SGVsbG8gV29ybGQhIFRoaXMgaXMgYSB0ZXN0IGZpbGUu"
  }')
echo "$UPLOAD_RESPONSE"
UPLOAD_DOC_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.document_id')

# 문서 목록에서 해당 document_id의 timestamp 추출
echo -e "${BLUE}→ timestamp 조회 중...${RESET}"
UPLOAD_TIMESTAMP=$(curl -s -X GET "${API_URL}/documents" | jq -r --arg id "$UPLOAD_DOC_ID" '.documents[] | select(.document_id == $id) | .timestamp')
echo -e "업로드된 문서 ID: ${GREEN}$UPLOAD_DOC_ID${RESET}"
echo -e "업로드된 문서 TIMESTAMP: ${GREEN}$UPLOAD_TIMESTAMP${RESET}"
echo

# 13. 특정 문서 조회 테스트 (복합 키)
echo -e "${BLUE}===== 13. 특정 문서 조회 테스트 (document_id + timestamp) =====${RESET}"
curl -s -X GET "${API_URL}/documents/$UPLOAD_DOC_ID/$UPLOAD_TIMESTAMP"
echo

# 14. 문서 삭제 테스트
echo -e "${BLUE}===== 14. 문서 삭제 테스트 =====${RESET}"
curl -s -X DELETE "${API_URL}/documents/$UPLOAD_DOC_ID/$UPLOAD_TIMESTAMP"
echo

echo -e "\n${BLUE}===== WMS API 테스트 완료 =====${RESET}"
