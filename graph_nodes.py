from typing import TypedDict, Dict, Any, List, Set
from utils import combined, combine_causes, safe_rate
from llm import generate_llm_prompt, generate_llm_summary, generate_chef_feedback_prompt, generate_chef_feedback_summary
from config import EXPECTED_THRESHOLD, RATE_THRESHOLD, STATION_MULT, SHIFT_MULT, PEAK_MULT, HOT_TEMP, HOT_MULT, COLD_TEMP, COST_CRITICAL_THRESHOLD, COST_IGNORE_THRESHOLD
import pandas as pd

class AgentState(TypedDict):
    record: Dict[str, Any]
    branch_metrics: Dict[str, Any]
    status: str

def analysis_and_llm_node(state: AgentState) -> AgentState:
    record = state['record']
    metrics = state['branch_metrics']
    
    branch_avg = metrics.get('branch_avg', 0.0)
    nonpeak_rate = metrics.get('nonpeak_rate', 0.0)
    moderate_temp_rate = metrics.get('moderate_temp_rate', 0.0)
    sales_med = metrics.get('sales_med', 0.0)
    station_avg_map: Dict[str, float] = metrics.get('station_avg_map', {})
    shift_avg_map: Dict[str, float] = metrics.get('shift_avg_map', {})
    bad_quality_suppliers_list: List[str] = metrics.get('bad_quality_suppliers_list', [])
    supplier_rotation_history_set: Set[str] = metrics.get('supplier_rotation_history_set', set())
    overall_avg = branch_avg
    
    wastage_qty = record.get("Wastage Qty", 0.0)
    planned_qty = record.get("Planned Qty", 0.0)
    expected_qty = record.get("Expected Waste Qty", 0.0)
    
    record["Waste Rate"] = safe_rate(wastage_qty, planned_qty)
    
    dev_flag = wastage_qty > expected_qty * EXPECTED_THRESHOLD
    record["Waste_Deviation_Flag"] = dev_flag
    
    rate_limit = branch_avg * RATE_THRESHOLD if branch_avg > 0 else 0.0
    hr_flag = record["Waste Rate"] > rate_limit
    record["High_Waste_Flag"] = hr_flag
    
    record["Combined_Flag"] = combined(dev_flag, hr_flag)
    
    expiry_flag = False
    date = record.get("Date")
    expiry_date = record.get("Expiry Date")
    if date and expiry_date and pd.notna(date) and pd.notna(expiry_date):
        try:
            expiry_flag = pd.to_datetime(date).normalize() > pd.to_datetime(expiry_date).normalize()
        except:
            pass
    record["Expiry_Flag"] = expiry_flag
    
    station = record.get("Kitchen Station")
    station_inefficiency = False
    if station and station in station_avg_map:
        station_rate = station_avg_map[station]
        station_inefficiency = station_rate > (overall_avg * STATION_MULT)
    record["Station_Inefficiency"] = station_inefficiency
    
    shift = record.get("Shift")
    shift_issue = False
    if shift and shift in shift_avg_map:
        shift_rate = shift_avg_map[shift]
        shift_issue = shift_rate > (overall_avg * SHIFT_MULT)
    record["Shift_Issue"] = shift_issue
    
    peak_pressure = False
    if record.get("Peak Hour Flag", False) and nonpeak_rate > 0:
        peak_pressure = record["Waste Rate"] > (nonpeak_rate * PEAK_MULT)
    record["Peak_Pressure_Issue"] = peak_pressure
    
    temp = record.get("Temperature (°C)")
    sales_qty = record.get("Sales Qty")
    
    heat_spoilage_flag = False
    if pd.notna(temp) and moderate_temp_rate > 0:
        heat_spoilage_flag = (temp > HOT_TEMP) and (record["Waste Rate"] > (moderate_temp_rate * HOT_MULT))
    record["Heat_Spoilage_Flag"] = heat_spoilage_flag
    
    cold_overprep_flag = False
    if pd.notna(temp) and pd.notna(sales_qty) and sales_med is not None:
        cold_overprep_flag = (temp <= COLD_TEMP) and (sales_qty < sales_med) and (record["Waste Rate"] > overall_avg * 1.3)
    record["Cold_Overprep_Flag"] = cold_overprep_flag
    
    supplier_name = record.get("Supplier Name")
    
    supplier_quality_issue = False
    if supplier_name and supplier_name in bad_quality_suppliers_list:
        supplier_quality_issue = True
    record["Supplier_Quality_Issue"] = supplier_quality_issue
    
    supplier_rotation_issue = False
    if supplier_name and supplier_name in supplier_rotation_history_set:
        if hr_flag:
            supplier_rotation_issue = True
    record["Supplier_Rotation_Issue"] = supplier_rotation_issue
    
    record["Root_Causes"] = combine_causes(record)
    
    record["LLM_Prompt"] = generate_llm_prompt(record, branch_avg)
    
    if record["LLM_Prompt"]:
        record["LLM_Summary"] = generate_llm_summary(record["LLM_Prompt"])
    else:
        record["LLM_Summary"] = "N/A (No major issue detected)"
        
    record["Chef_Feedback_Prompt"] = "N/A"
    record["Chef_Feedback_Summary"] = "N/A"
    state['record'] = record
    return state

def status_router_node(state: AgentState) -> AgentState:
    record = state['record']
    
    if record.get("LLM_Prompt") == "":
        status = 'N/A (No Issue)'
    else:
        wastage_cost = record.get('Wastage Cost', 0.0)
        wastage_qty = record.get('Wastage Qty', 0.0)
        expected_qty = record.get('Expected Waste Qty', 0.0)
        root_causes: str = record.get('Root_Causes', 'None')
        num_causes = len(root_causes.split(';')) if root_causes != 'None' else 0
        
        status = 'Pending'
        ignore_cost = wastage_cost < COST_IGNORE_THRESHOLD
        ignore_expected = wastage_qty <= expected_qty
        if ignore_cost or ignore_expected:
            status = 'Ignore'
        elif wastage_cost >= COST_CRITICAL_THRESHOLD or num_causes > 1:
            status = 'Approved by Manager'
    
    record['Status'] = status
    state['status'] = status
    return state

def chef_feedback_node(state: AgentState) -> AgentState:
    record = state['record']
    
    if state['status'] == 'Approved by Manager':
        chef_prompt = generate_chef_feedback_prompt(record)
        record["Chef_Feedback_Prompt"] = chef_prompt
        record["Chef_Feedback_Summary"] = generate_chef_feedback_summary(chef_prompt)
    else:
        record["Chef_Feedback_Summary"] = "N/A"
    
    state['record'] = record
    return state

def append_data_node(state: AgentState) -> AgentState:
    return state

def communication_node(state: AgentState) -> AgentState:
    return state

def router_edge(state: AgentState) -> str:
    status = state['status']
    if status == 'Ignore':
        return 'append_ignore'
    elif status == 'Pending':
        return 'append_pending'
    elif status == 'Approved by Manager':
        return 'chef_feedback_gen'
    return 'end_path'