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
        df.loc[mask, 'status'] = 'Rescheduled' # Mark as changed
        conn.update(worksheet="Timeline", data=df)
        return True
    return False

def update_submission_status(index, new_status):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = get_submissions()
    df.at[index, 'status'] = new_status
    conn.update(worksheet="Submissions", data=df)

# --- VISUALIZATION ENGINE ---
def render_timeline(df):
    df['date'] = pd.to_datetime(df['date'])
    # Make bars 10 days wide visually so they are easy to click/see
    df['finish'] = df['date'] + timedelta(days=10)
    
    # Sort by date so the earliest is at the top
    df = df.sort_values(by="date", ascending=False)

    # Professional Legal Color Palette
    color_map = {
        "Tribunal": "#2C3E50",    # Navy Blue
        "Claimant": "#E74C3C",    # Red
        "Respondent": "#F39C12",  # Orange
        "All": "#7F8C8D"          # Gray
    }

    fig = px.timeline(
        df, 
        x_start="date", 
        x_end="finish", 
        y="event", 
        color="owner",
        title=None,
        color_discrete_map=color_map,
        hover_data={"date": "|%B %d, %Y", "finish": False} # Format hover date
    )

    # Add "Today" Line
    today = datetime.now().strftime("%Y-%m-%d")
    fig.add_vline(x=today, line_width=2, line_dash="dot", line_color="green", annotation_text="Today")

    # Clean "Přehledný" Layout
    fig.update_layout(
        xaxis_title="",
        yaxis_title="",
        legend_title="Responsible Party",
        height=400,
        margin=dict(l=0, r=0, t=30, b=0),
        plot_bgcolor="white",
        font=dict(family="Arial", size=12)
    )
    
    # Add borders to grid
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='#eee')
    
    st.plotly_chart(fig, use_container_width=True)

# --- MAIN APP ---
st.title("📅 Smart Procedural Timeline")

# 1. LOAD DATA
df_timeline = get_timeline()

# 2. VISUALIZATION (Split View)
# We give the Chart and the Table equal weight for clarity
tab_viz, tab_data = st.tabs(["📊 Gantt Chart", "📋 List View"])

with tab_viz:
    render_timeline(df_timeline)

with tab_data:
    # A clean, readable table sorted by date
    st.caption("Official Procedural Order No. 1 Schedule")
    display_df = df_timeline[['date', 'event', 'owner', 'status']].sort_values(by='date')
    st.dataframe(
        display_df, 
        use_container_width=True,
        column_config={
            "date": st.column_config.DateColumn("Deadline", format="DD MMM YYYY"),
            "event": "Procedural Step",
            "owner": "Party",
            "status": "Status"
        },
        hide_index=True
    )

st.divider()

# --- 3. INTERACTION AREA ---

if st.session_state['user_role'] == 'arbitrator':
    st.subheader("📥 Tribunal Action Required")
    
    subs_df = get_submissions()
    
    if not subs_df.empty:
        pending = subs_df[subs_df['status'] == 'Pending']
    else:
        pending = pd.DataFrame()
        
    if pending.empty:
        st.success("✅ All requests processed. No pending actions.")
    else:
        for index, row in pending.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{row['doc_type']}** from {row['party']}")
                    st.caption(f"Reason: {row['summary']}")
                    st.markdown(f"➡️ Move **'{row['target_event']}'** to **{row['proposed_date']}**")
                
                with c2:
                    if st.button("Approve", key=f"app_{index}", type="primary"):
                        # FIX: Use the actual target_event from the row
                        update_timeline_event(row['target_event'], row['proposed_date'])
                        update_submission_status(index, "Approved")
                        st.rerun()
                        
                    if st.button("Reject", key=f"rej_{index}"):
                        update_submission_status(index, "Rejected")
                        st.rerun()

else:
    st.subheader("📤 Request Extension")
    
    with st.form("request_form"):
        c1, c2 = st.columns(2)
        with c1:
            # Dropdown selects the EXACT event name from DB
            target = st.selectbox("Event to Reschedule", df_timeline['event'].unique())
            new_date = st.date_input("Proposed Date")
        with c2:
            reason = st.text_area("Reason for Delay", placeholder="Ex: Expert witness unavailable...")
            
        if st.form_submit_button("🚀 Submit Request"):
            add_submission(
                party=st.session_state['user_role'],
                doc_type="Extension Request",
                summary=reason,
                proposed_date=str(new_date),
                target_event=target  # SAVING THE EXACT EVENT NAME
            )
            st.success("Request submitted to Tribunal.")
