from typing import Any, Dict, List, Optional, Union

def format_patient_search_results(bundle: Dict[str, Any]) -> str:
    # bundle?.entry?.length 체크
    entries = bundle.get('entry') if bundle else None
    if not entries:
        return "No patients found matching search criteria"

    results = []
    for entry in entries:
        # entry?.resource 체크
        patient = entry.get('resource')
        if not patient:
            continue

        # Safe navigation logic
        name_list = patient.get('name', [{}])
        name = name_list[0] if name_list else {}
        
        address_list = patient.get('address', [{}])
        address = address_list[0] if address_list else {}

        # Phone lookup logic
        telecoms = patient.get('telecom', [])
        phone = 'Not provided'
        # find((t: Telecom) => t.system === 'phone') logic
        for t in telecoms:
            if t.get('system') == 'phone':
                phone = t.get('value', 'Not provided')
                break

        given_name = ' '.join(name.get('given', [])) if name.get('given') else 'Unknown'
        
        patient_info = (
            f"Patient ID: {patient.get('id', 'Unknown')}\n"
            f"                Name: {name.get('family', 'Unknown')}, {given_name}\n"
            f"                DOB: {patient.get('birthDate', 'Unknown')}\n"
            f"                Gender: {patient.get('gender', 'Unknown')}\n"
            f"                Address: {format_address(address)}\n"
            f"                Phone: {phone}\n"
            f"                -----------------"
        )
        results.append(patient_info)

    # filter(Boolean) -> 빈 문자열 제거 및 join
    return '\n\n'.join([res for res in results if res])


def format_vital_signs(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry') if bundle else None
    if not entries:
        return "No vital signs recorded"

    # Map<string, Map<string, any>> 구조 대응
    vitals_by_date: Dict[str, Dict[str, Any]] = {}

    for entry in entries:
        vital = entry.get('resource')
        if not vital:
            continue

        effective_date = vital.get('effectiveDateTime')
        date = effective_date.split('T')[0] if effective_date else 'unknown date'

        if date not in vitals_by_date:
            vitals_by_date[date] = {}

        # code?.coding?.[0]?.display ?? code?.text ?? 'Unknown'
        coding = vital.get('code', {}).get('coding', [{}])[0]
        vital_type = coding.get('display') or vital.get('code', {}).get('text') or 'Unknown'

        # valueQuantity logic
        val_q = vital.get('valueQuantity')
        if val_q and val_q.get('value') is not None:
            unit = val_q.get('unit', '')
            value = f"{val_q.get('value')} {unit}"
        else:
            value = 'No value'

        vitals_by_date[date][vital_type] = value

    return _format_date_grouped_data(vitals_by_date, "vital signs")


def format_lab_results(bundle: Dict[str, Any]) -> str:
    entries = bundle.get('entry') if bundle else None
    if not entries:
        return "No lab results found"

    labs_by_panel: Dict[str, List[Dict[str, Any]]] = {}

    for entry in entries:
        lab = entry.get('resource')
        if not lab:
            continue

        # lab.code?.coding?.[0]?.display ?? 'Other'
        coding = lab.get('code', {}).get('coding', [{}])[0]
        panel = coding.get('display') or 'Other'

        if panel not in labs_by_panel:
            labs_by_panel[panel] = []

        effective_date = lab.get('effectiveDateTime')
        date = effective_date.split('T')[0] if effective_date else 'unknown date'
        
        val_q = lab.get('valueQuantity', {})
        
        # referenceRange?.[0]
        ref_ranges = lab.get('referenceRange', [])
        reference = ref_ranges[0] if ref_ranges else None
        
        # interpretation?.[0]?.coding?.[0]?.code
        interp_list = lab.get('interpretation', [{}])
        interp_coding = interp_list[0].get('coding', [{}])[0] if interp_list else {}
        interpretation = interp_coding.get('code')

        labs_by_panel[panel].append({
            "date": date,
            "value": val_q.get('value', 'No value'),
            "unit": val_q.get('unit', ''),
            "reference": reference,
            "interpretation": interpretation
        })

    return _format_panel_grouped_data(labs_by_panel, "lab results")


# Helper functions for common formatting patterns (Internal use)
def _format_date_grouped_data(data_map: Dict[str, Dict[str, Any]], data_type: str) -> str:
    if not data_map:
        return f"No {data_type} to display"

    # sort keys desc (b.localeCompare(a))
    sorted_dates = sorted(data_map.keys(), reverse=True)
    
    formatted_groups = []
    for date in sorted_dates:
        items = data_map[date]
        # items entry -> string
        item_lines = []
        for type_name, value in items.items():
            item_lines.append(f"  {type_name}: {value}")
        
        items_str = '\n'.join(item_lines)
        if items_str:
            formatted_groups.append(f"Date: {date}\n{items_str}")

    return '\n\n'.join(formatted_groups)


def _format_panel_grouped_data(data_map: Dict[str, List[Dict[str, Any]]], data_type: str) -> str:
    if not data_map:
        return f"No {data_type} to display"

    formatted_panels = []
    for panel, items in data_map.items():
        if not items:
            continue
            
        # Sort items by date descending
        # (b.date ?? '').localeCompare(a.date ?? '')
        sorted_items = sorted(items, key=lambda x: x.get('date', ''), reverse=True)
        
        item_lines = []
        for item in sorted_items:
            if not item:
                continue
            line = f"  {item['date']}: {item['value']} {item['unit']}"
            item_lines.append(line)
        
        items_str = '\n'.join(item_lines)
        if items_str:
            formatted_panels.append(f"{panel}:\n{items_str}")

    return '\n\n'.join(formatted_panels)


# Utility functions with null checks
def calculate_trend(current: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    # current?.value check
    if not current or current.get('value') is None:
        return ''
    
    # history?.[1]?.value check
    if not history or len(history) < 2 or history[1].get('value') is None:
        return ''

    try:
        current_value = float(current['value'])
        previous_value = float(history[1]['value'])
    except (ValueError, TypeError):
        return ''

    if current_value == previous_value: return '→'
    if current_value > previous_value: return '↑'
    return '↓'


def format_interpretation(result: Dict[str, Any]) -> str:
    # !result?.value || !result?.reference check
    if not result or result.get('value') is None or not result.get('reference'):
        return ''

    try:
        value = float(result['value'])
        ref = result['reference']
        
        # Safe access to nested low/high
        low_val = ref.get('low', {}).get('value')
        high_val = ref.get('high', {}).get('value')
        
        low = float(low_val) if low_val is not None else None
        high = float(high_val) if high_val is not None else None
        
        if low is not None and value < low:
            return '⚠️ Below range'
        if high is not None and value > high:
            return '⚠️ Above range'
        
        return '✓ Normal'
    except (ValueError, TypeError):
        return ''


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
    
    # filter(Boolean) equivalent
    clean_parts = [p for p in parts if p]
    
    return ', '.join(clean_parts) if clean_parts else 'Not provided'