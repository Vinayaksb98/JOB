from job_sources import fetch_arbeitnow, fetch_remotive, fetch_adzuna

SEARCH_TERMS = ("supplier", "quality", "manufacturing quality",
                "quality assurance", "supplier development")

def is_relevant(job):
    text = (job.get("title", "") + " " + job.get("description", "")).lower()
    return any(term in text for term in SEARCH_TERMS)

def collect_jobs():
    collected, errors = [], []
    for source_name, source_fn in [
        ("Arbeitnow", fetch_arbeitnow), ("Remotive", fetch_remotive), ("Adzuna", fetch_adzuna)
    ]:
        try:
            collected.extend(job for job in source_fn() if is_relevant(job))
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
    deduplicated = {}
    for job in collected:
        if job.get("url"):
            deduplicated[job["url"]] = job
    return list(deduplicated.values()), errors
