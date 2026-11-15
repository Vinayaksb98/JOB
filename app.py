import re
import fitz
from jobspy import scrape_jobs
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import streamlit as st

st.set_page_config(page_title="Universal Job & ATS Matcher", layout="wide")
HEADERS = {"User-Agent": "Mozilla/5.0"}


def extract_resume(pdf_file):
  doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
  return re.sub(r"\s+", " ", " ".join(p.get_text() for p in doc)).strip()


def score_ats(resume_txt, jd_txt):
  if not resume_txt or not jd_txt or len(str(jd_txt)) < 10:
    return 25.0, [], []
  try:
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    mat = vec.fit_transform([resume_txt.lower(), str(jd_txt).lower()])
    sim = float(cosine_similarity(mat[0:1], mat[1:2]).item())
    names = vec.get_feature_names_out()
    jd_weights = mat.toarray().tolist()
    ranked = sorted(zip(jd_weights, names), reverse=True)[:15]
    top_kws = [w for _, w in ranked if len(w) > 2]
    res_low = resume_txt.lower()
    matched = [k for k in top_kws if k in res_low]
    missing = [k for k in top_kws if k not in res_low]
    ratio = len(matched) / len(top_kws) if top_kws else 0.0
    final = min(round((ratio * 60.0) + (sim * 40.0), 1), 100.0)
    return final, matched[:6], missing[:6]
  except Exception:
    return 25.0, [], []


def fetch_jobs(roles, loc_scope, city, country, hours_old, remote_only):
  jobs = []
  stats = {
      "JobSpy": 0,
      "Remotive": 0,
      "Jobicy": 0,
      "Himalayas": 0,
      "Arbeitnow": 0,
  }
  loc_str = (
      (city if city else "India") if loc_scope == "Within India" else country
  )

  # 1. JobSpy (Naukri & Indeed)
  sites = ["naukri", "indeed"] if loc_scope == "Within India" else ["indeed"]
  for r in roles:
    try:
      df = scrape_jobs(
          site_name=sites,
          search_term=r,
          location=loc_str,
          results_wanted=15,
          hours_old=hours_old,
          country_indeed="India" if loc_scope == "Within India" else country,
          is_remote=remote_only,
      )
      if df is not None and not df.empty:
        for _, row in df.iterrows():
          jobs.append({
              "title": str(row.get("title", "Role")),
              "company": str(row.get("company", "Company")),
              "location": str(row.get("location", loc_str)),
              "site": str(row.get("site", "Portal")).capitalize(),
              "hours": hours_old if hours_old <= 24 else 48,
              "posted": str(row.get("date_posted", "Recent")),
              "remote": bool(row.get("is_remote", False)),
              "url": str(row.get("job_url", "#")),
              "jd": str(row.get("description", row.get("title", ""))),
          })
          stats["JobSpy"] += 1
    except Exception:
      pass

  # 2. Remotive API
  for r in roles:
    try:
      url = f"https://remotive.com{requests.utils.quote(r)}&limit=25"
      res = requests.get(url, headers=HEADERS, timeout=10)
      if res.status_code == 200:
        for item in res.json().get("jobs", []):
          jobs.append({
              "title": item.get("title", ""),
              "company": item.get("company_name", "Company"),
              "location": item.get("candidate_required_location", "Worldwide"),
              "site": "Remotive",
              "hours": 24,
              "posted": item.get("publication_date", "Recent")[:10],
              "remote": True,
              "url": item.get("url", "#"),
              "jd": re.sub(r"<[^<]+?>", " ", item.get("description", "")),
          })
          stats["Remotive"] += 1
    except Exception:
      pass

  # 3. Jobicy API
  for r in roles:
    try:
      url = f"https://jobicy.com{requests.utils.quote(r)}"
      res = requests.get(url, headers=HEADERS, timeout=10)
      if res.status_code == 200:
        for item in res.json().get("jobs", []):
          jobs.append({
              "title": item.get("jobTitle", ""),
              "company": item.get("companyName", "Company"),
              "location": item.get("jobGeo", "Remote"),
              "site": "Jobicy",
              "hours": 24,
              "posted": item.get("pubDate", "Recent")[:10],
              "remote": True,
              "url": item.get("url", "#"),
              "jd": re.sub(r"<[^<]+?>", " ", item.get("jobDescription", "")),
          })
          stats["Jobicy"] += 1
    except Exception:
      pass

  # 4. Himalayas & Arbeitnow APIs
  endpoints = [
      (
          "https://himalayas.app",
          "jobs",
          "title",
          "companyName",
          "applicationLink",
          "Himalayas",
      ),
      (
          "https://arbeitnow.com",
          "data",
          "title",
          "company_name",
          "url",
          "Arbeitnow",
      ),
  ]
  for api_url, root_key, t_key, c_key, u_key, label in endpoints:
    try:
      res = requests.get(api_url, headers=HEADERS, timeout=10)
      if res.status_code == 200:
        for item in res.json().get(root_key, [])[:50]:
          title = item.get(t_key, "")
          if any(
              w.lower() in title.lower()
              for r in roles
              for w in r.split()
              if len(w) > 2
          ):
            jobs.append({
                "title": title,
                "company": item.get(c_key, "Company"),
                "location": str(item.get("location", "Global Remote")),
                "site": label,
                "hours": 24,
                "posted": "Recent",
                "remote": True,
                "url": item.get(u_key, "#"),
                "jd": re.sub(r"<[^<]+?>", " ", item.get("description", "")),
            })
            stats[label] += 1
    except Exception:
      pass

  return jobs, stats


# --- UI SIDEBAR ---
st.sidebar.header("1. Resume")
resume_file = st.sidebar.file_uploader("Upload PDF Resume", type=["pdf"])

st.sidebar.header("2. Roles")
roles_in = st.sidebar.text_input(
    "Target Roles", value="Software Engineer, Data Analyst, Manager"
)

st.sidebar.header("3. Location & Culture")
loc_scope = st.sidebar.radio(
    "Location", ["All Locations (Universal)", "Within India", "Outside India"]
)
city_in = (
    st.sidebar.text_input("City (Optional)")
    if loc_scope == "Within India"
    else ""
)
country_in = (
    st.sidebar.selectbox(
        "Country", ["USA", "UK", "Canada", "Germany", "UAE", "Singapore"]
    )
    if loc_scope == "Outside India"
    else "India"
)
culture = st.sidebar.multiselect(
    "Work Culture",
    ["Remote", "Hybrid", "On-site"],
    default=["Remote", "Hybrid", "On-site"],
)

st.sidebar.header("4. Freshness & ATS")
freshness = st.sidebar.selectbox(
    "Posted Within",
    [
        "All Recent (Up to 7 days)",
        "Last 1 Hour",
        "Last 8 Hours",
        "Last 24 Hours",
        "More than 24 Hours",
    ],
)
min_ats = st.sidebar.slider("Min ATS Score (%)", 0, 100, 10)
run_btn = st.sidebar.button(
    "Search Jobs", type="primary", use_container_width=True
)

# --- MAIN DASHBOARD ---
st.title("Universal Job Search & ATS Matcher")

if run_btn:
  if not resume_file:
    st.warning("Upload your PDF resume first.")
  else:
    with st.spinner("Searching universal job boards..."):
      res_text = extract_resume(resume_file)
      roles_list = [r.strip() for r in roles_in.split(",") if r.strip()]
      hrs_map = {
          "Last 1 Hour": 1,
          "Last 8 Hours": 8,
          "Last 24 Hours": 24,
          "More than 24 Hours": 168,
          "All Recent (Up to 7 days)": 168,
      }
      raw, stats = fetch_jobs(
          roles_list,
          loc_scope,
          city_in,
          country_in,
          hrs_map[freshness],
          culture == ["Remote"],
      )

      st.subheader(f"Source Diagnostics (Raw Found: {len(raw)})")
      st.json(stats)

      seen = set()
      results = []
      for j in raw:
        if j["url"] in seen:
          continue
        seen.add(j["url"])
        blob = (j["title"] + " " + j["location"] + " " + j["jd"]).lower()
        mode = (
            "Remote"
            if (j["remote"] or "remote" in blob or "worldwide" in blob)
            else ("Hybrid" if "hybrid" in blob else "On-site")
        )
        if mode not in culture:
          continue
        if freshness == "Last 1 Hour" and j["hours"] > 1:
          continue
        if freshness == "Last 8 Hours" and j["hours"] > 8:
          continue
        if freshness == "Last 24 Hours" and j["hours"] > 24:
          continue
        if freshness == "More than 24 Hours" and j["hours"] <= 24:
          continue
        sc, m_kw, miss_kw = score_ats(res_text, j["jd"])
        if sc < min_ats:
          continue
        j["mode"] = mode
        j["score"] = sc
        j["matched"] = m_kw
        j["missing"] = miss_kw
        results.append(j)

      results.sort(key=lambda x: x["score"], reverse=True)
      c1, c2 = st.columns(2)
      c1.metric("Matching Jobs", len(results))
      avg_val = (
          round(sum(x["score"] for x in results) / len(results), 1)
          if results
          else 0
      )
      c2.metric("Avg ATS Score", f"{avg_val}%")
      st.divider()

      for j in results:
        st.subheader(f"{j['title']} — {j['company']} (ATS: {j['score']}%)")
        st.write(
            f"**Location:** {j['location']} | **Culture:** `{j['mode']}` |"
            f" **Source:** {j['site']} | **Posted:** {j['posted']}"
        )
        st.write(
            f"**Matched:** {', '.join(j['matched']) or 'General'} |"
            f" **Missing:** {', '.join(j['missing']) or 'None'}"
        )
        if str(j["url"]).startswith("http"):
          st.link_button("Apply Now", j["url"])
        with st.expander("View Job Description"):
          st.write(j["jd"])
        st.divider()
