from datetime import datetime, timezone
import re
import fitz  # PyMuPDF
from jobspy import scrape_jobs
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

st.set_page_config(page_title="AI Job Matcher & ATS Dashboard", layout="wide")


# --- RESUME PARSER ---
def extract_resume_text(uploaded_file):
  doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
  text = " ".join([page.get_text() for page in doc])
  return re.sub(r"\s+", " ", text).strip()


# --- ATS SCORING ENGINE (FIXED) ---
def evaluate_ats(resume_text, jd_text):
  if (
      not resume_text
      or not jd_text
      or str(jd_text).strip().lower() in ["nan", "none", ""]
  ):
    return 0.0, [], []

  try:
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    vectors = vectorizer.fit_transform(
        [resume_text.lower(), str(jd_text).lower()]
    )

    # Extract scalar float from cosine_similarity matrix
    similarity = float(cosine_similarity(vectors[0:1], vectors[1:2])[0][0])

    feature_names = vectorizer.get_feature_names_out()
    # Select row index 1 (the Job Description vector) instead of flattening both rows
    jd_vector = vectors.toarray()[1]
    resume_lower = resume_text.lower()

    num_features = len(feature_names)
    top_n = min(15, num_features)
    top_indices = jd_vector.argsort()[-top_n:][::-1]

    top_jd_keywords = [
        feature_names[i]
        for i in top_indices
        if i < num_features and len(feature_names[i]) > 2
    ]

    matched = [kw for kw in top_jd_keywords if kw in resume_lower]
    missing = [kw for kw in top_jd_keywords if kw not in resume_lower]

    kw_ratio = (len(matched) / len(top_jd_keywords)) if top_jd_keywords else 0.0
    final_score = round((kw_ratio * 60.0) + (similarity * 40.0), 1)
    return min(final_score, 100.0), matched[:8], missing[:8]
  except ValueError:
    # Handles edge cases where JD contains only stop words or empty tokens
    return 0.0, [], []


# --- KEY-FREE MULTI-SOURCE FETCHER ---
def fetch_all_free_jobs(
    roles, location_scope, city, country_name, hours_old, remote_only
):
  combined_results = []

  sites = (
      ["linkedin", "indeed", "naukri", "glassdoor"]
      if location_scope == "Within India"
      else ["linkedin", "indeed", "glassdoor"]
  )
  search_location = (
      (city if city else "India")
      if location_scope == "Within India"
      else country_name
  )
  indeed_country = "India" if location_scope == "Within India" else country_name

  for role in roles:
    try:
      df = scrape_jobs(
          site_name=sites,
          search_term=role,
          location=search_location,
          results_wanted=15,
          hours_old=hours_old,
          country_indeed=indeed_country,
          is_remote=remote_only,
          linkedin_fetch_description=True,
      )
      if df is not None and not df.empty:
        for _, row in df.iterrows():
          combined_results.append({
              "title": row.get("title", "Unknown Role"),
              "company": row.get("company", "Unknown Company"),
              "location": str(row.get("location", search_location)),
              "site": str(row.get("site", "Job Board")).capitalize(),
              "date_posted": str(row.get("date_posted", "")),
              "is_remote": bool(row.get("is_remote", False)),
              "apply_link": row.get("job_url", "#"),
              "jd": str(row.get("description", "")),
          })
    except Exception as e:
      st.warning(f"Note on {role} search: {e}")

  # Arbeitnow Free Keyless API (Global / Remote ATS boards)
  if location_scope != "Within India" or remote_only:
    try:
      res = requests.get(
          "https://arbeitnow.com", timeout=10
      )
      if res.status_code == 200:
        for item in res.json().get("data", [])[:30]:
          title = item.get("title", "")
          if any(r.lower() in title.lower() for r in roles):
            combined_results.append({
                "title": title,
                "company": item.get("company_name", "Unknown Company"),
                "location": item.get("location", "Remote / Global"),
                "site": "Arbeitnow ATS",
                "date_posted": str(item.get("created_at", "")),
                "is_remote": bool(item.get("remote", False)),
                "apply_link": item.get("url", "#"),
                "jd": re.sub(r"<[^<]+?>", " ", item.get("description", "")),
            })
    except Exception:
      pass

  return combined_results


# --- SIDEBAR ---
with st.sidebar:
  st.header("1. Upload Resume")
  resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])

  st.header("2. Target Roles & Fields")
  roles_input = st.text_input(
      "Target Roles (comma-separated)",
      value="Data Analyst, Business Analyst",
  )

  st.header("3. Location & Work Culture")
  location_scope = st.radio(
      "Working Location", ["Within India", "Outside India (Global)"]
  )
  if location_scope == "Within India":
    city_filter = st.text_input(
        "City in India (Optional)", placeholder="e.g., Pune, Bengaluru, Mumbai"
    )
    country_name = "India"
  else:
    city_filter = ""
    country_name = st.selectbox(
        "Target Country",
        [
            "USA",
            "UK",
            "Canada",
            "Germany",
            "United Arab Emirates",
            "Singapore",
            "Australia",
        ],
    )

  work_culture = st.multiselect(
      "Work Culture",
      ["Remote", "Hybrid", "On-site"],
      default=["Remote", "Hybrid", "On-site"],
  )

  st.header("4. Freshness & ATS Score")
  freshness_choice = st.selectbox(
      "Job Freshness",
      [
          "Last 1 Hour",
          "Last 8 Hours",
          "Last 24 Hours",
          "More than 24 Hours (Up to 7 days)",
      ],
  )
  min_ats = st.slider("Minimum ATS Match Score (%)", 0, 100, 35)

  search_btn = st.button(
      "Search Free Job Boards", type="primary", use_container_width=True
  )

# --- MAIN DASHBOARD ---
st.title("Universal Job Search & ATS Matcher")
st.caption(
    "Searches LinkedIn, Indeed, Naukri, Glassdoor, and public ATS feeds"
    " directly."
)

if search_btn:
  if not resume_file:
    st.warning("Please upload your PDF resume in the sidebar first.")
  else:
    with st.spinner(
        "Scanning LinkedIn, Naukri, Indeed, Glassdoor & ATS feeds..."
    ):
      resume_text = extract_resume_text(resume_file)
      roles = [r.strip() for r in roles_input.split(",") if r.strip()]

      hours_map = {
          "Last 1 Hour": 1,
          "Last 8 Hours": 8,
          "Last 24 Hours": 24,
          "More than 24 Hours (Up to 7 days)": 168,
      }
      hours_old = hours_map[freshness_choice]
      remote_only = work_culture == ["Remote"]

      raw_jobs = fetch_all_free_jobs(
          roles,
          location_scope,
          city_filter,
          country_name,
          hours_old,
          remote_only,
      )

      # Deduplicate & Score
      seen_links = set()
      final_jobs = []
      for job in raw_jobs:
        link = job["apply_link"]
        if link in seen_links:
          continue
        seen_links.add(link)

        text_blob = (job["title"] + " " + job["jd"]).lower()
        if job["is_remote"] or "remote" in text_blob:
          mode = "Remote"
        elif "hybrid" in text_blob:
          mode = "Hybrid"
        else:
          mode = "On-site"

        if mode not in work_culture:
          continue

        score, matched_kw, missing_kw = evaluate_ats(resume_text, job["jd"])
        if score < min_ats:
          continue

        job["mode"] = mode
        job["ats_score"] = score
        job["matched_kw"] = matched_kw
        job["missing_kw"] = missing_kw
        final_jobs.append(job)

      final_jobs.sort(key=lambda x: x["ats_score"], reverse=True)

      c1, c2, c3 = st.columns(3)
      c1.metric("Matching Vacancies", len(final_jobs))
      avg_score = (
          round(sum(j["ats_score"] for j in final_jobs) / len(final_jobs), 1)
          if final_jobs
          else 0
      )
      c2.metric("Average ATS Score", f"{avg_score}%")
      c3.metric("Freshness Filter", freshness_choice)

      st.divider()

      if not final_jobs:
        st.info(
            "No jobs matched your exact filters. Try lowering the Minimum ATS"
            " Score or expanding the freshness window."
        )
      else:
        for job in final_jobs:
          with st.container(border=True):
            col_info, col_action = st.columns([4, 1])
            with col_info:
              st.subheader(f"{job['title']} — {job['company']}")
              st.write(
                  f"**Location:** {job['location']} | **Culture:**"
                  f" `{job['mode']}` | **Source:** {job['site']} | **Posted:**"
                  f" {job['date_posted']}"
              )
              st.write(
                  "**Matched Skills:**"
                  f" {', '.join(job['matched_kw']) if job['matched_kw'] else 'General Match'}"
              )
              st.write(
                  "**Missing Keywords:**"
                  f" {', '.join(job['missing_kw']) if job['missing_kw'] else 'None'}"
              )
            with col_action:
              st.metric("ATS Match", f"{job['ats_score']}%")
              if job["apply_link"] and str(job["apply_link"]).startswith(
                  "http"
              ):
                st.link_button(
                    "Apply Now", job["apply_link"], use_container_width=True
                )

            with st.expander("Read Full Job Description"):
              st.write(job["jd"])
