import os
from dotenv import load_dotenv

load_dotenv()

# Configuration constants
EXPECTED_THRESHOLD = 1.0
RATE_THRESHOLD = 1.5
STATION_MULT = 1.3
SHIFT_MULT = 1.3
PEAK_MULT = 1.25
HOT_TEMP = 27.0
HOT_MULT = 1.3
COLD_TEMP = 10.0
SUPPLIER_MULT = 1.3
REPEATED_EXPIRY_COUNT = 2
COST_CRITICAL_THRESHOLD = 100.0
COST_IGNORE_THRESHOLD = 5.0
BRANCH_COLUMN = "Branch"
MYSQL_TABLE_NAME = "waste_logs"

# MySQL configuration
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY")