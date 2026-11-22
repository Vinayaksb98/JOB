from ats_matcher import assess_role, match_job
CV="14 years supplier quality supplier audits manufacturing quality ISO 9001 IATF 16949 APQP PPAP 8D RCA CAPA FMEA castings forgings fabrication welding machining"
tests=[
({"title":"Principal Software Engineer, Data Lakes","description":"Build data lake software and ensure product quality."},False),
({"title":"Content Reviewer - United States","description":"Review content quality and editorial guidelines."},False),
({"title":"Senior Supplier Quality Engineer","description":"Lead supplier audits, APQP, PPAP, 8D, RCA and CAPA. Improve supplier PPM and manufacturing quality. Requires 8 years of experience."},True),
({"title":"QA Engineer","description":"Test web applications, write automation scripts and report bugs."},False)]
for job,expected in tests: assert assess_role(job)[0] is expected, job
assert match_job(CV,tests[2][0])["match_score"] >= 70
print("PASS: 4 role-filter regression cases.")
