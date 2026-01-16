import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# 1. CONFIGURATION (Must be the first command)
st.set_page_config(page_title="ArbOS: Procedural History", layout="wide")

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
        expected_cols = ['party', 'doc_type', 'summary', 'proposed_date', 'status', 'target_event', 'decision_reason', 'decision_date']
        # Add missing cols if they don't exist yet
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        return df
    except:
        return pd.DataFrame(columns=['party', 'doc_type', 'summary', 'proposed_date', 'status', 'target_event', 'decision_reason', 'decision_date'])

def add_submission(party, doc_type, summary, proposed_date, target_event):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = get_submissions()
    
    new_row = pd.DataFrame([{
        "party": party,
        "doc_type": doc_type,
        "summary": summary,
        "proposed_date": proposed_date,
        "status": "Pending",
        "target_event": target_event,
        "decision_reason": "",
        "decision_date": ""
    }])
    
    updated_df = pd.concat([df, new_row], ignore_index=True)
    conn.update(worksheet="Submissions", data=updated_df)

def process_decision(index, status, reason, event_name, new_date_str):
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 1. Update Log
    subs_df = get_submissions()
    subs_df.at[index, 'status'] = status
    subs_df.at[index, 'decision_reason'] = reason
    subs_df.at[index, 'decision_date'] = datetime.now().strftime("%Y-%m-%d")
    conn.update(worksheet="Submissions", data=subs_df)
    
    # 2. Update Timeline (Only if Approved)
    if status == "Approved":
        timeline_df = conn.read(worksheet="Timeline", ttl=0)
        mask = timeline_df['event'] == event_name
        if mask.any():
            timeline_df.loc[mask, 'date'] = new_date_str
            timeline_df.loc[mask, 'status'] = 'Rescheduled'
            conn.update(worksheet="Timeline", data=timeline_df)

# --- VISUALIZATION: THE "VARIABLE STALK" TIMELINE (Přehledný) ---
def render_horizontal_timeline(df):
    if df.empty or 'date' not in df.columns:
        st.info("No schedule available.")
        return

    # 1. Prepare Data
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date']).sort_values(by="date")
    
    # 2. Smart Staggering Logic
    # Creates different heights for labels to prevent overlapping
    stagger_levels = [0.8, -0.8, 1.4, -1.4, 0.4, -0.4]
    df['y_pos'] = [stagger_levels[i % len(stagger_levels)] for i in range(len(df))]
    
    # 3. Colors
    color_map = {"Tribunal": "#2C3E50", "Claimant": "#E74C3C", "Respondent": "#F39C12", "All": "#95a5a6"}
    df['color'] = df['owner'].map(color_map).fillna("grey")

    fig = go.Figure()

    # A. The Time Axis (Gray Line)
    fig.add_trace(go.Scatter(
        x=[df['date'].min(), df['date'].max()], 
        y=[0, 0],
        mode="lines",
        line=dict(color="lightgray", width=3),
        hoverinfo="skip"
    ))

    # B. The Milestones (Dots on the line)
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=[0] * len(df),
        mode="markers",
        marker=dict(size=12, color=df['color'], line=dict(width=2, color="white")),
        hoverinfo="skip"
    ))

    # C. The Stalks and Labels (The Zipper)
    for _, row in df.iterrows():
        # Format the date nicely (e.g., "12 May")
        date_str = row['date'].strftime("%d %b")
        
        # Draw the line (stalk)
        fig.add_trace(go.Scatter(
            x=[row['date'], row['date']],
            y=[0, row['y_pos']],
            mode="lines",
            line=dict(color=row['color'], width=1),
            hoverinfo="skip",
            showlegend=False
        ))
        
        # Draw the Text Label (Event + Date)
        fig.add_trace(go.Scatter(
            x=[row['date']],
            y=[row['y_pos']],
            mode="text",
            text=[f"<b>{row['event']}</b><br><span style='font-size:10px; color:gray;'>{date_str}</span>"],
            textposition="top center" if row['y_pos'] > 0 else "bottom center",
            textfont=dict(size=11),
            hoverinfo="text",
            hovertext=f"Owner: {row['owner']}<br>Status: {row['status']}",
            showlegend=False
        ))

    # D. "Today" Indicator
    today_val = pd.Timestamp("today")
    fig.add_vline(x=today_val, line_width=1, line_dash="dash", line_color="green")
    fig.add_annotation(x=today_val, y=0, text="TODAY", showarrow=True, arrowhead=2, arrowcolor="green", ax=0, ay=-20, font=dict(color="green", size=10))

    # Clean Layout
    fig.update_layout(
        height=400, # Taller to accommodate the staggered labels
        yaxis=dict(
            range=[-2, 2], # More vertical space
            showgrid=False, 
            zeroline=False, 
            showticklabels=False,
            fixedrange=True
        ),
        xaxis=dict(
            showgrid=False, # Hide vertical gridlines for cleaner look
            zeroline=False,
            showticklabels=True, # Keep dates at bottom just in case
            side="bottom"
        ),
        margin=dict(l=10, r=10, t=20, b=20),
        plot_bgcolor="white",
        showlegend=False
    )

    st.plotly_chart(fig, use_container_width=True)

# --- MAIN APP UI ---
st.title("⚖️ Case Management Console")
st.caption(f"Logged in as: {st.session_state['user_role'].upper()}")

# TABS
tab_schedule, tab_history, tab_actions = st.tabs(["📅 Timeline View", "📜 Procedural Log", "⚡ Actions"])

# --- TAB 1: VISUALS ---
with tab_schedule:
    df_timeline = get_timeline()
    render_horizontal_timeline(df_timeline)
    
    # Simple list below for detail
    with st.expander("View as List"):
        st.dataframe(
            df_timeline[['date', 'event', 'owner', 'status']].sort_values(by='date'),
            use_container_width=True,
            hide_index=True
        )

# --- TAB 2: HISTORY ---
with tab_history:
    st.header("📜 Procedural History")
    df_log = get_submissions()
    
    if not df_log.empty:
        history = df_log[df_log['status'].isin(['Approved', 'Rejected'])]
        if history.empty:
            st.info("No historical decisions yet.")
        else:
            for _, row in history.iterrows():
                # Color code status
                status_color = "🟢" if row['status'] == "Approved" else "🔴"
                with st.expander(f"{status_color} {row['decision_date']}: {row['doc_type']}"):
                    st.markdown(f"**Party:** {row['party']} | **Event:** {row['target_event']}")
                    st.write(f"**Request:** {row['summary']}")
                    st.divider()
                    st.markdown(f"**Tribunal Reasoning:**")
                    st.info(row['decision_reason'])
    else:
        st.info("Log is empty.")

# --- TAB 3: ACTIONS ---
with tab_actions:
    if st.session_state['user_role'] == 'arbitrator':
        st.header("👨‍⚖️ Tribunal Chambers")
        
        subs_df = get_submissions()
        pending = subs_df[subs_df['status'] == 'Pending'] if not subs_df.empty else pd.DataFrame()
        
        if pending.empty:
            st.success("✅ Inbox Zero. No pending procedural requests.")
        else:
            st.write(f"You have **{len(pending)}** pending request(s).")
            
            # Selector
            req_options = {f"{i}: {row['party']} - {row['target_event']}": i for i, row in pending.iterrows()}
            selected_label = st.selectbox("Select Request to Adjudicate", list(req_options.keys()))
            selected_index = req_options[selected_label]
            
            row = pending.loc[selected_index]
            
            with st.container(border=True):
                st.markdown(f"**Motion to Reschedule '{row['target_event']}'**")
                st.write(f"**Proposed Date:** {row['proposed_date']}")
                st.write(f"**Argument:** {row['summary']}")
            
            # Decision Form
            with st.form("decision_form"):
                st.subheader("📝 Issue Procedural Order")
                decision_reason = st.text_area("Tribunal's Reasoning", placeholder="The Tribunal grants the request because...")
                
                c1, c2 = st.columns(2)
                with c1:
                    approve = st.form_submit_button("✅ APPROVE & Update Timeline")
                with c2:
                    reject = st.form_submit_button("❌ REJECT & Maintain Schedule")
                
                if approve:
                    if not decision_reason:
                        st.error("Reasoning required for the record.")
                    else:
                        process_decision(selected_index, "Approved", decision_reason, row['target_event'], row['proposed_date'])
                        st.success("Order Issued: Timeline Updated.")
                        st.rerun()
                        
                if reject:
                    if not decision_reason:
                        st.error("Reasoning required for the record.")
                    else:
                        process_decision(selected_index, "Rejected", decision_reason, row['target_event'], row['proposed_date'])
                        st.error("Order Issued: Request Denied.")
                        st.rerun()

    else:
        # PARTY VIEW
        st.header("📤 File Procedural Application")
        df_timeline = get_timeline()
        
        with st.form("request_form"):
            c1, c2 = st.columns(2)
            with c1:
                event_options = df_timeline['event'].unique() if not df_timeline.empty and 'event' in df_timeline.columns else []
                target = st.selectbox("Target Event", event_options)
                new_date = st.date_input("Proposed New Date")
            with c2:
                reason = st.text_area("Grounds for Application", placeholder="Explain why the extension is necessary...")
                
            if st.form_submit_button("🚀 Submit Application"):
                if target:
                    add_submission(
                        party=st.session_state['user_role'],
                        doc_type="Extension Request",
                        summary=reason,
                        proposed_date=str(new_date),
                        target_event=target
                    )
                    st.success("Application filed.")
                else:
                    st.error("Error: Timeline data unavailable.")
