from fastapi import FastAPI, Query, HTTPException, APIRouter, BackgroundTasks
import pandas as pd
import os
from typing import List
import mysql.connector
from config import MYSQL_CONFIG, MYSQL_TABLE_NAME

from db import load_mysql_data, update_mysql_data
from analysis import run_branch_analysis
from graph import build_graph
from pydantic import BaseModel
import smtplib
from email.message import EmailMessage

app = FastAPI(title="Waste Pattern Detection API")
graph_app = build_graph()

# ====================== /analyze Endpoint (unchanged) ======================
@app.get("/analyze")
def analyze(
    branch: str = Query(..., description="Branch Name (e.g., LA - Downtown)"),
    year: int = Query(..., description="Year (e.g., 2025)"),
    month: str = Query(..., description="Month Name (e.g., February)")
):
    try:
        df_data = load_mysql_data(branch_name=branch, year=year, month_name=month)
        if df_data.empty:
            raise ValueError("No data found for the specified branch, year, and month.")

        final_df = run_branch_analysis(df=df_data, branch_name=branch, app=graph_app)
        if final_df.empty or 'ID' not in final_df.columns:
            raise ValueError("Analysis completed but no data processed or 'ID' column missing.")

        update_mysql_data(final_df)

        output_df = final_df.copy()
        if 'Date' in output_df.columns:
            output_df['Date'] = pd.to_datetime(output_df['Date']).dt.strftime('%Y-%m-%d')
            output_df['Time'] = pd.to_datetime(output_df['Date']).dt.strftime('%H:%M')
            output_df['Weekday'] = pd.to_datetime(output_df['Date']).dt.strftime('%A')
        else:
            output_df['Date'] = 'N/A'
            output_df['Time'] = 'N/A'
            output_df['Weekday'] = 'N/A'

        columns_to_select = [
            'ID', 'Date', 'Time', 'Weekday', 'Recipe', 'Ingredient',
            'Kitchen Station', 'Branch', 'Branch Manager', 'Chef',
            'Status', 'Chef_Feedback_Summary'
        ]
        output_df = output_df.reindex(columns=columns_to_select, fill_value='N/A')
        output_df = output_df.rename(columns={'Chef_Feedback_Summary': 'Chef_Feedback'})

        return output_df.to_dict(orient='records')

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ====================== Email Router ======================
router = APIRouter()

GMAIL_USER = os.getenv("GMAIL_APP_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")


# chef_email is now REQUIRED!
class FeedbackRequestItem(BaseModel):
    id: int
    chef_email: str          # ← REQUIRED now


class FeedbackRequest(BaseModel):
    records: List[FeedbackRequestItem]


class SendFeedbackResponse(BaseModel):
    total: int
    sent: List[int]
    failed: List[int]
    errors: dict = {}


def send_email(to_email: str, subject: str, body: str):
    if not GMAIL_USER or not GMAIL_PASS:
        raise ValueError("Gmail credentials missing in .env")

    msg = EmailMessage()
    msg["From"] = GMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)


@router.post("/send-chef-feedback", response_model=SendFeedbackResponse)
async def send_chef_feedback(request: FeedbackRequest, background_tasks: BackgroundTasks):
    if not GMAIL_USER or not GMAIL_PASS:
        raise HTTPException(status_code=500, detail="Email service not configured. Check .env")

    ids = [item.id for item in request.records]
    if not ids:
        raise HTTPException(status_code=400, detail="No records provided")

    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor(dictionary=True)

        placeholders = ",".join(["%s"] * len(ids))
        query = f"""
            SELECT ID, Chef, Branch, `Branch Manager`, Chef_Feedback
            FROM {MYSQL_TABLE_NAME}
            WHERE ID IN ({placeholders})
              AND Status = 'Approved by Manager'
              AND Chef_Feedback IS NOT NULL 
              AND TRIM(Chef_Feedback) != ''
              AND TRIM(Chef_Feedback) != 'N/A'
        """
        cursor.execute(query, ids)
        rows = cursor.fetchall()
        df = pd.DataFrame(rows)

    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database error: {err}")
    finally:
        if conn and conn.is_connected():
            conn.close()

    if df.empty:
        raise HTTPException(status_code=404, detail="No approved records with feedback found")

    email_map = {item.id: item.chef_email for item in request.records}

    sent = []
    failed = []
    errors = {}

    for _, row in df.iterrows():
        record_id = int(row["ID"])
        chef_name = row["Chef"] or "Chef"
        branch = row["Branch"]
        manager_name = row["Branch Manager"] or "Management"
        raw_feedback = row["Chef_Feedback"]

        # Extract subject from first line if it starts with "Subject:"
        lines = raw_feedback.strip().split('\n')
        subject_line = lines[0].strip()
        if subject_line.lower().startswith("subject:"):
            email_subject = subject_line[8:].strip()  # Remove "Subject:" part
            body_lines = lines[1:]  # Rest is body
        else:
            email_subject = f"Waste Feedback Required – {row.get('Ingredient', 'Item')} ({branch})"
            body_lines = lines

        # Clean body: remove empty lines at start + fix common placeholders
                # Clean body: remove empty lines at start
        body_text = '\n'.join(line.strip() for line in body_lines if line.strip())

        # Replace placeholders
        body_text = body_text.replace("[Station Chef's Name]", (chef_name or "Chef").split()[0])
        body_text = body_text.replace("[Your Name]", manager_name)

        # ---- EXTRA CLEANUP: remove duplicate greetings and signatures ----
        lines = body_text.splitlines()

        # 1) Remove inner greeting lines like "Hello Chef David," or "Hi Chef,"
        cleaned_lines = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            lower = stripped.lower()

            is_greeting = (
                lower.startswith("hi ") or lower == "hi" or
                lower.startswith("hello ") or lower == "hello" or
                lower.startswith("dear ") or lower == "dear"
            )

            # Only treat very early lines as greetings (first 2–3 lines)
            if idx <= 2 and is_greeting:
                # Skip this greeting line; we already add "Hello {chef_name}," outside
                continue

            cleaned_lines.append(line)

        lines = cleaned_lines

        # 2) Remove any signature block ("Best,", "Regards,", etc.) and everything after
        closers = (
            "best,",
            "best regards,",
            "regards,",
            "thanks,",
            "thank you,",
        )

        cut_index = None
        for i, line in enumerate(lines):
            if line.strip().lower() in closers:
                cut_index = i
                break

        if cut_index is not None:
            lines = lines[:cut_index]

        # Rebuild final cleaned body text (middle content only)
        body_text = "\n".join(l for l in lines if l.strip())
        # ---- END EXTRA CLEANUP ----

        recipient_email = email_map.get(record_id)
        if not recipient_email or "@" not in recipient_email:
            failed.append(record_id)
            errors[record_id] = "Missing or invalid chef_email"
            continue

        final_body = f"""Hello {chef_name},

{body_text}

Thank you,
{manager_name}
{branch}
Waste Intelligence System
        """.strip()

        try:
            background_tasks.add_task(send_email, recipient_email, email_subject, final_body)
            sent.append(record_id)
        except Exception as e:
            failed.append(record_id)
            errors[record_id] = str(e)

    return SendFeedbackResponse(total=len(ids), sent=sent, failed=failed, errors=errors)

app.include_router(router)

@app.get("/")
def root():
    return {"message": "Waste Pattern Detection API is running!"}