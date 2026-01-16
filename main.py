import streamlit as st

st.set_page_config(page_title="ArbOS Dashboard", layout="wide")

st.title("⚖️ ArbOS: Tribunal Dashboard")

st.markdown("""
### Welcome, Arbitrator.
Select a tool from the sidebar to begin:

* **Drafting:** Generate procedural orders using Safe AI.
* **Timeline:** (Coming Soon) Track deadlines.
""")

st.info("Status: System Online")
