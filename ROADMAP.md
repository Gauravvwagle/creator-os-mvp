# CreatorOS roadmap

Read this first, whether you are the owner or a new coding session picking the work up.

## The rules that make CreatorOS trustworthy

1. **Evidence before score.** A niche is scored only when all seven criteria have evidence.
2. **A human decides.** Only an approved candidate becomes real evidence. Approve and reject are final.
3. **Honest labels.** Demo data is flagged and ranks last. AI output is labelled `ai_draft`, is never saved as evidence and never scored. Scores are decision support, not revenue forecasts.
4. **Machine checks are warnings, not proof.** A quote check proves characters appear on a page, nothing more.

Any change must keep all four true. Add a test for each rule you touch.

## Done

| # | What | Where |
| --- | --- | --- |
| 1 | Niches, evidence, weighted scoring, rankings | `app/scoring.py`, `app/api/routes.py` |
| 2 | Candidate review: pending, approve, reject | `app/api/candidate_routes.py` |
| 3 | Local Ollama connection and research plans (`ai_draft`) | `app/ai/`, `app/agents/`, `app/api/research_routes.py` |
| 4 | Quote verification (one page, text match) | `app/research/` |
| 5 | Quote-check results recorded on candidates and in approved evidence (warn, not block) | `candidate_routes.py`, `app/migrations.py` |
| 6 | Direct evidence entry restricted to demo data | `routes.py` |
| 7 | Local dashboard at `/dashboard` | `app/static/dashboard.html` |
| 8 | Demo niches rank below real ones; criteria defined once, guarded by a test | `tests/test_consistency.py` |
| 9 | AI-suggested evidence: code picks and copies the excerpt, the model picks a sentence number and drafts claim and score; saved as `pending`, confidence `low`, origin `ai_suggested` | `app/research/suggest.py`, `app/api/suggest_routes.py` |
| 10 | Content planning: ideas and scripts from approved real evidence only (demo ignored); drafts need human approval; numbers not in the evidence are flagged | `app/content/`, `app/api/content_routes.py` |
| 11 | Publishing queue: planned, ready, published; a package to post by hand. No automatic upload | `app/api/tracking_routes.py` |
| 12 | Performance snapshots (cumulative per day), money entries (integer cents, per currency) and an outcomes report that refuses conclusions below 5 posts | `app/api/tracking_routes.py` |
| 13 | Dashboard tabs for all of the above | `app/static/dashboard.html` |

## Next: can be built without new decisions

Do these in order, one branch and one pull request each.

- [ ] **Reviewer name.** Optional `reviewer` on approve and reject, stored on the candidate and written into the evidence text ("Approved by ..."). This is a label, not login security.
- [x] **AI-suggested candidates, safely.** The user supplies a page URL. Code fetches the page and splits it into sentences. The model may only choose a sentence by **number** and draft a claim and a score; **code copies the excerpt**, so the model can never invent a quote. The result is saved as a `pending` candidate with `origin = ai_suggested`, then quote-checked automatically. A human still approves.
- [ ] **Show evidence on the dashboard.** Per niche, list approved evidence with its source, date and quote-check line.
- [ ] **Confidence in the score.** Needs the owner's choice first (see below). Until then confidence stays recorded and unused.
- [x] **Content planning (drafts only).** From a ranked niche with real evidence, generate video ideas and outlines with Ollama. Store them as drafts labelled `ai_draft`. Nothing is published.
- [x] **Performance log.** Manual entry or CSV import of video results (views, watch time, revenue). Compare the research score with what actually happened.
- [ ] **Alembic migrations**, when a change needs a rename or a type change (`app/migrations.py` only adds columns).

## Needs a decision or credentials from the owner

These are deliberately **not** started.

- **Should a failed quote check block approval?** Today it warns. JavaScript-heavy pages produce false failures, so warning is the safer default.
- **How should confidence change the score?** Options: shrink low-confidence scores toward the middle, show a score range, or cap the total.
- **Publishing to YouTube or Instagram (live upload).** The human-gated queue and package exist; the uploader does not. Needs the owner's own accounts, OAuth credentials, a check of each platform's current API rules, and a decision on how much is automated. Automated posting can get an account restricted. Keep a human approval step before anything is posted.
- **Sharing the app with other people.** Needs real login, per-user reviewer identity and hosting. Today it is for one person on one laptop and must not be exposed to the internet.
- **Any paid API.** Nothing in the project costs money today. Ask before adding one.

## Rules for any working session

- Never push to `main`. One branch per milestone, then a pull request for the owner to read and merge.
- Run `python -m pytest -q` before every commit. All tests must pass.
- Never commit `.env`, `creatoros.db` or practice scripts.
- Keep this file current: tick items off and add what you learn.
- Say what you did not test. For example, the Windows laptop, a live Ollama call, or a live web fetch.
- Do not mark something done if it only works in a mock.

## Not yet tested (be honest)

- Anything on the owner's Windows laptop.
- Live Ollama calls: tests and the browser walk-through use a fake model. Small models may return poor JSON; the code retries twice and refuses bad output.
- A live web fetch that finds a quote.
- Money and results are entered by hand; nothing is imported from YouTube or a bank.
