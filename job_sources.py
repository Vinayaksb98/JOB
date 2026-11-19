"""Adapters for public job feeds and optional Adzuna API credentials."""
import os
import requests

HEADERS = {"User-Agent": "SupplierQualityJobFinder/1.0"}

def get_json(url, params=None):
    response = requests.get(url, params=params, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json()

def fetch_arbeitnow():
    payload = get_json("https://www.arbeitnow.com/api/job-board-api")
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
    payload = get_json("https://remotive.com/api/remote-jobs", {"category": "all"})
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
    for country in ["in", "gb", "us", "ca", "au", "de", "nl", "sg", "ae"]:
        try:
            payload = get_json(
                f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                {"app_id": app_id, "app_key": app_key, "results_per_page": 50,
                 "what": "supplier quality OR supplier development OR quality engineer"}
            )
            for item in payload.get("results", []):
                location = item.get("location", {}).get("display_name", "")
                jobs.append({
                    "id": f"adzuna:{item.get('id')}", "title": item.get("title", ""),
                    "company": item.get("company", {}).get("display_name", ""),
                    "location": location, "country": "India" if country == "in" else country.upper(),
                    "work_mode": "Remote" if "remote" in (item.get("title","") + location).lower() else "Unspecified",
                    "posted_at": item.get("created"), "url": item.get("redirect_url", ""),
                    "description": item.get("description", ""), "source": f"Adzuna ({country})"
                })
        except Exception:
            continue
    return jobs
