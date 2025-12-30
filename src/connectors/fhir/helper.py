import re
from datetime import datetime
from typing import Any, List, Dict, Optional, Union

TARGET_FHIR_RESOURCES = [
    "Patient",
    "Encounter",
    "Observation",        
    "Condition",
    "Procedure",    
    "MedicationRequest",
    "MedicationDispense",
    "MedicationAdministration",
    "MedicationStatement",
    "DiagnosticReport",
    "DocumentReference",
    "AllergyIntolerance",
    "FamilyMemberHistory",
    "Immunization"
]

def convert_fhir_to_local_str(fhir_time_str: str) -> str:
    """
    FHIR 날짜/시간을 입력받아 현재 로컬 타임존 기준으로 변환하여 출력합니다.
    - 'T' 포함 시: 로컬 타임존으로 변환 후 YYYY-MM-DD HH:MM:SS
    - 'T' 미포함 시: YYYY-MM-DD (날짜만 출력)
    """
    # 1. 안전한 입력을 위한 유효성 검사
    if not isinstance(fhir_time_str, str) or "-" not in fhir_time_str:
        return fhir_time_str

    try:
        if "T" in fhir_time_str:
            # 2. DateTime 처리: ISO 8601 파싱 (타임존 정보 포함)
            dt_obj = datetime.fromisoformat(fhir_time_str)
            
            # 3. 로컬 타임존으로 변환 (astimezone에 인자 없으면 시스템 설정 기준)
            local_dt = dt_obj.astimezone()
            
            return local_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        else:
            # 4. Date 처리 (T가 없는 경우): 날짜만 파싱하여 형식 통일
            # FHIR date는 보통 'YYYY-MM-DD' 형식이므로 문자열 슬라이싱만으로도 충분합니다.
            dt_obj = datetime.strptime(fhir_time_str[:10], "%Y-%m-%d")
            return dt_obj.strftime("%Y-%m-%d")

    except ValueError:
        return fhir_time_str

def extract_ref_display(data):
    results = []

    # 1. 데이터가 딕셔너리인 경우
    if isinstance(data, dict):
        # 원하는 키("reference")가 있는지 확인: tool 로 제작한 FHIR resource 만 해당
        if "reference" in data :
            reference_split = data["reference"].split("/")
            if len(reference_split) == 2:                
                resource_type = data["reference"].split("/")[0]
                if resource_type in TARGET_FHIR_RESOURCES:
                    current_result = {
                        "display": data.get("display", ""),
                        "resourceType": resource_type,
                        "id": data["reference"].split("/")[1]
                    }                   
                    results.append(current_result)
        
        # 딕셔너리의 내부 값들 중 또 다른 딕셔너리나 리스트가 있을 수 있으므로 재귀 호출
        for value in data.values():
            results.extend(extract_ref_display(value))

    # 2. 데이터가 리스트인 경우
    elif isinstance(data, list):
        # 리스트의 각 아이템에 대해 다시 함수 호출 (재귀)
        for item in data:
            results.extend(extract_ref_display(item))

    return results

def apply_reference_info(item: Dict[str, Any], reference_result: List[Dict[str, Any]]) -> None:    
    for current_reference in reference_result:
        current_display_key = f"Ref_Display_{current_reference['resourceType']}"
        if current_display_key in item:            
            if not isinstance(item[current_display_key], list):                
                item[current_display_key] = [item[current_display_key]]            
            item[current_display_key].append(current_reference['display'])
        else:                
            item[current_display_key] = current_reference['display']
        
        current_id_key = f"Ref_ID_{current_reference['resourceType']}"
        if current_id_key in item:            
            if not isinstance(item[current_id_key], list):                
                item[current_id_key] = [item[current_id_key]]            
            item[current_id_key].append(current_reference['id'])
        else:                
            item[current_id_key] = current_reference['id']
        
# Enhanced Helper Functions
def get_reference_info(resource: Dict[str, Any]) -> Dict[str, Any]:
    result_value = {}

    #
    return result_value

def format_patient_search_results(bundle: Dict[str, Any], params: Optional[Dict[str, Any]] = None):
    results = []

    entries = bundle.get('entry', [])
    if not entries:
        return results

    for entry in entries:
        patient = entry.get('resource', {})
        name_list = patient.get('name', [{}])
        name = name_list[0] if name_list else {}
        
        address_list = patient.get('address', [{}])
        address = address_list[0] if address_list else {}

        # Phone formatting
        telecoms = patient.get('telecom', [])
        phone = 'Not provided'
        for t in telecoms:
            if t.get('system') == 'phone':
                phone = t.get('value', 'Not provided')
                break

        given_name = ' '.join(name.get('given', []))
        
        if params is not None:
            if params.get('lastName'): 
                if name.get('family', '').lower() != params['lastName'].lower():
                    continue
            if params.get('firstName'):
                if given_name.lower() != params['firstName'].lower():
                    continue
            if params.get('gender') and params.get('gender') != 'unknown':
                if patient.get('gender').lower() != params['gender'].lower():
                    continue
        
        reference_result = extract_ref_display(patient)        
        
        current_result = {}
        current_result['PatientID'] = patient.get('id')
        current_result['Name'] = f"{name.get('family')}, {given_name}"
        current_result['DateOfBirth'] = patient.get('birthDate')
        current_result['Gender'] = patient.get('gender')
        current_result['Address'] = format_address(address)
        current_result['Phone'] = phone
        apply_reference_info(current_result, reference_result)
        results.append(current_result)

    return results





def format_procedures(bundle: Dict[str, Any]):
    output = []
    
    entries = bundle.get('entry', [])
    if not entries:
        return output

    for entry in entries:
        procedure = entry.get('resource', {})
        proc_display = procedure.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown procedure'
        category = procedure.get('category', {}).get('coding', [{}])[0].get('code') or 'Unknown category'
        Status = procedure.get('status') or 'unknown status'
        period = procedure.get('performedPeriod')
        period_str = 'unknown'
        if period:
            start = convert_fhir_to_local_str(period.get('start', ''))
            end = convert_fhir_to_local_str(period.get('end', ''))
            period_str = f"{start} to {end}"
        reference_result = extract_ref_display(procedure)
        current_result = {}
        current_result['Procedure'] = proc_display
        current_result['Category'] = category
        current_result['Status'] = Status
        current_result['Period'] = period_str
        apply_reference_info(current_result, reference_result)
        output.append(current_result)
        
    return output


def format_encounters(bundle: Dict[str, Any]):
    output = []
    
    entries = bundle.get('entry', [])
    if not entries:
        return output

    for entry in entries:
        encounter = entry.get('resource', {})
        period_str = 'unknown period'
        if 'period' in encounter:
            start = convert_fhir_to_local_str(encounter['period'].get('start', ''))
            end = convert_fhir_to_local_str(encounter['period'].get('end', ''))
            period_str = f"{start} to {end}"
        
        #"start"와 "end" 를 period로 정리해서 출력
        type_list = encounter.get('type', [{}])
        type_display = type_list[0].get('coding', [{}])[0].get('display') if type_list else 'Unknown encounter type'
        class_display = encounter.get('class', {}).get('code', '')
        reason_list = encounter.get('reasonCode', [{}])
        reason_display = 'Unknown reason for encounter'
        if reason_list:
            reason_display = reason_list[0].get('coding', [{}])[0].get('display') or reason_list[0].get('text') or reason_display
        
        reference_result = extract_ref_display(encounter)
        
        current_result = {}
        current_result['period'] = period_str        
        current_result['type'] = type_display
        current_result['reason'] = reason_display
        current_result['status'] = encounter.get('status')
        current_result['class'] = class_display
        
        apply_reference_info(current_result, reference_result)
        output.append(current_result)
        
    return output





# New Analysis Features




def format_address(address: Dict[str, Any]) -> str:
    if not address:
        return 'Not provided'
    
    lines = address.get('line', [])
    line_str = ' '.join(lines) if lines else None
    
    parts = [
        line_str,
        address.get('city'),
        address.get('state'),
        address.get('postalCode')
    ]
    
    # Filter Boolean equivalent in Python (removes None/Empty strings)
    filtered_parts = [p for p in parts if p]
    
    return ', '.join(filtered_parts)


# Utility functions

def calculate_timeframe_date(timeframe: str) -> Optional[str]:
    match = re.match(r"^(\d+)([my])$", timeframe)
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)
    
    today = datetime.now()
    target_date = today

    if unit == 'm':
        # Simple month subtraction logic
        year = today.year
        month = today.month - value
        while month <= 0:
            year -= 1
            month += 12
        # Handle day overflow (e.g. March 30 - 1 month = Feb 30 -> Feb 28)
        # This is a simplification; for production code consider dateutil.relativedelta
        day = today.day
        if month == 2:
            day = min(day, 28) # Leap year ignored for simplicity to match JS simple logic
        elif month in [4, 6, 9, 11]:
            day = min(day, 30)
            
        target_date = datetime(year, month, day)
        
    elif unit == 'y':
        target_date = today.replace(year=today.year - value)

    return target_date.isoformat().split('T')[0]





def format_recent_health_metrics(bundle: Dict[str, Any]):
    entries = bundle.get('entry', [])
    if not entries:
        return "No recent health metrics available"

    metrics: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        obs = entry.get('resource', {})
        obs_type = obs.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown'
        obs_category = obs.get('category', [{}])[0].get('coding',[{}])[0].get('code') or 'Unknown'
        if obs_type not in metrics:
            val_q = obs.get('valueQuantity', {})
            value_str = f"{val_q.get('value', 'No value')} {val_q.get('unit', '')}"
            date_str = "unknown"
            if obs.get('effectiveDateTime'):
                date_str = convert_fhir_to_local_str(obs['effectiveDateTime'])
            elif obs.get('effectivePeriod'):
                period = obs.get('effectivePeriod', {})
                if 'start' in period and 'end' in period:
                    start = convert_fhir_to_local_str(period.get('start'))
                    end = convert_fhir_to_local_str(period.get('end'))
                    date_str = f"{start} to {end}"                                            
            
            reference_result = extract_ref_display(obs)
            metrics[obs_type] = {
                'category': obs_category,
                'type': obs_type,
                'status': obs.get('status', 'unknown'),
                'value': value_str,
                'date_time': date_str,
                'references': reference_result                
            }

    output = []
    for type_name, data in metrics.items():
        current_output = {}
        current_output['Category'] = data['category']
        current_output['Type'] = data['type']
        current_output['Status'] = data['status']
        current_output['Value'] = data['value']
        current_output['Date'] = data['date_time']
        apply_reference_info(current_output, data['references'])
        output.append(current_output)
        
    return output





def format_conditions(bundle: Dict[str, Any]):
    lines = []
    # Supports both Bundle (dict with entry) or List of entries if passed directly
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return lines

    for entry in entries:
        condition = entry.get('resource', {})
        coding = condition.get('code', {}).get('coding', [{}])[0]
        name = coding.get('display') or condition.get('code', {}).get('text') or 'Unknown Condition'        
        category = condition.get('category', [{}])[0].get('coding', [{}])[0].get('code') or 'Unknown Category'
        
        if condition.get('onsetDateTime'):
            onset_str = convert_fhir_to_local_str(condition['onsetDateTime'])            
        elif condition.get('recordedDate'):
            onset_str = convert_fhir_to_local_str(condition['recordedDate'])
        else:
            onset_str = 'unknown'    
        status = condition.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', '')
        if status == '':
            status = condition.get('status', 'unknown')
        reference_result = extract_ref_display(condition)    
        
        item = {}
        item['name'] = name
        item['category'] = category        
        item['onset'] = onset_str
        item['status'] = status
        apply_reference_info(item, reference_result)
        
        lines.append(item)

    return lines

#for medication request
def format_medication_requests(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        med = entry.get('resource', {})
        identifier = med.get('identifier', [{}])
        identifier_txt = ''
        for contents in identifier:
            current_value = contents.get('value', '')
            identifier_txt += current_value
        identifier_code = ''
                
        status = med.get('status', 'unknown')
        intent = med.get('intent', 'unknown')
        dateOn = 'unknown date'        
        if med.get('authoredOn'):
            dateOn = convert_fhir_to_local_str(med.get('authoredOn'))
                
        valid_start = med.get('dispenseRequest', {}).get('validityPeriod', {}).get('start', '')
        valid_end = med.get('dispenseRequest', {}).get('validityPeriod', {}).get('end', '')

        valid_str = ''
        if valid_start != '' and valid_end != '':
            valid_str = f"{convert_fhir_to_local_str(valid_start)} to {convert_fhir_to_local_str(valid_end)}"
        
        medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('code', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationReference', {}).get('reference') or 'Unknown Medication'
        
        dosage_instr = med.get('dosageInstruction', [{}])[0]
        dosage_text = dosage_instr.get('text', 'No dosage instructions')
        dosage_timing = dosage_instr.get('timing', {}).get('code', {}).get('coding', [{}])[0].get('code', '')
        
        dose_quantity_value = dosage_instr.get('doseAndRate', [{}])[0].get('doseQuantity', {}).get('value', '')
        dose_quantity_unit = dosage_instr.get('doseAndRate', [{}])[0].get('doseQuantity', {}).get('unit', '')
        
        reference_result = extract_ref_display(med)        
        item = {}
        item['medication'] = medication
        item['status'] = status
        item['intent'] = intent
        item['dateOn'] = dateOn
        item['validity'] = valid_str
        item['dosage'] = dosage_text
        item['dosage_timing'] = dosage_timing
        item['dosage_quantity'] = f"{dose_quantity_value} {dose_quantity_unit}"
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines

def format_medication_dispenses(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        med = entry.get('resource', {})               
        status = med.get('status', 'unknown')
        medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display', {}) or 'Unknown Medication'        
        if medication == 'Unknown Medication':
            medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('code', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationReference', {}).get('reference') or 'Unknown Medication'
        
        dosage_instr = med.get('dosageInstruction', [{}])[0]
        dosage_text =  dosage_instr.get('route', {}).get('coding', [{}])[0].get('code', '')
        dosage_timing = dosage_instr.get('timing', {}).get('code', {}).get('coding', [{}])[0].get('code', '')
        reference_result = extract_ref_display(med)        
        item = {}
        item['medication'] = medication
        item['status'] = status        
        item['dosage'] = dosage_text
        item['dosage_timing'] = dosage_timing      
        apply_reference_info(item, reference_result)  
        lines.append(item)

    return lines

def format_medication_administrations(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        med = entry.get('resource', {})               
        status = med.get('status', 'unknown')
        category = med.get('category', {}).get('coding', [{}])[0].get('code', {}) or 'Unknown Category'                
        medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('code', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationReference', {}).get('reference') or 'Unknown Medication'
        
        dosage_instr = med.get('dosage', {})
        dosage_method = ''
        dosage_dose = ''
        dosage_rate = ''
        
        if dosage_instr != {}:
            dosage_method = dosage_instr.get('method', {}).get('coding', [{}])[0].get('code', '')
            dosage_dose = str(dosage_instr.get('dose', {}).get('value', '')) + ' ' + dosage_instr.get('dose', {}).get('unit', '')
            dosage_rate = str(dosage_instr.get('rateQuantity', {}).get('value', '')) + ' ' + dosage_instr.get('rateQuantity', {}).get('unit', '')
        
        valid_start = med.get('effectivePeriod', {}).get('start', '')
        valid_end = med.get('effectivePeriod', {}).get('end', '')

        valid_str = ''
        if valid_start != '' and valid_end != '':
            valid_str = f"{convert_fhir_to_local_str(valid_start)} to {convert_fhir_to_local_str(valid_end)}"
        elif valid_start != '':
            valid_str = f"From {convert_fhir_to_local_str(valid_start)}"
            
        reference_result = extract_ref_display(med)   
        item = {}
        item['medication'] = medication
        item['status'] = status        
        item['category'] = category
        item['dosage_method'] = dosage_method
        item['dosage_dose'] = dosage_dose        
        item['dosage_rate'] = dosage_rate        
        item['effective_period'] = valid_str
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines

def format_medication_info(input: Dict[str, Any]) -> str:

    result_value = 'Unknown Medication'
    identifier_list = input.get('identifier', [{}])
    for identifier in identifier_list:
        current_system = identifier.get('system', '')
        current_value = identifier.get('value', '')
        if current_system.endswith('medication-name'):
            result_value = current_value
            break
        if current_system.endswith('medication-mix'):
            result_value = current_value
            
    return result_value

def format_medication_statement(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        med = entry.get('resource', {})               
        status = med.get('status', 'unknown')
        
        medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('display', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationCodeableConcept', {}).get('coding', [{}])[0].get('code', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationReference', {}).get('reference') or 'Unknown Medication'
        
        dosage = med.get('dosage', [{}])[0].get('text', '')
        
        valid_start = med.get('effectivePeriod', {}).get('start', '')
        valid_end = med.get('effectivePeriod', {}).get('end', '')

        valid_str = ''
        if valid_start != '' and valid_end != '':
            valid_str = f"{convert_fhir_to_local_str(valid_start)} to {convert_fhir_to_local_str(valid_end)}"
        elif valid_start != '':
            valid_str = f"From {convert_fhir_to_local_str(valid_start)}"
              
        reference_result = extract_ref_display(med) 
        item = {}
        item['medication'] = medication
        item['status'] = status                
        item['dosage'] = dosage        
        item['effective_period'] = valid_str
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines

def format_diagnostic_reports(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        med = entry.get('resource', {})               
        status = med.get('status', '')
        category = med.get('category', [{}])[0].get('coding', [{}])[0].get('display', '')
        if category == '':
            category = med.get('category', [{}])[0].get('coding', [{}])[0].get('code', '')
        issued_date = med.get('issued', '')
        if issued_date != '':
            issued_date = convert_fhir_to_local_str(issued_date)                
        code = med.get('code', {}).get('text', '')
        if code == '':
            code = med.get('code', {}).get('coding', [{}])[0].get('display', '')
        conclusion = med.get('conclusion', '')
        reference_result = extract_ref_display(med) 
        item = {}
        item['status'] = status                
        item['category'] = category        
        item['issued_date'] = issued_date
        item['code'] = code
        item['conclusion'] = conclusion        
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines

def format_document_references(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        doc = entry.get('resource', {})               
        status = doc.get('status', '')
        doc_type = doc.get('type', {}).get('coding', [{}])[0].get('display', '')   
        if doc_type == '':
            doc_type = doc.get('type', {}).get('coding', [{}])[0].get('code', '')     
        category = doc.get('category', [{}])[0].get('coding', [{}])[0].get('display', '')
        if category == '':
            category = doc.get('category', [{}])[0].get('coding', [{}])[0].get('code', '')
            
        date = doc.get('date', '')
        if date != '':
            date = convert_fhir_to_local_str(date)         
                   
        title = doc.get('description', '')        
        author = doc.get('author', [{}])[0].get('display', '')
        
        content = doc.get('content', [{}])[0].get('attachment', {})
        content_title = content.get('title', '')
        content_url = content.get('url', '')
        content_type = content.get('contentType', '')
        content_str = ''
        if content != {}:
            content_str = f"Title: {content_title}, URL: {content_url}, Type: {content_type}"
        
        reference_result = extract_ref_display(doc) 
        item = {}
        item['status'] = status                
        item['type'] = doc_type        
        item['date'] = date
        item['title'] = title         
        item['author'] = author       
        item['content'] = content_str
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines

def format_allergy_intolerances(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        allergy = entry.get('resource', {})               
        clinical_status = allergy.get('clinicalStatus', {}).get('coding', [{}])[0].get('display', '')
        if clinical_status == '':
            clinical_status = allergy.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', '')
        
        verification_status = allergy.get('verificationStatus', {}).get('coding', [{}])[0].get('display', '')
        if verification_status == '':
            verification_status = allergy.get('verificationStatus', {}).get('coding', [{}])[0].get('code', '')
            
        allergy_type = allergy.get('type', '')
        
        category_list = allergy.get('category', [])
        category_str = ', '.join(category_list) if category_list else ''
        
        criticality = allergy.get('criticality', '')
        
        code_list = allergy.get('code', {}).get('coding', [])
        code_str = ''
        for code in code_list:
            current_code = code.get('display', '')
            if current_code == '':
                current_code = code.get('code', '')
            if current_code != '':
                if code_str != '':
                    code_str += ', '
                code_str += current_code
        
        substance = allergy.get('code', {}).get('text', '')        
        note = allergy.get('note', [{}])[0].get('text', '')
        
        onset_date = ''
        if allergy.get('onsetDateTime'):
            onset_date = convert_fhir_to_local_str(allergy['onsetDateTime'])
        recorded_date = allergy.get('recordedDate', '')
        if recorded_date != '':
            recorded_date = convert_fhir_to_local_str(recorded_date)
            
        
        reference_result = extract_ref_display(allergy) 
        item = {}
        item['clinical_status'] = clinical_status                
        item['verification_status'] = verification_status        
        item['type'] = allergy_type
        item['category'] = category_str        
        item['criticality'] = criticality        
        item['substance'] = substance
        item['code'] = code_str
        item['onset_date'] = onset_date
        item['recorded_date'] = recorded_date
        item['note'] = note
        
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines

def format_family_member_history(bundle: Dict[str, Any]) -> list:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return []

    lines = []
    for entry in entries:
        family_members = entry.get('resource', {})               
        status = family_members.get('status', '')
        relationship = family_members.get('relationship', {}).get('coding', [{}])[0].get('display', '')   
        if relationship == '':
            relationship = family_members.get('relationship', {}).get('coding', [{}])[0].get('code', '')
        sex = family_members.get('sex', {}).get('coding', [{}])[0].get('display', '')
        if sex == '':
            sex = family_members.get('sex', {}).get('coding', [{}])[0].get('code', '')
        name = family_members.get('name', '')
        deceased_str = 'Unknown'
        deceasedBoolean = family_members.get('deceasedBoolean', None)
        if deceasedBoolean is not None:
            if deceasedBoolean:
                deceased_str = 'Deceased'
            else:
                deceased_str = 'Living'
        condition_list = family_members.get('condition', [])
        conditions_str = ''
        for condition in condition_list:
            current_condition = condition.get('code', {}).get('text', '')
            if current_condition != '':    
                current_condition += ', '
            current_condition += condition.get('code', {}).get('coding', [{}])[0].get('display', '')
            if conditions_str != '':
                conditions_str += '; '
            conditions_str += current_condition
            
        reference_result = extract_ref_display(family_members) 
        item = {}
        item['status'] = status
        item['relationship'] = relationship
        item['name'] = name
        item['sex'] = sex
        item['deceased'] = deceased_str
        item['conditions'] = conditions_str
        
        apply_reference_info(item, reference_result)
        lines.append(item)

    return lines