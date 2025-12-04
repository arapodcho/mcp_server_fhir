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
async def find_patient(lastName: str, firstName: Optional[str] = None, birthDate: Optional[str] = None, gender: Optional[Literal["male", "female", "other", "unknown"]] = None):
    """
    Search for a patient by demographics.
    
    Args:
        lastName: Family name
        firstName: Given name
        birthDate: YYYY-MM-DD format
        gender: Patient gender
    """
    await ensure_auth()
    args = {
        "lastName": lastName,
        "firstName": firstName,
        "birthDate": birthDate,
        "gender": gender
    }
    # None 값 제거 (TS의 args 구성 방식 따름)
    cleaned_args = {k: v for k, v in args.items() if v is not None}
    return await fhir_client.find_patient(cleaned_args)

@mcp.tool()
async def get_patient_observations(patientId: str, code: Optional[str] = None, dateFrom: Optional[str] = None, dateTo: Optional[str] = None, status: Optional[Literal["registered", "preliminary", "final", "amended", "corrected", "cancelled"]] = None):
    """Get observations (vitals, labs) for a patient."""
    await ensure_auth()
    args = {
        "patientId": patientId,
        "code": code,
        "dateFrom": dateFrom,
        "dateTo": dateTo,
        "status": status
    }
    return await fhir_client.get_patient_observations({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_conditions(patientId: str, status: Optional[Literal["active", "inactive", "resolved"]] = None, onsetDate: Optional[str] = None):
    """Get medical conditions/diagnoses for a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "status": status, "onsetDate": onsetDate}
    return await fhir_client.get_patient_conditions({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_medications(patientId: str, status: Optional[Literal["active", "completed", "stopped", "on-hold"]] = None):
    """Get medication orders for a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "status": status}
    return await fhir_client.get_patient_medications({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_encounters(patientId: str, status: Optional[Literal["planned", "arrived", "in-progress", "finished", "cancelled"]] = None, dateFrom: Optional[str] = None, dateTo: Optional[str] = None):
    """Get healthcare encounters/visits for a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
    return await fhir_client.get_patient_encounters({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_allergies(patientId: str, status: Optional[Literal["active", "inactive", "resolved"]] = None, type: Optional[Literal["allergy", "intolerance"]] = None, category: Optional[Literal["food", "medication", "environment", "biologic"]] = None):
    """Get allergies and intolerances for a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "status": status, "type": type, "category": category}
    return await fhir_client.get_patient_allergies({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_procedures(patientId: str, status: Optional[Literal["preparation", "in-progress", "completed", "entered-in-error"]] = None, dateFrom: Optional[str] = None, dateTo: Optional[str] = None):
    """Get procedures performed on a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
    return await fhir_client.get_patient_procedures({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_careplans(patientId: str, category: Optional[str] = None, status: Optional[Literal["draft", "active", "suspended", "completed", "cancelled"]] = None, dateFrom: Optional[str] = None, dateTo: Optional[str] = None):
    """Get care plans for a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "category": category, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
    return await fhir_client.get_patient_care_plans({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_careteam(patientId: str, status: Optional[str] = None):
    """Get care team members for a patient."""
    await ensure_auth()
    args = {"patientId": patientId, "status": status}
    return await fhir_client.get_patient_care_team({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_vital_signs(patientId: str, timeframe: Optional[str] = None):
    """
    Get patient's vital signs history.
    
    Args:
        timeframe: e.g., 3m, 6m, 1y, all
    """
    await ensure_auth()
    args = {"patientId": patientId, "timeframe": timeframe}
    return await fhir_client.get_patient_vital_signs({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_lab_results(patientId: str, category: Optional[str] = None, timeframe: Optional[str] = None):
    """
    Get patient's lab results.
    
    Args:
        category: e.g., CBC, METABOLIC, LIPIDS, ALL
    """
    await ensure_auth()
    args = {"patientId": patientId, "category": category, "timeframe": timeframe}
    return await fhir_client.get_patient_lab_results({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_medications_history(patientId: str, includeDiscontinued: Optional[bool] = None):
    """Get patient's medication history including changes."""
    await ensure_auth()
    args = {"patientId": patientId, "includeDiscontinued": includeDiscontinued}
    return await fhir_client.get_medication_history({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_appointments(patientId: str, dateFrom: Optional[str] = None, dateTo: Optional[str] = None):
    """Get patient's Appointments."""
    await ensure_auth()
    args = {"patientId": patientId, "dateFrom": dateFrom, "dateTo": dateTo}
    return await fhir_client.get_patient_appointments({k: v for k, v in args.items() if v is not None})

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