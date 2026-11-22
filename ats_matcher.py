
import re
from candidate_profile import CORE_SKILLS, YEARS_EXPERIENCE
SKILLS = list(dict.fromkeys(CORE_SKILLS + ["process audit","product audit","system audit","as9100","vendor quality","vendor development","supplier industrialization","incoming inspection","final inspection"]))
BAD = ("software","frontend","front end","backend","back end","full stack","mobile developer","web developer","data engineer","data scientist","content reviewer","content writer","game designer","graphic designer","sales","marketing","recruiter","customer support","call center","operations monitor","digital operations","financial analyst")
GOOD = ("supplier quality","supplier development","supplier assurance","vendor quality","manufacturing quality","quality engineer","quality manager","quality assurance","quality systems","supplier auditor","sqe","sqa")
DOMAIN = ("supplier quality","supplier audit","supplier development","supplier performance","manufacturing quality","production quality","incoming inspection","final inspection","ppap","apqp","iatf 16949","iso 9001","8d","scar","corrective action","root cause analysis","fmea","control plan","casting","forging","fabrication","welding","machining","stamping","foundry","industrial manufacturing","automotive","industrial equipment","quality management system")
DUTIES = ("supplier audit","supplier development","supplier corrective action","supplier performance","ppap","apqp","incoming quality","production quality","manufacturing quality","root cause","8d","capa","quality system","process audit","vendor development","customer complaint","quality improvement")
def norm(s): return re.sub(r"[^a-z0-9+# ]+"," ",str(s or "").lower())
def has(term,text): return norm(term) in norm(text)
def assess_role(job):
    title, desc = norm(job.get("title","")), norm(job.get("description",""))
    if any(x in title for x in BAD): return False,"Unrelated job family excluded."
    if not any(x in title for x in GOOD): return False,"Not a Supplier / Manufacturing Quality title."
    if sum(has(x,desc) for x in DOMAIN)<2 and not any(has(x,desc) for x in ("supplier quality","supplier development","manufacturing quality")): return False,"Insufficient industrial quality evidence."
    if not any(has(x,desc) for x in DUTIES): return False,"No relevant quality responsibilities."
    return True,"Relevant Supplier / Manufacturing Quality role."
def match_job(resume_text, job_or_description):
    job = job_or_description if isinstance(job_or_description,dict) else {"title":"","description":str(job_or_description or "")}
    ok, reason = assess_role(job)
    if not ok: return {"is_relevant":False,"match_score":0,"matched_skills":[],"missing_skills":[],"role_fit":0,"skill_fit":0,"responsibility_fit":0,"experience_fit":0,"match_note":reason}
    jd=norm(job.get("description","")); candidate=norm(resume_text)+" "+norm(" ".join(CORE_SKILLS))
    req=list(dict.fromkeys(s for s in SKILLS if has(s,jd)))
    matched=[s for s in req if has(s,candidate)]; missing=[s for s in req if s not in matched]
    sf=round(100*len(matched)/len(req)) if req else 45
    duties=sum(has(x,jd) for x in DUTIES); rf=min(100,duties*20)
    years_found=re.findall(r"(\\d{1,2})\\+ years|(\\d{1,2}) years of experience",jd)
    years=max([int(a or b) for a,b in years_found] or [0])
    ef=85 if not years else (100 if years<=YEARS_EXPERIENCE else round(100*YEARS_EXPERIENCE/years))
    note="Experience requirement not stated." if not years else f"JD asks {years}+ years; candidate baseline is {YEARS_EXPERIENCE}+ years."
    score=round(.25*100+.45*sf+.20*rf+.10*ef)
    return {"is_relevant":True,"match_score":score,"matched_skills":matched,"missing_skills":missing,"role_fit":100,"skill_fit":sf,"responsibility_fit":rf,"experience_fit":ef,"match_note":note}
