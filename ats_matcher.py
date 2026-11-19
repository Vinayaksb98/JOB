import re

SKILLS = [
    "supplier quality", "supplier quality development", "supplier development",
    "supplier audit", "supplier audits", "process audit", "system audit",
    "product audit", "apqp", "ppap", "ppap level 1", "ppap level 2",
    "ppap level 3", "ppap level 4", "fai", "first article inspection",
    "scar", "8d", "root cause analysis", "rca", "5 why", "fishbone",
    "capa", "corrective action", "preventive action", "iso 9001",
    "iatf 16949", "as9100", "fmea", "pfmea", "control plan", "msa",
    "spc", "lean", "continuous improvement", "welding", "fabrication",
    "machining", "casting", "castings", "forging", "forgings", "stamping",
    "sheet metal", "foundry", "metrology", "inspection", "customer complaint",
    "customer quality", "ppm", "copq", "manufacturing quality",
    "quality management system", "qms", "process capability",
    "supplier performance", "capacity assessment"
]

def normalize(text):
    return re.sub(r"[^a-z0-9+# ]+", " ", (text or "").lower())

def match_job(resume_text, job_description):
    resume, jd = normalize(resume_text), normalize(job_description)
    required = list(dict.fromkeys(s for s in SKILLS if normalize(s) in jd))
    if not required:
        return {"match_score": 0, "matched_skills": [], "missing_skills": [],
                "match_note": "No recognized skills found in this job description."}
    matched = [s for s in required if normalize(s) in resume]
    missing = [s for s in required if s not in matched]
    return {"match_score": round(100 * len(matched) / len(required)),
            "matched_skills": matched, "missing_skills": missing}
