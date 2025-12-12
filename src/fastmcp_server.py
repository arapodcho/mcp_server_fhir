import asyncio
import os
from typing import Optional, Literal
from mcp.server.fastmcp import FastMCP, Context

# 가정: 커넥터와 유틸리티는 이미 python으로 변환되어 있다고 가정하고 import합니다.
# 실제 경로에 맞게 수정이 필요할 수 있습니다.
from connectors.fhir.fhir_client import FhirClient
from utils.cache import CacheManager
from utils.auth import Auth
from utils.auth_config import AuthConfig
# from query_parser import parse_clinician_query # 필요한 경우 import

# 1. Configuration & Dependencies Initialization
# TypeScript의 constructor에서 받던 인자들을 환경 변수나 설정에서 가져옵니다.
FHIR_URL = os.getenv("FHIR_URL", "http://hapi.fhir.org/baseR4")
FHIR_URL = "http://127.0.0.1:8084/fhir"
# Auth Config 구성
# auth_config = AuthConfig(
#     # 필요한 설정값 채우기
# )

# 2. Initialize Clients
# TS의 Server 클래스와 유사하게 상태를 관리합니다.
fhir_client = FhirClient(FHIR_URL)
cache_manager = CacheManager()

# Auth 처리를 위한 간단한 래퍼 (TS 로직 모방)
# auth_handler = Auth(auth_config)
auth_initialized = False

def _is_valid_yyyy_mm_dd(value: str) -> bool:
    """Return True if value matches YYYY-MM-DD and is a valid date."""
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        import datetime as _dt
        _dt.date.fromisoformat(value)
        return True
    except Exception:
        return False

async def ensure_auth():
    global auth_initialized
    if not auth_initialized:
        # auth_handler.initialize() # 필요한 경우 초기화 로직
        auth_initialized = True
    
    # TS 코드의 주석 처리된 로직: 
    # access_token = await auth_handler.ensure_valid_token()
    # fhir_client.set_access_token(access_token)
    pass

# 3. Initialize FastMCP Server
mcp = FastMCP("fhir-mcp", host="0.0.0.0", port=8052)

# 4. Tool Definitions
# ToolHandler.ts의 switch-case와 tools.ts의 Schema를 매핑합니다.
# FastMCP는 함수 시그니처와 Docstring을 통해 Schema를 자동 생성합니다.

@mcp.tool()
async def find_patient(last_name: str, first_name= None, birth_date=None, gender=None):
    """
    Search for a patient by demographics.
    
    Args:
        lastName: Family name (required)
        firstName: Given name (can be None)
        birthDate: YYYY-MM-DD format (can be None)
        gender: Patient gender (can be None, otherwise it has to be among "male", "female", "other" and "unknown")
    """
    await ensure_auth()
    # 조립 전 기본 검증 및 정제
    args = {
        "lastName": last_name or "",
        "firstName": first_name or "",
    }
    # birthDate는 YYYY-MM-DD 형식일 때만 포함
    if birth_date and _is_valid_yyyy_mm_dd(birth_date):
        args["birthDate"] = birth_date
    else:
        args["birthDate"] = None
    
    # gender는 허용된 값일 때만 포함
    allowed_genders = {"male", "female", "other", "unknown"}
    if gender and gender in allowed_genders:
        args["gender"] = gender
    else:
        args["gender"] = None
    
    # 빈 문자열 제거
    cleaned_args = {k: v for k, v in args.items() if v != ''}
    
    return await fhir_client.find_patient(cleaned_args)

@mcp.tool()
async def get_patient_observations(patientId: str, category, code = None, dateFrom = None, dateTo = None, status = None):
    """
    Get observations (vitals, labs) for a patient.        
    Searches for FHIR Observation resources. The category parameter is mandatory and must be automatically selected based on the user's intent. Map inquiries about measurements (BP, HR) to 'vital-signs', lab results/bloodwork to 'laboratory', radiology to 'imaging', lifestyle/smoking to 'social-history', physical findings to 'exam', and patient complaints to 'symptom'. Valid categories are: social-history, vital-signs, imaging, laboratory, procedure, survey, exam, therapy, activity, symptom.
    
    Args:
        patientId: required
        category: required and it has to be among "social-history", "vital-signs", "imaging", "laboratory", "procedure", "survey", "exam", "therapy", "activity", and "symptom"
        code:  can be None
        dateFrom: YYYY-MM-DD format (can be None)
        dateTo: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "registered", "preliminary", "final", "amended", "corrected", and "cancelled"
    """
    await ensure_auth()
    args = {
        "patientId": patientId,
        "category": category,
        "code": code,
        "dateFrom": dateFrom,
        "dateTo": dateTo,
        "status": status
    }
    
    allowed_category = ["social-history", "vital-signs", "imaging", "laboratory", "procedure", "survey", "exam", "therapy", "activity", "symptom"]
    if category and category in allowed_category:
        args["category"] = category
    else:
        args["category"] = None
        
    # dateFrom YYYY-MM-DD 형식일 때만 포함
    if dateFrom and _is_valid_yyyy_mm_dd(dateFrom):
        args["dateFrom"] = dateFrom
    else:
        args["dateFrom"] = None
        
    if dateTo and _is_valid_yyyy_mm_dd(dateTo):
        args["dateTo"] = dateTo
    else:
        args["dateTo"] = None
        
    # status 허용된 값일 때만 포함
    allowed_status = ["registered", "preliminary", "final", "amended", "corrected", "cancelled"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
    
    return await fhir_client.get_patient_observations({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_conditions(patientId: str, onsetDate = None,  status = None):
    """Get medical conditions/diagnoses for a patient.
    Args:
        patientId: required
        onsetDate: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "active", "inactive", and "resolved"
    """
    await ensure_auth()
    args = {"patientId": patientId, "onsetDate": onsetDate, "status": status}
    
    # onsetDate YYYY-MM-DD 형식일 때만 포함
    if onsetDate and _is_valid_yyyy_mm_dd(onsetDate):
        args["onsetDate"] = onsetDate
    else:
        args["onsetDate"] = None
    
    # status 허용된 값일 때만 포함
    allowed_status = ["active", "inactive", "resolved"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
        
    return await fhir_client.get_patient_conditions({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_medication_requests(patientId: str, status = None):
    """
    Retrieves medication orders (prescriptions) for a specific patient. 
    
    Use this tool to find out what medications a doctor has prescribed or ordered, 
    regardless of whether the patient has actually taken them.
    
    Args:
        patient_id: The FHIR Logical ID of the patient (e.g., "P001").
        status: Optional filter for the order status (e.g., "active", "on-hold", "ended", "stopped", "completed", "cancelled", "entered-in-error", "draft", "unknown"). 
    """
    await ensure_auth()
    args = {"patientId": patientId, "status": status}
    allowed_status = ["active", "on-hold", "ended", "stopped", "completed", "cancelled", "entered-in-error", "draft", "unknown"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
        
    return await fhir_client.get_patient_medication_requests({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def search_medication_dispenses(patient_id: str, status = None):
    """
    Retrieves records of medications dispensed (supplied) by a pharmacy.
    
    Use this tool to verify if the patient has actually received or picked up 
    the prescribed medication from the pharmacy.
    
    Args:
        patient_id: The FHIR Logical ID of the patient (e.g., "P001").
        status: Optional filter for the order status (e.g., "preparation", "in-progress", "cancelled", "on-hold", "completed", "entered-in-error", "unfulfilled", "declined", "unknown").
    """
    await ensure_auth()
    args = {"patientId": patient_id, "status": status}
    allowed_status = ["preparation", "in-progress", "cancelled", "on-hold", "completed", "entered-in-error", "unfulfilled", "declined", "unknown"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
        
    return await fhir_client.get_patient_medication_dispenses({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def search_medication_administrations(patient_id: str, status = None):
    """
    Retrieves records of actual medication administration events.
    
    Use this tool to track exactly when and how much medication was consumed by 
    or injected into the patient (common in inpatient or supervised settings).
    
    Args:
        patient_id: The FHIR Logical ID of the patient (e.g., "P001").
        status: Optional filter for the order status (e.g. "in-progress", "not-done", "on-hold", "completed", "entered-in-error", "stopped", "unknown").
    """
    await ensure_auth()
    args = {"patientId": patient_id, "status": status}
    allowed_status = ["in-progress", "not-done", "on-hold", "completed", "entered-in-error", "stopped", "unknown"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
    
    return await fhir_client.get_patient_medication_administrations({k: v for k, v in args.items() if v is not None}) 

@mcp.tool()
async def get_patient_encounters(patientId: str, dateFrom = None, dateTo = None, status = None):
    """
    Get healthcare encounters/visits for a patient.

    Args:
        dateFrom: YYYY-MM-DD format (can be None)
        dateTo: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "planned", "arrived", "in-progress", "finished", and "cancelled"
    """
    await ensure_auth()
    args = {"patientId": patientId, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
    
    # dateFrom YYYY-MM-DD 형식일 때만 포함
    if dateFrom and _is_valid_yyyy_mm_dd(dateFrom):
        args["dateFrom"] = dateFrom
    else:
        args["dateFrom"] = None
        
    if dateTo and _is_valid_yyyy_mm_dd(dateTo):
        args["dateTo"] = dateTo
    else:
        args["dateTo"] = None
        
    # status 허용된 값일 때만 포함
    allowed_status = ["planned", "arrived", "in-progress", "finished", "cancelled"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
        
    return await fhir_client.get_patient_encounters({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_procedures(patientId: str, dateFrom = None, dateTo = None, status = None):
    """
    Get procedures performed on a patient.
        
    Args:
        dateFrom: YYYY-MM-DD format (can be None)
        dateTo: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "preparation", "in-progress", "completed", and "entered-in-error""    
    """
    await ensure_auth()
    args = {"patientId": patientId, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
    
    # dateFrom YYYY-MM-DD 형식일 때만 포함
    if dateFrom and _is_valid_yyyy_mm_dd(dateFrom):
        args["dateFrom"] = dateFrom
    else:
        args["dateFrom"] = None
        
    if dateTo and _is_valid_yyyy_mm_dd(dateTo):
        args["dateTo"] = dateTo
    else:
        args["dateTo"] = None
        
    # status 허용된 값일 때만 포함
    allowed_status = ["preparation", "in-progress", "completed", "entered-in-error"]
    if status and status in allowed_status:
        args["status"] = status
    else:
        args["status"] = None
        
    return await fhir_client.get_patient_procedures({k: v for k, v in args.items() if v is not None})

# @mcp.tool()
# async def get_patient_allergies(patientId: str, status: Optional[Literal["active", "inactive", "resolved"]] = None, type: Optional[Literal["allergy", "intolerance"]] = None, category: Optional[Literal["food", "medication", "environment", "biologic"]] = None):
#     """Get allergies and intolerances for a patient."""
#     await ensure_auth()
#     args = {"patientId": patientId, "status": status, "type": type, "category": category}
#     return await fhir_client.get_patient_allergies({k: v for k, v in args.items() if v is not None})

# @mcp.tool()
# async def get_patient_careplans(patientId: str, category: Optional[str] = None, status: Optional[Literal["draft", "active", "suspended", "completed", "cancelled"]] = None, dateFrom: Optional[str] = None, dateTo: Optional[str] = None):
#     """Get care plans for a patient."""
#     await ensure_auth()
#     args = {"patientId": patientId, "category": category, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
#     return await fhir_client.get_patient_care_plans({k: v for k, v in args.items() if v is not None})

# @mcp.tool()
# async def get_patient_careteam(patientId: str, status: Optional[str] = None):
#     """Get care team members for a patient."""
#     await ensure_auth()
#     args = {"patientId": patientId, "status": status}
#     return await fhir_client.get_patient_care_team({k: v for k, v in args.items() if v is not None})

# @mcp.tool()
# async def get_vital_signs(patientId: str, timeframe: Optional[str] = None):
#     """
#     Get patient's vital signs history.
    
#     Args:
#         timeframe: e.g., 3m, 6m, 1y, all
#     """
#     await ensure_auth()
#     args = {"patientId": patientId, "timeframe": timeframe}
#     return await fhir_client.get_patient_vital_signs({k: v for k, v in args.items() if v is not None})

# @mcp.tool()
# async def get_lab_results(patientId: str, category: Optional[str] = None, timeframe: Optional[str] = None):
#     """
#     Get patient's lab results.
    
#     Args:
#         category: e.g., CBC, METABOLIC, LIPIDS, ALL
#     """
#     await ensure_auth()
#     args = {"patientId": patientId, "category": category, "timeframe": timeframe}
#     return await fhir_client.get_patient_lab_results({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_medications_history(patientId: str, includeDiscontinued: Optional[bool] = None):
    """Get patient's medication history including changes."""
    await ensure_auth()
    args = {"patientId": patientId, "includeDiscontinued": includeDiscontinued}
    return await fhir_client.get_medication_history({k: v for k, v in args.items() if v is not None})

# @mcp.tool()
# async def get_appointments(patientId: str, dateFrom: Optional[str] = None, dateTo: Optional[str] = None):
#     """Get patient's Appointments."""
#     await ensure_auth()
#     args = {"patientId": patientId, "dateFrom": dateFrom, "dateTo": dateTo}
#     return await fhir_client.get_patient_appointments({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def clinical_query(query: str):
    """Execute a natural language clinical query."""
    await ensure_auth()
    # query-parser 로직 필요 (여기서는 mock)
    # query_params = await parse_clinician_query(query)
    # return await fhir_client.execute_query(query_params)
    pass

# 5. Run Server
if __name__ == "__main__":
    # TypeScript의 stdio transport 실행과 동일
    print("FHIR MCP server running on stdio", file=os.sys.stderr)
    mcp.run(transport='sse')