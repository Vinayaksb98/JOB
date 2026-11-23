"""Adapters for public job feeds, Adzuna, JSearch, and direct Naukri/LinkedIn search."""
import os
import requests
import streamlit as st

HEADERS = {"User-Agent": "SupplierQualityJobFinder/2.3"}


def get_secret(key):
    val = os.getenv(key)
    if not val:
        try:
            val = st.secrets.get(key)
        except Exception:
            val = None
    if not val or "your_" in str(val).lower() or "paste_" in str(val).lower():
        return None
    return str(val).strip()


def get_json(url, params=None, headers=None):
    req_headers = {**HEADERS, **(headers or {})}
    response = requests.get(url, params=params, headers=req_headers, timeout=25)
    response.raise_for_status()
    return response.json()


def fetch_naukri_linkedin():
    """Fetches direct Naukri & LinkedIn job listings via Google Search API (Serper.dev)."""
    api_key = get_secret("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError("SERPER_API_KEY missing in Secrets.")

    endpoint = "https://" + "google.serper.dev" + "/search"
    req_headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json"
    }

    targeted_queries = [
        'site:://linkedin.com ("Supplier Quality Manager" OR "Supplier Quality Engineer") "India"',
        'site:://naukri.com ("Supplier Quality Manager" OR "Supplier Development Manager") "India"',
        'site:://naukri.com ("Supplier Quality" OR "Quality Assurance Manager") ("casting" OR "forging" OR "IATF 16949")',
        'site:://linkedin.com ("Supplier Development" OR "Lead Auditor") "IATF 16949" "India"'
    ]

    jobs = []
    last_err = None
    for q in targeted_queries:
        try:
            resp = requests.post(endpoint, json={"q": q, "gl": "in", "num": 20}, headers=req_headers, timeout=25)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("organic", []):
                link = item.get("link", "")
                raw_title = item.get("title", "")
                snippet = item.get("snippet", "")
                source_name = "Naukri.com" if "naukri.com" in link else ("LinkedIn" if "linkedin.com" in link else "Web")

                clean_title = raw_title.split(" - ")[0].split(" | ")[0].strip()
                company = "See posting"
                if " - " in raw_title:
                    parts = raw_title.split(" - ")
                    if len(parts) > 1:
                        company = parts[1].split("|")[0].strip()

                text_lower = (raw_title + " " + snippet).lower()
                work_mode = "Remote" if "remote" in text_lower else ("Hybrid" if "hybrid" in text_lower else "Unspecified")

                jobs.append({
                    "id": f"serper:{link}",
                    "title": clean_title or raw_title,
                    "company": company,
                    "location": "India",
                    "country": "India",
                    "work_mode": work_mode,
                    "posted_at": item.get("date"),
                    "url": link,
                    "description": f"{raw_title}\n\n{snippet}",
                    "source": source_name
                })
        except Exception as exc:
            last_err = exc
            continue

    if not jobs and last_err:
        raise last_err
    return jobs


def fetch_jsearch():
    """Fetches live LinkedIn/Indeed/Glassdoor jobs via RapidAPI JSearch."""
    api_key = get_secret("RAPIDAPI_KEY")
    if not api_key:
        raise RuntimeError("RAPIDAPI_KEY not configured (optional).")

    endpoint = "https://" + "://rapidapi.com" + "/search"
    req_headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "://rapidapi.com"
    }

    queries = [
        "Supplier Quality Manager remote India",
        "Supplier Quality Engineer remote India",
        "Supplier Development Manager India manufacturing"
    ]

    jobs = []
    last_err = None
    for q in queries:
        try:
            payload = get_json(endpoint, params={"query": q, "num_pages": "2", "date_posted": "month"}, headers=req_headers)
            for item in payload.get("data", []):
                is_remote = bool(item.get("job_is_remote", False))
                city = item.get("job_city") or ""
                country = item.get("job_country") or ""
                loc_str = f"{city}, {country}".strip(", ") or "India"
                desc = item.get("job_description") or ""
                work_mode = "Remote" if (is_remote or "remote" in desc.lower()) else ("Hybrid" if "hybrid" in desc.lower() else "Unspecified")

                jobs.append({
                    "id": f"jsearch:{item.get('job_id')}",
                    "title": item.get("job_title", ""),
                    "company": item.get("employer_name", ""),
                    "location": loc_str,
                    "country": "India" if "in" in country.lower() or "india" in loc_str.lower() else country,
                    "work_mode": work_mode,
                    "posted_at": item.get("job_posted_at_datetime_utc"),
                    "url": item.get("job_apply_link") or item.get("job_google_link", ""),
                    "description": desc,
                    "source": f"JSearch ({item.get('job_publisher', 'Web')})"
                })
        except Exception as exc:
            last_err = exc
            continue

    if not jobs and last_err:
        raise last_err
    return jobs


def fetch_arbeitnow():
    api_url = "https://" + "://arbeitnow.com" + "/api/job-board-api"
    payload = get_json(api_url)
    jobs = []
    for item in payload.get("data", []):
        remote = bool(item.get("remote")) or "remote" in " ".join(item.get("tags", [])).lower()
        jobs.append({
            "id": f"arbeitnow:{item.get('slug') or item.get('url')}",
            "title": item.get("title", ""),
            "company": item.get("company_name", ""),
            "location": item.get("location", ""),
            "country": "",
            "work_mode": "Remote" if remote else "Unspecified",
            "posted_at": item.get("created_at"),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "source": "Arbeitnow"
        })
    return jobs


def fetch_remotive():
    api_url = "https://" + "remotive.com" + "/api/remote-jobs"
    payload = get_json(api_url, {"category": "all"})
    return [{
        "id": f"remotive:{item.get('id')}",
        "title": item.get("title", ""),
        "company": item.get("company_name", ""),
        "location": item.get("candidate_required_location", "Worldwide"),
        "country": "",
        "work_mode": "Remote",
        "posted_at": item.get("publication_date"),
        "url": item.get("url", ""),
        "description": item.get("description", ""),
        "source": "Remotive"
    } for item in payload.get("jobs", [])]


def fetch_adzuna():
    app_id, app_key = get_secret("ADZUNA_APP_ID"), get_secret("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("Adzuna keys not configured (optional).")

    jobs = []
    last_err = None
    for country in ["in", "us", "gb", "de"]:
        try:
            query = "supplier quality remote" if country != "in" else "supplier quality OR supplier development"
            api_url = "https://" + "://adzuna.com" + f"/v1/api/jobs/{country}/search/1"
            payload = get_json(api_url, {"app_id": app_id, "app_key": app_key, "results_per_page": 50, "what": query})
            for item in payload.get("results", []):
                location = item.get("location", {}).get("display_name", "")
                desc = item.get("description", "")
                is_remote = "remote" in (item.get("title", "") + location + desc).lower()
                jobs.append({
                    "id": f"adzuna:{item.get('id')}",
                    "title": item.get("title", ""),
                    "company": item.get("company", {}).get("display_name", ""),
                    "location": location,
                    "country": "India" if country == "in" else country.upper(),
                    "work_mode": "Remote" if is_remote else "Unspecified",
                    "posted_at": item.get("created"),
                    "url": item.get("redirect_url", ""),
                    "description": desc,
                    "source": f"Adzuna ({country.upper()})"
                })
        except Exception as exc:
            last_err = exc
            continue

    if not jobs and last_err:
        raise last_err
    return jobs
