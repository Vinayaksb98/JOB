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
st.caption("Global Supplier Quality vacancies • CV-to-JD matching • Application tracking")
init_db()

with st.sidebar:
    st.header("Search filters")
    regions = st.multiselect("Location", ["India", "Outside India"], default=["India", "Outside India"])
    modes = st.multiselect("Work mode", ["Remote", "Hybrid", "Onsite", "Unspecified"],
                           default=["Remote", "Hybrid", "Onsite", "Unspecified"])
    age_filter = st.selectbox("Posting age", ["Any time", "Last 8 hours", "Last 12 hours",
                                              "Last 24 hours", "Older than 24 hours"])
    min_score = st.slider("Minimum CV match (%)", 0, 100, 30, 5)
    cv = st.file_uploader("Upload CV (PDF / DOCX / TXT)", type=["pdf", "docx", "txt"])

resume_text = ""
if cv:
    try:
        resume_text = extract_resume_text(cv.getvalue(), cv.name)
        st.success("CV loaded. Job matches will be scored against this CV.")
    except Exception as exc:
        st.error(f"CV could not be read: {exc}")

left, right = st.columns(2)
with left:
    if st.button("🔄 Scan job sources now", type="primary", use_container_width=True):
        with st.spinner("Searching configured public job feeds..."):
            found, errors = collect_jobs()
            for job in found:
                job.update(match_job(resume_text, job))
                save_job(job)
            SCAN_FILE.parent.mkdir(exist_ok=True)
            SCAN_FILE.write_text(json.dumps({"scanned_at": datetime.now(timezone.utc).isoformat(),
                                              "jobs": found, "errors": errors},
                                             ensure_ascii=False, indent=2), encoding="utf-8")
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
            st.warning("No scan file found yet. Run a scan first.")

jobs = st.session_state.get("jobs")
if jobs is None and SCAN_FILE.exists():
    try:
        payload = json.loads(SCAN_FILE.read_text(encoding="utf-8"))
        jobs = payload.get("jobs", []) if isinstance(payload, dict) else payload
        st.session_state["errors"] = payload.get("errors", []) if isinstance(payload, dict) else []
    except Exception:
        jobs = []
if jobs is None:
    jobs = []

# Recalculate match scores for the CV uploaded in the current session.
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

errors = st.session_state.get("errors", [])
if errors:
    with st.expander("Job-source notes"):
        for error in errors:
            st.write(f"• {error}")

st.subheader("Job opportunities")
if not visible:
    st.info("No jobs meet the selected filters. Try lowering the match threshold or including Unspecified work mode.")
for job, hours in sorted(visible, key=lambda item: item[0].get("match_score", 0), reverse=True):
    title, company = job.get("title", "Untitled role"), job.get("company", "Company not listed")
    with st.expander(f"{title} — {company} | Match {job.get('match_score',0)}%"):
        st.write(f"**Location:** {job.get('location') or 'Not stated'}")
        st.write(f"**Work mode:** {job.get('work_mode') or 'Unspecified'}")
        st.write(f"**Source:** {job.get('source','')} | **Posted:** {job.get('posted_at') or 'Date not supplied'}")
        st.write(f"**Matched skills:** {', '.join(job.get('matched_skills', [])) or 'None detected'}")
        st.write(f"**Score breakdown:** Role {job.get('role_fit',0)}% | Skills {job.get('skill_fit',0)}% | Responsibilities {job.get('responsibility_fit',0)}% | Experience {job.get('experience_fit',0)}%")
        st.write(f"**Experience check:** {job.get('match_note','')}")
        st.write(f"**Missing skills:** {', '.join(job.get('missing_skills', [])) or 'None detected'}")
        st.write((job.get("description") or "")[:2200])
        url = job.get("url", "")
        if url.startswith("http"):
            st.markdown(f"[Open original job posting / application page]({url})")
        if st.button("Save to application tracker", key=f"save_{job.get('id', title)}"):
            save_job(job)
            st.success("Job saved.")

st.subheader("Application tracker")
if tracker:
    df = pd.DataFrame(tracker)
    st.dataframe(df[["title", "company", "location", "match_score", "status", "url"]],
                 use_container_width=True, hide_index=True)
    selected = st.selectbox("Choose saved job", tracker,
                            format_func=lambda x: f"{x['title']} — {x['company']}")
    status = st.selectbox("Update application status",
                          ["Saved", "Applied", "Recruiter contacted", "Interview", "Rejected", "Offer"])
    if st.button("Update status"):
        update_application(selected["id"], status)
        st.success("Status updated. Refresh the page to see the change.")
else:
    st.caption("Jobs you save will appear here.")

st.caption("Coverage is limited to configured public feeds/APIs; this is not an exhaustive global crawler. LinkedIn and Indeed are not scraped. Unknown work modes and posting dates remain marked as unspecified rather than guessed. ATS score is a transparent keyword-coverage estimate, not a hiring prediction.")
