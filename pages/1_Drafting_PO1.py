import streamlit as st
from docxtpl import DocxTemplate
from pypdf import PdfReader
import io
import os
from groq import Groq
import json

# 1. Page Config (Must be the first Streamlit command)
st.set_page_config(page_title="ArbOS: PO1 Generator", layout="wide")

# --- 🔒 THE BOUNCER (SECURITY CHECK) ---
# Initialize user_role if it doesn't exist (e.g., if they skipped the login page)
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None

# Check ID Card
if st.session_state['user_role'] != 'arbitrator':
    st.error("⛔ ACCESS DENIED: This tool is restricted to the Tribunal.")
    st.info("Please log in as an Arbitrator to access the Drafting Engine.")
    st.stop()  # <--- Hails the script here. No code below this line runs.
# ---------------------------------------

st.title("ArbOS: PO1 Generator")
st.caption("The Librarian Mode: Extracting complex data from your report.")

# 2. Auth (Looking for secrets in .streamlit/secrets.toml)
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Missing API Key. Check your .streamlit/secrets.toml file.")
    st.stop()

# 3. Input
uploaded_file = st.file_uploader("Upload Preliminary Meeting Report (PDF)", type="pdf")

# Default values
extracted_data = {}

if uploaded_file:
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    
    st.info("Librarian is reading the report... This may take a few seconds.")

    # 4. The Librarian (Extracting Data)
    prompt = f"""
    You are a legal assistant. Read these meeting notes and extract the following details.
    
    Return ONLY a JSON object with these exact keys:
    - meeting_date (e.g., "15 January 2026")
    - claimant_rep_1 (Name of first lawyer for claimant)
    - claimant_rep_2 (Name of second lawyer, or "" if none)
    - respondent_rep_1 (Name of first lawyer for respondent)
    - respondent_rep_2 (Name of second lawyer, or "" if none)
    - claimant_contact (Email/Address summary)
    - respondent_contact (Email/Address summary)
    - arbitrator_contact (Email/Address of presiding arbitrator)
    
    Meeting Notes:
    {text}
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile", 
            response_format={"type": "json_object"}
        )
        extracted_data = json.loads(chat_completion.choices[0].message.content)
        st.success("Data successfully extracted!")
    except Exception as e:
        st.error(f"AI Reading Error: {e}")

# 5. The Arbitrator's Dashboard (Review & Edit)
st.divider()
st.subheader("Review Extracted Data")

with st.form("drafting_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**General Info**")
        meeting_date = st.text_input("Meeting Date", value=extracted_data.get("meeting_date", ""))
        confirmation_period = st.text_input("Confirmation Period", value="14 days")
        timetable_text = st.text_area("Procedural Timetable Clause", value="The procedural timetable is set forth in Annex A.")

        st.markdown("**Claimant Info**")
        claimant_rep_1 = st.text_input("Claimant Rep 1", value=extracted_data.get("claimant_rep_1", ""))
        claimant_rep_2 = st.text_input("Claimant Rep 2", value=extracted_data.get("claimant_rep_2", ""))
        claimant_contact = st.text_input("Claimant Contact", value=extracted_data.get("claimant_contact", ""))

    with col2:
        st.markdown("**Respondent Info**")
        respondent_rep_1 = st.text_input("Respondent Rep 1", value=extracted_data.get("respondent_rep_1", ""))
        respondent_rep_2 = st.text_input("Respondent Rep 2", value=extracted_data.get("respondent_rep_2", ""))
        respondent_contact = st.text_input("Respondent Contact", value=extracted_data.get("respondent_contact", ""))
        
        st.markdown("**Tribunal Info**")
        arbitrator_contact = st.text_input("Presiding Arbitrator Contact", value=extracted_data.get("arbitrator_contact", ""))

    submitted = st.form_submit_button("Generate Final PO1")

# 6. The Printer (Docxtpl)
if submitted:
    try:
        # Load the template (looking in the main folder)
        doc = DocxTemplate("template_po1.docx")
        
        context = {
            "meeting_date": meeting_date,
            "claimant_rep_1": claimant_rep_1,
            "claimant_rep_2": claimant_rep_2,
            "respondent_rep_1": respondent_rep_1,
            "respondent_rep_2": respondent_rep_2,
            "Procedural_timetable": timetable_text,
            "Contact_details_of_Claimant": claimant_contact,
            "Contact_details_of_Respondent": respondent_contact,
            "Contact_details_of_the_Presiding_Arbitrator": arbitrator_contact,
            "Tribunal_confirmation_period": confirmation_period
        }
        
        doc.render(context)
        
        bio = io.BytesIO()
        doc.save(bio)
        
        st.download_button(
            label="Download Completed PO1",
            data=bio.getvalue(),
            file_name="PO1_Generated.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        st.balloons()
        
    except Exception as e:
        st.error(f"Error: {e}")
