from typing import Any, Dict
from . import helper

def build_patient_summary_prompt(data: Dict[str, Any]) -> str:
    patient = data.get('patient', {})
    name_list = patient.get('name', [{}])
    name = name_list[0] if name_list else {}
    
    family_name = name.get('family', '')
    given_name = ' '.join(name.get('given', []))

    return f"""Please provide a comprehensive health summary for:
            Patient: {family_name}, {given_name}
            DOB: {patient.get('birthDate', 'Unknown')}
            Gender: {patient.get('gender', 'Unknown')}
            
            Current Conditions:
            {helper.format_conditions(data.get('conditions'))}
            
            Active Medications:
            {helper.format_medication_requests(data.get('medications'))}
            
            Allergies:
            {helper.format_allergies(data.get('allergies'))}
            
            Recent Lab Results:
            {helper.format_lab_results(data.get('recentLabs'))}
            
            Immunizations:
            {helper.format_immunizations(data.get('immunizations'))}
            
            Procedures:
            {helper.format_procedures(data.get('procedures'))}
            
            Care Plans:
            {helper.format_care_plans(data.get('carePlans'))}
            
            Encounters:
            {helper.format_encounters(data.get('encounters'))}
            
            Appointments:
            {helper.format_appointments(data.get('appointments'))}
            
            Please analyze this information and provide:
            1. A summary of the patient's current health status
            2. Key health concerns that should be addressed
            3. Any patterns or trends that should be monitored
            4. Recommendations for follow-up care"""

def build_medication_review_prompt(data: Dict[str, Any]) -> str:
    return f"""Please review the following medication regimen:
  
            Current Medications:
            {helper.format_medication_requests(data.get('medications'))}
            
            Patient Allergies:
            {helper.format_allergies(data.get('allergies'))}
            
            Active Conditions:
            {helper.format_conditions(data.get('conditions'))}
            
            Please analyze for:
            1. Potential drug interactions
            2. Contraindications with current conditions
            3. Possible adverse reactions based on allergies
            4. Opportunities for regimen optimization
            5. Any medications that may need monitoring or adjustment"""

def build_condition_timeline_prompt(data: Dict[str, Any]) -> str:
    # TS코드에서 data 자체를 넘겼으므로 동일하게 처리
    return f"""Please analyze this patient's condition timeline:

            Conditions History:
            {helper.format_conditions(data)}
            
            Please provide:
            1. A chronological analysis of how conditions have developed
            2. Any patterns or relationships between conditions
            3. Key milestones or significant changes in health status
            4. Recommendations for ongoing monitoring
            5. Potential preventive measures based on condition progression"""

def build_lab_trend_analysis_prompt(data: Dict[str, Any]) -> str:
    return f"""Please analyze the following laboratory test trends:

            Patient Lab History:
            {helper.format_lab_results(data.get('labResults'))}
            
            Related Conditions:
            {helper.format_conditions(data.get('conditions'))}
            
            Current Medications:
            {helper.format_medication_requests(data.get('medications'))}
            
            Please provide:
            1. Analysis of trends and patterns in lab values over time
            2. Identification of any values outside normal ranges
            3. Correlation with current conditions and medications
            4. Potential clinical implications of observed trends
            5. Recommendations for monitoring and follow-up testing"""

def build_care_gaps_prompt(data: Dict[str, Any]) -> str:
    return f"""Please analyze the following patient's care gaps:

            Patient Summary:
            {helper.format_patient_summary(data)}
            
            Please provide:
            1. A list of care gaps identified in the patient's record
            2. Potential reasons for these gaps
            3. Recommendations for addressing these gaps
            4. Any additional information that would be helpful in understanding the patient's care history"""

def build_preventive_care_review_prompt(data: Dict[str, Any]) -> str:
    return f"""Please analyze the following patient's preventive care:

            Patient Summary:
            {helper.format_patient_summary(data)}
            
            Please provide:
            1. A list of preventive care measures identified in the patient's record
            2. Potential reasons for these gaps
            3. Recommendations for addressing these gaps
            4. Any additional information that would be helpful in understanding the patient's care history"""

def build_chronic_disease_management_prompt(data: Dict[str, Any]) -> str:
    return f"""Please analyze the following patient's chronic disease management:

            Patient Summary:
            {helper.format_patient_summary(data)}
            
            Please provide:
            1. A list of chronic disease management measures identified in the patient's record
            2. Potential reasons for these gaps
            3. Recommendations for addressing these gaps
            4. Any additional information that would be helpful in understanding the patient's care history"""

def build_risk_assessment_prompt(data: Dict[str, Any]) -> str:
    return f"""Please analyze the following patient's risk assessment:

            Patient Summary:
            {helper.format_patient_summary(data)}
            
            Please provide:
            1. A list of risk factors identified in the patient's record
            2. Potential reasons for these risks
            3. Recommendations for addressing these risks
            4. Any additional information that would be helpful in understanding the patient's care history"""

def build_care_coordination_prompt(data: Dict[str, Any]) -> str:
    return f"""Please analyze the following patient's care coordination:

            Patient Summary:
            {helper.format_patient_summary(data)}
            
            Please provide:
            1. A list of care coordination measures identified in the patient's record
            2. Potential reasons for these gaps
            3. Recommendations for addressing these gaps
            4. Any additional information that would be helpful in understanding the patient's care history"""