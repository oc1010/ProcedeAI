import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="ArbOS Login", layout="centered")

# --- DATABASE FUNCTIONS (REAL) ---
def get_db_connection():
    # Establishes the connection using the secrets you just set up
    return st.connection("gsheets", type=GSheetsConnection)

def fetch_users():
    conn = get_db_connection()
    # Read the 'Users' worksheet. ttl=0 means "don't cache, always get fresh data"
    try:
        df = conn.read(worksheet="Users", ttl=0)
        return df
    except Exception:
        # If the sheet is empty or fails, return an empty dataframe structure
        return pd.DataFrame(columns=["username", "name", "password", "role"])

def create_user(username, name, password, role):
    conn = get_db_connection()
    df = fetch_users()
    
    # Check if username exists
    if not df.empty and username in df['username'].values:
        return False # User already exists
    
    # Create new row
    new_user = pd.DataFrame([{
        "username": username,
        "name": name,
        "password": password, # In production, HASH this!
        "role": role
    }])
    
    # Add to existing data
    updated_df = pd.concat([df, new_user], ignore_index=True)
    
    # Update Google Sheet
    conn.update(worksheet="Users", data=updated_df)
    return True

def verify_user(username, password):
    df = fetch_users()
    if df.empty:
        return None
        
    # Filter for the username
    user_row = df[df['username'] == username]
    
    if not user_row.empty:
        stored_password = user_row.iloc[0]['password']
        # Convert both to string to be safe
        if str(stored_password) == str(password):
            return user_row.iloc[0] # Return the user data
    return None

# --- UI LAYOUT ---
st.title("⚖️ ArbOS: Secure Access")

# Initialize Session State
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = None
if 'user_name' not in st.session_state:
    st.session_state['user_name'] = ""

# --- LOGGED IN VIEW ---
if st.session_state['logged_in']:
    st.success(f"Welcome back, {st.session_state['user_name']}!")
    
    # Sidebar Info
    with st.sidebar:
        st.write(f"Logged in as: **{str(st.session_state['user_role']).upper()}**")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['user_role'] = None
            st.rerun()

    # ROUTING: Show different screens based on Role
    st.divider()
    
    if st.session_state['user_role'] == 'arbitrator':
        st.info("ACCESS LEVEL: TRIBUNAL (Full Control)")
        st.markdown("### 🛠️ Tribunal Dashboard")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 📝 Drafting")
            st.write("Generate procedural orders.")
            st.page_link("pages/1_Drafting_PO1.py", label="Open Drafting Engine", icon="⚖️")
            
        with col2:
            st.markdown("#### 📅 Timeline")
            st.write("Manage deadlines and extensions.")
            # Note: We will build this page next!
            st.button("Manage Timeline (Coming Soon)", disabled=True)

    else:
        st.warning(f"ACCESS LEVEL: PARTY ({str(st.session_state['user_role']).upper()})")
        st.write("You have read-only access to official orders. You may request timeline extensions below.")
        
        st.markdown("#### 📅 Case Status")
        # Note: We will build this page next!
        st.button("View Timeline (Coming Soon)", disabled=True)

# --- LOGIN / SIGNUP VIEW ---
else:
    tab1, tab2 = st.tabs(["🔒 Login", "✍️ Sign Up"])

    # LOGIN TAB
    with tab1:
        st.write("Please sign in to access the case files.")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Enter")
            
            if submit_login:
                if not username or not password:
                    st.warning("Please enter both username and password.")
                else:
                    with st.spinner("Verifying credentials..."):
                        user = verify_user(username, password)
                        if user is not None:
                            st.session_state['logged_in'] = True
                            st.session_state['user_role'] = user['role']
                            st.session_state['user_name'] = user['name']
                            st.toast("Login Successful!", icon="✅")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("Incorrect username or password")

    # SIGN UP TAB
    with tab2:
        st.markdown("### Create New Account")
        with st.form("signup_form"):
            new_user = st.text_input("Choose a Username")
            new_name = st.text_input("Full Name (e.g. 'Counsel for Claimant')")
            new_pass = st.text_input("Choose a Password", type="password")
            new_role = st.selectbox("I am a...", ["claimant", "respondent", "arbitrator"]) 
            # Added 'arbitrator' here for your testing, but usually we hide it!
            
            submit_signup = st.form_submit_button("Create Account")
            
            if submit_signup:
                if new_user and new_pass:
                    with st.spinner("Creating account in cloud database..."):
                        success = create_user(new_user, new_name, new_pass, new_role)
                        if success:
                            st.success("Account created! Please switch to the Login tab.")
                        else:
                            st.error("Username already taken.")
                else:
                    st.warning("Please fill in all fields.")
