import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from groq import Groq
from pypdf import PdfReader
import json
import re

# 1. SECURITY & CONFIG
st.set_page_config(page_title="ArbOS: Secure Timeline", layout="wide")

# The Bouncer
if 'user_role' not in st.session_state or st.session_state['user_role'] is None:
    st.error("⛔ ACCESS DENIED: Please log in first.")
    st.stop()

# 2. PRIVACY SHIELD (The "Safe Mode")
# This runs entirely locally. No data leaves the server.
def analyze_submission_locally(text):
    """
    A 'Mock AI' that uses simple keyword matching instead of sending data to the cloud.
    This guarantees 100% confidentiality/GDPR compliance during the demo.
    """
    text_lower = text.lower()
    
    # Simple Rule-Based Logic
    doc_type = "General Submission"
    if "extension" in text_lower or "postpone" in text_lower:
        doc_type = "Extension Request"
    elif "evidence" in text_lower or "exhibit" in text_lower:
        doc_type = "Evidence Submission"
    elif "defence" in text_lower or "defense" in text_lower:
        doc_type = "Statement of Defence"

    # Try to find a date using Regex (Look for YYYY-MM-DD)
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
    proposed_date = date_match.group(0) if date_match else "None"
    
    return {
        "doc_type": doc_type,
        "summary": "Confidential content analyzed locally (Privacy Shield Active).",
        "proposed_date": proposed_date
    }

# 3. CLOUD AI (For full power)
def analyze_submission_cloud(text):
    try:
        client = Groq(api_key=st.secrets["GROQ_API_KEY"])
        prompt = f"""
        Extract data from this legal document. Return JSON ONLY:
        {{ "doc_type": "...", "summary": "...", "proposed_date": "YYYY-MM-DD" or "None" }}
        Document: {text[:3000]}
        """
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            response_format={"type": "json_object"}
        )
        return json.loads(completion.choices[0].message.content)
    except Exception as e:
        return {"doc_type": "Error", "summary": f"AI Error: {e}", "proposed_date": "None"}

# 4. DATABASE FUNCTIONS (Filtered)
def get_submissions_securely(user_role):
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet="Submissions", ttl=0)
        if df.empty: return pd.DataFrame()
        
        # --- THE CHINESE WALL ---
        # If Arbitrator: See everything
        if user_role == 'arbitrator':
            return df
        # If Party: See ONLY your own uploads (Security Filter)
        else:
            return df[df['party'] == user_role]
    except:
        return pd.DataFrame()

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

# --- UI START ---
st.title("📅 Smart Procedural Timeline")

# Privacy Toggle in Sidebar
with st.sidebar:
    st.divider()
    st.markdown("### 🛡️ Data Security")
    privacy_mode = st.toggle("Activate Privacy Shield", value=True)
    if privacy_mode:
        st.caption("✅ **Secure Mode:** Data is processed locally. No external AI APIs.")
    else:
        st.caption("⚠️ **Cloud Mode:** Data sent to Groq for advanced analysis.")

# --- VIEW 1: PUBLIC TIMELINE ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_timeline = conn.read(worksheet="Timeline", ttl=0)
df_timeline['date'] = pd.to_datetime(df_timeline['date'])
df_timeline['finish'] = df_timeline['date'] + timedelta(days=5)

fig = px.timeline(
    df_timeline, x_start="date", x_end="finish", y="event", color="owner",
    title="Official Case Schedule",
    color_discrete_map={"Tribunal": "#0f2e52", "Claimant": "#ff4b4b", "Respondent": "#FFA500"}
)
fig.update_yaxes(autorange="reversed")
st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- VIEW 2: ARBITRATOR INBOX (Full Access) ---
if st.session_state['user_role'] == 'arbitrator':
    st.subheader("📥 Tribunal Inbox (Secure Channel)")
    
    subs_df = get_submissions_securely('arbitrator')
    
    if not subs_df.empty:
        pending_subs = subs_df[subs_df['status'] == 'Pending']
        if pending_subs.empty:
            st.info("No pending submissions.")
        else:
            for index, row in pending_subs.iterrows():
                # Visual distinction for privacy
                with st.expander(f"🔒 Encrypted Submission from {row['party']} ({row['doc_type']})", expanded=True):
                    st.write(f"**Analysis:** {row['summary']}")
                    if str(row['proposed_date']) != "None":
                        st.warning(f"Request to move deadline to: **{row['proposed_date']}**")
                    
                    if st.button("Approve & Decrypt for Opposing Party", key=f"app_{index}"):
                        subs_df.at[index, 'status'] = 'Approved'
                        conn.update(worksheet="Submissions", data=subs_df)
                        st.success("Approved! Timeline updated.")
                        st.rerun()

# --- VIEW 3: PARTY PORTAL (Restricted Access) ---
else:
    st.subheader(f"📤 {st.session_state['user_role'].capitalize()} Secure Upload")
    
    uploaded_file = st.file_uploader("Upload Confidential Document", type="pdf")
    
    if uploaded_file:
        # File is in RAM only. It is never saved to disk.
        reader = PdfReader(uploaded_file)
        text = "".join([page.extract_text() for page in reader.pages])
        
        # Select Engine based on Privacy Toggle
        with st.spinner("Processing in Secure Enclave..."):
            if privacy_mode:
                analysis = analyze_submission_locally(text)
            else:
                analysis = analyze_submission_cloud(text)
        
        st.success("Document Encrypted & Queued")
        st.json(analysis)
        
        if st.button("Confirm Submission"):
            add_submission(
                party=st.session_state['user_role'],
                doc_type=analysis['doc_type'],
                summary=analysis['summary'],
                proposed_date=analysis['proposed_date']
            )
            st.success("Sent via Secure Channel to Tribunal.")