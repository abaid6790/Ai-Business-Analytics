# AI Business Analytics Platform

A multi-user SaaS web application that lets people upload a CSV/Excel dataset and get automatic data cleaning, exploratory analysis, AI-powered insights and Q&A, anomaly detection, machine-learning predictions, forecasting, and exportable reports — without writing code.

Built with Flask, Pandas, scikit-learn/XGBoost, and a provider-agnostic AI layer (Gemini by default, with Groq/OpenRouter/Claude/OpenAI as configurable fallbacks).

**Status:** All 14 planned phases complete. 332 automated tests passing.

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [AI architecture](#ai-architecture)
- [ML pipeline](#ml-pipeline)
- [Project structure](#project-structure)
- [Installation](#installation)
- [Environment configuration](#environment-configuration)
- [Database setup](#database-setup)
- [Running locally](#running-locally)
- [Testing](#testing)
- [Deployment](#deployment)
- [Security](#security)
- [Future improvements](#future-improvements)
- [License](#license)

---

## Features

**Accounts & workspace**
- Registration with email verification, login/logout, forgot/reset password, change password, account deletion — all data-isolated per user.
- Admin panel: user management (disable/delete), global activity logs, AI provider monitoring, live-editable usage limits and provider fallback order.

**Data**
- Drag-and-drop CSV/XLSX/XLS upload with a live preview and data-quality summary before you commit.
- Automatic data cleaning: missing values, duplicates, outliers, type conversion, column removal — always writes a new file, never touches the original.
- Automatic EDA: descriptive statistics, correlation heatmap, and auto-suggested charts based on column types.
- Interactive chart builder (bar/line/area/pie/scatter/histogram) with filters and aggregation, saved and reusable.

**AI**
- Ask questions about your data in plain English, with the answer streamed to you as it's generated — the AI is never allowed to invent a number. It proposes a computation plan, the plan is validated against a whitelist, Pandas executes it, and only the *real, computed result* is fed back to the AI to explain in words.
- One-click automatic insights, grounded the same way.
- Provider-agnostic: Gemini by default, with automatic multi-key rotation and fallback to Groq/OpenRouter/Claude/OpenAI if configured. See [AI architecture](#ai-architecture).

**Analytics**
- Anomaly detection via IQR, Z-score, or Isolation Forest (multivariate), with per-row scoring and visualization.
- Machine learning: automatic classification/regression detection, 9 algorithms trained and compared per run (Logistic Regression, Decision Tree, Random Forest, Gradient Boosting, XGBoost for classification; Linear, Random Forest, Gradient Boosting, XGBoost for regression), leakage-safe pipelines, cross-validation, SHAP-based explainability with a built-in fallback, and a working prediction form.
- Forecasting: automatic trend/seasonality detection and Holt-Winters / Holt-linear / linear-regression forecasting with approximate confidence bands — only shown for datasets that actually have a date + numeric column.

**Reports & organization**
- Saved Projects group related datasets, charts, and reports together.
- Report generator pulls together the dataset overview, data quality, EDA, saved charts, AI insights, and ML results into one report, exportable as PDF, Excel, CSV, or JSON.
- Personal History page and, for admins, a global system log.

---

## Architecture

```mermaid
flowchart TB
    subgraph Client
        Browser[Browser / Bootstrap UI]
    end

    subgraph Flask["Flask Application"]
        Routes[Blueprints / Routes]
        Forms[WTForms]
        Services[Service Layer]
    end

    subgraph Services["app/services/"]
        Analytics[analytics/<br/>profiling, cleaning, EDA,<br/>charts, anomalies, queries]
        MLSvc[ml/<br/>pipelines, training,<br/>evaluation, SHAP]
        ForecastSvc[forecasting/<br/>trend, seasonality,<br/>Holt-Winters]
        ReportSvc[reports/<br/>PDF/Excel/CSV/JSON export]
        AISvc[ai/<br/>AIProviderManager]
    end

    subgraph AIProviders["AI Providers"]
        Gemini[Gemini<br/>multi-key rotation]
        Groq[Groq]
        OpenRouter[OpenRouter]
        Claude[Claude]
        OpenAI[OpenAI]
    end

    DB[(PostgreSQL / SQLite)]
    FS[(Local file storage<br/>uploads / models / reports)]
    Mail[SMTP]

    Browser <--> Routes
    Routes --> Forms
    Routes --> Services
    Analytics --> DB
    MLSvc --> DB
    MLSvc --> FS
    ReportSvc --> FS
    AISvc --> Gemini
    AISvc -.fallback.-> Groq
    AISvc -.fallback.-> OpenRouter
    AISvc -.fallback.-> Claude
    AISvc -.fallback.-> OpenAI
    Routes --> DB
    Routes --> Mail
```

**Key design decisions:**
- **Every AI request goes through one class, `AIProviderManager`.** No route or service ever imports a specific provider directly — this is what makes "add a new AI provider" a config change, not a code change.
- **Every user-owned resource is fetched through `get_owned_or_404()` / `owner_scoped_query()`.** This is the single choke point that guarantees one user can never read or modify another user's data.
- **Cleaning never mutates the original file.** A cleaned dataset is always a new `Dataset` row pointing at a new file, linked back via `source_dataset_id`.
- **The AI Data Analyst never invents numbers.** User questions go through plan -> validate -> execute (real Pandas) -> explain, with the computed result injected into the AI's context for the final explanation.
- **Background ML training** runs on a thread pool so the request returns immediately; the UI polls for status. Documented as an MVP choice — moving to Celery/RQ for multi-worker deployments doesn't require changing any training logic, only how it's invoked.

---

## AI architecture

```mermaid
sequenceDiagram
    participant U as User
    participant R as Flask Route
    participant M as AIProviderManager
    participant C as Response Cache
    participant G as Gemini Key Pool
    participant F as Fallback Provider

    U->>R: Ask a question
    R->>M: generate_json(plan_prompt)
    M->>C: cache hit?
    alt cache hit
        C-->>M: cached response
    else cache miss
        M->>G: try key 1
        alt rate limited
            G->>G: cooldown key 1, try key 2
        end
        alt all Gemini keys exhausted
            M->>F: fall back to next provider in order
        end
        G-->>M: response
        M->>C: store in cache
    end
    M-->>R: plan JSON
    R->>R: validate_plan against whitelist
    R->>R: execute_plan with real Pandas
    R->>M: analyze(computed_result, question)
    M-->>R: grounded explanation
    R-->>U: answer (never an invented number)
```

**Supported providers:** Gemini (default), Groq, OpenRouter, Claude (Anthropic), OpenAI — all implementing the same `generate()` / `generate_json()` / `stream()` / `analyze()` interface (`app/services/ai/base_provider.py`).

**Gemini multi-key rotation:** configure up to 4 keys (`GEMINI_API_KEY_1..4`). Requests round-robin across available keys (never random); a rate-limited or auth-failing key is cooled down and skipped until it recovers, and the pool only surfaces a failure to the fallback chain once every key has been tried.

**Fallback order:** configurable via `AI_PROVIDER_ORDER` (or live-editable by an admin in the AI Providers panel). A permanent/user error (bad prompt) never triggers fallback — only rate-limit/transient/auth errors do, per the reasoning that retrying a broken request against a different provider just wastes a call.

**Response caching & usage limits:** identical (provider, model, prompt, context) requests are cached; every attempt is logged to `AIUsage`; daily/monthly per-user limits are enforced before any provider is called, and cache hits don't count against them. Both the cache and Gemini's key-rotation state default to in-process storage (zero setup) and automatically switch to Redis-backed implementations when `REDIS_URL` is set — same logic either way, just shared across workers instead of siloed per worker.

**Controlled execution, not arbitrary code:** the AI never generates or executes Python/Pandas code. It only ever names one of a fixed set of whitelisted operations (`aggregate`, `top_n`, `correlation`, `trend`, ...) plus column names, which are validated against the actual dataset before anything runs (`app/services/analytics/query_executor.py`).

---

## ML pipeline

```mermaid
flowchart LR
    A[Select target column] --> B[Auto-detect<br/>classification vs regression]
    B --> C[Build leakage-safe Pipeline<br/>ColumnTransformer + estimator]
    C --> D[Train/test split<br/>+ cross-validation]
    D --> E[Fit each of 9 algorithms<br/>on a background thread]
    E --> F[Evaluate:<br/>accuracy/F1/ROC-AUC or<br/>MAE/RMSE/R2]
    F --> G[SHAP feature importance<br/>with built-in fallback]
    G --> H[Rank models,<br/>flag the best]
    H --> I[Prediction form<br/>+ report inclusion]
```

Imputation, scaling, and one-hot encoding are always fit *inside* the pipeline, so cross-validation and the train/test split each refit preprocessing from scratch per fold — never peeking at test data.

---

## Project structure

```
ai-business-analytics/
    app.py                  # WSGI entry point
    config.py                # Environment-based config (Dev/Testing/Production)
    requirements.txt
    .env.example
    app/
        __init__.py           # App factory
        extensions.py         # Shared Flask extension instances
        cli.py                 # flask create-admin
        models/                 # SQLAlchemy models
        routes/                 # Blueprints (one per feature area)
        forms/                  # WTForms
        services/
            ai/                    # AIProviderManager + provider implementations
            analytics/              # Profiling, cleaning, EDA, charts, anomalies, query executor
            ml/                     # Pipelines, training, evaluation, explainability, job runner
            forecasting/             # Trend/seasonality detection, forecasting
            reports/                 # PDF/Excel/CSV/JSON export
        templates/               # Jinja2 templates
        static/                  # CSS/JS
        utils/                   # tokens, email, ownership guard, activity logging
    migrations/                # Alembic migration history
    tests/                     # 332 tests across 29 files
    data/
        uploads/ processed/ models/ reports/
    logs/
```

---

## Installation

```bash
git clone <this-repo>
cd ai-business-analytics

python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

## Environment configuration

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
- `SECRET_KEY` — a real random value. **The app will refuse to start in production with the default dev key.**
- `DATABASE_URL` — leave blank for SQLite (auto-resolves to an absolute path under `data/`), or set a PostgreSQL URL (see below).
- At least one AI provider key if you want the AI features (`GEMINI_API_KEY_1` is the simplest to start with).
- `MAIL_*` — leave `MAIL_USERNAME` blank in development; emails are logged to `logs/app.log` instead of sent.
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — used by `flask create-admin`.

All AI provider keys, model names, the fallback order, and per-user usage limits are environment-driven — adding a new provider or changing limits never requires touching business logic (though an admin can also live-edit limits and fallback order from the Admin panel without a restart).

## Database setup

**SQLite (default, zero setup):**
```bash
export FLASK_APP=app.py
flask db upgrade
```

**PostgreSQL:**
```bash
# 1. Create a database
createdb ai_analytics

# 2. Point DATABASE_URL at it
export DATABASE_URL="postgresql+psycopg2://user:password@localhost:5432/ai_analytics"

# 3. Run the same migrations - no code changes needed
flask db upgrade
```
This has been verified against a real PostgreSQL 16 instance (all 14 tables created correctly, full register -> upload -> dataset-persistence flow tested end to end) — not just structurally checked.

**Bootstrap an admin account:**
```bash
flask create-admin
```
Reads `ADMIN_EMAIL` / `ADMIN_PASSWORD` from your environment; safe to re-run (promotes an existing user if the email already exists).

## Running locally

```bash
flask run
# or: python app.py
```
Visit `http://127.0.0.1:5000`.

In dev mode (no `MAIL_USERNAME` set), verification/reset emails are logged instead of sent — look in `logs/app.log` (or your terminal) for a line like:
```
[EMAIL SUPPRESSED] to=[...] subject=Verify your email address
...
http://localhost/auth/verify-email/<token>
```

## Testing

```bash
python -m pytest tests/ -v
```

332 tests across 29 files, covering:
- Full auth lifecycle (register -> verify -> login -> reset -> change password -> delete) and cross-user data isolation on every resource type
- Upload validation (extension whitelist, magic-byte sniffing, empty/binary rejection)
- Data cleaning (each action in isolation, immutability of the source data)
- EDA/chart-builder correctness against known aggregation results
- AI provider manager: key rotation under simulated failures, fallback ordering, cache hit/miss, usage-limit enforcement — with a real DB-backed run confirming actual `AIUsage` rows and limit blocking
- The AI Data Analyst's "never invent a number" guarantee, asserted explicitly (the computed value is checked to appear in what's passed to the explanation call)
- Anomaly detection against datasets with deliberately injected, known outliers
- ML training end-to-end through the real background thread pool (not mocked) — kickoff -> poll -> completion -> best-model ranking -> prediction
- Forecasting against synthetic data with known trend/seasonality
- Report generation: all 4 export formats verified as genuinely valid files (PDF parsed and page-counted, Excel sheet names checked, JSON round-tripped)
- Admin access control on every route, and an explicit test that a realistic-looking API key never appears in the rendered admin page

## Deployment

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env: set a real SECRET_KEY and at least one AI provider key.
# Leave DATABASE_URL blank — docker-compose overrides it to point at
# the bundled Postgres service automatically.

docker compose up --build
```

This starts two containers: `web` (the Flask app behind gunicorn, 4 workers) and `db` (PostgreSQL 16). On startup, `web` automatically waits for the database, runs `flask db upgrade`, and — if `ADMIN_EMAIL`/`ADMIN_PASSWORD` are set in `.env` — bootstraps the admin account, before starting the server. Visit `http://localhost:8000`.

Data persists across restarts via named volumes (`postgres_data`, `app_data` for uploads/models/reports, `app_logs`). To stop: `docker compose down` (add `-v` to also wipe the volumes).

**Note on verification:** the Dockerfile and compose file have been validated for YAML/shell syntax correctness and reviewed line-by-line against known gotchas for this dependency set (XGBoost needs `libgomp1`, psycopg2 needs `libpq5`, both included) — but a full build-and-run wasn't possible in the environment this was developed in due to a network restriction on reaching Docker Hub. If you hit a build issue on a real machine, it's most likely a missing system library for one of the heavier scientific packages (pandas/sklearn/xgboost/shap/matplotlib) — please report it and it can be added to the `apt-get install` line in the Dockerfile.

### Manual (gunicorn + reverse proxy)

**WSGI entry point:** `app.py` exposes `app`, usable directly with gunicorn:
```bash
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```
Put a reverse proxy (nginx, Caddy) in front for TLS termination and static file serving.

**Before deploying:**
1. Set `FLASK_ENV=production` and a real `SECRET_KEY` — the app validates this at startup and refuses to run with the dev default.
2. Point `DATABASE_URL` at PostgreSQL.
3. Set real `MAIL_*` credentials so verification/reset emails actually send.
4. Set real AI provider keys if AI features are wanted.
5. Consider moving `RATELIMIT_STORAGE_URI` off `memory://` to Redis if running multiple workers (rate limits are currently per-process).
6. Schedule `flask cleanup-temp-uploads` to run periodically (e.g. hourly via cron) — it deletes temp files from abandoned uploads (previewed but never committed) older than `DATASET_TEMP_MAX_AGE_HOURS` (default 24h). Safe to run repeatedly; a no-op if nothing is stale. Example crontab entry:
   ```
   0 * * * * cd /path/to/ai-business-analytics && /path/to/venv/bin/flask cleanup-temp-uploads >> logs/cleanup.log 2>&1
   ```

**Known multi-worker limitation (documented, not silently ignored):** the ML background thread pool still lives in-process per worker — training runs are only visible to the worker that started them. Gemini key rotation and the AI response cache are no longer subject to this: setting `REDIS_URL` (the `docker compose` stack does this automatically) shares both correctly across every worker/container. Set `RATELIMIT_STORAGE_URI` to the same Redis instance too if running multiple workers, so rate limits are also shared rather than per-process.

## Security

- Passwords hashed with Werkzeug (never stored or logged in plaintext).
- Email verification required before login; forgot/reset password flows never reveal whether an email is registered.
- CSRF protection on every form (Flask-WTF), including AJAX requests via the `X-CSRFToken` header.
- Rate limiting on auth endpoints, uploads, AI chat/insights, and ML training kickoff (the most resource-intensive endpoint in the app).
- Upload validation: extension whitelist plus magic-byte sniffing (a renamed `.exe` claiming to be `.csv` is rejected), file-size limits, and per-user isolated temp/permanent storage.
- SQL injection: not applicable — every query goes through the SQLAlchemy ORM, no raw SQL anywhere in the codebase.
- XSS: Jinja2 auto-escaping everywhere server-side; all dynamically-inserted values in JavaScript (including user-controlled data like uploaded-file column names) go through an explicit `escapeHtml()` helper.
- Secure cookies (`HttpOnly`, `SameSite=Lax`, `Secure` in production).
- `SECRET_KEY` validated at startup — the app refuses to start in production with the insecure development default.
- Report download filenames are sanitized (`secure_filename`) independent of the actual (always server-controlled) file path.
- Errors are logged server-side; users never see a stack trace (custom 404/403/413/500 pages).
- The AI layer never sends passwords/auth data to any provider, never executes AI-generated code, and only ever sends a bounded, pre-computed summary of a dataset — never the raw dataset itself.
- Admin panel: every route gated behind `is_admin`, tested for both anonymous and non-admin access; API keys are never rendered anywhere in the UI, even to admins (only a 4-character key suffix, for identification).

## Future improvements

- Replace the `ThreadPoolExecutor`-based ML job runner with Celery/RQ for true multi-process background processing and job persistence across restarts.
- Object storage (S3-compatible) backend for uploads/models/reports — the storage layer is already abstracted behind `LocalStorage`, so this is a swap-in, not a rewrite.
- Real-time SHAP explanations capped more intelligently for very large datasets (currently a fixed sample-size cap).

## License

MIT
