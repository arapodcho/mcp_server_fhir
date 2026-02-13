import httpx
import json
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode

# 같은 폴더에 있는 helper.py를 import 한다고 가정합니다.
from . import helper
from .fhir_auth import FHIRClient
import copy
# ResourceType은 문자열로 처리
ResourceType = str
MEDICATION_INFO_RESOURCE = "Medication"

class FhirClient:
    def __init__(self, base_url: str, grant_type=None, token_url=None, client_id=None, client_secret=None, resource_value=None):
        self.fhir_auth_client = FHIRClient(token_url, client_id, client_secret, grant_type, resource_value)
        self.access_token: Optional[str] = self.fhir_auth_client.get_access_token()
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Accept": "application/fhir+json",
                # Authorization은 set_access_token에서 설정
                "Authorization": f"Bearer {self.access_token}" if self.access_token else ""
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
        if args.get('id'):
            params['_id'] = args['id']
        else:
            if args.get('_sort'):
                if args['_sort'] == "-_lastUpdated":
                    params['_sort'] = '-_lastUpdated'
                    if args.get('_count'): params['_count'] = args['_count']
            
            if args.get('lastName'): params['family'] = args['lastName']
            if args.get('firstName'): params['given'] = args['firstName']        
            if args.get('birthDate'): params['birthdate'] = args['birthDate']
            if args.get('gender'): params['gender'] = args['gender'] #it is not work in fhir interface
            if args.get('lastUpdated'): params['_lastUpdated'] = args['lastUpdated']
            
        response = await self.client.get("/Patient", params=params)
        formatted_result = helper.format_patient_search_results(response.json(), args)
        mk_table = self._dicts_to_markdown_table(formatted_result, resource_type='Patient')
        return mk_table

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

    def _dicts_to_markdown_table(self, data_list, resource_type):
        """
        딕셔너리 리스트를 마크다운 표 형식의 문자열로 변환합니다.
        """
        if not data_list or not isinstance(data_list, list):
            return "No matching records found."

        # 1. 헤더 추출 (첫 번째 딕셔너리의 키 기준) -> 전체 딕셔너리를 확인해서, 모든 key를 헤더로 만든다.
        header_list = []
        header_seen = set()
        for row in data_list:
            if not isinstance(row, dict):
                continue
            for key in row.keys():
                if key not in header_seen:
                    header_seen.add(key)
                    header_list.append(key)
        if not header_list:
            return "No matching records found."
        headers = header_list
        
        # 2. 마크다운 표의 헤더와 구분선 생성
        header_row = "| " + " | ".join(headers) + " |"
        separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        
        # 3. 데이터 행 생성
        body_rows = []
        for data in data_list:
            if not isinstance(data, dict):
                continue
            # 각 값을 문자열로 변환하고, 줄바꿈이 있다면 제거하여 표 깨짐 방지
            # 헤더의 값이 없으면, 빈 문자열로 채운다.
            row_values = [str(data.get(h, "")).replace("\n", " ") for h in headers]
            body_rows.append("| " + " | ".join(row_values) + " |")
        
        # 4. 전체 합치기
        result_table = "\n".join([header_row, separator_row] + body_rows)
        result_value = f"""
        ### FHIR Resource: {resource_type}
        The following table provides structured details for the **{resource_type}** resource.
        {result_table}
        """
        
        return result_value
    
    async def get_patient_observations(self, args: Dict[str, Any]):                
        params = {            
            '_sort': '-date',
            '_count': '100'
        }                
        if args.get('id'):
            params['_id'] = args['id']
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('category'): params['category'] = args['category']
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])
            if args.get('code'): params['code'] = args['code']
            if args.get('status'): params['status'] = args['status']
            if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
            if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")
            
        response = await self.client.get("/Observation", params=params)
        # Observation은 종류가 다양하므로 helper의 recent metrics 사용
        formatted_result = helper.format_recent_health_metrics(response.json())
        md_text = self._dicts_to_markdown_table(formatted_result, resource_type='Observation')
        return md_text

    async def get_patient_conditions(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])
            if args.get('status'): params['clinical-status'] = args['status']
            if args.get('onsetDate'): params['onset-date'] = args['onsetDate']

        response = await self.client.get("/Condition", params=params)
        formatted_result = helper.format_conditions(response.json())
        md_text = self._dicts_to_markdown_table(formatted_result, resource_type='Condition')
        return md_text

    async def _get_medication_info(self, input: list[Dict[str, Any]]):
        result_value = copy.deepcopy(input)
        current_medications = [current_result.get('medication', '') for current_result in input if current_result.get('medication', '')]
        #if Medication is retrieved as reference number, get Medication info
        for index, current_medication in enumerate(current_medications):
            if current_medication.startswith('Medication/'):
                med_id = current_medication.split('/')[1]
                response = await self.client.get(f"/{MEDICATION_INFO_RESOURCE}/{med_id}")
                current_medication_info = helper.format_medication_info(response.json())
                result_value[index]['medication'] = current_medication_info  
        return result_value        
        
    #for medication request
    async def get_patient_medication_requests(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])
            if args.get('status'): params['status'] = args['status']
        
        response = await self.client.get(f"/MedicationRequest", params=params)
        
        format_result = helper.format_medication_requests(response.json()) #adding medication name or reference info
        result_list = await self._get_medication_info(format_result)
        
        md_text = self._dicts_to_markdown_table(result_list, resource_type='MedicationRequest')
        
        return md_text
    
    async def get_patient_medication_dispenses(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])
            if args.get('status'): params['status'] = args['status']
        
        response = await self.client.get(f"/MedicationDispense", params=params)
        
        format_result = helper.format_medication_dispenses(response.json()) #adding medication name or reference info
        result_list = await self._get_medication_info(format_result)
        
        md_text = self._dicts_to_markdown_table(result_list, resource_type='MedicationDispense')
        
        return md_text

    async def get_patient_medication_administrations(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])
            if args.get('status'): params['status'] = args['status']
        
        response = await self.client.get(f"/MedicationAdministration", params=params)
        
        formatted_list = helper.format_medication_administrations(response.json()) #adding medication name or reference info
        result_list = await self._get_medication_info(formatted_list)
        
        md_text = self._dicts_to_markdown_table(result_list, resource_type='MedicationAdministration')
        
        return md_text
    

    async def get_patient_encounters(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = args['patientId']
            if args.get('status'): params['status'] = args['status']
            if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
            if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Encounter", params=params)
        formatted_result = helper.format_encounters(response.json())
        mk_table = self._dicts_to_markdown_table(formatted_result, resource_type='Encounter')
        return mk_table


    async def get_patient_procedures(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])                    
            if args.get('status'): params['status'] = args['status']
            if args.get('dateFrom'): params.setdefault('date', []).append(f"ge{args['dateFrom']}")
            if args.get('dateTo'): params.setdefault('date', []).append(f"le{args['dateTo']}")

        response = await self.client.get("/Procedure", params=params)
        format_result = helper.format_procedures(response.json())
        md_text = self._dicts_to_markdown_table(format_result, resource_type='Procedure')
        return md_text


    async def get_medication_history(self, args: Dict[str, Any]):
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            params = {'patient': str(args['patientId'])}
        
        response = await self.client.get("/MedicationStatement", params=params)        
        formatted_list = helper.format_medication_statement(response.json())
        result_list = await self._get_medication_info(formatted_list)
        
        md_text = self._dicts_to_markdown_table(result_list, resource_type='MedicationStatement')
        
        return md_text
    
    
    async def get_diagnostic_reports(self, args: Dict[str, Any])->str:
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            params = {'patient': str(args['patientId'])}
        
        response = await self.client.get("/DiagnosticReport", params=params)        
        formatted_list = helper.format_diagnostic_reports(response.json())
        
        md_text = self._dicts_to_markdown_table(formatted_list, resource_type='DiagnosticReport')
        
        return md_text
    
    async def get_document_references(self, args: Dict[str, Any])->str:
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            params = {'patient': str(args['patientId'])}
        
        response = await self.client.get("/DocumentReference", params=params)        
        formatted_list = helper.format_document_references(response.json())
        
        md_text = self._dicts_to_markdown_table(formatted_list, resource_type='DocumentReference')
        
        return md_text
    
    async def get_allergy_intolerances(self, args: Dict[str, Any])->str:
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            params = {'patient': str(args['patientId'])}
        
        response = await self.client.get("/AllergyIntolerance", params=params)        
        formatted_list = helper.format_allergy_intolerances(response.json())
        
        md_text = self._dicts_to_markdown_table(formatted_list, resource_type='AllergyIntolerance')
        
        return md_text
    
    async def get_family_member_history(self, args: Dict[str, Any])->str:
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            params = {'patient': str(args['patientId'])}
        
        response = await self.client.get("/FamilyMemberHistory", params=params)        
        formatted_list = helper.format_family_member_history(response.json())
        
        md_text = self._dicts_to_markdown_table(formatted_list, resource_type='FamilyMemberHistory')
        
        return md_text
    
    async def get_patient_immunizations(self, args: Dict[str, Any])->str:
        params = {}
        if args.get('id'):
            params['_id'] = args['id']        
        else:
            if args.get('patientId'): params['patient'] = str(args['patientId'])                            
            if args.get('encounter_id'): params['encounter'] = str(args['encounter_id'])    
        
        response = await self.client.get("/Immunization", params=params)        
        formatted_list = helper.format_immunizations(response.json())
        
        md_text = self._dicts_to_markdown_table(formatted_list, resource_type='Immunization')
        
        return md_text