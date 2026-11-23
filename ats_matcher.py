import re
from candidate_profile import CORE_SKILLS, YEARS_EXPERIENCE

SKILLS = list(dict.fromkeys(CORE_SKILLS + [
    "process audit", "product audit", "system audit", "vda 6.3", "as9100",
    "vendor quality", "vendor development", "supplier industrialization",
    "incoming inspection", "final inspection", "gd&t", "cmm", "foundry", "sheet metal"
]))

BAD_TITLES = (
    "software", "frontend", "front end", "backend", "back end", "full stack",
    "mobile", "web", "data", "content", "game", "graphic", "sales", "marketing",
    "recruiter", "support", "call center", "clinical", "pharma", "pharmaceutical",
    "food", "laboratory", "lab ", "microbiology", "biotech", "nurse", "medical"
)

GOOD_TITLES = (
    "supplier quality", "supplier development", "supplier assurance", "vendor quality",
    "manufacturing quality", "quality manager", "quality assurance manager",
    "supplier auditor", "sqe", "sqa", "sqm", "supplier industrialization"
)

HEAVY_INDUSTRY = (
    "casting", "castings", "forging", "forgings", "fabrication", "welding",
    "machining", "stamping", "foundry", "sheet metal", "automotive", "heavy engineering",
    "pumps", "valves", "motors", "steel", "mechanical", "assemblies", "oem"
)

GLOBAL_BRIDGE_SIGNALS = (
    "india", "global supplier", "international", "regional", "travel",
    "supplier base", "vendors in india", "us ", "europe", "emea", "apac"
)

DUTIES = (
    "supplier audit", "supplier development", "supplier corrective action", "scar",
    "supplier performance", "ppap", "apqp", "iatf 16949", "iso 9001", "8d",
    "capa", "root cause", "fmea", "control plan", "process audit", "customer complaint"
)

def norm(s):
    return re.sub(r"[^a-z0-9+# ]+", " ", str(s or "").lower())

def has(term, text):
    return norm(term) in norm(text)

def assess_role(job):
    title = norm(job.get("title", ""))
    desc = norm(job.get("description", ""))
    full_text = f"{title} {desc}"

    if any(x in title for x in BAD_TITLES):
        return False, "Excluded non-manufacturing/IT/Pharma title."
    if not any(x in title for x in GOOD_TITLES):
        return False, "Title does not match Supplier or Manufacturing Quality leadership."
    
    industry_hits = sum(has(x, full_text) for x in HEAVY_INDUSTRY)
    duty_hits = sum(has(x, desc) for x in DUTIES)
    
    if industry_hits == 0 and duty_hits < 2:
        return False, "Lacks heavy manufacturing or core SQA responsibilities."
    return True, "Verified Industrial Supplier Quality role."

def match_job(resume_text, job_or_description):
    job = job_or_description if isinstance(job_or_description, dict) else {"title": "", "description": str(job_or_description or "")}
    ok, reason = assess_role(job)
    if not ok:
        return {
            "is_relevant": False, "match_score": 0, "matched_skills": [],
            "missing_skills": [], "role_fit": 0, "skill_fit": 0,
            "responsibility_fit": 0, "experience_fit": 0, "match_note": reason
        }

    title = norm(job.get("title", ""))
    jd = norm(job.get("description", ""))
    loc = norm(f"{job.get('location', '')} {job.get('country', '')}")
    candidate = norm(resume_text) + " " + norm(" ".join(CORE_SKILLS))

    # 1. Dynamic Role & India-Bridge Fit (25%)
    role_fit = 60
    if any(k in title for k in ("manager", "lead", "head", "senior", "staff")):
        role_fit += 20
    if "india" in loc or any(has(sig, jd) for sig in GLOBAL_BRIDGE_SIGNALS):
        role_fit += 20
    role_fit = min(100, role_fit)

    # 2. Technical & Commodity Skill Fit (45%)
    req = list(dict.fromkeys(s for s in SKILLS if has(s, jd)))
    matched = [s for s in req if has(s, candidate)]
    missing = [s for s in req if s not in matched]
    skill_fit = round(100 * len(matched) / len(req)) if req else 50

    # 3. Core SQA Responsibilities (20%)
    duties = sum(has(x, jd) for x in DUTIES)
    resp_fit = min(100, duties * 18)

    # 4. Experience Fit (10%)
    years_found = re.findall(r"(\d{1,2})\+?\s*years", jd)
    years = max([int(y) for y in years_found if int(y) <= 25] or)
    if not years:
        exp_fit = 85
        note = "Experience years not specified."
    elif years <= YEARS_EXPERIENCE:
        exp_fit = 100
        note = f"Requires {years}+ yrs (You have {YEARS_EXPERIENCE}+ yrs)."
    else:
        exp_fit = round(100 * YEARS_EXPERIENCE / years)
        note = f"Requires {years}+ yrs (Baseline: {YEARS_EXPERIENCE}+ yrs)."

    score = round(0.25 * role_fit + 0.45 * skill_fit + 0.20 * resp_fit + 0.10 * exp_fit)

    return {
        "is_relevant": True,
        "match_score": score,
        "matched_skills": matched,
        "missing_skills": missing,
        "role_fit": role_fit,
        "skill_fit": skill_fit,
        "responsibility_fit": resp_fit,
        "experience_fit": exp_fit,
        "match_note": note
    }
