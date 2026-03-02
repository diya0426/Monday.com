#!/usr/bin/env python3
"""
Script to import Deal_funnel_Data.xlsx and Work_Order_Tracker_Data.xlsx into Monday.com boards.

Usage:
    pip install openpyxl pandas requests python-dotenv
    python import_to_monday.py
"""

import os
import json
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
API_URL = "https://api.monday.com/v2"

HEADERS = {
    "Authorization": MONDAY_API_TOKEN,
    "Content-Type": "application/json",
    "API-Version": "2024-01",
}

# ----------------- Helper Functions -----------------
def run_query(query: str, variables: dict = None, retries: int = 5):
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    for attempt in range(retries):
        response = requests.post(API_URL, json=payload, headers=HEADERS)
        if response.status_code == 429:
            wait_time = 2 ** attempt
            print(f"⏳ Rate limit hit. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise Exception(f"Monday API error: {data['errors']}")
        return data
    raise Exception("❌ Failed after multiple retries due to rate limiting.")

def create_board(name: str, board_kind: str = "public") -> str:
    query = """
    mutation ($name: String!, $kind: BoardKind!) {
        create_board(board_name: $name, board_kind: $kind) { id }
    }
    """
    result = run_query(query, {"name": name, "kind": board_kind})
    return result["data"]["create_board"]["id"]

def create_column(board_id: str, title: str, col_type: str) -> str:
    query = """
    mutation ($boardId: ID!, $title: String!, $type: ColumnType!) {
        create_column(board_id: $boardId, title: $title, column_type: $type) { id }
    }
    """
    result = run_query(query, {"boardId": board_id, "title": title, "type": col_type})
    return result["data"]["create_column"]["id"]

def create_item(board_id: str, item_name: str, column_values: dict) -> str:
    query = """
    mutation ($boardId: ID!, $itemName: String!, $columnValues: JSON!) {
        create_item(board_id: $boardId, item_name: $itemName, column_values: $columnValues) { id }
    }
    """
    result = run_query(query, {
        "boardId": board_id,
        "itemName": item_name,
        "columnValues": json.dumps(column_values)
    })
    return result["data"]["create_item"]["id"]

def safe_str(val):
    if pd.isna(val) or val is None:
        return ""
    return str(val).strip()

def safe_date(val):
    if pd.isna(val) or val is None or str(val).strip() == "":
        return None
    try:
        dt = pd.to_datetime(val)
        return {"date": dt.strftime("%Y-%m-%d")}
    except:
        return None

def safe_num(val):
    try:
        if pd.isna(val):
            return None
        return float(val)
    except:
        return None

# ----------------- Import Deals -----------------
def import_deals():
    print("📊 Reading Deals Excel file...")
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), '..', 'data', 'Deal_funnel_Data.xlsx'))
    df.columns = df.columns.str.strip()
    print(f"  Found {len(df)} deals with columns: {list(df.columns)}")

    print("\n🏗️ Creating Deals board on Monday.com...")
    board_id = create_board("Deals Funnel - Skylark BI")
    print(f"  Board created: ID={board_id}")

    print("\n📐 Creating columns...")
    cols = {}
    col_map = [
        ("Owner Code", "text"),
        ("Client Code", "text"),
        ("Deal Status", "status"),
        ("Close Date (Actual)", "date"),
        ("Closure Probability", "text"),
        ("Deal Value (Masked)", "numbers"),
        ("Tentative Close Date", "date"),
        ("Deal Stage", "text"),
        ("Product", "text"),
        ("Sector", "text"),
        ("Created Date", "date"),
    ]
    for title, col_type in col_map:
        try:
            cols[title] = create_column(board_id, title, col_type)
            print(f"  ✅ {title} ({col_type}) -> {cols[title]}")
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ Failed to create column {title}: {e}")

    print(f"\n⬆️ Importing {len(df)} deals...")
    success, fail = 0, 0

    status_map = {"Open": "Working on it", "On Hold": "Stuck", "Closed": "Done", "Dead": "Stuck"}

    for idx, row in df.iterrows():
        deal_name = safe_str(row.get("Deal Name", f"Deal_{idx}"))
        column_values = {}
        if "Owner Code" in cols:
            column_values[cols["Owner Code"]] = safe_str(row.get("Owner code"))
        if "Client Code" in cols:
            column_values[cols["Client Code"]] = safe_str(row.get("Client Code"))
        if "Deal Status" in cols:
            status = safe_str(row.get("Deal Status"))
            column_values[cols["Deal Status"]] = {"label": status_map.get(status, "Working on it")}
        if "Close Date (Actual)" in cols:
            d = safe_date(row.get("Close Date (A)"))
            if d: column_values[cols["Close Date (Actual)"]] = d
        if "Closure Probability" in cols:
            column_values[cols["Closure Probability"]] = safe_str(row.get("Closure Probability"))
        if "Deal Value (Masked)" in cols:
            n = safe_num(row.get("Masked Deal value"))
            if n is not None: column_values[cols["Deal Value (Masked)"]] = n
        if "Tentative Close Date" in cols:
            d = safe_date(row.get("Tentative Close Date"))
            if d: column_values[cols["Tentative Close Date"]] = d
        if "Deal Stage" in cols:
            column_values[cols["Deal Stage"]] = safe_str(row.get("Deal Stage"))
        if "Product" in cols:
            column_values[cols["Product"]] = safe_str(row.get("Product deal"))
        if "Sector" in cols:
            column_values[cols["Sector"]] = safe_str(row.get("Sector/service"))
        if "Created Date" in cols:
            d = safe_date(row.get("Created Date"))
            if d: column_values[cols["Created Date"]] = d

        try:
            create_item(board_id, deal_name, column_values)
            success += 1
            if success % 20 == 0:
                print(f"  Progress: {success}/{len(df)}")
            time.sleep(0.5)
        except Exception as e:
            fail += 1
            print(f"  ❌ Failed row {idx} ({deal_name}): {e}")
            time.sleep(1)

    print(f"\n✅ Deals import complete: {success} success, {fail} failed")
    print(f"📋 Board ID: {board_id}")
    print(f"👉 Add this to your .env: MONDAY_DEALS_BOARD_ID={board_id}")
    return board_id

# ----------------- Import Work Orders -----------------
def import_work_orders():
    print("\n📊 Reading Work Orders Excel file...")
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), '..', 'data', 'Work_Order_Tracker_Data.xlsx'), header=1)
    df.columns = df.columns.str.strip()
    print(f"  Found {len(df)} work orders with columns: {list(df.columns)[:10]}...")

    print("\n🏗️ Creating Work Orders board on Monday.com...")
    board_id = create_board("Work Orders Tracker - Skylark BI")
    print(f"  Board created: ID={board_id}")

    print("\n📐 Creating columns...")
    cols = {}
    col_map = [
        ("Customer Code", "text"),
        ("Serial Number", "text"),
        ("Nature of Work", "text"),
        ("Execution Status", "status"),
        ("Data Delivery Date", "date"),
        ("Date of PO/LOI", "date"),
        ("Document Type", "text"),
        ("Probable Start Date", "date"),
        ("Probable End Date", "date"),
        ("BD Personnel Code", "text"),
        ("Sector", "text"),
        ("Type of Work", "text"),
        ("Skylark Software", "text"),
        ("Amount Excl GST", "numbers"),
        ("Amount Incl GST", "numbers"),
        ("Billed Value Excl GST", "numbers"),
        ("Billed Value Incl GST", "numbers"),
        ("Collected Amount", "numbers"),
        ("Amount Receivable", "numbers"),
        ("WO Status", "status"),
        ("Invoice Status", "text"),
        ("Collection Status", "text"),
        ("Billing Status", "text"),
        ("Expected Billing Month", "text"),
        ("Actual Billing Month", "text"),
    ]
    for title, col_type in col_map:
        try:
            cols[title] = create_column(board_id, title, col_type)
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️ Failed to create column {title}: {e}")

    print(f"\n⬆️ Importing {len(df)} work orders...")
    success, fail = 0, 0

    status_map = {
        "Open": "Working on it",
        "On Hold": "Stuck",
        "Closed": "Done",
        "Completed": "Done",
        "In Progress": "Working on it",
        "Dead": "Stuck"
    }

    field_map = {
        "Customer Code": ("Customer Name Code", safe_str),
        "Serial Number": ("Serial #", safe_str),
        "Nature of Work": ("Nature of Work", safe_str),
        "BD Personnel Code": ("BD/KAM Personnel code", safe_str),
        "Sector": ("Sector", safe_str),
        "Type of Work": ("Type of Work", safe_str),
        "Skylark Software": ("Is any Skylark software platform part of the client deliverables in this deal?", safe_str),
        "Invoice Status": ("Invoice Status", safe_str),
        "Collection Status": ("Collection status", safe_str),
        "Billing Status": ("Billing Status", safe_str),
        "Expected Billing Month": ("Expected Billing Month", safe_str),
        "Actual Billing Month": ("Actual Billing Month", safe_str),
        "Document Type": ("Document Type", safe_str),
        "Amount Excl GST": ("Amount in Rupees (Excl of GST) (Masked)", safe_num),
        "Amount Incl GST": ("Amount in Rupees (Incl of GST) (Masked)", safe_num),
        "Billed Value Excl GST": ("Billed Value in Rupees (Excl of GST.) (Masked)", safe_num),
        "Billed Value Incl GST": ("Billed Value in Rupees (Incl of GST.) (Masked)", safe_num),
        "Collected Amount": ("Collected Amount in Rupees (Incl of GST.) (Masked)", safe_num),
        "Amount Receivable": ("Amount Receivable (Masked)", safe_num),
        "Data Delivery Date": ("Data Delivery Date", safe_date),
        "Date of PO/LOI": ("Date of PO/LOI", safe_date),
        "Probable Start Date": ("Probable Start Date", safe_date),
        "Probable End Date": ("Probable End Date", safe_date),
    }

    for idx, row in df.iterrows():
        wo_name = safe_str(row.get("Deal name masked", f"WO_{idx}"))
        column_values = {}

        for col_title, (excel_col, transform) in field_map.items():
            if col_title not in cols:
                continue
            val = row.get(excel_col)
            transformed = transform(val)
            if transformed is None or transformed == "":
                continue
            column_values[cols[col_title]] = transformed

        exec_status = safe_str(row.get("Execution Status"))
        if exec_status and "Execution Status" in cols:
            column_values[cols["Execution Status"]] = {"label": status_map.get(exec_status, "Working on it")}

        wo_status = safe_str(row.get("WO Status (billed)"))
        if wo_status and "WO Status" in cols:
            column_values[cols["WO Status"]] = {"label": status_map.get(wo_status, "Working on it")}

        try:
            create_item(board_id, wo_name, column_values)
            success += 1
            if success % 20 == 0:
                print(f"  Progress: {success}/{len(df)}")
            time.sleep(0.5)
        except Exception as e:
            fail += 1
            print(f"  ❌ Failed row {idx} ({wo_name}): {e}")
            time.sleep(1)

    print(f"\n✅ Work Orders import complete: {success} success, {fail} failed")
    print(f"📋 Board ID: {board_id}")
    print(f"👉 Add this to your .env: MONDAY_WORKORDERS_BOARD_ID={board_id}")
    return board_id

# ----------------- Main -----------------
if __name__ == "__main__":
    if not MONDAY_API_TOKEN:
        print("❌ MONDAY_API_TOKEN not set in .env file!")
        exit(1)

    print("="*60)
    print("Monday.com Data Import Script - Skylark Drones BI Agent")
    print("="*60)

    deals_board_id = import_deals()
    print("\n" + "="*60)
    work_orders_board_id = import_work_orders()

    print("\n" + "="*60)
    print("✅ ALL DONE! Add these to your .env file:")
    print(f"MONDAY_DEALS_BOARD_ID={deals_board_id}")
    print(f"MONDAY_WORKORDERS_BOARD_ID={work_orders_board_id}")
    print("="*60)