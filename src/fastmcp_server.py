import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Optional, Literal
from mcp.server.fastmcp import FastMCP, Context

from connectors.fhir.fhir_client import FhirClient

# 1. Configuration & Dependencies Initialization
# TypeScript의 constructor에서 받던 인자들을 환경 변수나 설정에서 가져옵니다.
MCP_NAME = os.getenv("MCP_NAME", "fhir-mcp")
MCP_IP = os.getenv("MCP_IP", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8052"))

#FHIR_URL = "http://127.0.0.1:8084/fhir" #For Mimic-iv demo data in localhost
# FHIR_URL = "https://server.fire.ly" #for Firely test server
FHIR_URL = os.getenv("FHIR_URL", "http://hapi.fhir.org/baseR4")
FHIR_TOKEN_ENDPOINT = os.getenv("FHIR_TOKEN_ENDPOINT", None)
FHIR_CLIENT_ID = os.getenv("FHIR_CLIENT_ID", None)
FHIR_CLIENT_SECRET = os.getenv("FHIR_CLIENT_SECRET", None)
FHIR_GRANT_TYPE = os.getenv("FHIR_GRANT_TYPE", "Client_Credentials")
FHIR_RESOURCE_VALUE = os.getenv("FHIR_RESOURCE_VALUE", None)
# 2. Initialize Clients
# TS의 Server 클래스와 유사하게 상태를 관리합니다.
fhir_client = FhirClient(FHIR_URL, FHIR_GRANT_TYPE, FHIR_TOKEN_ENDPOINT, FHIR_CLIENT_ID, FHIR_CLIENT_SECRET, FHIR_RESOURCE_VALUE)

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
        auth_initialized = True
    pass

# 3. Initialize FastMCP Server
mcp = FastMCP(MCP_NAME, host=MCP_IP, port=MCP_PORT)

# 4. Tool Definitions
# ToolHandler.ts의 switch-case와 tools.ts의 Schema를 매핑합니다.
# FastMCP는 함수 시그니처와 Docstring을 통해 Schema를 자동 생성합니다.

@mcp.tool()
async def find_patient(last_name=None, first_name=None, patient_id=None, birth_date=None, gender=None):
    """
    Search for a patient to retrieve their unique FHIR Resource ID (patient_id).
    
    Args:
        last_name: Family name (Optional, but recommended if patient_id is missing)
        first_name: Given name (Optional)
        patient_id: Patient resource ID (Optional, if provided, other fields can be omitted)
        birth_date: YYYY-MM-DD format (Optional)
          - For 'born after 2020', use 'ge2020-01-01'.
          - For 'born in 2020', use 'eq2020'.
          - For 'between 2010 and 2015', use 'ge2010-01-01&birthdate=le2015-12-31'.
        gender: Patient gender ("male", "female", "other", "unknown") (Optional)
    """
    await ensure_auth()
    # 최소한의 검색 조건이 있는지 확인 (ID 혹은 성 중 하나는 있어야 함)
    if not patient_id and not last_name:
        return "Error: You must provide either 'patient_id' or 'last_name' to search for a patient."
    
    if patient_id is not None:
        args = {"id": patient_id}
    else:    
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
async def get_patient_observations(patient_id=None, category=None, observation_id=None, encounter_id=None, code = None, dateFrom = None, dateTo = None, status = None):
    """
    Get clinical observations (vitals, labs, exams, etc.) for a patient from FHIR resources.    
    The model should analyze the user's specific request to infer the appropriate 'category' (e.g., use 'vital-signs' for blood pressure requests).
    
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if observation_id or encounter_id is missing).
        category: can be None, otherwise it has to be among "social-history", "vital-signs", "imaging", "laboratory", "procedure", "survey", "exam", "therapy", "activity", and "symptom"
        observation_id: The FHIR Resource ID of the observation (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if observation_id or patient_id is missing)
        code:  can be None
        dateFrom: YYYY-MM-DD format (can be None)
        dateTo: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "registered", "preliminary", "final", "amended", "corrected", and "cancelled"
    """
    await ensure_auth()
    if patient_id is None and observation_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, observation_id, or encounter_id"
    
    if observation_id is not None:
        args = {'id': observation_id}
    else:
        args = {
            "patientId": patient_id,
            "category": category,        
            "encounter_id": encounter_id,
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
async def get_patient_conditions(patient_id=None, condition_id=None, encounter_id=None, onsetDate = None,  status = None):
    """Get medical conditions/diagnoses for a patient.
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if condition_id or encounter_id is missing)        
        condition_id: The FHIR Resource ID of the condition (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if condition_id or patient_id is missing)
        onsetDate: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "active", "inactive", and "resolved"
    """
    await ensure_auth()
    if patient_id is None and condition_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, condition_id, or encounter_id"
    
    if condition_id is not None:
        args = {'id': condition_id}
    else:
        args = {
            "patientId": patient_id, 
            "encounter_id": encounter_id,
            "onsetDate": onsetDate, 
            "status": status
            }
        
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
async def get_patient_medication_requests(patient_id=None, medication_request_id=None, encounter_id=None, status = None):
    """
    Retrieves medication orders (prescriptions) for a specific patient. 
    
    Use this tool to find out what medications a doctor has prescribed or ordered, 
    regardless of whether the patient has actually taken them.
    
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if medication_request_id or encounter_id is missing)        
        medication_request_id: The FHIR Resource ID of the MedicationRequest (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if medication_request_id or patient_id is missing)
        status: Optional filter for the order status (e.g., "active", "on-hold", "ended", "stopped", "completed", "cancelled", "entered-in-error", "draft", "unknown"). 
    """
    await ensure_auth()
    if patient_id is None and medication_request_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, medication_request_id, or encounter_id"
    if medication_request_id is not None:
        args = {'id': medication_request_id}
    else:                 
        args = {
            "patientId": patient_id, 
            "encounter_id": encounter_id,
            "status": status
            }
        allowed_status = ["active", "on-hold", "ended", "stopped", "completed", "cancelled", "entered-in-error", "draft", "unknown"]
        if status and status in allowed_status:
            args["status"] = status
        else:
            args["status"] = None
            
    return await fhir_client.get_patient_medication_requests({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def search_medication_dispenses(patient_id=None, medication_dispense_id=None, encounter_id=None, status = None):
    """
    Retrieves records of medications dispensed (supplied) by a pharmacy.
    
    Use this tool to verify if the patient has actually received or picked up 
    the prescribed medication from the pharmacy.
    
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if medication_dispense_id or encounter_id is missing)        
        medication_dispense_id: The FHIR Resource ID of the MedicationDispense (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if medication_dispense_id or patient_id is missing)
        status: Optional filter for the order status (e.g., "preparation", "in-progress", "cancelled", "on-hold", "completed", "entered-in-error", "unfulfilled", "declined", "unknown").
    """
    await ensure_auth()
    if patient_id is None and medication_dispense_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, medication_dispense_id, or encounter_id"
    if medication_dispense_id is not None:
        args = {'id': medication_dispense_id}
    else:                 
        args = {
            "patientId": patient_id, 
            "encounter_id": encounter_id,
            "status": status
            }
        allowed_status = ["preparation", "in-progress", "cancelled", "on-hold", "completed", "entered-in-error", "unfulfilled", "declined", "unknown"]
        if status and status in allowed_status:
            args["status"] = status
        else:
            args["status"] = None
            
    return await fhir_client.get_patient_medication_dispenses({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def search_medication_administrations(patient_id=None, medication_administration_id=None, encounter_id=None, status = None):
    """
    Retrieves records of actual medication administration events.
    
    Use this tool to track exactly when and how much medication was consumed by 
    or injected into the patient (common in inpatient or supervised settings).
    
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if medication_administration_id or encounter_id is missing)        
        medication_administration_id: The FHIR Resource ID of the MedicationAdministration (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if medication_administration_id or patient_id is missing)
        status: Optional filter for the order status (e.g. "in-progress", "not-done", "on-hold", "completed", "entered-in-error", "stopped", "unknown").
    """
    await ensure_auth()
    if patient_id is None and medication_administration_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, medication_administration_id, or encounter_id"
    if medication_administration_id is not None:
        args = {'id': medication_administration_id}
    else:                 
        args = {
            "patientId": patient_id, 
            "encounter_id": encounter_id,
            "status": status
            }
        allowed_status = ["in-progress", "not-done", "on-hold", "completed", "entered-in-error", "stopped", "unknown"]
        if status and status in allowed_status:
            args["status"] = status
        else:
            args["status"] = None
        
    return await fhir_client.get_patient_medication_administrations({k: v for k, v in args.items() if v is not None}) 

@mcp.tool()
async def get_patient_encounters(patient_id=None, encounter_id=None, dateFrom = None, dateTo = None, status = None):
# async def get_patient_encounters(patient_id:Optional[str]=None, input_id:Optional[str]=None, dateFrom :Optional[str]= None, dateTo :Optional[str]= None, status :Optional[str]= None):
    """
    Get healthcare encounters/visits for a patient.

    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if encounter_id is missing)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, if provided, other fields can be omitted)
        dateFrom: YYYY-MM-DD format (can be None)
        dateTo: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "planned", "arrived", "in-progress", "finished", and "cancelled"
    """
    await ensure_auth()
    if patient_id is None and encounter_id is None:
        return "Error: You must provide either patient_id or encounter_id"
    
    if encounter_id is not None:
        args = {'id': encounter_id}
    else:
        args = {"patientId": patient_id, "status": status, "dateFrom": dateFrom, "dateTo": dateTo}
        
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
async def get_patient_procedures(patient_id = None, procedure_id=None, encounter_id=None, dateFrom = None, dateTo = None, status = None):
    """
    Get procedures performed on a patient.
        
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if procedure_id or encounter_id is missing)        
        procedure_id: The FHIR Resource ID of the procedure (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if procedure_id or patient_id is missing)
        dateFrom: YYYY-MM-DD format (can be None)
        dateTo: YYYY-MM-DD format (can be None)
        status: can be None, otherwise it has to be among "preparation", "in-progress", "completed", and "entered-in-error""    
    """
    await ensure_auth()
    if patient_id is None and procedure_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, procedure_id, or encounter_id"
    
    if procedure_id is not None:
        args = {'id': procedure_id}
    else:        
        args = {
            "patientId": patient_id, 
            "encounter_id": encounter_id,
            "status": status, 
            "dateFrom": dateFrom, 
            "dateTo": dateTo
            }
        
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

@mcp.tool()
async def get_medications_history(patient_id=None, medication_statement_id=None):
    """
    Retrieves a patient's medication history from FHIR resources.
    
    This tool fetches MedicationStatement records to provide a chronological view 
    of medications a patient has taken, is taking, or is intended to take.

    Args:
        patient_id: The FHIR Logical ID of the patient. Use this to get all medication records for a specific person. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first.
        medication_statement_id: The specific FHIR Resource ID for a single MedicationStatement. If provided, the search focuses on this specific record's history.        
    """
    await ensure_auth()
    if patient_id is None and medication_statement_id is None:
        return "Error: You must provide either patient_id or medication_statement_id"
    if medication_statement_id is not None:
        args = {'id': medication_statement_id}
    else:                 
        args = {"patientId": patient_id}
    return await fhir_client.get_medication_history({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_diagnostic_report(patient_id=None, diagnostic_report_id=None):
    """
    Retrieves a patient's diagnostic report from FHIR resources.
    This tool fetches DiagnosticReport records to provide detailed information

    Args:
        patient_id: The FHIR Logical ID of the patient. Use this to get all medication records for a specific person. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first.
        diagnostic_report_id: The specific FHIR Resource ID for a single MedicationStatement. If provided, the search focuses on this specific record's history.        
    """
    await ensure_auth()
    if patient_id is None and diagnostic_report_id is None:
        return "Error: You must provide either patient_id or diagnostic_report_id"
    if diagnostic_report_id is not None:
        args = {'id': diagnostic_report_id}
    else:                 
        args = {"patientId": patient_id}
    return await fhir_client.get_diagnostic_reports({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_document_references(patient_id=None, document_reference_id=None):
    """
    Retrieves a patient's document references from FHIR resources.
    This tool fetches DocumentReference records to provide detailed information

    Args:
        patient_id: The FHIR Logical ID of the patient. Use this to get all medication records for a specific person. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first.
        document_reference_id: The specific FHIR Resource ID for a single DocumentReference. If provided, the search focuses on this specific item.        
    """
    await ensure_auth()
    if patient_id is None and document_reference_id is None:
        return "Error: You must provide either patient_id or document_reference_id"
    if document_reference_id is not None:
        args = {'id': document_reference_id}
    else:                 
        args = {"patientId": patient_id}
    return await fhir_client.get_document_references({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_allergy_intolerances(patient_id=None, allergy_intolerance_id=None):
    """
    Retrieves a patient's allergy intolerances from FHIR resources.
    This tool fetches AllergyIntolerance records to provide detailed information

    Args:
        patient_id: The FHIR Logical ID of the patient. Use this to get all medication records for a specific person. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first.
        allergy_intolerance_id: The specific FHIR Resource ID for a single AllergyIntolerance. If provided, the search focuses on this specific item.        
    """
    await ensure_auth()
    if patient_id is None and allergy_intolerance_id is None:
        return "Error: You must provide either patient_id or allergy_intolerance_id"
    if allergy_intolerance_id is not None:
        args = {'id': allergy_intolerance_id}
    else:                 
        args = {"patientId": patient_id}
    return await fhir_client.get_allergy_intolerances({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_family_member_history(patient_id=None, family_member_history_id=None):
    """
    Retrieves a patient's family member history from FHIR resources.
    This tool fetches FamilyMemberHistory records to provide detailed information

    Args:
        patient_id: The FHIR Logical ID of the patient. Use this to get all medication records for a specific person. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first.
        family_member_history_id: The specific FHIR Resource ID for a single FamilyMemberHistory. If provided, the search focuses on this specific item.        
    """
    await ensure_auth()
    if patient_id is None and family_member_history_id is None:
        return "Error: You must provide either patient_id or family_member_history_id"
    if family_member_history_id is not None:
        args = {'id': family_member_history_id}
    else:                 
        args = {"patientId": patient_id}
    return await fhir_client.get_family_member_history({k: v for k, v in args.items() if v is not None})

@mcp.tool()
async def get_patient_immunizations(patient_id=None, immunization_id=None, encounter_id=None):
    """
    Retrieves a patient's immunization history from FHIR resources.
    This tool fetches Immunization records to provide detailed information
    
    Args:
        patient_id: The FHIR Logical ID of the patient. It is the output of find_patient. If the patient_id is missing, use find_patient to identify it first. (Optional, but recommended if immunization_id or encounter_id is missing)        
        immunization_id: The FHIR Resource ID of the Immunization (Optional, if provided, other fields can be omitted)
        encounter_id: The FHIR Resource ID of the encounter. It is the output of get_patient_encounters. If the encounter_id is missing, use get_patient_encounters to identify it first. (Optional, but recommended if immunization_id or patient_id is missing)
    """
    await ensure_auth()
    if patient_id is None and immunization_id is None and encounter_id is None:
        return "Error: You must provide either patient_id, immunization_id, or encounter_id"
    if immunization_id is not None:
        args = {'id': immunization_id}
    else:                 
        args = {
            "patientId": patient_id, 
            "encounter_id": encounter_id,
            }
        
    return await fhir_client.get_patient_immunizations({k: v for k, v in args.items() if v is not None})

# 5. Run Server
if __name__ == "__main__":
    # TypeScript의 stdio transport 실행과 동일
    print("FHIR MCP server running on stdio", file=os.sys.stderr)
    mcp.run(transport='sse')