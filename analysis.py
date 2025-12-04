import pandas as pd
from typing import Dict, Any, List, Set
from utils import safe_rate
from config import (
    STATION_MULT, SHIFT_MULT, PEAK_MULT, HOT_TEMP, HOT_MULT, COLD_TEMP, 
    SUPPLIER_MULT, REPEATED_EXPIRY_COUNT, BRANCH_COLUMN
)

def calculate_branch_metrics(df_branch: pd.DataFrame) -> Dict[str, Any]:
    df_branch["Waste Rate"] = df_branch.apply(
        lambda r: safe_rate(r.get("Wastage Qty"), r.get("Planned Qty")), axis=1
    )
    mask_planned = df_branch["Planned Qty"].notna() & (df_branch["Planned Qty"] > 0)
    
    metrics = {}
    branch_avg = df_branch.loc[mask_planned, "Waste Rate"].mean() if mask_planned.any() else 0.0
    metrics['branch_avg'] = branch_avg
    overall_avg = branch_avg
    
    metrics['station_avg_map'] = df_branch.loc[mask_planned].groupby("Kitchen Station")["Waste Rate"].mean().fillna(0).to_dict() if "Kitchen Station" in df_branch.columns else {}
    metrics['shift_avg_map'] = df_branch.loc[mask_planned].groupby("Shift")["Waste Rate"].mean().fillna(0).to_dict() if "Shift" in df_branch.columns else {}
    
    if "Peak Hour Flag" in df_branch.columns:
        nonpeak_mask = (~df_branch["Peak Hour Flag"].astype(bool)) & mask_planned
        metrics['nonpeak_rate'] = df_branch.loc[nonpeak_mask, "Waste Rate"].mean() if nonpeak_mask.any() else 0.0
    else:
        metrics['nonpeak_rate'] = 0.0
    
    if "Temperature (°C)" in df_branch.columns:
        moderate_mask = (df_branch["Temperature (°C)"].notna()) & (df_branch["Temperature (°C)"] <= HOT_TEMP) & mask_planned
        metrics['moderate_temp_rate'] = df_branch.loc[moderate_mask, "Waste Rate"].mean() if moderate_mask.any() else 0.0
    else:
        metrics['moderate_temp_rate'] = 0.0
    
    metrics['sales_med'] = df_branch["Sales Qty"].median() if "Sales Qty" in df_branch.columns else None
    
    if "Supplier Name" in df_branch.columns:
        supplier_avg = df_branch.loc[mask_planned].groupby("Supplier Name")["Waste Rate"].mean().fillna(0)
        bad_quality_suppliers = supplier_avg[supplier_avg > (overall_avg * SUPPLIER_MULT)].index.tolist()
        metrics['bad_quality_suppliers_list'] = bad_quality_suppliers
        
        df_temp = df_branch.copy()
        df_temp["Expiry_Flag"] = False
        if "Date" in df_temp.columns and "Expiry Date" in df_temp.columns:
            date_col = pd.to_datetime(df_temp["Date"], errors='coerce').dt.normalize()
            expiry_col = pd.to_datetime(df_temp["Expiry Date"], errors='coerce').dt.normalize()
            df_temp["Expiry_Flag"] = date_col > expiry_col
        expiry_counts = df_temp.groupby("Supplier Name")["Expiry_Flag"].sum()
        supplier_total = df_temp.groupby("Supplier Name")["Expiry_Flag"].size()
        
        supplier_rotation_history = set()
        for sup in expiry_counts.index:
            cnt = int(expiry_counts.get(sup, 0))
            total = int(supplier_total.get(sup, 0))
            prop = (cnt / total) if total and total > 0 else 0
            if (cnt >= REPEATED_EXPIRY_COUNT) or (prop > 0.2):
                supplier_rotation_history.add(sup)
        
        metrics['supplier_rotation_history_set'] = supplier_rotation_history
    else:
        metrics['bad_quality_suppliers_list'] = []
        metrics['supplier_rotation_history_set'] = set()
    
    return metrics

def run_branch_analysis(df: pd.DataFrame, branch_name: str, app) -> pd.DataFrame:
    df_branch = df[df[BRANCH_COLUMN] == branch_name].copy().reset_index(drop=True)
    
    if df_branch.empty:
        return pd.DataFrame()
    
    branch_metrics = calculate_branch_metrics(df_branch)
    
    all_results = []
    for index, record_series in df_branch.iterrows():
        record = record_series.to_dict()
        initial_state = {
            "record": record,
            "branch_metrics": branch_metrics,
            "status": ""
        }
        final_state = app.invoke(initial_state)
        all_results.append(final_state['record'])
    
    return pd.DataFrame(all_results)