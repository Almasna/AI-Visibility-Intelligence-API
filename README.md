# AI Visibility Intelligence API

## Overview

This Flask API helps a business measure where commercially valuable AI-search demand exists, whether its domain is cited in a current ChatGPT answer, and what content could close the most valuable gaps. It discovers realistic buyer questions with an LLM, enriches them with paid third-party data, calculates a deterministic opportunity score, and persists every run for historical analysis.

There is intentionally no frontend or authentication. The pipeline is synchronous and creates a new historical `PipelineRun` on every invocation.

## Architecture

```text
REST API (Flask blueprints + Pydantic validation)
  -> PipelineService (orchestration and intermediate commits)
     -> QueryDiscoveryAgent
        -> LLMService -> OpenAI Chat Completions JSON mode
     -> VisibilityScoringAgent
        -> ExternalDataService -> DataForSEO Google Ads Live
                               -> DataForSEO ChatGPT LLM Responses Live
        -> deterministic opportunity scoring utility
     -> ContentRecommendationAgent
        -> LLMService -> OpenAI Chat Completions JSON mode
  -> SQLAlchemy -> SQLite by default / PostgreSQL via DATABASE_URL
```

`create_app()` loads configuration, initializes SQLAlchemy and Flask-Migrate, registers the versioned API blueprint and centralized JSON error handlers, and configures logging. HTTP, validation, persistence, agent reasoning, provider I/O, scoring, and orchestration are separate modules.

## Agent design

The agents always execute in this order:

1. `QueryDiscoveryAgent` receives the complete profile and asks for 10–20 unique, natural-language buyer questions spanning commercial, comparison, transactional, and useful informational intent.
2. `VisibilityScoringAgent` batches the query set through DataForSEO Google Ads, checks each query through DataForSEO's web-enabled ChatGPT response endpoint, and calculates its opportunity score. A failure for one query is stored in `scoring_error` and does not discard successful queries.
3. `ContentRecommendationAgent` receives only the highest-scoring gaps where `domain_visible == false` and produces 3–5 specific recommendations tied verbatim to those queries.

Agents have independent system prompts and exact JSON schemas. Raw LLM text is JSON-decoded, safely unwrapped only when a JSON object is clearly present, and validated with strict Pydantic models. Invalid JSON, missing fields, extra fields, invalid enums, insufficient list lengths, and duplicates become controlled agent errors.

The service constructors accept their external dependencies, so tests use deterministic fakes and never call a paid service.

## Opportunity score

For each successfully scored batch:

```text
volume_score     = log(1 + volume) / log(1 + max_batch_volume)
difficulty_score = 1 - clamp(competition_index, 0, 100) / 100
visibility_gap   = 1.0 when absent, 0.0 when visible, 0.5 when unknown
intent_score     = 1.0 commercial/comparison, 0.9 transactional, 0.6 informational

opportunity = clamp(
    0.35 * volume_score
  + 0.25 * difficulty_score
  + 0.25 * visibility_gap
  + 0.15 * intent_score,
  0.0,
  1.0
)
```

Logarithmic volume normalization preserves ordering without allowing one very large keyword to dominate. Difficulty rewards less-contested demand, the visibility gap gives absent domains a material uplift, and intent favors queries closer to a purchase decision. The result is rounded to four decimal places and is deterministic.

## External APIs

### DataForSEO Google Ads Search Volume Live

The adapter sends one batch to:

```text
POST /v3/keywords_data/google_ads/search_volume/live
```

It reads the real `search_volume` and `competition_index` fields documented by [DataForSEO](https://docs.dataforseo.com/v3/keywords_data-google_ads-search_volume-live/). Authentication uses HTTP Basic credentials from `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`; requests have explicit timeouts and controlled handling for connection failures, invalid JSON, HTTP errors, provider task errors, authentication failures, and rate limits.

Google Ads limits keywords to 10 words and 80 characters. Natural-language questions are therefore converted to a normalized 10-word keyword proxy while the original question remains stored and is used for the AI visibility check. Google may return `null`/no data; the API records that query as a scoring failure and never invents a number.

`competition_index` is Google Ads paid-search competition (0–100), not an organic keyword-difficulty metric. It is named `competitive_difficulty` in the simplified domain model but this limitation matters when interpreting results.

### DataForSEO ChatGPT LLM Responses Live

Each question is sent to:

```text
POST /v3/ai_optimization/chat_gpt/llm_responses/live
```

The integration enables and forces web search using the current contract in [DataForSEO's LLM Responses documentation](https://docs.dataforseo.com/v3/ai_optimization-chat_gpt-llm_responses-live/). It checks ordered annotation URLs in the returned `items[].sections[].annotations[]` array. `domain_visible` is true when the normalized target domain (or its subdomain) is cited. `visibility_position` is the target's 1-based position among unique cited source domains—not a ranking assigned by ChatGPT. An exact uncited domain mention counts as visible but has a null position. DataForSEO notes that forced web search does not guarantee citations; an answer with neither a matching citation nor literal domain mention is recorded as not visible.

This is a real observation of one configured ChatGPT model, country, prompt, and point in time. It is not a guarantee about every model, session, geography, or future answer.

### OpenAI

Discovery and recommendation use the official OpenAI Python client and Chat Completions JSON mode. Provider token usage is stored when returned; DataForSEO AI input/output token counts are also included. Token counts remain null if a provider does not return them and are never estimated.

## Setup

Requirements: Python 3.12+ and API credentials for OpenAI and DataForSEO.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Fill in OPENAI_API_KEY, DATAFORSEO_LOGIN, and DATAFORSEO_PASSWORD
flask --app run.py db upgrade
flask --app run.py run
```

### Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in OPENAI_API_KEY, DATAFORSEO_LOGIN, and DATAFORSEO_PASSWORD
flask --app run.py db upgrade
flask --app run.py run
```

The development server listens on `http://127.0.0.1:5000`. `GET /health` returns `{"status":"ok"}`.

### Environment variables

| Variable | Required for live run | Default / purpose |
|---|---:|---|
| `OPENAI_API_KEY` | Yes | Agent 1 and Agent 3 |
| `LLM_PROVIDER` | Yes | `openai` (the supported provider in this build) |
| `OPENAI_MODEL` | No | `gpt-4.1-mini` |
| `DATAFORSEO_LOGIN` | Yes | DataForSEO Basic Auth username |
| `DATAFORSEO_PASSWORD` | Yes | DataForSEO Basic Auth password |
| `DATAFORSEO_LOCATION_CODE` | No | `2840` (United States) |
| `DATAFORSEO_LANGUAGE_CODE` | No | `en` |
| `DATAFORSEO_AI_MODEL` | No | `gpt-4.1-mini` |
| `DATAFORSEO_COUNTRY_CODE` | No | `US` |
| `DATABASE_URL` | No | `sqlite:///dev.db`; accepts PostgreSQL URLs |
| `SECRET_KEY` | Production | Flask secret |
| `LOG_LEVEL` | No | `INFO` |

The app fails clearly when live credentials are absent. There is no fake or random production fallback.

## Database migrations

An initial working migration is checked in. For normal setup:

```bash
flask --app run.py db upgrade
```

When intentionally creating a new migration after changing models:

```bash
# Only for a repository that has no migrations directory:
flask --app run.py db init

flask --app run.py db migrate -m "describe the schema change"
flask --app run.py db upgrade
```

Review generated migrations before applying them. UUIDs are stored as portable 36-character strings, JSON uses SQLAlchemy's cross-dialect type, foreign keys cascade, and query/filter columns have explicit indexes.

## API examples

### Create a profile

```bash
curl -X POST http://localhost:5000/api/v1/profiles \
  -H "Content-Type: application/json" \
  -d '{
    "name":"Surfer SEO",
    "domain":"https://www.surferseo.com/",
    "industry":"SEO Software",
    "description":"AI-powered SEO content optimization tool",
    "competitors":["clearscope.io","marketmuse.com","frase.io"]
  }'
```

```json
{
  "profile_uuid": "6601db54-9ec4-4ddd-a458-ebd37ac2ad07",
  "name": "Surfer SEO",
  "domain": "surferseo.com",
  "status": "created",
  "created_at": "2026-08-08T20:00:00Z"
}
```

### Run the three-agent pipeline

```bash
curl -X POST http://localhost:5000/api/v1/profiles/PROFILE_UUID/run
```

```json
{
  "pipeline_run_uuid": "97b4f129-128b-4e80-bfdf-a87e92a04dd6",
  "status": "completed",
  "queries_discovered": 15,
  "queries_scored": 15,
  "top_opportunity_queries": [
    {
      "query_uuid": "35f577a2-ed6d-4d4d-a24f-40bd25f7cb01",
      "run_uuid": "97b4f129-128b-4e80-bfdf-a87e92a04dd6",
      "query_text": "What is the best AI SEO content tool?",
      "search_intent": "commercial",
      "estimated_search_volume": 1200,
      "competitive_difficulty": 62.0,
      "opportunity_score": 0.845,
      "domain_visible": false,
      "visibility_position": null,
      "visibility_source": "dataforseo_chatgpt_web_search",
      "scoring_error": null,
      "discovered_at": "2026-08-08T20:00:01Z",
      "updated_at": "2026-08-08T20:00:07Z"
    }
  ],
  "recommendations": [
    {
      "recommendation_uuid": "fc33fd1b-d40d-4ac9-8b3d-a53a640dff35",
      "target_query_uuid": "35f577a2-ed6d-4d4d-a24f-40bd25f7cb01",
      "content_type": "comparison_page",
      "title": "Best AI SEO Content Tools for Content Teams",
      "rationale": "Addresses a measured high-opportunity citation gap.",
      "target_keywords": ["AI SEO content tool", "content optimization software"],
      "priority": "high",
      "created_at": "2026-08-08T20:00:09Z"
    }
  ],
  "tokens_used": 12345
}
```

A partial Agent 2 or Agent 3 failure returns successful work with `status: "partially_completed"`. A fatal failure returns a consistent error and includes the recorded run UUID:

```json
{
  "error": {
    "code": "PIPELINE_FAILED",
    "message": "Query discovery failed; the pipeline run was recorded.",
    "details": {
      "pipeline_run_uuid": "97b4f129-128b-4e80-bfdf-a87e92a04dd6",
      "status": "failed"
    }
  }
}
```

### Read profile and results

```bash
curl http://localhost:5000/api/v1/profiles/PROFILE_UUID
curl "http://localhost:5000/api/v1/profiles/PROFILE_UUID/queries?min_score=0.5&status=not_visible&page=1&per_page=20"
curl "http://localhost:5000/api/v1/profiles/PROFILE_UUID/recommendations?page=1&per_page=20"
```

Query status values are `visible`, `not_visible`, and `unknown`. Results sort by opportunity score descending with null scores last. Filtering and pagination execute in the database.

### Recheck one query

```bash
curl -X POST http://localhost:5000/api/v1/queries/QUERY_UUID/recheck
```

Recheck invokes only `VisibilityScoringAgent`, refreshes the existing row, uses the run's maximum volume for normalization, and neither rediscovers queries nor creates recommendations.

## Error format

All errors use one JSON shape and never include a traceback or secret:

```json
{
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "Business profile not found."
  }
}
```

Validation errors add a safe `details` list. Relevant statuses include 400, 404, 409, 422, 500, and 502.

## Testing

```bash
pytest
```

The suite covers profile validation, both generative agents' malformed output, duplicate queries, scoring and bounds, visible/absent domains, DataForSEO contract parsing and errors, complete/partial/failed pipelines, filters, ordering, pagination, recommendations, and recheck behavior. All provider calls are mocked with deterministic fixtures.

To smoke-test migrations with a temporary database:

```bash
DATABASE_URL=sqlite:///migration_smoke.db flask --app run.py db upgrade
flask --app run.py db downgrade base
flask --app run.py db upgrade
```

## Docker

```bash
cp .env.example .env
# Fill in live credentials
docker compose up --build
```

The container applies migrations on startup and serves Gunicorn on `http://localhost:8000`. SQLite data is kept in a named volume. For PostgreSQL, change `DATABASE_URL`; no application code changes are required.

## Tradeoffs and limitations

- Synchronous execution keeps the assessment deployable without Celery, but a run can take longer than a normal request and incurs paid requests. Production deployments should consider a job queue and polling endpoint.
- One Google Ads batch minimizes paid keyword calls; AI visibility still requires one live answer per query so failures can be isolated.
- Google Ads competition is paid-search competition, not organic SEO difficulty.
- Long questions use a documented 10-word Google Ads proxy for volume while visibility uses the full question.
- Citation order is a transparent proxy for visibility position, not a provider-supplied brand rank.
- AI answers are model-, prompt-, time-, and geography-specific. Recheck exists because visibility is not stable.
- The OpenAI implementation is intentionally one provider despite a provider selector; unsupported values fail explicitly. An Anthropic adapter can be added behind `LLMService` without changing agents.
- SQLite is the zero-setup default. PostgreSQL is the recommended multi-process production database.

## Project tree

```text
.
|-- app/
|   |-- agents/          # three independent agent components
|   |-- api/             # versioned Flask routes
|   |-- models/          # SQLAlchemy entities and relationships
|   |-- schemas/         # Pydantic request, response, and LLM schemas
|   |-- services/        # LLM, DataForSEO, dependencies, orchestration
|   |-- utils/           # errors, domains, logging, scoring, time
|   |-- __init__.py      # application factory
|   |-- config.py
|   `-- extensions.py
|-- migrations/          # working Alembic environment and initial revision
|-- tests/               # deterministic unit and API tests
|-- .env.example
|-- Dockerfile
|-- docker-compose.yml
|-- pytest.ini
|-- requirements.txt
|-- run.py
`-- README.md
```

## AI tools

AI coding assistance was used to help implement and review this assessment. The implementation was validated with the included deterministic tests and a migration upgrade/downgrade smoke test; live paid requests still require the user's own credentials.
