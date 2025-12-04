import httpx
import json
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

# 같은 폴더에 있는 helper.py를 import 한다고 가정합니다.
from . import helper

# ResourceType은 문자열로 처리
ResourceType = str

class FhirClient:
    def __init__(self, base_url: str):
        self.access_token: Optional[str] = None
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Accept": "application/fhir+json",
                # Authorization은 set_access_token에서 설정
            }
        )

    def set_access_token(self, token: str):
        self.access_token = token
        self.client.headers["Authorization"] = f"Bearer {self.access_token}"

    async def search(self, resource_type: str, params: Dict[str, Any] = {}) -> Any:
        response = await self.client.get(f"/{resource_type}", params=params)
        response.raise_for_status()
        return response.json()

    async def get(self, resource_type: str, id: str) -> Any:
        response = await self.client.get(f"/{resource_type}/{id}")
        response.raise_for_status()
        return response.json()

    async def execute_query(self, query_params: Any):
        params = self._build_search_params(query_params)
        # params가 str일 경우 직접 url에 붙이고, dict일 경우 params 인자로 전달
        if isinstance(params, str):
            response = await self.client.get(f"/{query_params['resourceType']}?{params}")
        else:
            response = await self.client.get(f"/{query_params['resourceType']}", params=params)
            
        # 일반 쿼리는 결과 포맷터가 특정되지 않았으므로 기본 JSON 덤프 사용
        return self._format_results(response.json(), query_params['resourceType'])

    async def get_active_conditions(self):
        response = await self.client.get('/Condition?clinical-status=active')
        formatted_text = helper.format_conditions(response.json())
        return self._format_response_text(formatted_text)

    async def find_patient(self, args: Dict[str, Any]):
        params = {}
        if args.get('lastName'): params['family'] = args['lastName']
        if args.get('firstName'): params['given'] = args['firstName']
        if args.get('birthDate'): params['birthdate'] = args['birthDate']

        response = await self.client.get("/Patient", params=params)
        
        # Helper를 사용하여 검색 결과 포맷팅
        formatted_text = helper.format_patient_search_results(response.json())
        
        #입력 값과 matching
        
        # Helper가 "No patients found..." 메시지도 처리하므로 그대로 반환
        return self._format_response_text(formatted_text)

    def handle_error(self, error: Any):
        if isinstance(error, httpx.HTTPStatusError) or isinstance(error, httpx.RequestError):
            try:
                error_data = error.response.json()
                details = error_data.get('issue', [{}])[0].get('details', {}).get('text')
                error_msg = f"FHIR API error: {details or str(error)}"
            except:
                error_msg = f"FHIR API error: {str(error)}"
        else:
            error_msg = str(error)
            
        return {"content": [{"type": "text", "text": error_msg}], "isError": True}

    def _build_search_params(self, query_params: Any) -> Any:
        # httpx 호환을 위해 Dict로 반환하거나, 복잡한 로직(중복 키 등)을 위해 str로 반환
        params = {}
        if query_params.get('codes'):
            params['code'] = ','.join(query_params['codes'])
        
        date_range = query_params.get('dateRange')
        if date_range:
            # httpx는 동일 키에 대한 리스트 값을 지원합니다 (예: date=ge...&date=le...)
            dates = []
            if date_range.get('start'): dates.append(f"ge{date_range['start']}")
            if date_range.get('end'): dates.append(f"le{date_range['end']}")
            if dates:
                params['date'] = dates

        return params

    def _format_results(self, data: Any, resource_type: ResourceType):
        # Fallback for generic queries
        return {"content": [{"type": "text", "text": json.dumps(data, indent=2)}]}

    def _format_response_text(self, text: str):
        # 헬퍼가 생성한 텍스트를 반환 포맷에 맞게 래핑
        return {
            "content": [{
                "type": "text",
                "text": text
            }]
        }

    # 이전 코드 호환용 (JSON 덤프가 필요한 경우)
    def _format_response(self, uri: str, data: Any):
        return {
            "content": [{
                "type": "text",
                "text": json.dumps(data, indent=2)
            }]
        }

    async def get_patient_observations(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('code'): params['code'] = args['code']
        if args.get('status'): params['status'] = args['status']
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Observation", params=params)
        # Observation은 종류가 다양하므로 helper의 recent metrics 사용
        formatted_text = helper.format_recent_health_metrics(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_conditions(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('status'): params['clinical-status'] = args['status']
        if args.get('onsetDate'): params['onset-date'] = args['onsetDate']

        response = await self.client.get("/Condition", params=params)
        formatted_text = helper.format_conditions(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_medications(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('status'): params['status'] = args['status']

        response = await self.client.get("/MedicationRequest", params=params)
        formatted_text = helper.format_medications(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_encounters(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('status'): params['status'] = args['status']
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Encounter", params=params)
        formatted_text = helper.format_encounters(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_allergies(self, args: Dict[str, Any]):
        params = {'patient': args['patientId']}
        if args.get('status'): params['clinical-status'] = args['status']
        if args.get('type'): params['type'] = args['type']
        if args.get('category'): params['category'] = args['category']

        response = await self.client.get("/AllergyIntolerance", params=params)
        formatted_text = helper.format_allergies(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_procedures(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('status'): params['status'] = args['status']
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Procedure", params=params)
        formatted_text = helper.format_procedures(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_care_team(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('status'): params['status'] = args['status']

        response = await self.client.get("/CareTeam", params=params)
        formatted_text = helper.format_care_team(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_care_plans(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('status'): params['status'] = args['status']
        if args.get('category'): params['category'] = args['category']
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/CarePlan", params=params)
        formatted_text = helper.format_care_plans(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_vital_signs(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        # Vital Signs 카테고리 필터 추가 (일반적으로 필요함)
        params['category'] = 'vital-signs'
        
        response = await self.client.get("/Observation", params=params)
        formatted_text = helper.format_vital_signs(response.json())
        return self._format_response_text(formatted_text)

    async def get_medication_history(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/MedicationStatement", params=params)
        # MedicationStatement도 MedicationRequest와 구조가 유사하므로 같은 포맷터 시도
        formatted_text = helper.format_medications(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_lab_results(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        # Lab results category
        params['category'] = 'laboratory'
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Observation", params=params)
        formatted_text = helper.format_lab_results(response.json())
        return self._format_response_text(formatted_text)

    async def get_patient_appointments(self, args: Dict[str, Any]):
        params = {'patient': str(args['patientId'])}
        if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
        if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Appointment", params=params)
        formatted_text = helper.format_appointments(response.json())
        return self._format_response_text(formatted_text)

    async def get_vital_signs(self, patient_id: str, timeframe: Optional[str] = None):
        params = {
            'patient': patient_id,
            'category': 'vital-signs',
            '_sort': '-date',
            '_count': '50'
        }

        if timeframe:
            # Helper의 날짜 계산 함수 적용
            date = helper.calculate_timeframe_date(timeframe)
            if date:
                params["date"] = f"ge{date}"
        
        response = await self.client.get("/Observation", params=params)
        return response.json()

    async def get_patient_summary_data(self, patient_id: str):
        # 여러 요청을 병렬로 실행
        results = await asyncio.gather(
            self.get("Patient", patient_id),
            self.search("Condition", {"patient": patient_id}),
            self.search("MedicationRequest", {"patient": patient_id}),
            self.search("AllergyIntolerance", {"patient": patient_id}),
            self.search("Immunization", {"patient": patient_id}),
            self.search("Procedure", {"patient": patient_id}),
            self.search("CarePlan", {"patient": patient_id}),
            self.get_patient_lab_data(patient_id),
            self.search("Encounter", {"patient": patient_id}),
            self.search("Appointment", {"patient": patient_id})
        )

        data = {
            "patient": results[0],
            "conditions": results[1],
            "medications": results[2],
            "allergies": results[3],
            "immunizations": results[4],
            "procedures": results[5],
            "carePlans": results[6],
            "recentLabs": results[7],
            "encounters": results[8],
            "appointments": results[9]
        }
        
        # 원본 TS는 객체를 반환했으나, 필요시 helper.format_patient_summary(data)를 호출하여 
        # 텍스트로 변환할 수 있습니다. 여기서는 원본 TS와의 일치를 위해 data를 반환합니다.
        return data

    # Additional helper functions using internal helpers
    async def get_patient_condition_data(self, patient_id: str, timeframe: Optional[str] = None):
        search_params = {
            "patient": patient_id,
            "_sort": "date"
        }

        if timeframe:
            # Helper 적용
            date = helper.calculate_timeframe_date(timeframe)
            if date:
                search_params["date"] = f"ge{date}"
        
        return await self.search("Condition", search_params)

    async def get_patient_lab_data(self, patient_id: str, lab_type: Optional[str] = None):
        search_params = {
            "patient": patient_id,
            "category": "laboratory",
            "_sort": "-date"
        }

        if lab_type:
            search_params["code"] = lab_type

        return await self.search("Observation", search_params)

    async def get_patient_care_gaps_data(self, patient_id: str):
        results = await asyncio.gather(
            self.get("Patient", patient_id),
            self.search("Immunization", {"patient": patient_id}),
            self.search("Procedure", {"patient": patient_id}),
            self.search("CarePlan", {"patient": patient_id, "status": "active"})
        )

        return {
            "patient": results[0],
            "immunizations": results[1],
            "procedures": results[2],
            "carePlans": results[3]
        }

    # TS 클래스 내에 있던 getRelevantMetrics는 helper.py로 이동했으므로 
    # 필요하다면 helper.get_relevant_metrics를 직접 사용하도록 유도하거나 
    # 아래와 같이 래퍼를 둘 수 있습니다.
    def get_relevant_metrics(self, observations: List[Any], condition: Any) -> List[str]:
        return helper.get_relevant_metrics(observations, condition)