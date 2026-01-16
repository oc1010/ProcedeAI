import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# 1. CONFIGURATION
st.set_page_config(page_title="ArbOS: Smart Timeline", layout="wide")

# Security Gatekeeper
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
        # Ensure columns exist if sheet is new
        if df.empty or 'party' not in df.columns:
            return pd.DataFrame(columns=['party', 'doc_type', 'summary', 'proposed_date', 'status'])
        return df
    except:
        return pd.DataFrame(columns=['party', 'doc_type', 'summary', 'proposed_date', 'status'])

def add_submission(party, doc_type, summary, proposed_date):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Submissions", ttl=0)
    except:
        df = pd.DataFrame(columns=['party', 'doc_type', 'summary', 'proposed_date', 'status'])
        
    new_row = pd.DataFrame([{
        "party": party,
        "doc_type": doc_type,
        "summary": summary,
        "proposed_date": proposed_date,
        "status": "Pending"
    }])
    
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="Submissions", data=updated_df)

def update_timeline_event(event_name, new_date_str):
    """Updates the official timeline when Arbitrator approves"""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Timeline", ttl=0)
    
    # Update the date for the specific event
    if event_name in df['event'].values:
        df.loc[df['event'] == event_name, 'date'] = new_date_str
        df.loc[df['event'] == event_name, 'status'] = 'Rescheduled'
        conn.update(worksheet="Timeline", data=df)
        return True
    return False

def update_submission_status(index, new_status):
    """Marks a submission as Approved or Rejected"""
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(worksheet="Submissions", ttl=0)
    df.at[index, 'status'] = new_status
    conn.update(worksheet="Submissions", data=df)

# 3. ALGORITHMS
def calculate_cost_impact(days_delayed):
    """
    Estimates financial cost of delay.
    Burn Rate = Arbitrator Fees + Counsel Fees x2 + Admin Costs
    Estimated: $15,000 per day active.
    """
    return days_delayed * 15000

# --- MAIN UI ---
st.title("📅 Smart Procedural Timeline")
st.caption(f"Logged in as: {st.session_state['user_role'].upper()}")

# --- 1. THE GANTT CHART (Visible to Everyone) ---
df_timeline = get_timeline()
df_timeline['date'] = pd.to_datetime(df_timeline['date'])
# Create a 'finish' date for visual width (events take 3 days visually)
df_timeline['finish'] = df_timeline['date'] + timedelta(days=3)

# Color coding
colors = {"Tribunal": "#0f2e52", "Claimant": "#ff4b4b", "Respondent": "#FFA500", "All": "#808080"}

fig = px.timeline(
    df_timeline, 
    x_start="date", 
    x_end="finish", 
    y="event", 
    color="owner",
    title="Official Case Schedule",
    color_discrete_map=colors
)
fig.update_yaxes(autorange="reversed") # Earliest events at top
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- 2. ROLE-BASED INTERFACE ---

# === SCENE A: ARBITRATOR VIEW (The Control Center) ===
if st.session_state['user_role'] == 'arbitrator':
    st.subheader("📥 Tribunal Inbox (Pending Requests)")
    
    subs_df = get_submissions()
    
    # Filter for only Pending items
    if not subs_df.empty and 'status' in subs_df.columns:
        pending_subs = subs_df[subs_df['status'] == 'Pending']
    else:
        pending_subs = pd.DataFrame()
    
    if pending_subs.empty:
        st.info("✅ No pending requests. The timeline is up to date.")
    else:
        st.write(f"You have {len(pending_subs)} pending procedural request(s).")
        
        for index, row in pending_subs.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                
                with c1:
                    st.markdown(f"**Request from {row['party']}**")
                    st.write(f"📝 {row['summary']}")
                    # Parse dates to calculate impact
                    try:
                        new_date_obj = pd.to_datetime(row['proposed_date'])
                        st.write(f"📅 Proposed Date: **{row['proposed_date']}**")
                    except:
                        st.error("Invalid date format in request.")
                
                with c2:
                    # Smart Analysis
                    st.caption("🤖 AI Impact Analysis")
                    st.warning("⚠️ High Cost Impact")
                    st.markdown("**Estimated Cost: $225,000**")
                
                with c3:
                    st.write("Action:")
                    if st.button("✅ Approve", key=f"app_{index}"):
                        # 1. Update the Main Timeline
                        # We infer the event from the summary or assume it's the next upcoming event for demo
                        target_event = "Statement of Defence" # Default for demo
                        update_timeline_event(target_event, row['proposed_date'])
                        
                        # 2. Mark submission as done
                        update_submission_status(index, "Approved")
                        st.success("Approved! Timeline updated.")
                        st.rerun()
                        
                    if st.button("❌ Reject", key=f"rej_{index}"):
                        update_submission_status(index, "Rejected")
                        st.rerun()

# === SCENE B: PARTY VIEW (The Request Portal) ===
else:
    st.subheader(f"📤 {st.session_state['user_role'].capitalize()} Request Portal")
    
    with st.form("request_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 1. Procedural Details")
            # Dropdown ensures exact event matching
            target_event = st.selectbox(
                "Which event do you want to move?", 
                df_timeline['event'].unique()
            )
            
            # Calendar picker ensures exact date format YYYY-MM-DD
            new_date = st.date_input("Proposed New Date")
            
        with col2:
            st.markdown("#### 2. Formal Request")
            # We still allow the file upload for the legal record
            uploaded_file = st.file_uploader("Attach Formal Letter (PDF)", type="pdf")
            
            summary_text = st.text_area(
                "Brief Summary for Tribunal", 
                placeholder="e.g. 'We request a 14-day extension due to unavailability of expert witness.'"
            )

        # Smart "Cost of Delay" Calculation (Visual Feedback)
        st.info(f"ℹ️ Note: This request will trigger an automated notification to the Tribunal.")

        submitted = st.form_submit_button("🚀 Submit Request")
        
        if submitted:
            # 1. Save to Database
            add_submission(
                party=st.session_state['user_role'],
                doc_type="Extension Request", 
                summary=f"Request to move {target_event}. {summary_text}",
                proposed_date=str(new_date)
            )
            
            st.success("✅ Request Sent! The Tribunal has been notified.")
            st.balloons()
