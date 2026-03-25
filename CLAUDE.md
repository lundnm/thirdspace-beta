# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ThirdSpace Beta** — A community platform that matches sports fans with local Ann Arbor venues to watch games together. The system scrapes live sports schedules, cleans user survey data, matches fans to venues, and sends personalized emails with AI-generated game previews.

## Running the Pipeline

```bash
# Install dependencies (uses .venv/)
pip install -r requirements.txt
playwright install chromium

# Run the full daily pipeline
python app/main.py

# Send emails after pipeline completes
cd app/
python ThirdSpace_Mailer.py
```

Individual stages can be run standalone from within `scripts/`:
```bash
cd scripts/
python DailyStreamingScraperV2.py   # Stage 1: Scrape schedules
python stream_cleaningV2.py          # Stage 2: Clean stream data
python user_cleaning.py             # Stage 3: Clean user data
python matching.py                  # Stage 4: Match users to venues
```

## Architecture

The system is a 4-stage daily pipeline, all orchestrated by `scripts/main.py`:

```
livesportsontv.com
       ↓
[DailyStreamingScraperV2.py] → livesports_schedule_{DATE}.csv
       ↓
[stream_cleaningV2.py] → streaming_cleaned_{DATE}.csv
                                         ↓
Raw_User_Responses.csv → [user_cleaning.py] → User_Responses_Cleaned.csv
                                         ↓
                              [matching.py] → User_Responses_With_Venues_{DATE}.csv
                                         ↓
                           [ThirdSpace_Mailer.py] → Personalized emails
```

**Stage 1 — Scraper (`scripts/DailyStreamingScraperV2.py`):** Uses Playwright (headless Chromium, async) + BeautifulSoup to scrape NBA/MCBB/WCBB game schedules. Filters for today's games only.

**Stage 2 — Stream Cleaning (`scripts/stream_cleaningV2.py`):** Normalizes times to 24hr format, reformats matchups, filters broadcast services to Detroit-area channels (cable, streaming, local networks).

**Stage 3 — User Cleaning (`scripts/user_cleaning.py`):** Validates emails, normalizes team names via fuzzy matching against `data/master_teams.csv` (85% threshold using `thefuzz`), extracts 5 predefined venue feature preferences.

**Stage 4 — Matching (`scripts/matching.py`):** Builds fanbase stats per team, matches games to venues by venue features + streaming service overlap, assigns one venue per game, outputs personalized recommendations per user.

**Email (`app/ThirdSpace_Mailer.py`):** Jinja2-templated HTML emails via Gmail SMTP, with Google Gemini API generating game preview text. Uses `app/ThirdSpace_template.html`. Sends with 1-second delay between recipients.

## Key Data Files

| File | Description |
|------|-------------|
| `data/Raw_User_Responses.csv` | User survey input (source of truth for users) |
| `data/User_Responses_Cleaned.csv` | Cleaned/validated user data |
| `data/ThirdSpaceVenues.csv` | Venue database with features + streaming services |
| `data/master_teams.csv` | Reference list of NBA + college basketball teams |
| `data/streaming_cleaned_{DATE}.csv` | Today's filtered game schedule |
| `data/User_Responses_With_Venues_{DATE}.csv` | Final pipeline output |

## Configuration

**Environment variables (`.env`):**
- `OPENAI_API_KEY` — LangChain/OpenAI
- `TAVILY_API_KEY` — Web search
- Gemini API key and Gmail App Password are set directly in `ThirdSpace_Mailer.py`

**Email sender:** `thirdspace.beta@gmail.com` via Gmail SMTP (`smtp.gmail.com:587`) using an App Password (not the account password).

## Development Notebooks

The `notebooks/` directory contains Jupyter notebooks used for prototyping each pipeline stage. The production scripts in `scripts/` are the canonical versions.
