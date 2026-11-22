from job_sources import fetch_arbeitnow, fetch_remotive, fetch_adzuna
from ats_matcher import assess_role
def collect_jobs():
    all_jobs, errors = [], []
    for name, fn in [("Arbeitnow",fetch_arbeitnow),("Remotive",fetch_remotive),("Adzuna",fetch_adzuna)]:
        try: all_jobs.extend(fn())
        except Exception as e: errors.append(f"{name}: {e}")
    kept, seen, rejected = [], set(), 0
    for job in all_jobs:
        ok, reason = assess_role(job)
        if not ok: rejected += 1; continue
        job["relevance_reason"] = reason
        if job.get("url") and job["url"] not in seen: kept.append(job); seen.add(job["url"])
    errors.append(f"Role filter kept {len(kept)} relevant jobs; excluded {rejected} unrelated/weak matches.")
    return kept, errors
