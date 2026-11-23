import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from ats_matcher import match_job
from database import init_db, save_job, list_jobs, update_application
from job_collector import collect_jobs
from resume_parser import extract_resume_text

ROOT = Path(__file__).parent
SCAN_FILE = ROOT / "data" / "job_scan.json"

st.set_page_config(page_title="Supplier Quality Job Finder", page_icon="🔎", layout="wide")
st.title("🌍 Supplier Quality Job Finder")
st.caption("Global Supplier Quality vacancies • Naukri & LinkedIn integration • CV-to-JD matching")
init_db()

with st.sidebar:
    st.header("Search filters")
    regions = st.multiselect("Location", ["India", "Outside India"], default=["India", "Outside India"])
    modes = st.multiselect("Work mode", ["Remote", "Hybrid", "Onsite", "Unspecified"], default=["Remote", "Hybrid", "Onsite", "Unspecified"])
    age_filter = st.selectbox("Posting age", ["Any time", "Last 8 hours", "Last 12 hours", "Last 24 hours", "Older than 24 hours"])
    min_score = st.slider("Minimum CV match (%)", 0, 100, 30, 5)
    cv = st.file_uploader("Upload CV (PDF / DOCX / TXT)", type=["pdf", "docx", "txt"])

    st.divider()
    st.subheader("🔗 Direct Naukri & LinkedIn")
    st.markdown(
        "- [LinkedIn: Remote SQM (India)](https://linkedin.com)\n"
        "- [LinkedIn: Hybrid SQM (India)](https://linkedin.com)\n"
        "- [Naukri: Remote SQM (14 yrs)](https://naukri.com)\n"
        "- [Naukri: Supplier Dev (India)](https://naukri.com)\n"
        "- [Indeed India: Remote SQM](https://indeed.com)"
    )

resume_text = ""
if cv:
    try:
        resume_text = extract_resume_text(cv.getvalue(), cv.name)
        st.success("CV loaded.")
    except Exception as exc:
        st.error(f"CV error: {exc}")

tab_scanner, tab_manual = st.tabs(["📡 Live Job Scanner & Tracker", "📋 Paste Naukri / LinkedIn JD"])

with tab_scanner:
    left, right = st.columns(2)
    with left:
        if st.button("🔄 Scan job sources now", type="primary", use_container_width=True):
            with st.spinner("Searching Naukri, LinkedIn, Adzuna & global feeds..."):
                found, errors = collect_jobs()
                for job in found:
                    job.update(match_job(resume_text, job))
                    save_job(job)
                SCAN_FILE.parent.mkdir(exist_ok=True)
                SCAN_FILE.write_text(json.dumps({"scanned_at": datetime.now(timezone.utc).isoformat(), "jobs": found, "errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")
                st.session_state["jobs"] = found
                st.session_state["errors"] = errors
                st.success(f"Scan finished. {len(found)} relevant jobs collected.")
    with right:
        if st.button("Load latest saved scan", use_container_width=True):
            if SCAN_FILE.exists():
                payload = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
                st.session_state["jobs"] = payload.get("jobs", []) if isinstance(payload, dict) else payload
                st.session_state["errors"] = payload.get("errors", []) if isinstance(payload, dict) else []
            else:
                st.warning("No scan file found yet.")

    jobs = st.session_state.get("jobs")
    if jobs is None and SCAN_FILE.exists():
        try:
            payload = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
            jobs = payload.get("jobs", []) if isinstance(payload, dict) else payload
            st.session_state["errors"] = payload.get("errors", []) if isinstance(payload, dict) else []
        except Exception:
            jobs = []
    jobs = jobs or []

    if resume_text:
        jobs = [dict(j, **match_job(resume_text, j)) for j in jobs]

    def posted_age_hours(job):
        stamp = job.get("posted_at")
        if not stamp:
            return None
        try:
            dt = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600)
        except Exception:
            return None

    visible = []
    for job in jobs:
        loc = f"{job.get('location','')} {job.get('country','')}".lower()
        region = "India" if "india" in loc else "Outside India"
        mode = job.get("work_mode") or "Unspecified"
        hours = posted_age_hours(job)
        score = int(job.get("match_score", 0))
        if regions and region not in regions: continue
        if modes and mode not in modes: continue
        if score < min_score: continue
        if age_filter == "Last 8 hours" and (hours is None or hours > 8): continue
        if age_filter == "Last 12 hours" and (hours is None or hours > 12): continue
        if age_filter == "Last 24 hours" and (hours is None or hours > 24): continue
        if age_filter == "Older than 24 hours" and (hours is None or hours <= 24): continue
        if job.get("is_relevant", True):
            visible.append((job, hours))

    tracker = list_jobs()
    m1, m2, m3 = st.columns(3)
    m1.metric("Matching jobs", len(visible))
    m2.metric("Average match", f"{round(sum(j.get('match_score',0) for j,_ in visible)/len(visible))}%" if visible else "—")
    m3.metric("Saved applications", len(tracker))

    if st.session_state.get("errors"):
        with st.expander("Job-source notes", expanded=True):
            for error in st.session_state["errors"]:
                st.write(f"• {error}")

    st.subheader("Job opportunities")
    if not visible:
        st.info("No jobs meet the selected filters. Check Job-source notes above.")
    for job, hours in sorted(visible, key=lambda item: item[0].get("match_score", 0), reverse=True):
        title, company = job.get("title", "Untitled"), job.get("company", "Unknown")
        score = job.get("match_score", 0)
        badge = "🟢 TOP MATCH" if score >= 85 else ("🟡 GOOD FIT" if score >= 70 else "⚪ REVIEW")
        with st.expander(f"{badge} ({score}%) | {title} — {company}"):
            st.write(f"**Location:** {job.get('location') or 'Not stated'} | **Mode:** {job.get('work_mode') or 'Unspecified'} | **Source:** {job.get('source','')}")
            st.write(f"**Matched:** {', '.join(job.get('matched_skills', [])) or 'None'}")
            st.write(f"**Missing:** {', '.join(job.get('missing_skills', [])) or 'None'}")
            st.write((job.get("description") or "")[:2000])
            url = job.get("url", "")
            if url.startswith("http"):
                st.markdown(f"👉 **[Open original job posting]({url})**")
            if st.button("Save to tracker", key=f"save_{job.get('id', title)}"):
                save_job(job)
                st.success("Saved.")

    st.subheader("Application tracker")
    if tracker:
        df = pd.DataFrame(tracker)
        st.dataframe(df[["title", "company", "location", "match_score", "status", "url"]], use_container_width=True, hide_index=True)
        selected = st.selectbox("Choose saved job", tracker, format_func=lambda x: f"{x['title']} — {x['company']}")
        status = st.selectbox("Status", ["Saved", "Applied", "Recruiter contacted", "Interview", "Rejected", "Offer"])
        if st.button("Update status"):
            update_application(selected["id"], status)
            st.success("Updated.")

with tab_manual:
    st.subheader("Score Any Naukri / LinkedIn Job Description")
    c1, c2, c3 = st.columns(3)
    m_title = c1.text_input("Job Title", placeholder="Supplier Quality Manager")
    m_company = c2.text_input("Company", placeholder="Eaton / GE Vernova")
    m_url = c3.text_input("Job URL", placeholder="https://...")
    m_desc = st.text_area("Paste Job Description", height=200)

    if st.button("Analyze & Draft Cover Note", type="primary"):
        if m_title and m_desc:
            custom_job = {"id": f"manual:{m_title}", "title": m_title, "company": m_company or "Hiring Team", "location": "India", "work_mode": "Remote", "url": m_url, "description": m_desc, "source": "Manual"}
            res = match_job(resume_text, custom_job)
            custom_job.update(res)
            st.metric("ATS Match Score", f"{res['match_score']}%")
            st.write(f"**Matched:** {', '.join(res['matched_skills'])}")
            st.write(f"**Missing:** {', '.join(res['missing_skills'])}")
            skills_txt = ", ".join(res["matched_skills"][:5]) or "PPAP, APQP, 8D, and IATF 16949 audits"
            note = f"Dear {custom_job['company']},\n\nI am applying for {m_title}. With 14+ years in Supplier Quality & Manufacturing QA (Karad Projects, Wilo Mather & Platt, POSCO Steel) and IATF 16949 Internal Auditor certification, I specialize in {skills_txt} and delivered 20-30% supplier defect reductions.\n\nRegards,\nVinayak Suresh Boragale | +91 9890897235"
            st.text_area("Cover Note", value=note, height=180)
            if st.button("Save manual job"):
                save_job(custom_job)
                st.success("Saved.")
