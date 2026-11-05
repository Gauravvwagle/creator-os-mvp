# CreatorOS MVP v0.1

A local-first niche research and scoring backend for a YouTube + Instagram creator business.

## What this MVP does

- Create and list niche candidates.
- Store evidence against seven scoring criteria.
- Calculate a transparent weighted score (1–10).
- Rank niches and return a research report.
- Expose an interactive API at `/docs`.
- Use SQLite locally; no paid API or cloud service is required.

**Important:** Scores are only as good as the evidence entered. The included demo seed data is fictional and clearly marked as demonstration data. It is not market research or a profitability claim.

## Requirements

- Windows 10/11
- Python 3.12 recommended
- VS Code
- PowerShell terminal

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

In `/docs`, open `POST /niches`, click **Try it out**, and submit:

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

Open `POST /niches/{niche_id}/evidence`. Add one evidence record per criterion. Allowed criteria and weights:

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

Then call `POST /niches/{niche_id}/evaluate`.

## 7. View rankings

Call `GET /reports/rankings`. Niches with incomplete criteria are returned as `incomplete` and are not ranked as if they had a complete score.

## API endpoints

- `GET /health` — health check
- `POST /niches` — create a niche
- `GET /niches` — list niches
- `GET /niches/{niche_id}` — niche details and evidence
- `POST /niches/{niche_id}/evidence` — add evidence
- `POST /niches/{niche_id}/evaluate` — calculate score
- `GET /reports/rankings` — ranked report

## Scoring model

Each criterion is scored from 1 to 10. The weights total 100.

`weighted_score = sum(score * weight) / 100`

The result is from 1 to 10. The API only treats a niche as fully evaluated when all seven criteria have evidence. The latest evidence for each criterion is used.

The score is a decision-support signal, not a prediction of income. Revenue depends on audience, geography, execution, eligibility, conversion, costs and many other factors.

## Project structure

```text
creator-os-mvp/
├── app/
│   ├── api/routes.py
│   ├── models.py
│   ├── schemas.py
│   ├── scoring.py
│   ├── database.py
│   └── main.py
├── prompts/
│   ├── niche_research_agent.md
│   └── evidence_review_agent.md
├── tests/
│   └── test_scoring.py
├── .env.example
├── requirements.txt
└── README.md
```

## Troubleshooting

**`py` is not recognized:** Install Python 3.12 and reopen the terminal.

**`uvicorn` is not recognized:** Activate `.venv`, then run `python -m pip install -r requirements.txt`; start with `python -m uvicorn app.main:app --reload`.

**PowerShell activation is blocked:** Use the process-scoped execution-policy command above. It only affects the current PowerShell process.

**Port 8000 is busy:** Run `python -m uvicorn app.main:app --reload --port 8001`.

**Database schema changed:** Stop the server, back up `creatoros.db`, then delete it only if you are happy to lose local test data. For a serious deployment, add Alembic migrations rather than deleting the database.

## Next milestones

1. Add a research-source collector with source/date capture.
2. Add a local Ollama model for research synthesis (not as a source of facts).
3. Add LangGraph orchestration and human approval checkpoints.
4. Add a React dashboard.
5. Add content planning, production and publishing modules.
6. Add YouTube/Instagram integrations after checking current API permissions and platform rules.
