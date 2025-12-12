import requests
import json

# ================= CONFIGURATION =================
# FHIR 서버 주소 (마지막 슬래시 제외)
FHIR_BASE_URL = "http://localhost:8080/fhir"
FHIR_BASE_URL = "http://127.0.0.1:8084/fhir"
# 인증이 필요한 경우 헤더 추가 (예: Authorization: Bearer token)
HEADERS = {
    "Content-Type": "application/fhir+json",
    # "Authorization": "Bearer YOUR_ACCESS_TOKEN" 
}

# 변경 대상이 되는 잘못된 카테고리 코드들 (대소문자 혼용 고려)
TARGET_CATEGORIES = ["Output", "Drains", "output", "drains"]

# 변경할 목표 표준 카테고리 (vital-signs)
NEW_CATEGORY = [
    {
        "coding": [
            {
                "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                "code": "vital-signs",
                "display": "Vital Signs"
            }
        ]
    }
]

# True: 실제 변경은 안 하고 로그만 출력 / False: 실제 서버 데이터 수정
DRY_RUN = False 
# =================================================

def update_observation_category():
    # 1. 대상 데이터 검색 (콤마로 구분하여 OR 검색)
    # 예: GET /Observation?category=Output,Drains,output,drains
    search_query = ",".join(TARGET_CATEGORIES)
    next_url = f"{FHIR_BASE_URL}/Observation?category={search_query}"
    
    processed_count = 0
    
    print(f"[*] 검색 시작: category가 {TARGET_CATEGORIES}인 Observation 찾기...")
    if DRY_RUN:
        print("[!] DRY_RUN 모드입니다. 실제 데이터는 변경되지 않습니다.\n")

    while next_url:
        try:
            response = requests.get(next_url, headers=HEADERS)
            response.raise_for_status()
            bundle = response.json()
        except requests.exceptions.RequestException as e:
            print(f"[Error] 검색 중 오류 발생: {e}")
            break

        if 'entry' not in bundle:
            print("[-] 더 이상 변경할 데이터가 없습니다.")
            break

        entries = bundle['entry']
        print(f"[*] 현재 페이지에서 {len(entries)}개의 리소스 처리 중...")

        for entry in entries:
            resource = entry['resource']
            resource_id = resource['id']
            old_categories = resource.get('category', [])

            # 현재 카테고리 로깅
            # print(f"    - ID: {resource_id}, Old Category: {json.dumps(old_categories, ensure_ascii=False)}")

            # 2. 데이터 수정
            # 기존 category를 완전히 덮어씌웁니다.
            resource['category'] = NEW_CATEGORY
            
            # 3. 서버에 업데이트 요청 (PUT)
            update_url = f"{FHIR_BASE_URL}/Observation/{resource_id}"
            
            if not DRY_RUN:
                try:
                    update_res = requests.put(update_url, headers=HEADERS, json=resource)
                    update_res.raise_for_status()
                    print(f"    [Success] ID: {resource_id} -> vital-signs 로 변경 완료")
                    processed_count += 1
                except requests.exceptions.RequestException as e:
                    print(f"    [Fail] ID: {resource_id} 업데이트 실패: {e}")
            else:
                print(f"    [Dry-Run] ID: {resource_id} -> vital-signs 로 변경 예정 (실행 안함)")
                processed_count += 1

        # 4. Pagination (다음 페이지 링크 확인)
        next_link = next((link for link in bundle.get('link', []) if link['relation'] == 'next'), None)
        next_url = next_link['url'] if next_link else None

    print(f"\n[Done] 총 {processed_count}개의 Observation이 처리되었습니다.")

if __name__ == "__main__":
    update_observation_category()