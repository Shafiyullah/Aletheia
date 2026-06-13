import streamlit as st
import asyncio
import os
import json
import httpx
import time
from typing import Optional, Dict, Any

# PAGE CONFIGURATION
st.set_page_config(layout="wide", page_title="ALETHEIA: Enterprise Truth Engine", page_icon="⚖️")

# ENTERPRISE STYLING
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #c9d1d9; font-family: 'Inter', sans-serif; }
    .stSidebar { background-color: #161b22; border-right: 1px solid #30363d; }
    .stButton>button { 
        background: linear-gradient(135deg, #238636 0%, #2ea043 100%); 
        color: white; border: none; border-radius: 6px; 
        padding: 0.5rem 1rem; font-weight: 600;
    }
    .terminal-box {
        background-color: #010409; color: #3fb950;
        font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
        padding: 1rem; border: 1px solid #30363d;
        border-radius: 6px; height: 300px; overflow-y: auto;
    }
    h1, h2, h3 { color: #58a6ff; }
</style>
""", unsafe_allow_html=True)

# STATE MANAGEMENT
API_URL = os.environ.get("API_URL", "http://localhost:8000")

if "token" not in st.session_state:
    st.session_state.token = None
if "logs" not in st.session_state:
    st.session_state.logs = ["> Aletheia Enterprise Client v1.0 Initialized...", "> Awaiting Authentication..."]

def add_log(msg):
    st.session_state.logs.append(f"> {time.strftime('%H:%M:%S')} - {msg}")

# AUTHENTICATION GATEWAY
if not st.session_state.token:
    st.title("⚖️ ALETHEIA ENTERPRISE LOGIN")
    with st.form("login_form"):
        username = st.text_input("Username", value="enterprise_admin")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("LOGIN TO CLUSTER")
        
        if submitted:
            try:
                resp = httpx.post(f"{API_URL}/token", data={"username": username, "password": password})
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    add_log(f"Authenticated as {username}. Session Token secured.")
                    st.rerun()
                else:
                    st.error("Authentication Failed. Invalid Credentials.")
            except Exception as e:
                st.error(f"Cluster Connection Error: {e}")
    st.stop()

# MAIN APPLICATION INTERFACE
st.sidebar.title("🛡️ ALETHEIA CORE")
st.sidebar.info(f"Connected to: {API_URL}")
if st.sidebar.button("LOGOUT"):
    st.session_state.token = None
    st.rerun()

navigation = st.sidebar.radio("Navigation", [
    "Prometheus: Hyper-Optimize",
    "Veritas: Audit Claims",
])

# SYSTEM TELEMETRY (TERMINAL)
def render_terminal():
    st.subheader("SYSTEM TELEMETRY")
    log_content = "<br>".join(st.session_state.logs[-12:])
    st.markdown(f'<div class="terminal-box">{log_content}</div>', unsafe_allow_html=True)

headers = {"Authorization": f"Bearer {st.session_state.token}"}

if navigation == "Prometheus: Hyper-Optimize":
    st.title("🚀 PROMETHEUS // HYPER-OPTIMIZATION")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("CODE INJECTION")
        source_code = st.text_area("Paste Python Code for Formal Verification & JAX Optimization", height=300, 
                                  placeholder="def complex_calc(x):\n    return x * 2")
        
        if st.button("INITIATE ASYNC OPTIMIZATION"):
            add_log("Dispatching code to Celery Cluster...")
            try:
                resp = httpx.post(f"{API_URL}/api/v1/optimize", json={"code": source_code}, headers=headers)
                if resp.status_code == 200:
                    task_id = resp.json()["task_id"]
                    add_log(f"Task Queued: ID {task_id}")
                    
                    # Async Polling loop
                    with st.status("Solving Formal Behavioral Equivalence...", expanded=True) as status:
                        while True:
                            status.write("⏳ Polling Z3 SMT Solver status...")
                            task_resp = httpx.get(f"{API_URL}/api/v1/tasks/{task_id}", headers=headers)
                            task_data = task_resp.json()
                            
                            if task_data["status"] == "SUCCESS":
                                status.update(label="Optimization Proved & Completed!", state="complete", expanded=False)
                                add_log("Formal proof verification successful.")
                                result = json.loads(task_data["result"])
                                st.session_state.optimized_res = result
                                break
                            elif task_data["status"] == "FAILED":
                                status.update(label="Optimization Rejected.", state="error", expanded=False)
                                add_log(f"Z3 Solver error: {task_data['error']}")
                                st.error(f"Reason: {task_data['error']}")
                                break
                                
                            time.sleep(2)
                elif resp.status_code == 403:
                    st.error(f"Security Sandbox Violation: {resp.json()['detail']}")
                    add_log(f"Security BLOCK: {resp.json()['detail']}")
                else:
                    st.error(f"API Error {resp.status_code}")
            except Exception as e:
                st.error(f"Network Failure: {e}")

        if "optimized_res" in st.session_state:
            res = st.session_state.optimized_res
            st.success(f"Optimized using {res['method']}")
            st.code(res["code"], language="python")

    with col2:
        render_terminal()

elif navigation == "Veritas: Audit Claims":
    st.title("⚖️ VERITAS // TRUTH SCOPE")
    
    uploaded_file = st.file_uploader("Upload PDF Paper to Audit", type=["pdf"])
    extracted_text = "Google Research (2024) demonstrated JAX speedups."
    
    if uploaded_file is not None:
        try:
            import pypdf
            reader = pypdf.PdfReader(uploaded_file)
            extracted_text = ""
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
            st.success(f"PDF processed: {len(extracted_text)} characters extracted.")
            add_log(f"PDF processed: {uploaded_file.name}")
        except Exception as e:
            st.error(f"Error parsing PDF: {e}")
    
    claim = st.text_input("Enter Claim to Verify", value="JAX provides 100x speedup for gradient descent.")
    context = st.text_area("Source Context", value=extracted_text, height=150)
    
    if st.button("AUDIT CLAIM"):
        add_log(f"Auditing claim: {claim[:30]}...")
        try:
            resp = httpx.post(f"{API_URL}/api/v1/audit", json={"claims": [claim], "context": context}, headers=headers)
            if resp.status_code == 200:
                result = resp.json()["results"][0]
                st.json(result)
                add_log("Audit complete.")
            else:
                st.error("Audit Service Unavailable.")
        except Exception as e:
            st.error(f"Network Failure: {e}")