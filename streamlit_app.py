"""
📄 CostOpt AI Resume & Job Fit Analyzer — Streamlit Web App
-----------------------------------------------------------
Supports Free Tier Providers:
- Google Gemini (100% Free Tier from https://aistudio.google.com)
- Ollama (Local $0.00 Free Models)
- OpenAI (gpt-4o-mini / gpt-4o)
"""

import os
import time
import streamlit as st
from openai import OpenAI
from costopt import CostOpt

# Page Config
st.set_page_config(
    page_title="CostOpt Resume Analyzer",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
    <style>
    .main { background-color: #0d1117; color: #c9d1d9; }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        color: white;
        font-weight: 600;
        border-radius: 8px;
        padding: 12px 24px;
        border: none;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3);
    }
    .stButton>button:hover { background: linear-gradient(135deg, #1d4ed8, #1e40af); }
    .metric-card {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📄 CostOpt AI Resume & Job Fit Analyzer")
st.caption("⚡ Powered by CostOpt: Drop-in LLM Caching, Smart Model Routing & Real-Time FinOps")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Provider & Model Setup")
    
    provider_choice = st.selectbox(
        "Select Provider",
        ["Google Gemini (Free Tier)", "OpenAI (gpt-4o-mini)", "Ollama (Local $0.00)"],
        index=0
    )

    if provider_choice == "Google Gemini (Free Tier)":
        st.info("💡 Get a 100% Free Gemini API key at: [aistudio.google.com](https://aistudio.google.com/app/apikey)")
        api_key_input = st.text_input("Gemini API Key", value=os.getenv("GEMINI_API_KEY", ""), type="password", help="Get a free key from https://aistudio.google.com/app/apikey (starts with AIzaSy...)")
        default_model = "gemini-1.5-flash"
    elif provider_choice == "Ollama (Local $0.00)":
        st.info("💡 Make sure Ollama is running locally (`ollama run qwen2.5:0.5b`)")
        api_key_input = "ollama-local"
        default_model = "qwen2.5:0.5b"
    else: # OpenAI
        api_key_input = st.text_input("OpenAI API Key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
        default_model = "gpt-4o-mini"
    
    dashboard_url = st.text_input("Local Dashboard URL", value="http://127.0.0.1:8400")
    st.markdown(f"[📊 Open CostOpt Console]({dashboard_url})")
    
    st.divider()
    st.subheader("💡 Why CostOpt?")
    st.markdown("""
    - ⚡ **Local Cache**: <15ms replay on identical resumes ($0.00 cost)
    - 🔀 **Smart Routing**: Reroutes queries to cost-effective models
    - 🏷️ **Feature Spend**: Tracks costs by feature tag
    - 🛡️ **Circuit Breaker**: Stops runaway API billing loops
    """)

# Main Input Section
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. Upload or Paste Resume")
    uploaded_file = st.file_uploader("Drop your resume file (.txt or .pdf)", type=["txt", "pdf"])
    
    resume_text = ""
    if uploaded_file is not None:
        if uploaded_file.name.endswith(".pdf"):
            try:
                import pypdf
                reader = pypdf.PdfReader(uploaded_file)
                resume_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
            except Exception:
                resume_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
        else:
            resume_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
    
    resume_input = st.text_area(
        "Or paste resume content directly:",
        value=resume_text,
        height=280,
        placeholder="Paste your skills, experience, and education here..."
    )

with col2:
    st.subheader("2. Target Job Role")
    job_role = st.text_input(
        "Job Title / Role Description",
        value="Senior Full-Stack AI Engineer",
        placeholder="e.g. Lead Machine Learning Engineer / DevOps Lead"
    )
    
    st.markdown("### 🚀 Trigger Analysis")
    analyze_btn = st.button("✨ Analyze Resume with CostOpt", use_container_width=True)

# Processing Logic
if analyze_btn:
    if not resume_input.strip():
        st.error("❌ Please upload or paste your resume content before analyzing.")
    else:
        active_key = api_key_input.strip()
        
        # Configure client based on provider selection
        if provider_choice == "Google Gemini (Free Tier)":
            if not active_key:
                st.error("❌ Please enter your free Gemini API key from https://aistudio.google.com/app/apikey")
                st.stop()
            if not active_key.startswith("AIzaSy"):
                st.warning("⚠️ Notice: Valid Google AI Studio API keys start with `AIzaSy...`. If you hit an error, verify your key at https://aistudio.google.com/app/apikey")
            raw_client = OpenAI(
                api_key=active_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            target_provider = "google"
        elif provider_choice == "Ollama (Local $0.00)":
            raw_client = OpenAI(
                api_key="ollama",
                base_url="http://localhost:11434/v1"
            )
            target_provider = "ollama"
        else:
            if not active_key:
                st.error("❌ Please enter your OpenAI API key.")
                st.stop()
            raw_client = OpenAI(api_key=active_key)
            target_provider = "openai"

        # 1-Line Drop-in CostOpt Integration!
        client = CostOpt(raw_client, provider=target_provider)

        st.divider()
        st.subheader("📊 Analysis Results & CostOpt Intelligence")
        
        progress_bar = st.progress(0, text="Initializing CostOpt Engine...")

        # Feature 1: Strengths Extraction
        progress_bar.progress(25, text="Extracting Technical Strengths...")
        t0 = time.time()
        try:
            res1 = client.chat.completions.create(
                model=default_model,
                messages=[
                    {"role": "system", "content": "Extract 3 key technical strengths from the candidate resume."},
                    {"role": "user", "content": f"Resume:\n{resume_input}"}
                ]
            )
            out1 = res1.choices[0].message.content.strip()
            lat1 = int((time.time() - t0) * 1000)
            mod1 = getattr(res1, "model", default_model)
        except Exception as e:
            out1 = f"Error generating response: {e}"
            lat1 = int((time.time() - t0) * 1000)
            mod1 = default_model

        # Feature 2: Job Fit & Skill Gap
        progress_bar.progress(60, text="Evaluating Job Fit Score...")
        t0 = time.time()
        try:
            res2 = client.chat.completions.create(
                model=default_model,
                messages=[
                    {"role": "system", "content": f"Evaluate fit score (0-100%) and missing skills for target role: '{job_role}'."},
                    {"role": "user", "content": f"Resume:\n{resume_input}"}
                ]
            )
            out2 = res2.choices[0].message.content.strip()
            lat2 = int((time.time() - t0) * 1000)
            mod2 = getattr(res2, "model", default_model)
        except Exception as e:
            out2 = f"Error generating response: {e}"
            lat2 = int((time.time() - t0) * 1000)
            mod2 = default_model

        # Feature 3: Interview Questions
        progress_bar.progress(90, text="Generating Technical Questions...")
        t0 = time.time()
        try:
            res3 = client.chat.completions.create(
                model=default_model,
                messages=[
                    {"role": "system", "content": "Generate 2 sharp technical interview questions based on candidate experience."},
                    {"role": "user", "content": f"Resume:\n{resume_input}"}
                ]
            )
            out3 = res3.choices[0].message.content.strip()
            lat3 = int((time.time() - t0) * 1000)
            mod3 = getattr(res3, "model", default_model)
        except Exception as e:
            out3 = f"Error generating response: {e}"
            lat3 = int((time.time() - t0) * 1000)
            mod3 = default_model

        progress_bar.progress(100, text="Analysis Complete!")

        # Display Metrics Banner
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Total Latency", f"{lat1 + lat2 + lat3} ms")
        m_col2.metric("Provider Selected", provider_choice.split(" ")[0])
        m_col3.metric("Model Used", mod1)
        m_col4.metric("CostOpt Cache", "<15ms ($0.00 on re-run)")

        # Display AI Outputs
        res_tab1, res_tab2, res_tab3 = st.tabs(["📋 Core Strengths", "🎯 Job Fit & Skill Gap", "💡 Interview Questions"])
        
        with res_tab1:
            st.markdown(out1)
            st.caption(f"⚡ Feature Tag: `resume_strengths` | Model: `{mod1}` | Latency: {lat1}ms")
            
        with res_tab2:
            st.markdown(out2)
            st.caption(f"⚡ Feature Tag: `skill_gap_analysis` | Model: `{mod2}` | Latency: {lat2}ms")
            
        with res_tab3:
            st.markdown(out3)
            st.caption(f"⚡ Feature Tag: `interview_questions` | Model: `{mod3}` | Latency: {lat3}ms")

        st.success("✅ Results recorded in local CostOpt telemetry (`costopt_telemetry.db`)!")
        st.info("💡 **Tip**: Click 'Analyze Resume' again with the same content — notice how results return **instantly** via CostOpt's local cache at **$0.00 cost**!")
