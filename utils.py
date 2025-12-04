import pandas as pd
from typing import Dict, Any

def safe_rate(wastage, planned):
    if pd.isna(wastage): wastage = 0.0
    if pd.isna(planned) or planned is None or planned <= 0: return 0.0
    try:
        return wastage / planned
    except (TypeError, ZeroDivisionError):
        return 0.0

def combined(dev, hr):
    if dev and hr: return "Both"
    if dev: return "Deviation"
    if hr: return "HighRate"
    return "None"

def combine_causes(row):
    causes = []
    if row.get("Expiry_Flag"): causes.append("Expired_Used")
    if row.get("Station_Inefficiency"): causes.append("Station_Inefficiency")
    if row.get("Shift_Issue"): causes.append("Shift_Issue")
    if row.get("Peak_Pressure_Issue"): causes.append("Peak_Pressure")
    if row.get("Heat_Spoilage_Flag"): causes.append("Heat_Spoilage")
    if row.get("Cold_Overprep_Flag"): causes.append("Cold_Overprep")
    if row.get("Supplier_Quality_Issue"): causes.append("Supplier_Quality")
    if row.get("Supplier_Rotation_Issue"): causes.append("Supplier_Rotation")
    return ";".join(causes) if causes else "None"