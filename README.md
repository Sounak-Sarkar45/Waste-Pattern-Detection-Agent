# Waste Pattern Detection Agent
A **LangGraph-powered FastAPI** application that autonomously analyzes food waste patterns across restaurant branches, identifies critical outliers using multimodal Groq LLMs, generates personalized, human-like feedback for chefs, updates MySQL records, and sends actionable email alerts — all with zero manual intervention.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
  - [Clone the Repository](#clone-the-repository)
  - [Create Virtual Environment](#create-virtual-environment)
  - [Install Dependencies](#install-dependencies)
  - [Environment Configuration](#environment-configuration)
  - [Database Setup](#database-setup)
  - [Run the Application](#run-the-application)
- [API Endpoints](#api-endpoints)
  - [Waste Analysis Workflow](#waste-analysis-workflow)
  - [Chef Feedback Email Delivery](#chef-feedback-email-delivery)
- [Usage Examples](#usage-examples)
- [Configuration](#configuration)
- [Release Notes](#release-notes)

---

## Overview

The **Waste Pattern Detection Agent** is an intelligent food waste intelligence system designed for multi-branch restaurant operations. It processes daily waste logs, detects abnormal patterns using advanced root-cause analysis (expiry misuse, station inefficiency, shift issues, temperature effects, etc.), generates professional, friendly, and actionable feedback messages via Groq LLMs, updates the database with approval status and feedback, and delivers personalized emails directly to responsible chefs — fully automated.

## Features

1. **Smart Waste Pattern Detection** – Uses statistical thresholds and historical benchmarks to flag critical waste events.
2. **Root Cause Intelligence** – Identifies causes like expired stock usage, station/shift inefficiency, peak-hour pressure, and temperature-related spoilage.
3. **LLM-Powered Human Feedback** – Generates natural, firm-yet-friendly chef messages with specific recommendations.
4. **Dynamic Email Subject Generation** – Creates compelling, context-aware subject lines (e.g., “Let’s Fix $513 Milk Waste – FIFO Alert”).
5. **LangGraph Stateful Workflow** – Orchestrates analysis → feedback → DB update in a robust, traceable flow.
6. **FastAPI Backend** – Clean REST API for on-demand branch-month analysis and email dispatch.
7. **Real Email Delivery via Gmail SMTP** – Sends personalized feedback emails directly to chefs using secure App Passwords.

## Architecture

| Layer                | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| **LangGraph Layer**  | Manages stateful execution of analysis → feedback → database update flow.  |
| **Agent Layer**      | Contains nodes for waste flagging, root cause detection, and LLM generation. |
| **LLM Layer**        | Groq-powered models (llama-3.1-8b-instant) for feedback and subject generation. |
| **Service Layer**    | MySQL read/write, statistical analysis, email sending via SMTP.             |
| **FastAPI Layer**    | Exposes `/analyze` and `/send-chef-feedback` endpoints for orchestration.  |

---

## Prerequisites

- Python 3.10 or higher  
- Git
- MySQL (with access credentials)
- Groq API Key (for LLM inference)
- SMTP Account (for sending email reports)

---

## Installation & Setup

### Clone the Repository
```bash
git clone https://Sounak-Sarkar45/waste-pattern-detection.git
cd waste-pattern-detection
```

### Create Virtual Environment

Using Python venv:
```bash
python -m venv venv
# Activate on Windows
venv\Scripts\activate
# Activate on macOS/Linux
source venv/bin/activate
```
Optional: Using UV for virtual environment
```bash
pip install uv
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### Install Dependencies
```bash 
pip install -r requirements.txt
```
#### or using uv
```bash
uv add -r requirements.txt
```

### Environment Configuration

#### Create a ```.env``` file in the project root:
```bash
GROQ_API_KEY=<your_groq_api_key>

# Gmail SMTP (for sending chef emails)
GMAIL_APP_USER=yourgmail@gmail.com
GMAIL_APP_PASSWORD=your-16-digit-app-password

# MySQL Configuration
MYSQL_HOST=your_mysql_host
MYSQL_USER=your_username
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database_name

# Table & Column Settings (adjust if different)
MYSQL_TABLE_NAME=your_waste_table_name
BRANCH_COLUMN=Branch
```

### Database Setup

#### Ensure your waste table contains at minimum these columns:

```bash
ID (INT, Primary Key),
Date (DATETIME or VARCHAR),
Ingredient,
Wastage Qty,
Expected Waste Qty,
Wastage Cost,
Waste Rate,
Kitchen Station,
Shift,
Branch,
Branch Manager,
Chef,
Status,
Chef_Feedback (TEXT)
```

### Run the Application
#### Start the FastAPI app:
```bash
uvicorn main:app --reload
```
Access API at: http://127.0.0.1:8000/

Interactive docs: http://127.0.0.1:8000/docs

### API Endpoints
#### Waste Analysis Workflow
| Method | Endpoint                | Description                                  |
| ------ | ----------------------- | -------------------------------------------- |
| GET   | `/analyze?branch=...&year=...&month=...` | Triggers full analysis for a branch and month. |

Example Request :
```
GET /analyze?branch=New%20York%20-%20Main&year=2025&month=February
```
Example Response:
```
[
    {
        "ID": 2,
        "Date": "2025-02-17",
        "Time": "00:00",
        "Weekday": "Monday",
        "Recipe": "Chocolate Milkshake",
        "Ingredient": "Milk",
        "Kitchen Station": "Soup Station",
        "Branch": "New York - Main",
        "Branch Manager": "Robert",
        "Chef": "Chef Maria",
        "Status": "Approved by Manager",
        "Chef_Feedback": "Team, we need to talk about our milk waste. We had a significant issue on February 17th....."
    },
    {
        "ID": 105,
        "Date": "2025-02-22",
        "Time": "00:00",
        "Weekday": "Saturday",
        "Recipe": "Paneer Butter Masala",
        "Ingredient": "Paneer",
        "Kitchen Station": "Soup Station",
        "Branch": "New York - Main",
        "Branch Manager": "Robert",
        "Chef": "Chef Lee",
        "Status": "N/A (No Issue)",
        "Chef_Feedback": "N/A"
    }
]
```

#### Chef Feedback Email Delivery
| Method | Endpoint                | Description                                  |
| ------ | ----------------------- | -------------------------------------------- |
| POST   | `/send-chef-feedback` | Sends personalized feedback emails to chefs. |

Example Request :
```
{
  "records": [
    {
      "id": 123,
      "chef_email": "maria.garcia@restaurant.com"
    },
    {
      "id": 456,
      "chef_email": "john.smith@restaurant.com"
    }
  ]
}
```
Example Response:
```
{
  "total": 2,
  "sent": [123, 456],
  "failed": [],
  "errors": {}
}
```

### Usage Examples

- Run monthly analysis
  `GET http://127.0.0.1:8000/analyze?branch=LA%20-%20Downtown&year=2025&month=February`
  → Flags critical waste, generates feedback, updates DB.
- Send feedback emails
  ```
  POST /send-chef-feedback
  {
    "records": [
      { "id": 105, "chef_email": "chef.maria@restaurant.com" }
    ]
  }
  ```
  → Chef receives:
  Subject: Let’s Fix Our $513 Milk Waste – FIFO Alert!
  Body: Personalized, professional, actionable message.

### Configuration

#### Environmental Variables

| Variable | Description |
| :--- | :--- |
| `GROQ_API_KEY` | Required for LLM feedback & subject generation |
| `GMAIL_APP_USER` | Sending email address |
| `GMAIL_APP_PASSWORD` | 16-digit Gmail App Password (not regular pw) |
| `MYSQL_*` | Standard MySQL connection credentials |
| `MYSQL_TABLE_NAME` | Name of your waste data table |
| `BRANCH_COLUMN` | Column name storing branch (e.g., "Branch") |

### Release Notes
#### v1.0.0

- Full waste pattern detection with root cause analysis
- LLM-generated chef feedback (body + subject)
- Automated MySQL updates with Chef_Feedback and Chef_Feedback_Subject
- Real Gmail SMTP delivery to chefs
- Clean FastAPI + LangGraph architecture
