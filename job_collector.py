from job_sources import fetch_jsearch, fetch_arbeitnow, fetch_remotive, fetch_adzuna
from ats_matcher import assess_role

def collect_jobs():
    all_jobs, errors = [], []
    sources = [
        ("JSearch (LinkedIn/Indeed)", fetch_jsearch),
        ("Adzuna", fetch_adzuna),
        ("Arbeitnow", fetch_arbeitnow),
        ("Remotive", fetch_remotive),
    ]
    for name, fn in sources:
        try:
            fetched = fn()
            all_jobs.extend(fetched)
            errors.append(f"{name}: fetched {len(fetched)} raw listings.")
        except Exception as e:
            errors.append(f"{name} error: {e}")

    kept, seen, rejected = [], set(), 0
    for job in all_jobs:
        ok, reason = assess_role(job)
        if not ok:
            rejected += 1
            continue
        job["relevance_reason"] = reason
        if job.get("url") and job["url"] not in seen:
            kept.append(job)
            seen.add(job["url"])

    errors.append(f"Filter summary: Kept {len(kept)} industrial quality jobs; excluded {rejected} unrelated roles.")
    return kept, errors
