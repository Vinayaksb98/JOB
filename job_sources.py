"""Adapters for public job feeds, Adzuna, and JSearch (LinkedIn/Indeed aggregator)."""
import os
import requests

HEADERS = {"User-Agent": "SupplierQualityJobFinder/2.0"}

def get_json(url, params=None, headers=None):
    req_headers = {**HEADERS, **(headers or {})}
    response = requests.get(url, params=params, headers=req_headers, timeout=25)
    response.raise_for_status()
    return response.json()

def fetch_jsearch():
    """Fetches live LinkedIn/Indeed/Glassdoor jobs via RapidAPI JSearch."""
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return []
    
    url = "https://rapidapi.com"
    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": "://rapidapi.com"
    }
    
    # Targeted queries for US/EU companies hiring Supplier Quality in India
    queries = [
        "Supplier Quality Manager remote India",
        "Supplier Quality Engineer remote India",
        "Supplier Development Manager India manufacturing",
        "Lead Supplier Auditor India"
    ]
    
    jobs = []
    for q in queries:
        try:
            payload = get_json(url, params={"query": q, "num_pages": "2", "date_posted": "month"}, headers=headers)
            for item in payload.get("data", []):
                is_remote = item.get("job_is_remote", False)
                city = item.get("job_city") or ""
                country = item.get("job_country") or ""
                loc_str = f"{city}, {country}".strip(", ") or "India"
                
                jobs.append({
                    "id": f"jsearch:{item.get('job_id')}",
                    "title": item.get("job_title", ""),
                    "company": item.get("employer_name", ""),
                    "location": loc_str,
                    "country": "India" if "in" in country.lower() or "india" in loc_str.lower() else country,
                    "work_mode": "Remote" if is_remote else ("Hybrid" if "hybrid" in (item.get("job_description","")).lower() else "Unspecified"),
                    "posted_at": item.get("job_posted_at_datetime_utc"),
                    "url": item.get("job_apply_link") or item.get("job_google_link", ""),
                    "description": item.get("job_description", ""),
                    "source": f"JSearch ({item.get('job_publisher', 'Web')})"
                })
        except Exception:
            continue
    return jobs

def fetch_arbeitnow():
    payload = get_json("https://arbeitnow.com")
    jobs = []
    for item in payload.get("data", []):
        remote = bool(item.get("remote")) or "remote" in " ".join(item.get("tags", [])).lower()
        jobs.append({
            "id": f"arbeitnow:{item.get('slug') or item.get('url')}",
            "title": item.get("title", ""), "company": item.get("company_name", ""),
            "location": item.get("location", ""), "country": "",
            "work_mode": "Remote" if remote else "Unspecified",
            "posted_at": item.get("created_at"), "url": item.get("url", ""),
            "description": item.get("description", ""), "source": "Arbeitnow"
        })
    return jobs

def fetch_remotive():
    payload = get_json("https://remotive.com", {"category": "all"})
    return [{
        "id": f"remotive:{item.get('id')}", "title": item.get("title", ""),
        "company": item.get("company_name", ""),
        "location": item.get("candidate_required_location", "Worldwide"),
        "country": "", "work_mode": "Remote",
        "posted_at": item.get("publication_date"), "url": item.get("url", ""),
        "description": item.get("description", ""), "source": "Remotive"
    } for item in payload.get("jobs", [])]

def fetch_adzuna():
    app_id, app_key = os.getenv("ADZUNA_APP_ID"), os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []
    jobs = []
    # Focus heavily on India ('in') plus US/UK/DE remote feeds
    for country in ["in", "us", "gb", "de"]:
        try:
            query = "supplier quality remote" if country != "in" else "supplier quality OR supplier development"
            payload = get_json(
                f"https://adzuna.com{country}/search/1",
                {"app_id": app_id, "app_key": app_key, "results_per_page": 50, "what": query}
            )
            for item in payload.get("results", []):
                location = item.get("location", {}).get("display_name", "")
                desc = item.get("description", "")
                is_remote = "remote" in (item.get("title","") + location + desc).lower()
                jobs.append({
                    "id": f"adzuna:{item.get('id')}", "title": item.get("title", ""),
                    "company": item.get("company", {}).get("display_name", ""),
                    "location": location, "country": "India" if country == "in" else country.upper(),
                    "work_mode": "Remote" if is_remote else "Unspecified",
                    "posted_at": item.get("created"), "url": item.get("redirect_url", ""),
                    "description": desc, "source": f"Adzuna ({country.upper()})"
                })
        except Exception:
            continue
    return jobs
