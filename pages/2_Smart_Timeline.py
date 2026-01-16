import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. CONFIGURATION
st.set_page_config(page_title="ArbOS: Smart Timeline", layout="wide")

if 'user_role' not in st.session_state or st.session_state['user_role'] is None:
    st.error("⛔ ACCESS DENIED: Please log in first.")
    st.stop()

# 2. DATABASE FUNCTIONS
def get_timeline():
    conn = st.connection("gsheets", type=GSheetsConnection)
    return conn.read(worksheet="Timeline", ttl=0)

def get_submissions():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Submissions", ttl=0)
        expected_cols = ['party', 'doc_type', 'summary', 'proposed_date', 'status', 'target_event']
        # Add missing cols if they don't exist yet
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        return df
    except:
        return pd.DataFrame(columns=['party', 'doc_type', 'summary', 'proposed_date', 'status', 'target_event'])

def add_submission(party, doc_type, summary, proposed_date, target_event):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = get_submissions()
    
    new_row = pd.DataFrame([{
        "party": party,
        "doc_type": doc_type,
        "summary": summary,
        "proposed_date": proposed_date,
        "status": "Pending",
        "target_event": target_event
    }])
    
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="Submissions", data=updated_df)

def update_timeline_event(event_name, new_date_str):
    """Updates the official timeline dynamically"""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Timeline", ttl=0)
    
    # Precise Match Update
    mask = df['event'] == event_name
    if mask.any():
        df.loc[mask, 'date'] = new_date_str
        df.loc[mask, 'status'] = 'Rescheduled'
        conn.update(worksheet="Timeline", data=df)
        return True
    return False

def update_submission_status(index, new_status):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = get_submissions()
    df.at[index, 'status'] = new_status
    conn.update(worksheet="Submissions", data=df)

# --- VISUALIZATION ENGINE (FIXED) ---
def render_timeline(df):
    # 1. Clean Data strictly
    if df.empty or 'date' not in df.columns:
        st.info("ℹ️ No timeline data available.")
        return

    # Force conversion to datetime, turning errors (like 'Pending') into NaT
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Remove rows where date is missing/invalid so graph doesn't break
    df = df.dropna(subset=['date'])
    
    if df.empty:
        st.warning("⚠️ Timeline data exists but dates are invalid.")
        return

    # 2. Visual Width (Events take 10 days visually)
    df['finish'] = df['date'] + timedelta(days=10)
    df = df.sort_values(by="date", ascending=False)

    # 3. Colors
    color_map = {
        "Tribunal": "#2C3E50",    # Navy Blue
        "Claimant": "#E74C3C",    # Red
        "Respondent": "#F39C12",  # Orange
        "All": "#7F8C8D"          # Gray
    }

    # 4. Generate Chart
    fig = px.timeline(
        df, 
        x_start="date", 
        x_end="finish", 
        y="event", 
        color="owner",
        title=None,
        color_discrete_map=color_map,
        hover_data={"date": "|%B %d, %Y", "finish": False}
    )

    # --- THE FIX IS HERE ---
    # We calculate Today as a timestamp to avoid type errors
    today_val = pd.Timestamp("today")
    
    # Draw the line (WITHOUT text, to prevent calculation crash)
    fig.add_vline(x=today_val, line_width=2, line_dash="dot", line_color="green")
    
    # Draw the text label separately (Manually positioned)
    fig.add_annotation(
        x=today_val, 
        y=1.05,             # Position slightly above the graph area
        yref="paper",       # Use relative coordinates for Y (0=bottom, 1=top)
        text="Today", 
        showarrow=False, 
        font=dict(color="green", size=12)
    )

    fig.update_layout(
        xaxis_title="",
        yaxis_title="",
        legend_title="Responsible Party",
        height=400,
        margin=dict(l=0, r=0, t=4
