# Supplier Quality Job Finder

Streamlit app to discover public Supplier Quality / Manufacturing Quality vacancies, compare job descriptions with an uploaded CV, and track applications.

## Included features
- India / Outside India filters.
- Remote / Hybrid / Onsite / Unspecified work-mode filters.
- Posting-age filters: 8h, 12h, 24h, and older than 24h.
- CV-to-JD match percentage, matched skills, and missing skills.
- Original job posting/application links returned by source feeds.
- SQLite application tracker.
- GitHub Actions scheduled scanning with downloadable JSON artifact.

## Run locally
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Optional Adzuna source
Create Adzuna API credentials and set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` in your environment or GitHub Actions repository secrets. Without them, the app uses the configured public Arbeitnow and Remotive feeds.

## GitHub Actions
Upload the complete folder to a GitHub repository, preserving `.github/workflows/scan_jobs.yml`. Run **Scheduled Supplier Quality Job Scan** manually once to test. It also runs every four hours on weekdays (UTC). Download the `job-scan-data` artifact to obtain `job_scan.json`.

## Streamlit deployment
Deploy the repository on Streamlit Community Cloud and select `app.py` as the entry point.

## Accuracy and coverage notes
- This is a public-feed aggregator, not an exhaustive global job crawler.
- LinkedIn and Indeed are not scraped; unrestricted public APIs are not available for that purpose.
- A source may not provide a posting timestamp or work mode. Such data remains unknown; unknown timestamps cannot be included in exact age filters.
- The built-in ATS score is a transparent keyword coverage estimate against recognized skills in the JD, not a commercial ATS score or hiring prediction.
- GitHub Actions uploads a JSON artifact; it does not automatically synchronize that artifact into a separately hosted Streamlit instance.
