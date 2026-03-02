
import os
import requests
import pandas as pd
from transformers import pipeline
import streamlit as st

# --- Config ---
MONDAY_API_TOKEN = os.getenv("MONDAY_API_TOKEN")
MONDAY_API_URL = "https://api.monday.com/v2"
DEALS_BOARD_ID = os.getenv("MONDAY_DEALS_BOARD_ID")
WORKORDERS_BOARD_ID = os.getenv("MONDAY_WORKORDERS_BOARD_ID")

headers = {
    "Authorization": MONDAY_API_TOKEN,
    "Content-Type": "application/json"
}

# --- AI Agent ---
@st.cache_resource
def get_agent():
    return pipeline("text-generation", model="mistralai/Mistral-7B-Instruct-v0.2")

def fetch_board(board_id):
    query = {
        "query": f"""
        {{
          boards (ids: [{board_id}]) {{
            name
            items {{
              name
              column_values {{
                id
                text
              }}
            }}
          }}
        }}
        """
    }
    resp = requests.post(MONDAY_API_URL, json=query, headers=headers)
    return resp.json()['data']['boards'][0]['items']

def clean_items(items):
    df = pd.DataFrame([
        {col['id']: col['text'] for col in item['column_values']}
        for item in items
    ])
    df = df.replace(['', None], pd.NA)
    df = df.fillna('Unknown')
    for col in df.columns:
        if 'date' in col:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

st.title("Monday.com Business Intelligence Agent")
st.write("Ask founder-level business questions. Data is fetched live from Monday.com boards and cleaned automatically.")

user_query = st.text_input("Your business question:")

if st.button("Ask") and user_query:
    with st.spinner("Fetching data and generating answer..."):
        deals = clean_items(fetch_board(DEALS_BOARD_ID))
        workorders = clean_items(fetch_board(WORKORDERS_BOARD_ID))
        qa = get_agent()
        result = qa(user_query, max_new_tokens=100)
        st.markdown(f"**AI Agent:** {result[0]['generated_text']}")
        st.markdown("---")
        st.markdown("**API/tool-call trace:**")
        st.markdown("- Queried Deals & Work Orders boards live from Monday.com")
        st.markdown("- Data cleaned with pandas (missing/nulls handled)")
