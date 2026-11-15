from datetime import datetime, timezone
import re
import fitz  # PyMuPDF
from jobspy import scrape_jobs
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

st.set_page_config(page_title="Universal AI Job & ATS Dashboard", layout="wide")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


# --- RESUME PARSER ---
def extract_resume_text(uploaded_file):
  doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
  text = " ".join([page.get_text() for page in doc])
  return re.sub(r"\s+", " ", text).strip()


# --- ATS SCORING ENGINE ---
def evaluate_ats(resume_text, jd_text):
  if (
      not resume_text
      or not jd_text
      or str(jd_text).strip().lower() in ["nan", "none", ""]
  ):
    return 20.0, [], []

  try:
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    vectors = vectorizer.fit_transform(
        [resume_text.lower(), str(jd_text).lower()]
    )
    similarity = float(cosine_similarity(vectors[0:1], vectors[1:2]))

    feature_names = vectorizer.get_feature_names_out()
    jd_vector = vectors.toarray()
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
    return 20.0, [], []


# --- UNIVERSAL KEYLESS JOB FETCHER ---
def fetch_universal_jobs(
    roles, location_scope, city, country_name, hours_old, remote_only
):
  all_jobs = []
  diagnostics = {
      "LinkedIn Public Feed": 0,
      "JobSpy (Indeed / Naukri)": 0,
      "Remotive": 0,
      "Jobicy": 0,
      "Himalayas": 0,
      "Arbeitnow": 0,
      "RemoteOK": 0,
  }

  search_loc = (
      (city if city else "India")
      if location_scope == "Within India"
      else country_name
  )

  # 1. LinkedIn Unauthenticated Guest Jobs Endpoint
  for role in roles:
    try:
      f_tpr = (
          f"&f_TPR=r{hours_old * 3600}"
          if hours_old <= 24
          else "&f_TPR=r604800"
      )
      f_wt = "&f_WT=2" if remote_only else ""
      li_url = (
          "https://linkedin.com?"
          f"keywords={requests.utils.quote(role)}&location={requests.utils.quote(search_loc)}{f_tpr}{f_wt}"
      )
      res = requests.get(li_url, headers=HEADERS, timeout=10)
      if res.status_code == 200:
        titles = re.findall(
            r'<h3 class="base-search-card__title"[^>]*>(.*?)</h3>',
            res.text,
            re.S,
        )
        companies = re.findall(
            r'<h4 class="base-search-card__subtitle"[^>]*>.*?<a[^>]*>(.*?)</a>',
            res.text,
            re.S,
        )
        locations = re.findall(
            r'<span class="job-search-card__location"[^>]*>(.*?)</span>',
            res.text,
            re.S,
        )
        links = re.findall(
            r'<a class="base-card__full-link[^"]*" href="([^"]+)"', res.text
        )

        for i in range(min(len(titles), len(links))):
          t_clean = re.sub(r"\s+", " ", titles[i]).strip()
          c_clean = (
              re.sub(r"\s+", " ", companies[i]).strip()
              if i < len(companies)
              else "Company"
          )
          l_clean = (
              re.sub(r"\s+", " ", locations[i]).strip()
              if i < len(locations)
              else search_loc
          )
          clean_link = links[i].split("?")
          all_jobs.append({
              "title": t_clean,
              "company": c_clean,
              "location": l_clean,
              "site": "LinkedIn",
              "hours_ago": hours_old if hours_old <= 24 else 48,
              "posted_label": (
                  f"Within {hours_old}h" if hours_old <= 24 else "Last 7 days"
              ),
              "is_remote": remote_only or ("remote" in l_clean.lower()),
              "apply_link": clean_link,
              "jd": f"{t_clean} at {c_clean} in {l_clean}",
          })
          diagnostics["LinkedIn Public Feed"] += 1
    except Exception:
      pass

  # 2. JobSpy (Indeed & Naukri for India / Global)
  sites = ["naukri", "indeed"] if location_scope == "Within India" else ["indeed"]
  for role in roles:
    try:
      df = scrape_jobs(
          site_name=sites,
          search_term=role,
          location=search_loc,
          results_wanted=15,
          hours_old=hours_old,
          country_indeed="India"
          if location_scope == "Within India"
          else country_name,
          is_remote=remote_only,
      )
      if df is not None and not df.empty:
        for _, row in df.iterrows():
          all_jobs.append({
              "title": str(row.get("title", "Role")),
              "company": str(row.get("company", "Company")),
              "location": str(row.get("location", search_loc)),
              "site": str(row.get("site", "Portal")).capitalize(),
              "hours_ago": hours_old if hours_old <= 24 else 48,
              "posted_label": str(row.get("date_posted", "Recent")),
              "is_remote": bool(row.get("is_remote", False)),
              "apply_link": str(row.get("job_url", "#")),
              "jd": str(row.get("description", row.get("title", ""))),
          })
          diagnostics["JobSpy (Indeed / Naukri)"] += 1
    except Exception:
      pass

  # 3. Remotive Public API
  for role in roles:
    try:
      res = requests.get(
          f"https://remotive.com{requests.utils.quote(role)}&limit=25",
          headers=HEADERS,
          timeout=10,
      )
      if res.status_code == 200:
        for item in res.json().get("jobs", []):
          pub_str = item.get("publication_date", "")
          hrs = 48
          if pub_str:
            try:
              dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
              hrs = round(
                  (datetime.now(timezone.utc) - dt).total_seconds() / 3600, 1
              )
            except Exception:
              pass
          all_jobs.append({
              "title": item.get("title", ""),
              "company": item.get("company_name", "Company"),
              "location": item.get("candidate_required_location", "Worldwide"),
              "site": "Remotive",
              "hours_ago": hrs,
              "posted_label": f"{hrs}h ago" if hrs < 72 else pub_str[:10],
              "is_remote": True,
              "apply_link": item.get("url", "#"),
              "jd": re.sub(r"<[^<]+?>", " ", item.get("description", "")),
          })
          diagnostics["Remotive"] += 1
    except Exception:
      pass

  # 4. Jobicy Public API
  for role in roles:
    try:
      res = requests.get(
          f"https://jobicy.com{requests.utils.quote(role)}",
          headers=HEADERS,
          timeout=10,
      )
      if res.status_code == 200:
        for item in res.json().get("jobs", []):
          all_jobs.append({
              "title": item.get("jobTitle", ""),
              "company": item.get("companyName", "Company"),
              "location": item.get("jobGeo", "Remote"),
              "site": "Jobicy",
              "hours_ago": 24,
              "posted_label": item.get("pubDate", "Recent")[:10],
              "is_remote": True,
              "apply_link": item.get("url", "#"),
              "jd": re.sub(r"<[^<]+?>", " ", item.get("jobDescription", "")),
          })
          diagnostics["Jobicy"] += 1
    except Exception:
      pass

  # 5. Himalayas Public API
  try:
    res = requests.get(
        "https://himalayas.app", headers=HEADERS, timeout=10
    )
    if res.status_code == 200:
      for item in res.json().get("jobs", []):
        title = item.get("title", "")
        if any(
            w.lower() in title.lower()
            for r in roles
            for w in r.split()
            if len(w) > 2
        ):
          all_jobs.append({
              "title": title,
              "company": item.get("companyName", "Company"),
              "location": (
                  ", ".join(item.get("locationRestrictions", []))
                  or "Global Remote"
              ),
              "site": "Himalayas",
              "hours_ago": 24,
              "posted_label": "Recent",
              "is_remote": True,
              "apply_link": item.get("applicationLink", "#"),
              "jd": re.sub(r"<[^<]+?>", " ", item.get("description", "")),
          })
          diagnostics["Himalayas"] += 1
  except Exception:
    pass

  # 6. Arbeitnow Public API
  try:
    res = requests.get(
        "https://arbeitnow.com",
        headers=HEADERS,
        timeout=10,
    )
    if res.status_code == 200:
      for item in res.json().get("data", [])[:50]:
        title = item.get("title", "")
        if any(
            w.lower() in title.lower()
            for r in roles
            for w in r.split()
            if len(w) > 2
        ):
          all_jobs.append({
              "title": title,
              "company": item.get("company_name", "Company"),
              "location": item.get("location", "Global"),
              "site": "Arbeitnow",
              "hours_ago": 24,
              "posted_label": "Recent",
              "is_remote": bool(item.get("remote", False)),
