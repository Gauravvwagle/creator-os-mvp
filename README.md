# CreatorOS MVP v0.1

A local-first niche research and scoring backend for a YouTube + Instagram creator business.

## What this MVP does

- Create and list niches.
- Store evidence against seven scoring criteria.
- Calculate a transparent weighted score (1–10).
- Rank niches and return a research report. Niches containing demo evidence are always listed after niches with real evidence.
- Hold proposed evidence as **candidates** that a human must approve or reject. Only approved candidates become evidence.
- Draft research plans with a local Ollama model (`qwen2.5:1.5b`). AI output is labelled `ai_draft` and is never saved or scored.
- Check that a quoted excerpt actually appears on a web page (`/research/verify-quote`).
- Expose an interactive API at `/docs`.
- Use SQLite locally; no paid API or cloud service is required.

**Important:** Scores are only as good as the evidence entered. The included demo seed data is fictional and clearly marked as demonstration data. It is not market research or a profitability claim.

## Requirements

- Windows 10/11
- Python 3.12 recommended
- VS Code
- PowerShell terminal
- [Ollama](https://ollama.com) with the `qwen2.5:1.5b` model pulled (only needed for the AI endpoints; everything else works without it)

## 1. Create and activate a virtual environment

Open this folder in VS Code. In the VS Code terminal (PowerShell):

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If `py -3.12` is unavailable, install Python 3.12 from https://www.python.org/downloads/ and enable "Add Python to PATH". Then reopen VS Code.

## 2. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure environment

```powershell
Copy-Item .env.example .env
```

The defaults work locally. The database will be created automatically at `./creatoros.db`.

## 4. Start the API

```powershell
uvicorn app.main:app --reload
```

Open:
- API health: http://127.0.0.1:8000/health
- Interactive API documentation: http://127.0.0.1:8000/docs

Keep the terminal running while using the API.

## 5. Add a niche

In `/docs`, open `POST /api/v1/niches`, click **Try it out**, and submit:

```json
{
  "name": "AI tools and workflow tutorials",
  "description": "Practical demonstrations of AI tools and automations for students, developers and small businesses",
  "target_audience": "Students, developers, creators and small businesses",
  "platforms": ["YouTube", "Instagram"],
  "status": "candidate"
}
```

Copy the returned niche `id`.

## 6. Add evidence and scores

Open `POST /api/v1/niches/{niche_id}/evidence`. Add one evidence record per criterion. (For real research, prefer the candidate workflow described below, which requires a source and a human decision.) Allowed criteria and weights:

| Criterion | Weight |
|---|---:|
| audience_demand | 20 |
| monetization_potential | 20 |
| affiliate_opportunities | 15 |
| competition_accessibility | 10 |
| production_feasibility | 10 |
| long_term_demand | 15 |
| creator_capability | 10 |

Example:

```json
{
  "criterion": "audience_demand",
  "score": 7,
  "confidence": "medium",
  "observation": "Example only: several relevant search suggestions and active tutorial discussions were observed.",
  "source_url": "https://example.com/research-notes",
  "is_demo": true
}
```

Replace the example observation and URL with real research. Do not score a criterion without recording the reason and source. `is_demo` should be `false` for actual research.

Then call `POST /api/v1/niches/{niche_id}/evaluate`.

## 7. View rankings

Call `GET /api/v1/reports/rankings`. Niches with incomplete criteria are returned as `incomplete` and are not ranked as if they had a complete score. Niches that contain demo evidence appear after all niches with real evidence, whatever their score.

## 8. Review proposed evidence (human approval)

1. `POST /api/v1/niches/{niche_id}/candidates` — propose a claim with a source URL and a source excerpt. It starts as `pending` and does not affect any score.
2. Recommended: `POST /api/v1/candidates/{id}/verify` fetches the candidate's source page and records whether its excerpt appears in the page text. The result (`quote_check_status`: `not_checked`, `found`, `not_found` or `fetch_failed`) is saved on the candidate and shown in the candidate list. It never approves or rejects anything, and it does **not block** approval: a failed check is a warning, and it is written into the approved evidence text so it stays visible later. This is a text match only; a human must still judge whether the excerpt supports the claim. Pages that build their text with JavaScript will not match. (`POST /api/v1/research/verify-quote` does the same check for any URL and excerpt without saving anything.)
3. `GET /api/v1/candidates` — list candidates (default `pending`; use `?status=approved` or `?status=rejected`).
4. `POST /api/v1/candidates/{id}/approve` creates real evidence and resets the niche's score. `POST /api/v1/candidates/{id}/reject` requires a reviewer note. Decisions are final (a second decision returns 409).

## 9. Local AI (optional)

Start Ollama, then call `POST /api/v1/research/plan` with a niche name and a criterion to get a research **plan** (questions and source types, not facts). `POST /api/v1/ai/generate` sends a free prompt. Both return drafts that are not evidence and are not saved.

## API endpoints

All endpoints below use the `/api/v1` prefix, except `/health`.

- `GET /health` — health check
- `POST /niches` — create a niche
- `GET /niches` — list niches
- `GET /niches/{niche_id}` — niche details and evidence
- `POST /niches/{niche_id}/evidence` — add evidence directly
- `POST /niches/{niche_id}/evaluate` — calculate score
- `GET /reports/rankings` — ranked report
- `POST /niches/{niche_id}/candidates` — propose evidence for review
- `GET /candidates` — list candidates by status
- `POST /candidates/{candidate_id}/approve` — approve and create evidence
- `POST /candidates/{candidate_id}/verify` — check the candidate's excerpt against its source page and record the result
- `POST /candidates/{candidate_id}/reject` — reject with a note
- `POST /research/plan` — AI-drafted research plan (needs Ollama)
- `POST /research/verify-quote` — check an excerpt exists on a page
- `POST /ai/generate` — free prompt to the local model (needs Ollama)

## Scoring model

Each criterion is scored from 1 to 10. The weights total 100.

`weighted_score = sum(score * weight) / 100`

The result is from 1 to 10. The API only treats a niche as fully evaluated when all seven criteria have evidence. The latest evidence for each criterion is used.

The score is a decision-support signal, not a prediction of income. Revenue depends on audience, geography, execution, eligibility, conversion, costs and many other factors.

## Project structure

```text
creator-os-mvp/
├── app/
│   ├── api/
│   │   ├── routes.py            niches, evidence, evaluation, rankings
│   │   ├── candidate_routes.py  propose / approve / reject evidence
│   │   ├── research_routes.py   AI research plans
│   │   ├── verify_routes.py     quote verification
│   │   └── ai_routes.py         free prompt to the local model
│   ├── agents/research_planner.py   criteria descriptions and plan prompt
│   ├── ai/ollama_client.py          talks to the local Ollama server
│   ├── research/
│   │   ├── fetcher.py               downloads one page safely
│   │   └── verify.py                HTML to text, quote matching
│   ├── models.py
│   ├── schemas.py                   the single definition of the 7 criteria
│   ├── scoring.py                   weights and the score calculation
│   ├── database.py
│   ├── migrations.py                adds new model columns to an older database
│   └── main.py
├── prompts/                     role descriptions for future agents (not yet loaded by any code)
│   ├── niche_research_agent.md
│   └── evidence_review_agent.md
├── tests/
│   ├── conftest.py              shared in-memory test database
│   ├── test_scoring.py
│   ├── test_candidates.py
│   ├── test_rankings.py
│   ├── test_verify.py
│   ├── test_consistency.py      fails if the criteria lists drift apart
│   ├── test_quote_check.py      candidate quote checks (web page is mocked)
│   └── test_migrations.py       old database upgrade
├── pytest.ini
├── test_ollama.py               manual check that Ollama is reachable
├── .env.example
├── requirements.txt
└── README.md
```

Run the tests with `pytest -v` (configured by `pytest.ini`).

**Database upgrades.** When the app starts, `app/migrations.py` adds any model columns missing from an older `creatoros.db`, keeping all existing rows. It only adds columns; renames, type changes and deletions still need a real migration tool such as Alembic.

If you add or rename a scoring criterion, change `WEIGHTS` in `scoring.py`, `Criterion` in `schemas.py` and `CRITERIA_GUIDE` in `agents/research_planner.py`. `tests/test_consistency.py` fails if they disagree.

## Troubleshooting

**`py` is not recognized:** Install Python 3.12 and reopen the terminal.

**`uvicorn` is not recognized:** Activate `.venv`, then run `python -m pip install -r requirements.txt`; start with `python -m uvicorn app.main:app --reload`.

**PowerShell activation is blocked:** Use the process-scoped execution-policy command above. It only affects the current PowerShell process.

**Port 8000 is busy:** Run `python -m uvicorn app.main:app --reload --port 8001`.

**Database schema changed:** Stop the server, back up `creatoros.db`, then delete it only if you are happy to lose local test data. For a serious deployment, add Alembic migrations rather than deleting the database.

## Next milestones

Done: candidate review workflow, local Ollama research plans, single-page quote verification, quote-check results recorded on candidates.

1. Decide whether a failed quote check should block approval (today it only warns).
2. Restrict direct evidence entry so real evidence must pass through the candidate gate.
3. Decide how `confidence` should affect the score (it is stored but not used today).
4. Add an `ai_suggested` candidate flow, with automatic quote checks before human review.
5. Add a dashboard.
6. Add content planning, production and publishing modules.
7. Add YouTube/Instagram integrations after checking current API permissions and platform rules.
