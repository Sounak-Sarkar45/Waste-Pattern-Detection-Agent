import pandas as pd
import mysql.connector
from config import MYSQL_CONFIG, MYSQL_TABLE_NAME, BRANCH_COLUMN

def load_mysql_data(branch_name: str, year: int, month_name: str) -> pd.DataFrame:
    query = f"""
        SELECT *,
               STR_TO_DATE(Date, '%d-%b-%Y %H:%i') AS Analyzed_Date
        FROM {MYSQL_TABLE_NAME}
        WHERE `{BRANCH_COLUMN}` = %s
          AND YEAR(STR_TO_DATE(Date, '%d-%b-%Y %H:%i')) = %s
          AND MONTHNAME(STR_TO_DATE(Date, '%d-%b-%Y %H:%i')) = %s
    """
    conn = None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        df = pd.read_sql(query, conn, params=(branch_name, year, month_name))
    except mysql.connector.Error as err:
        raise ValueError(f"Could not read data from MySQL: {err}")
    finally:
        if conn and conn.is_connected():
            conn.close()

    # Post-processing: clean up date columns
    numeric_cols = ["Planned Qty", "Wastage Qty", "Expected Waste Qty", "Wastage Cost",
                    "Sales Qty", "Temperature (°C)", "Unit Cost", "Total Cost"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    date_cols = ['Date', 'Expiry Date', 'Stock Received Date']
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')

    return df

def update_mysql_data(df_results: pd.DataFrame):
    if not all(col in df_results.columns for col in ['ID', 'Status']):
        raise ValueError("Missing required columns (ID, Status) for DB update.")

    update_data = df_results[['ID', 'Status', 'Chef_Feedback_Summary']].copy()
    update_data = update_data.rename(columns={'Chef_Feedback_Summary': 'Chef_Feedback'})
    update_data['Chef_Feedback'] = update_data['Chef_Feedback'].fillna('').replace('N/A', '')

    if update_data.empty:
        return

    conn, cursor = None, None
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        update_query = f"""
            UPDATE {MYSQL_TABLE_NAME}
            SET `Status` = %s, `Chef_Feedback` = %s
            WHERE ID = %s
        """
        
        for _, row in update_data.iterrows():
            params = (
                row['Status'],
                row['Chef_Feedback'] if pd.notna(row['Chef_Feedback']) else '',
                int(row['ID'])
            )
            cursor.execute(update_query, params)
        
        conn.commit()
    except mysql.connector.Error as err:
        raise ValueError(f"Error updating database: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()