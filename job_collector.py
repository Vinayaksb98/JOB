from job_sources import (
    fetch_naukri_linkedin,
    fetch_jsearch,
    fetch_adzuna,
    fetch_arbeitnow,
    fetch_remotive,
)
from ats_matcher import assess_role


def collect_jobs():
    all_jobs, errors = [], []
    sources = [
        ("Naukri & LinkedIn (Serper)", fetch_naukri_linkedin),
        ("JSearch (LinkedIn/Indeed)", fetch_jsearch),
        ("Adzuna (IN/US/UK/DE)", fetch_adzuna),
        ("Arbeitnow", fetch_arbeitnow),
        ("Remotive", fetch_remotive),
    ]

    for name, fn in sources:
        try:
            fetched = fn()
            all_jobs.extend(fetched)
            errors.append(f"{name}: fetched {len(fetched)} raw listings.")
        except Exception as e:
            errors.append(f"{name} skipped: {e}")

    kept, seen, rejected = [], set(), 0
    for job in all_jobs:
        ok, reason = assess_role(job)
        if not ok:
            rejected += 1
            continue
        job["relevance_reason"] = reason
        dedup_key = job.get("url") or f"{job.get('title')}:{job.get('company')}"
        if dedup_key not in seen:
            kept.append(job)
            seen.add(dedup_key)

    errors.append(f"Filter summary: Kept {len(kept)} industrial quality jobs; excluded {rejected} unrelated roles.")
    return kept, errors
