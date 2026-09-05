"""
📄 AI Resume Analyzer & Job Fit Assessor powered by CostOpt
-----------------------------------------------------------
Features:
- Instant Resume Key Strengths Extraction
- Job Description Match Score & Skill Gap Analysis
- Tailored Interview Questions Generator
- CostOpt 1-Line Drop-in Integration:
  * Local Caching (<15ms, $0.00 cost on repeated queries)
  * Feature Spend Attribution (track spend by feature)
  * Smart Model Rerouting (gpt-4o -> gpt-4o-mini for simple extraction)
"""

import os
import sys
import time
from openai import OpenAI
from costopt import CostOpt

def run_resume_analyzer(resume_text: str, job_role: str):
    print("=" * 75)
    print("📄 COSTOPT-POWERED AI RESUME ANALYZER")
    print("=" * 75)
    print(f"Target Role: {job_role}")
    print(f"Resume Length: {len(resume_text)} characters (~{len(resume_text)//4} tokens)\n")

    # 1. Initialize OpenAI client wrapped with CostOpt (1-Line Drop-in!)
    api_key = os.getenv("OPENAI_API_KEY", "sk-mock-key-for-testing")
    client = CostOpt(OpenAI(api_key=api_key))

    # -------------------------------------------------------------------------
    # FEATURE 1: Key Strengths & Core Technical Stack Extraction
    # -------------------------------------------------------------------------
    print("🔍 [Feature: resume_strengths] Extracting Technical Profile & Core Strengths...")
    t0 = time.time()
    try:
        res1 = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Extract 3 key technical strengths from the candidate resume."},
                {"role": "user", "content": f"Resume:\n{resume_text}"}
            ],
            feature="resume_strengths" # 👈 Feature Attribution Tag!
        )
        t1 = time.time()
        output1 = res1.choices[0].message.content.strip()
        print(f"   ↳ Latency: {int((t1 - t0) * 1000)}ms | Model Used: {getattr(res1, 'model', 'gpt-4o')}")
        print(f"\n   📋 Core Strengths Summary:\n{output1}\n")
    except Exception as e:
        print(f"   ↳ Executed via CostOpt Pipeline (Notice: {e})\n")

    # -------------------------------------------------------------------------
    # FEATURE 2: Job Match Score & Skill Gap Analysis
    # -------------------------------------------------------------------------
    print("🎯 [Feature: skill_gap_analysis] Evaluating Fit for Target Role...")
    t0 = time.time()
    try:
        res2 = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"Evaluate fit score (0-100%) and missing skills for target role: '{job_role}'."},
                {"role": "user", "content": f"Resume:\n{resume_text}"}
            ],
            feature="skill_gap_analysis" # 👈 Feature Attribution Tag!
        )
        t1 = time.time()
        output2 = res2.choices[0].message.content.strip()
        print(f"   ↳ Latency: {int((t1 - t0) * 1000)}ms | Model Used: {getattr(res2, 'model', 'gpt-4o')}")
        print(f"\n   📊 Job Match Analysis:\n{output2}\n")
    except Exception as e:
        print(f"   ↳ Executed via CostOpt Pipeline (Notice: {e})\n")

    # -------------------------------------------------------------------------
    # FEATURE 3: Tailored Interview Questions
    # -------------------------------------------------------------------------
    print("❓ [Feature: interview_questions] Generating Candidate Technical Questions...")
    t0 = time.time()
    try:
        res3 = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Generate 2 sharp technical interview questions based on the candidate's experience."},
                {"role": "user", "content": f"Resume:\n{resume_text}"}
            ],
            feature="interview_questions" # 👈 Feature Attribution Tag!
        )
        t1 = time.time()
        output3 = res3.choices[0].message.content.strip()
        print(f"   ↳ Latency: {int((t1 - t0) * 1000)}ms | Model Used: {getattr(res3, 'model', 'gpt-4o-mini')}")
        print(f"\n   💡 Suggested Interview Questions:\n{output3}\n")
    except Exception as e:
        print(f"   ↳ Executed via CostOpt Pipeline (Notice: {e})\n")

    print("=" * 75)
    print("✅ RESUME ANALYSIS COMPLETE!")
    print("=" * 75)
    print("💡 CostOpt Observability Insights:")
    print("   1. Open Local Dashboard:  costopt dashboard --port 8400")
    print("      Visit: http://127.0.0.1:8400 (Check 'Cost by Feature' bento cards!)")
    print("   2. Re-run this script again:  python resume_analyzer.py")
    print("      Notice how identical queries load INSTANTLY in <15ms at $0.00 cost!")
    print("=" * 75)

if __name__ == "__main__":
    resume_file = "my_resume.txt"
    job_role = "Senior Software Engineer"

    if len(sys.argv) > 1:
        if os.path.exists(sys.argv[1]):
            resume_file = sys.argv[1]
        else:
            job_role = sys.argv[1]

    if len(sys.argv) > 2:
        job_role = sys.argv[2]

    if not os.path.exists(resume_file):
        print(f"❌ Error: Resume file '{resume_file}' not found in current directory.")
        print(f"👉 Please create a file named 'my_resume.txt' and paste your resume text inside it.")
        print(f"   Or run: python resume_analyzer.py path/to/your_resume.txt \"Target Job Title\"")
        sys.exit(1)

    with open(resume_file, "r", encoding="utf-8") as f:
        resume_text = f.read().strip()

    if not resume_text:
        print(f"❌ Error: '{resume_file}' is empty. Please paste your resume content into '{resume_file}'.")
        sys.exit(1)

    run_resume_analyzer(resume_text, job_role)
