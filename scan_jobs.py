import json
from datetime import datetime, timezone
from pathlib import Path
from job_collector import collect_jobs

jobs, errors = collect_jobs()
scanned_at = datetime.now(timezone.utc).isoformat()
for job in jobs:
    job.update({"match_score": 0, "matched_skills": [], "missing_skills": [],
                "scan_timestamp": scanned_at})
output = Path("data/job_scan.json")
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps({"scanned_at": scanned_at, "jobs": jobs, "errors": errors},
                             ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Collected {len(jobs)} relevant jobs.")
for error in errors:
    print("SOURCE ERROR:", error)
