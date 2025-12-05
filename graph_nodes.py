# graph_nodes.py
from typing import TypedDict, Dict, Any, List, Set
import pandas as pd

# Import utilities and configs (adjust paths if your project structure differs)
from utils import combined, combine_causes, safe_rate
from llm import (
    generate_llm_prompt,
    generate_llm_summary,
    generate_chef_feedback_prompt,
    generate_chef_feedback_summary,
)
from config import (
    EXPECTED_THRESHOLD,
    RATE_THRESHOLD,
    STATION_MULT,
    SHIFT_MULT,
    PEAK_MULT,
    HOT_TEMP,
    HOT_MULT,
    COLD_TEMP,
    SUPPLIER_MULT,
    REPEATED_EXPIRY_COUNT,
    COST_CRITICAL_THRESHOLD,
    COST_IGNORE_THRESHOLD,
)

class AgentState(TypedDict):
    record: Dict[str, Any]
    branch_metrics: Dict[str, Any]
    status: str


def analysis_and_llm_node(state: AgentState) -> AgentState:
    record = state["record"]
    metrics = state["branch_metrics"]

    # Extract pre-calculated branch metrics
    branch_avg = metrics.get("branch_avg", 0.0)
    nonpeak_rate = metrics.get("nonpeak_rate", 0.0)
    moderate_temp_rate = metrics.get("moderate_temp_rate", 0.0)
    sales_med = metrics.get("sales_med", 0.0)
    station_avg_map: Dict[str, float] = metrics.get("station_avg_map", {})
    shift_avg_map: Dict[str, float] = metrics.get("shift_avg_map", {})
    bad_quality_suppliers_list: List[str] = metrics.get("bad_quality_suppliers_list", [])
    supplier_rotation_history_set: Set[str] = metrics.get("supplier_rotation_history_set", set())
    overall_avg = branch_avg

    # --- Waste Detection ---
    wastage_qty = record.get("Wastage Qty", 0.0)
    planned_qty = record.get("Planned Qty", 0.0)
    expected_qty = record.get("Expected Waste Qty", 0.0)

    record["Waste Rate"] = safe_rate(wastage_qty, planned_qty)

    record["Waste_Deviation_Flag"] = wastage_qty > expected_qty * EXPECTED_THRESHOLD
    record["High_Waste_Flag"] = record["Waste Rate"] > (branch_avg * RATE_THRESHOLD if branch_avg > 0 else 0.0)
    record["Combined_Flag"] = combined(record["Waste_Deviation_Flag"], record["High_Waste_Flag"])

    # --- Root Cause Flags ---
    # Expiry
    expiry_flag = False
    if pd.notna(record.get("Date")) and pd.notna(record.get("Expiry Date")):
        try:
            expiry_flag = pd.to_datetime(record["Date"]).normalize() > pd.to_datetime(record["Expiry Date"]).normalize()
        except:
            pass
    record["Expiry_Flag"] = expiry_flag

    # Station & Shift inefficiency
    station = record.get("Kitchen Station")
    record["Station_Inefficiency"] = (
        station in station_avg_map and station_avg_map[station] > overall_avg * STATION_MULT
    )

    shift = record.get("Shift")
    record["Shift_Issue"] = shift in shift_avg_map and shift_avg_map[shift] > overall_avg * SHIFT_MULT

    # Peak pressure
    record["Peak_Pressure_Issue"] = (
        record.get("Peak Hour Flag", False)
        and nonpeak_rate > 0
        and record["Waste Rate"] > nonpeak_rate * PEAK_MULT
    )

    # Heat / Cold issues
    temp = record.get("Temperature (°C)")
    record["Heat_Spoilage_Flag"] = pd.notna(temp) and temp > HOT_TEMP and record["Waste Rate"] > moderate_temp_rate * HOT_MULT
    record["Cold_Overprep_Flag"] = (
        pd.notna(temp)
        and pd.notna(record.get("Sales Qty"))
        and sales_med is not None
        and temp <= COLD_TEMP
        and record.get("Sales Qty", 0) < sales_med
        and record["Waste Rate"] > overall_avg * 1.3
    )

    # Supplier issues
    supplier = record.get("Supplier Name")
    record["Supplier_Quality_Issue"] = supplier in bad_quality_suppliers_list
    record["Supplier_Rotation_Issue"] = supplier in supplier_rotation_history_set and record["High_Waste_Flag"]

    record["Root_Causes"] = combine_causes(record)

    # --- LLM Summaries ---
    record["LLM_Prompt"] = generate_llm_prompt(record, branch_avg)
    record["LLM_Summary"] = generate_llm_summary(record["LLM_Prompt"]) if record["LLM_Prompt"] else "N/A (No major issue detected)"

    # Chef feedback placeholders
    record["Chef_Feedback_Prompt"] = "N/A"
    record["Chef_Feedback_Summary"] = "N/A"

    state["record"] = record
    return state


def status_router_node(state: AgentState) -> AgentState:
    record = state["record"]

    if not record.get("LLM_Prompt"):
        status = "N/A (No Issue)"
    else:
        wastage_cost = record.get("Wastage Cost", 0.0)
        wastage_qty = record.get("Wastage Qty", 0.0)
        expected_qty = record.get("Expected Waste Qty", 0.0)
        root_causes = record.get("Root_Causes", "None")
        num_causes = len(root_causes.split(";")) if root_causes != "None" else 0

        status = "Pending"
        if wastage_cost < COST_IGNORE_THRESHOLD or wastage_qty <= expected_qty:
            status = "Ignore"
        elif wastage_cost >= COST_CRITICAL_THRESHOLD or num_causes > 1:
            status = "Approved by Manager"

    record["Status"] = status
    state["status"] = status
    return state


def chef_feedback_node(state: AgentState) -> AgentState:
    record = state["record"]

    if state["status"] == "Approved by Manager":
        prompt = generate_chef_feedback_prompt(record)
        record["Chef_Feedback_Prompt"] = prompt
        record["Chef_Feedback_Summary"] = generate_chef_feedback_summary(prompt)
    else:
        record["Chef_Feedback_Summary"] = "N/A"

    state["record"] = record
    return state


def append_data_node(state: AgentState) -> AgentState:
    # Simple pass-through node (used for logging/side-effects in the full script)
    return state


def communication_node(state: AgentState) -> AgentState:
    # In the full script this prints/sends the chef message
    return state


def router_edge(state: AgentState) -> str:
    """Decides which append node to route to based on status."""
    status = state["status"]
    if status == "Ignore":
        return "append_ignore"
    elif status == "Pending":
        return "append_pending"
    elif status == "Approved by Manager":
        return "append_approved"
    else:
        # Fallback for N/A or unexpected status
        return "append_pending"