import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "applications.db"

def connect():
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT,
            match_score INTEGER, status TEXT DEFAULT 'Saved', url TEXT, payload TEXT
        )""")

def save_job(job):
    job_id = str(job.get("id") or job.get("url") or job.get("title"))
    with connect() as con:
        con.execute("""INSERT INTO jobs
        (id,title,company,location,match_score,status,url,payload)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
        title=excluded.title, company=excluded.company, location=excluded.location,
        match_score=excluded.match_score, url=excluded.url, payload=excluded.payload""",
        (job_id, job.get("title",""), job.get("company",""), job.get("location",""),
         int(job.get("match_score",0)), "Saved", job.get("url",""),
         json.dumps(job, ensure_ascii=False)))

def list_jobs():
    with connect() as con:
        rows = con.execute("SELECT * FROM jobs ORDER BY rowid DESC").fetchall()
    return [dict(row) for row in rows]

def update_application(job_id, status):
    with connect() as con:
        con.execute("UPDATE jobs SET status=? WHERE id=?", (status, str(job_id)))
