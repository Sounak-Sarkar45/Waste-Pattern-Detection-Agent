from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from config import GROQ_API_KEY
import pandas as pd
from config import EXPECTED_THRESHOLD, RATE_THRESHOLD, STATION_MULT, SHIFT_MULT, PEAK_MULT, HOT_TEMP, HOT_MULT, COLD_TEMP, COST_CRITICAL_THRESHOLD, COST_IGNORE_THRESHOLD

def generate_llm_summary(prompt_text):
    if not GROQ_API_KEY:
        return "Simulated Management Summary: Critical waste event detected for Prime Beef due to multiple root causes: expiry date non-compliance and high shift-level waste. The total cost impact is $150.00. Recommend immediate process review for butchering station Night Shift operations and vendor rotation policies with SupplierY."
    try:
        chat = ChatGroq(temperature=0, groq_api_key=GROQ_API_KEY, model_name="llama-3.1-8b-instant")
        template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert waste analysis assistant. Compose a concise, actionable summary (3-4 sentences) and specific, clear recommendations, prioritizing the root causes found."),
            ("user", "{prompt}")
        ])
        chain = template | chat
        response = chain.invoke({"prompt": prompt_text})
        return response.content
    except Exception as e:
        return f"LLM Error: {e}"

def generate_llm_prompt(row, avg_rate):
    if row.get("Combined_Flag", "None") == "None" and row.get("Root_Causes", "None") == "None":
        return ""
    item_name = row.get('Ingredient', 'N/A')
    date_str = "N/A"
    if 'Date' in row and pd.notna(row['Date']):
        try:
            date_str = pd.to_datetime(row['Date']).strftime('%Y-%m-%d')
        except:
            pass
    summary = f"Waste Analysis Summary for Item: {item_name} on Date: {date_str} (Waste Rate: {row.get('Waste Rate', 0.0):.4f}, Wastage Qty: {row.get('Wastage Qty', 'N/A'):.1f}, Expected Qty: {row.get('Expected Waste Qty', 'N/A'):.1f}).\n"
    summary += f"The waste instance was categorized as **{row.get('Combined_Flag', 'None')}** (Branch Avg Rate: {avg_rate:.4f}).\n"
    
    if row.get("Root_Causes", "None") != "None":
        cause_list = row["Root_Causes"].split(";")
        summary += "\n**Detected Root Causes:**\n"
        cause_map = {
            "Expired_Used": "The item was used/wasted after its official Expiry Date.",
            "Station_Inefficiency": f"The Kitchen Station ({row.get('Kitchen Station', 'N/A')}) has a historical average waste rate higher than {STATION_MULT}x the branch average.",
            "Shift_Issue": f"The Shift ({row.get('Shift', 'N/A')}) is historically associated with a waste rate higher than {SHIFT_MULT}x the branch average.",
            "Peak_Pressure": f"The high waste occurred during a Peak Hour, where the waste rate was higher than {PEAK_MULT}x the non-peak average rate.",
            "Heat_Spoilage": f"The high waste occurred on a hot day (Temp > {HOT_TEMP}°C), and the waste rate exceeded {HOT_MULT}x the moderate-temperature average rate.",
            "Cold_Overprep": f"The high waste occurred on a cold day (Temp ≤ {COLD_TEMP}°C) with low sales, suggesting over-preparation.",
            "Supplier_Quality": f"The Supplier ({row.get('Supplier Name', 'N/A')}) is historically categorized as a quality risk due to a high average waste rate.",
            "Supplier_Rotation": f"The Supplier ({row.get('Supplier Name', 'N/A')}) has a history of expiry issues (rotation risk), and the current row exhibits high waste.",
        }
        for cause in cause_list:
            summary += f"* {cause_map.get(cause, cause.replace('_', ' ').title())}\n"
    
    summary += "\nBased on the above analysis, compose a concise, actionable summary (3-4 sentences) and specific, clear recommendations in professional, human-readable language, prioritizing the root causes found."
    return summary.strip()

def generate_chef_feedback_prompt(row):
    item_name = row.get('Ingredient', 'N/A')
    wastage_qty = row.get("Wastage Qty", 0.0)
    planned_qty = row.get("Planned Qty", 0.0)
    expected_qty = row.get("Expected Waste Qty", 0.0)
    wastage_cost = row.get('Wastage Cost', 0.0)
    
    facts = f"Wastage Event: {item_name} on {row.get('Date', 'N/A').strftime('%Y-%m-%d')}. "
    facts += f"The high-cost item had a waste value of ${wastage_cost:.2f}."
    quant_summary = []
    if row.get("Waste_Deviation_Flag"):
        quant_summary.append(
            f"We wasted {wastage_qty:.1f} units, which is significantly more than the expected waste of {expected_qty:.1f} units."
        )
    if row.get("High_Waste_Flag"):
        quant_summary.append(
            f"The waste rate for this item ({row['Waste Rate']:.2%}) is much higher than the standard branch rate."
        )
    
    cause_list = row.get("Root_Causes", "None").split(";")
    cause_facts = []
    for cause in cause_list:
        if cause == "Expired_Used":
            cause_facts.append(
                f"The item was used/wasted after its Expiry Date ({row.get('Expiry Date', 'N/A').strftime('%Y-%m-%d')}). This is a major rotation risk."
            )
        elif cause == "Station_Inefficiency":
            cause_facts.append(
                f"The '{row.get('Kitchen Station', 'N/A')}' station is showing a historical pattern of high waste for this type of ingredient."
            )
        elif cause == "Shift_Issue":
            cause_facts.append(
                f"The waste occurred during the '{row.get('Shift', 'N/A')}' shift, which has been flagged for consistent waste issues."
            )

    prompt = (
        f"Item: {item_name}. \n\n"
        f"**Facts:** {facts}\n"
        f"**Quantitative Issue:** {' '.join(quant_summary)}\n"
        f"**Root Causes:** {' '.join(cause_facts)}\n\n"
        "Your task: Act as a friendly, but firm, Head Chef providing direct, user-friendly feedback to a station chef for an "
        "'Approved by Manager' issue.\n\n"
        "Write ONLY the main body of the email in plain text:\n"
        "- Do NOT include any greeting lines (no 'Hi', 'Hello', 'Dear', names, etc.).\n"
        "- Do NOT include any closing or signature (no 'Thanks', 'Regards', names, roles, or branch names).\n"
        "- Do NOT include a subject line.\n"
        "- Start directly with the content of the message (for example: "
        "\"Team, we need to talk about our [Ingredient] waste.\").\n\n"
        "The body should include three parts (but as one short email body):\n"
        "1. A friendly opening sentence that mentions the ingredient and the issue.\n"
        "2. A clear, non-technical explanation of the problem, incorporating the facts and quantitative issues. "
        "   Keep the math simple (e.g., 'we wasted 5 kg when we should have only wasted 1 kg').\n"
        "3. A single, specific, and friendly recommendation on how to avoid the mistake immediately "
        "(e.g., 'Please double-check the FIFO tag every time you pull stock').\n"
    )
    return prompt

def generate_chef_feedback_summary(prompt_text):
    if not GROQ_API_KEY:
        # Fallback: BODY ONLY, no greeting / closing / names
        return (
            "Team, we need to address the waste on our Prime Beef. "
            "We wasted 5.0 units, which is five times the expected amount, leading to a critical cost loss of $150.00. "
            "The primary issue is that this batch from SupplierY was used two days past its expiry date, which is a serious rotation failure. "
            "Please implement a mandatory expiry check on all perishable items, especially Prime Beef, before they leave the cold storage area "
            "and reinforce strict FIFO procedures on the Night Shift."
        )
    try:
        chat = ChatGroq(
            temperature=0.3,
            groq_api_key=GROQ_API_KEY,
            model_name="llama-3.1-8b-instant"
        )
        template = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a professional Head Chef writing a direct, friendly, and actionable feedback message to a station chef "
                "about a waste issue. IMPORTANT:\n"
                "- Output ONLY the main body of the email.\n"
                "- Do NOT include any greeting lines (no 'Hi', 'Hello', 'Dear', no names).\n"
                "- Do NOT include any closing or signature (no 'Thanks', 'Regards', no names, roles, or branch names).\n"
                "- Do NOT include any subject line.\n"
                "- Start directly with the content of the message.\n"
                "The body should be brief and end with one clear recommendation sentence."
            ),
            ("user", "{prompt}")
        ])
        chain = template | chat
        response = chain.invoke({"prompt": prompt_text})
        return response.content
    except Exception as e:
        return f"LLM Error generating chef feedback: {e}"