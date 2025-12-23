import re
from datetime import datetime
from typing import Any, List, Dict, Optional, Union

def extract_ref_display(data):
    results = []

    # 1. 데이터가 딕셔너리인 경우
    if isinstance(data, dict):
        # 원하는 키("reference")가 있는지 확인
        if "reference" in data :
            reference_split = data["reference"].split("/")
            if len(reference_split) == 2:                
                current_result = {
                    "display": data.get("display", ""),
                    "resourceType": data["reference"].split("/")[0],
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
        for current_reference in reference_result:
            current_result[f"RefDisplay_{current_reference['resourceType']}"] = current_reference['display']                        
            current_result[f"RefID_{current_reference['resourceType']}"] = current_reference['id'] 
        results.append(current_result)

    return results


def format_vital_signs(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No vital signs recorded for the specified period"

    # Group vitals by date
    vitals_by_date: Dict[str, Dict[str, str]] = {}

    for entry in entries:
        vital = entry.get('resource', {})
        effective_date_time = vital.get('effectiveDateTime', '')
        date = effective_date_time.split('T')[0] if effective_date_time else 'unknown'

        if date not in vitals_by_date:
            vitals_by_date[date] = {}

        coding = vital.get('code', {}).get('coding', [{}])[0]
        vital_type = coding.get('display') or vital.get('code', {}).get('text')
        
        value_quantity = vital.get('valueQuantity', {})
        value = f"{value_quantity.get('value')} {value_quantity.get('unit')}"
        
        vitals_by_date[date][vital_type] = value

    # Format output
    # Sort by date descending
    sorted_dates = sorted(vitals_by_date.keys(), reverse=True)
    
    output_lines = []
    for date in sorted_dates:
        vitals = vitals_by_date[date]
        vitals_str = '\n'.join([f"  {t}: {v}" for t, v in vitals.items()])
        output_lines.append(f"Date: {date}\n{vitals_str}")

    return '\n\n'.join(output_lines)


def format_lab_results(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No lab results found for the specified criteria"

    # Group labs by panel/category
    labs_by_panel: Dict[str, List[Dict[str, Any]]] = {}

    for entry in entries:
        lab = entry.get('resource', {})
        coding = lab.get('code', {}).get('coding', [{}])[0]
        panel = coding.get('display') or 'Other'

        if panel not in labs_by_panel:
            labs_by_panel[panel] = []

        interp = lab.get('interpretation', [{}])[0].get('coding', [{}])[0].get('code')
        
        labs_by_panel[panel].append({
            'date': lab.get('effectiveDateTime', '').split('T')[0],
            'value': lab.get('valueQuantity', {}).get('value'),
            'unit': lab.get('valueQuantity', {}).get('unit'),
            'reference': lab.get('referenceRange', [None])[0],
            'interpretation': interp
        })

    # Format output with trending indicators
    final_output = []
    for panel, results in labs_by_panel.items():
        # Sort results by date descending
        sorted_results = sorted(results, key=lambda x: x['date'], reverse=True)
        
        results_str_list = []
        for result in sorted_results:
            trend = calculate_trend(result, sorted_results)
            interpretation = format_interpretation(result)
            line = f"  {result['date']}: {result['value']} {result['unit']} {interpretation} {trend}"
            results_str_list.append(line)
        
        results_str = '\n'.join(results_str_list)
        final_output.append(f"{panel}:\n{results_str}")

    return '\n\n'.join(final_output)


def format_care_plans(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No care plans found"
    
    output = []
    for entry in entries:
        care_plan = entry.get('resource', {})
        
        category_list = care_plan.get('category', [{}])
        category_coding = category_list[0].get('coding', [{}])[0] if category_list else {}
        category = category_coding.get('display') or category_list[0].get('text') or 'Unknown'

        period = care_plan.get('period', {})
        start_date = period.get('start', '').split('T')[0] or 'unknown date'
        end_date = period.get('end', '').split('T')[0] or 'unknown date'
        
        activities_str = []
        for activity in care_plan.get('activity', []):
            detail = activity.get('detail', {})
            code = detail.get('code', {})
            code_text = code.get('text') or code.get('coding', [{}])[0].get('display') or 'No details provided'
            
            location = detail.get('location', {})
            loc_display = location.get('display') or location.get('text') or 'No location provided'
            
            performer = detail.get('performer', [{}]) # detail.performer can be list or dict in some implementations, usually list in FHIR R4 but TS code treated as single or list? TS code: detail?.performer?.display. Assuming single or checking safe access
            # Re-checking TS: activity.detail?.performer?.display. In FHIR 'performer' is list usually.
            # We'll treat it safely.
            if isinstance(performer, list):
                performer_display = performer[0].get('display') if performer else 'No performer provided'
            elif isinstance(performer, dict):
                 performer_display = performer.get('display') or performer.get('reference') or 'No performer provided'
            else:
                 performer_display = 'No performer provided'

            act_str = (
                f"            - Activity: {code_text}\n"
                f"            - Status: {detail.get('status', 'unknown status')}\n"
                f"            - Location: {loc_display}\n"
                f"            - Performer: {performer_display}"
            )
            activities_str.append(act_str)

        activities_joined = '\n'.join(activities_str)
        
        plan_str = (
            f"\n        - Category: {category}\n"
            f"        - Start Date: {start_date}\n"
            f"        - End Date: {end_date}\n"
            f"        - Status: {care_plan.get('status')}\n"
            f"        - Details: \n"
            f"{activities_joined}\n"
            f"        "
        )
        output.append(plan_str)

    return '\n'.join(output)


def format_immunizations(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No immunizations found"

    output = []
    for entry in entries:
        immunization = entry.get('resource', {})
        vaccine_display = immunization.get('vaccineCode', {}).get('coding', [{}])[0].get('display') or 'Unknown vaccine'
        date = immunization.get('occurrenceDateTime', '').split('T')[0] or 'unknown date'
        
        item = (
            f"\n      \n"
            f"        - {vaccine_display}\n"
            f"        - {date}\n"
            f"        - {immunization.get('status')}\n"
            f"        "
        )
        output.append(item)
    
    return '\n'.join(output)


def format_procedures(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No procedures found"

    output = []
    for entry in entries:
        procedure = entry.get('resource', {})
        proc_display = procedure.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown procedure'
        category = procedure.get('category', {}).get('coding', [{}])[0].get('code') or 'Unknown category'
        period = procedure.get('performedPeriod', {})
        start = period.get('start', '').split('T')[0] or 'unknown date'
        start_time = period.get('start', '').split('T')[-1] or ''
        end = period.get('end', '').split('T')[0] or 'unknown date'
        end_time = period.get('end', '').split('T')[-1] or ''
        
        item = (
            f"\n        - {proc_display}\n"
            f"        - Start: {start}:{start_time}\n"
            f"        - End: {end}:{end_time}\n"
            f"        - Status: {procedure.get('status')}\n"
            f"        - Category: {category}\n"            
            f"        "
        )
        output.append(item)

    return '\n'.join(output)


def format_encounters(bundle: Dict[str, Any]):
    output = []
    
    entries = bundle.get('entry', [])
    if not entries:
        return output

    for entry in entries:
        encounter = entry.get('resource', {})
        start = encounter.get('period', {}).get('start', '').split('T')[0] or 'unknown date'
        start_time = encounter.get('period', {}).get('start', '').split('T')[-1] or ''
        end = encounter.get('period', {}).get('end', '').split('T')[0] or 'unknown date'
        end_time = encounter.get('period', {}).get('end', '').split('T')[-1] or ''
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
        current_result['start_time'] = f"{start}:{start_time}"
        current_result['end_time'] = f"{end}:{end_time}"        
        current_result['type'] = type_display
        current_result['reason'] = reason_display
        current_result['status'] = encounter.get('status')
        current_result['class'] = class_display
        
        for current_reference in reference_result:
            current_result[f"RefDisplay_{current_reference['resourceType']}"] = current_reference['display']                        
            current_result[f"RefID_{current_reference['resourceType']}"] = current_reference['id']
        output.append(current_result)
        
    return output


def format_appointments(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No appointments found"

    output = []
    for entry in entries:
        appointment = entry.get('resource', {})
        
        type_list = appointment.get('appointmentType', [{}])
        # In FHIR R4 appointmentType is CodeableConcept (not list), but TS code treats as list (R3 or custom). 
        # Adapting to TS code logic: appointment.appointmentType?.[0]...
        # If it's a dict in Python data, [0] will fail. Let's assume list as per TS.
        # However, safely handling if it's a dict is better.
        app_type = appointment.get('appointmentType')
        if isinstance(app_type, dict): app_type = [app_type]
        elif not isinstance(app_type, list): app_type = [{}]
        
        type_display = app_type[0].get('coding', [{}])[0].get('display') or app_type[0].get('text') or 'Unknown appointment type'

        reason_ref = appointment.get('reasonReference', [{}])
        reason_display = reason_ref[0].get('display') or reason_ref[0].get('reference') or 'Unknown reason for appointment'
        
        start = appointment.get('start', '').split('T')[0] or 'unknown date'
        end = appointment.get('end', '').split('T')[0] or 'unknown date'

        item = (
            f"- {appointment.get('status')}\n"
            f"              - {type_display}\n"
            f"              - {reason_display}\n"
            f"              - {start}\n"
            f"              - {end}\n"
            f"              "
        )
        output.append(item)

    return '\n'.join(output)


# New Analysis Features

def calculate_trend(current: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    if len(history) < 2:
        return ''
    
    # Assuming history is sorted descending, history[0] is current, history[1] is previous
    current_value = current.get('value')
    # history includes current result, so we look at index 1 for previous
    previous_value = history[1].get('value')

    # Basic comparison handling (assuming numbers)
    try:
        if current_value == previous_value: return '→'
        if current_value > previous_value: return '↑'
        return '↓'
    except:
        return ''


def format_interpretation(result: Dict[str, Any]) -> str:
    ref = result.get('reference')
    value = result.get('value')
    
    if not ref or value is None:
        return ''
    
    low = ref.get('low', {}).get('value')
    high = ref.get('high', {}).get('value')
    
    try:
        if low is not None and value < low: return '⚠️ Below range'
        if high is not None and value > high: return '⚠️ Above range'
        return '✓ Normal'
    except:
        return ''


def map_category_to_loinc(category: str) -> Optional[str]:
    loinc_map = {
        'CBC': '58410-2',
        'METABOLIC': '24323-8',
        'LIPIDS': '57698-3',
        'THYROID': '83937-0',
        'URINALYSIS': '24356-8'
        # Add more mappings as needed
    }
    return loinc_map.get(category.upper())


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


def format_preventive_procedures(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No preventive procedures recorded"

    lines = []
    for entry in entries:
        proc = entry.get('resource', {})
        display = proc.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown procedure'
        date = proc.get('performedDateTime', '').split('T')[0] or 'unknown date'
        lines.append(f"- {display} ({date})")

    return '\n'.join(lines)


def format_recent_health_metrics(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No recent health metrics available"

    metrics: Dict[str, Dict[str, str]] = {}

    for entry in entries:
        obs = entry.get('resource', {})
        obs_type = obs.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown'
        obs_category = obs.get('category', [{}])[0].get('coding',[{}])[0].get('code') or 'Unknown'
        if obs_type not in metrics:
            val_q = obs.get('valueQuantity', {})
            value_str = f"{val_q.get('value', 'No value')} {val_q.get('unit', '')}"
            date_str = obs.get('effectiveDateTime', '').split('T')[0] or 'unknown date'
            
            metrics[obs_type] = {
                'category': obs_category,
                'status': obs.get('status', 'unknown'),
                'value': value_str,
                'date': date_str
            }

    output = []
    for type_name, data in metrics.items():
        output.append(f"[{data['category']}] {type_name}: {data['value']} ({data['date']}), status = {data['status']}")

    return '\n'.join(output)


def format_chronic_conditions(conditions: List[Dict[str, Any]]) -> str:
    # Accepts list of entries
    if not conditions:
        return "No chronic conditions documented"

    lines = []
    for entry in conditions:
        condition = entry.get('resource', {})
        display = condition.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown condition'
        onset = condition.get('onsetDateTime', '').split('T')[0] or 'unknown'
        
        status_code = condition.get('clinicalStatus', {}).get('coding', [{}])[0].get('code')
        status_suffix = ' - Active' if status_code == 'active' else ''
        
        lines.append(f"- {display} (onset: {onset}){status_suffix}")

    return '\n'.join(lines)


def format_disease_metrics(observations: Dict[str, Any], conditions: List[Dict[str, Any]]) -> str:
    obs_entries = observations.get('entry')
    if not obs_entries or not conditions:
        return "No disease-specific metrics available"

    disease_metrics: Dict[str, List[str]] = {}

    for entry in conditions:
        condition = entry.get('resource', {})
        metrics = get_relevant_metrics(obs_entries, condition)
        
        if metrics:
            condition_name = condition.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown condition'
            disease_metrics[condition_name] = metrics

    output = []
    for condition_name, metric_list in disease_metrics.items():
        metrics_str = '\n'.join([f"  - {m}" for m in metric_list])
        output.append(f"{condition_name}:\n{metrics_str}")

    return '\n\n'.join(output)


def get_relevant_metrics(observations: List[Dict[str, Any]], condition: Dict[str, Any]) -> List[str]:
    # Map conditions to relevant LOINC codes
    metric_map = {
        'Diabetes': ['4548-4', '17856-6'], # HbA1c, Glucose
        'Hypertension': ['8480-6', '8462-4'], # Systolic BP, Diastolic BP
        'Hyperlipidemia': ['2093-3', '2571-8'], # Cholesterol, Triglycerides
    }

    condition_coding = condition.get('code', {}).get('coding', [{}])[0]
    condition_name = condition_coding.get('display', '')
    relevant_codes = metric_map.get(condition_name, [])

    results = []
    for obs in observations:
        resource = obs.get('resource', {})
        obs_code = resource.get('code', {}).get('coding', [{}])[0].get('code')
        
        if obs_code in relevant_codes:
            val_q = resource.get('valueQuantity', {})
            value = val_q.get('value', 'No value')
            unit = val_q.get('unit', '')
            date = resource.get('effectiveDateTime', '').split('T')[0] or 'unknown date'
            name = resource.get('code', {}).get('coding', [{}])[0].get('display') or 'Unknown metric'
            
            results.append(f"{name}: {value} {unit} ({date})")
            
    return results


def format_care_team(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', [])
    if not entries:
        return "No care team members documented"

    lines = []
    for entry in entries:
        role = entry.get('resource', {})
        practitioner = role.get('practitioner', {}).get('display', 'Unknown provider')
        specialty = role.get('specialty', [{}])[0].get('coding', [{}])[0].get('display') or 'Unknown specialty'
        contact = role.get('telecom', [{}])[0].get('value', 'Not provided')
        
        lines.append(f"- {practitioner} ({specialty})\n  Contact: {contact}")

    return '\n'.join(lines)


def calculate_age(birth_date_str: str) -> int:
    today = datetime.now()
    try:
        birth = datetime.strptime(birth_date_str, "%Y-%m-%d")
    except ValueError:
        return 0 # Or handle error appropriately
        
    age = today.year - birth.year
    # Adjust if birthday hasn't happened yet this year
    if (today.month, today.day) < (birth.month, birth.day):
        age -= 1
    return age


def format_conditions(bundle: Dict[str, Any]) -> str:
    # Supports both Bundle (dict with entry) or List of entries if passed directly
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return "No active conditions"

    lines = []
    for entry in entries:
        condition = entry.get('resource', {})
        coding = condition.get('code', {}).get('coding', [{}])[0]
        name = coding.get('display') or condition.get('code', {}).get('text') or 'Unknown Condition'
        code = coding.get('code', 'Unknown')
        system = coding.get('system', 'Unknown')
        category = condition.get('category', [{}])[0].get('coding', [{}])[0].get('code') or 'Unknown Category'
        onset_str = ''
        if condition.get('onsetDateTime'):
            onset_str = f" (onset: {condition['onsetDateTime'].split('T')[0]})"
            
        # item = (
        #     f"\n          - Name: {name}\n"
        #     f"          - Category: {category}\n"
        #     f"          - Code: {code}\n"
        #     f"          - System: {system}\n"
        #     f"          - OnSet Date:{onset_str}\n"
        #     f"          - Status: {condition.get('status')}\n"
        #     f"          "
        # )
        item = f"[{category}] {code}: {name} {onset_str}, status = {condition.get('status', 'unknown')}"
        
        lines.append(item)

    return '\n'.join(lines)

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
        dateOn = med.get('authoredOn', '').split('T')[0] or 'unknown date'
        valid_start = med.get('dispenseRequest', {}).get('validityPeriod', {}).get('start', '').split('T')[0] or 'unknown'
        valid_end = med.get('dispenseRequest', {}).get('validityPeriod', {}).get('end', '').split('T')[0] or 'unknown'
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
                
        item = {}
        item['medication'] = medication
        item['status'] = status
        item['intent'] = intent
        item['dateOn'] = dateOn
        item['validity'] = f"{valid_start} to {valid_end}"
        item['dosage'] = dosage_text
        item['dosage_timing'] = dosage_timing
        item['dosage_quantity'] = f"{dose_quantity_value} {dose_quantity_unit}"
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
                
        item = {}
        item['medication'] = medication
        item['status'] = status        
        item['dosage'] = dosage_text
        item['dosage_timing'] = dosage_timing        
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
                
        item = {}
        item['medication'] = medication
        item['status'] = status        
        item['category'] = category
        item['dosage_method'] = dosage_method
        item['dosage_dose'] = dosage_dose        
        item['dosage_rate'] = dosage_rate        
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
        
        medication = med.get('medicationCodeableConcept', {}).get('text', {}) or 'Unknown Medication'
        if medication == 'Unknown Medication':
            medication = med.get('medicationReference', {}).get('reference') or 'Unknown Medication'
        
        dosage = med.get('dosage', [{}])[0].get('text', '')
                
        item = {}
        item['medication'] = medication
        item['status'] = status                
        item['dosage'] = dosage        
        lines.append(item)

    return lines

def format_allergies(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry', []) if isinstance(bundle, dict) else bundle
    if not entries:
        return "No known allergies"

    lines = []
    for entry in entries:
        allergy = entry.get('resource', {})
        code_obj = allergy.get('code', {})
        name = code_obj.get('coding', [{}])[0].get('display') or code_obj.get('text') or 'Unknown Allergen'
        
        item = (
            f"\n          - {name} \n"
            f"          - {allergy.get('type', 'unknown type')}, {allergy.get('criticality', 'unknown criticality')}\n"
            f"          "
        )
        lines.append(item)

    return '\n'.join(lines)


def format_patient_summary(data: Dict[str, Any]) -> str:
    patient = data.get('patient')
    if not patient:
        return "No patient data available"

    name_obj = patient.get('name', [{}])[0]
    name_family = name_obj.get('family', 'Unknown')
    name_given = ' '.join(name_obj.get('given', [])) or 'Unknown'
    
    birth_date = patient.get('birthDate')
    age = calculate_age(birth_date) if birth_date else 'Unknown'
    
    # Phone lookup
    telecoms = patient.get('telecom', [])
    phone = 'Not provided'
    for t in telecoms:
        if t.get('system') == 'phone':
            phone = t.get('value', 'Not provided')
            break

    # Helper function calls
    # Note: data.get('conditions') returns the list/bundle expected by helper functions
    # Using 'or []' to pass empty list if None
    conditions_str = format_conditions(data.get('conditions') or [])
    medications_str = format_medication_requests(data.get('medications') or [])
    allergies_str = format_allergies(data.get('allergies') or [])
    immunizations_str = format_immunizations(data.get('immunizations') or {})
    procedures_str = format_procedures(data.get('procedures') or {})
    care_plans_str = format_care_plans(data.get('carePlans') or {})
    lab_results_str = format_lab_results(data.get('recentLabs') or {})
    encounters_str = format_encounters(data.get('encounters') or {})
    appointments_str = format_appointments(data.get('appointments') or {})

    return (
        f"\n"
        f"      - Name: {name_family}, {name_given}\n"
        f"      - DOB: {birth_date or 'Unknown'}\n"
        f"      - Gender: {patient.get('gender', 'Unknown')}\n"
        f"      - Address: {format_address(patient.get('address', [{}])[0])}\n"
        f"      - Phone: {phone}\n"
        f"      - Age: {age}\n"
        f"      - Conditions: {conditions_str}\n"
        f"      - Medications: {medications_str}\n"
        f"      - Allergies: {allergies_str}\n"
        f"      - Immunizations: {immunizations_str}\n"
        f"      - Procedures: {procedures_str}\n"
        f"      - Care Plans: {care_plans_str}\n"
        f"      - Lab Results: {lab_results_str}\n"
        f"      - Encounters: {encounters_str}\n"
        f"      - Appointments: {appointments_str}\n"
        f"    "
    )