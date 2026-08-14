**A multi-user AI-powered analytics and machine-learning platform that transforms CSV and Excel datasets into actionable insights, visualizations, predictions, forecasts, anomaly reports, and exportable business reports — without requiring users to write code.**

**Status:** Complete — all 14 planned phases implemented

**Test Suite:** 332 automated tests passing

**Backend:** Flask + SQLAlchemy

**Analytics:** Pandas + NumPy + Scikit-learn + XGBoost

**AI:** Gemini by default, with Groq, OpenRouter, Claude, and OpenAI support

**Database:** SQLite / PostgreSQL

**Frontend:** Flask/Jinja2 + Bootstrap + JavaScript

---

## Table of Contents

* [Overview](#overview)
* [Key Highlights](#key-highlights)
* [Features](#features)
* [How It Works](#how-it-works)
* [Architecture](#architecture)
* [AI Architecture](#ai-architecture)
* [AI Data Analyst](#ai-data-analyst)
* [Analytics Pipeline](#analytics-pipeline)
* [Machine Learning Pipeline](#machine-learning-pipeline)
* [Forecasting](#forecasting)
* [Anomaly Detection](#anomaly-detection)
* [Reports and Exports](#reports-and-exports)
* [Multi-User Architecture](#multi-user-architecture)
* [Project Structure](#project-structure)
* [Installation](#installation)
* [Environment Configuration](#environment-configuration)
* [Database Setup](#database-setup)
* [Create an Admin Account](#create-an-admin-account)
* [Running Locally](#running-locally)
* [Testing](#testing)
* [Deployment](#deployment)
* [Security](#security)
* [Known Multi-Worker Limitations](#known-multi-worker-limitations)
* [Future Improvements](#future-improvements)
* [Technology Stack](#technology-stack)
* [License](#license)

---

# Overview

**AI Business Analytics Platform** is a multi-user SaaS-style web application designed to make advanced data analytics accessible without requiring users to write Python, SQL, or machine-learning code.

Users can upload **CSV, XLSX, or XLS datasets** and work through a complete analytics workflow:

```text
Upload Dataset
      ↓
Data Quality Analysis
      ↓
Cleaning & Processing
      ↓
Exploratory Data Analysis
      ↓
Interactive Visualizations
      ↓
AI-Powered Questions & Insights
      ↓
Anomaly Detection
      ↓
Machine Learning
      ↓
Forecasting
      ↓
Reports & Exports
```

The platform combines traditional data analytics, controlled AI reasoning, machine learning, forecasting, anomaly detection, and report generation into a single application.

A major design goal is that the AI should **not invent analytical numbers**. When a user asks a numerical question about their dataset, the platform converts the request into a controlled computation plan, validates that plan, executes the calculation using the real dataset, and then gives the computed result to the AI for explanation.

---

# Key Highlights

### Multi-user SaaS architecture

* User registration and authentication
* Email verification
* Login/logout
* Forgot/reset password
* Password changes
* Account deletion
* Complete per-user data isolation
* Admin dashboard and system monitoring

### AI-powered analytics

* Natural-language questions about datasets
* Automatic AI-generated insights
* Provider-independent AI architecture
* Gemini multi-key rotation
* Automatic provider fallback
* Response caching
* Per-user AI usage limits
* Controlled analytics execution

### Advanced analytics

* Automatic data profiling
* Data-quality analysis
* Data cleaning
* Exploratory data analysis
* Correlation analysis
* Automatic chart suggestions
* Interactive chart builder
* Anomaly detection
* Machine learning
* Model comparison
* SHAP explainability
* Forecasting

### Professional reporting

* PDF reports
* Excel reports
* CSV exports
* JSON exports
* Saved projects
* Saved charts
* AI insights
* ML results
* Forecasting results

---

# Features

## 1. Accounts & Workspace

The platform provides a complete multi-user authentication and workspace system.

### User authentication

* Registration
* Email verification
* Login/logout
* Forgot password
* Password reset
* Change password
* Account deletion
* Password hashing
* Session-based authentication

Every user's resources are isolated from other users.

### Admin panel

Administrators can:

* Manage users
* Disable users
* Delete users
* View global activity logs
* Monitor AI providers
* Configure AI provider fallback order
* Manage AI usage limits
* Edit usage limits without restarting the application

---

# 2. Dataset Management

Users can upload:

* `.csv`
* `.xlsx`
* `.xls`

### Upload workflow

The platform provides:

* Drag-and-drop upload
* File validation
* File-size limits
* File-type validation
* Magic-byte validation
* Live dataset preview
* Data-quality summary
* Per-user isolated storage

The original uploaded dataset is **never modified** during cleaning.

Instead, every cleaned dataset becomes a new dataset linked to its original source.

```text
Original Dataset
       │
       ├── Cleaned Dataset
       │
       ├── Charts
       │
       ├── Analytics
       │
       ├── ML Results
       │
       └── Reports
```

---

# 3. Automatic Data Cleaning

The platform can automatically handle common data-quality problems, including:

* Missing values
* Duplicate rows
* Outliers
* Incorrect data types
* Unnecessary columns
* Data conversion

Cleaning operations always create a **new dataset file**.

The original file remains untouched.

This is implemented using dataset relationships such as:

```text
source_dataset_id
```

which allows the platform to track the origin of processed datasets.

---

# 4. Exploratory Data Analysis

The platform automatically analyzes uploaded datasets and provides:

* Dataset overview
* Number of rows
* Number of columns
* Column types
* Missing-value analysis
* Duplicate analysis
* Descriptive statistics
* Correlation analysis
* Correlation heatmaps
* Automatically suggested charts

The system can identify appropriate visualizations based on the dataset's column types.

---

# 5. Interactive Chart Builder

Users can create reusable charts without writing code.

Supported chart types include:

* Bar charts
* Line charts
* Area charts
* Pie charts
* Scatter plots
* Histograms

Charts support:

* Filters
* Aggregation
* Dataset columns
* Saved configurations
* Reusable visualizations

Saved charts can also be included in generated reports.

---

# 6. AI Data Analyst

One of the core features of the platform is the **AI Data Analyst**.

Users can ask questions about their datasets using natural language.

For example:

```text
What is the average sales value?

Which product generated the highest revenue?

What is the correlation between sales and profit?

Show me the top 10 customers.

What is the sales trend over time?
```

The AI does **not** directly generate Python or Pandas code.

Instead, the workflow is:

```text
User Question
     ↓
AI creates computation plan
     ↓
Plan validation
     ↓
Whitelist validation
     ↓
Real Pandas computation
     ↓
Computed result
     ↓
AI explanation
     ↓
Final answer
```

This prevents the AI from simply guessing numerical results.

---

# AI Data Analyst Safety Model

The platform follows a controlled-execution model.

The AI can only request predefined operations such as:

* `aggregate`
* `top_n`
* `correlation`
* `trend`
* Other explicitly whitelisted analytics operations

The requested operation and column names are validated against the actual dataset before execution.

The AI **never executes arbitrary Python or Pandas code**.

Relevant implementation:

```text
app/services/analytics/query_executor.py
```

This design provides a much safer architecture than allowing an LLM to generate and execute unrestricted code.

---

# AI-Generated Insights

Users can request automatic insights about their dataset.

The same grounded approach is used:

```text
Dataset
   ↓
Real analytics
   ↓
Computed values
   ↓
AI explanation
```

The AI receives computed information rather than being asked to invent statistics.

---

# AI Architecture

The platform uses a provider-independent AI architecture.

Every AI request goes through:

```text
AIProviderManager
```

Routes and other services do not directly depend on a specific AI provider.

This makes adding or changing AI providers primarily a configuration task.

## Supported providers

* Gemini — default
* Groq
* OpenRouter
* Claude / Anthropic
* OpenAI

All providers implement the same conceptual interface:

```text
generate()
generate_json()
stream()
analyze()
```

Provider implementations are located under:

```text
app/services/ai/
```

---

# Gemini Multi-Key Rotation

The platform supports up to four Gemini API keys:

```text
GEMINI_API_KEY_1
GEMINI_API_KEY_2
GEMINI_API_KEY_3
GEMINI_API_KEY_4
```

Keys are selected using round-robin rotation.

If a key becomes:

* Rate limited
* Authentication-failed
* Temporarily unavailable

the key is placed into cooldown and another available key is tried.

The system only moves to the configured fallback provider after all available Gemini keys have been attempted.

---

# AI Provider Fallback

Provider order can be configured using:

```text
AI_PROVIDER_ORDER
```

Example:

```text
gemini,groq,openrouter,claude,openai
```

The fallback system only retries errors considered appropriate for fallback, such as:

* Rate limits
* Temporary provider failures
* Authentication failures

Permanent/user errors are not blindly retried against other providers.

This avoids unnecessary API usage.

---

# AI Response Caching

Identical AI requests can be cached based on:

```text
provider
model
prompt
context
```

Cached responses reduce unnecessary provider calls.

Cache hits do not consume the user's AI usage allowance.

Every AI attempt is recorded in:

```text
AIUsage
```

---

# AI Usage Limits

The platform supports:

* Daily user limits
* Monthly user limits
* Provider usage tracking
* AI request logging
* Admin-configurable limits

Usage limits are checked **before** calling an external provider.

---

# Analytics Pipeline

The analytics pipeline follows a structured workflow:

```text
Upload
  ↓
Validate
  ↓
Profile
  ↓
Clean
  ↓
EDA
  ↓
Charts
  ↓
Anomaly Detection
  ↓
AI Analysis
  ↓
ML / Forecasting
  ↓
Reports
```

This separation keeps analytics logic independent from Flask routes and presentation code.

---

# Anomaly Detection

The platform supports multiple anomaly-detection strategies.

### IQR

Interquartile Range-based detection.

### Z-Score

Statistical anomaly detection based on standard deviation.

### Isolation Forest

Multivariate anomaly detection using machine learning.

Results include:

* Per-row anomaly scoring
* Anomaly identification
* Visualization
* Dataset-level analysis

---

# Machine Learning Pipeline

The platform automatically detects whether a selected target represents:

* Classification
* Regression

The ML pipeline then builds a leakage-safe preprocessing and training workflow.

```text
Select Target
      ↓
Auto-detect Task
      ↓
Build Pipeline
      ↓
ColumnTransformer
      ↓
Train/Test Split
      ↓
Cross Validation
      ↓
Train Models
      ↓
Evaluate Models
      ↓
Explainability
      ↓
Rank Models
      ↓
Prediction Form
      ↓
Report
```

---

# Supported ML Algorithms

## Classification

The platform evaluates:

1. Logistic Regression
2. Decision Tree
3. Random Forest
4. Gradient Boosting
5. XGBoost

## Regression

The platform evaluates:

1. Linear Regression
2. Random Forest
3. Gradient Boosting
4. XGBoost

The system compares trained models and identifies the best-performing model.

---

# Leakage-Safe ML

Preprocessing is performed inside the machine-learning pipeline.

This includes:

* Missing-value imputation
* Scaling
* One-hot encoding

The preprocessing steps are refitted during cross-validation instead of being fitted once on the entire dataset.

This prevents information from the test set leaking into training.

---

# Model Evaluation

Classification models can be evaluated using:

* Accuracy
* F1 score
* ROC-AUC

Regression models can be evaluated using:

* MAE
* RMSE
* R²

Models are ranked based on their evaluation results.

---

# SHAP Explainability

The platform provides feature-importance explanations using SHAP where supported.

A built-in fallback is available when SHAP cannot be used for a particular model.

This helps users understand which features influence predictions.

---

# Prediction Form

After training, the platform provides a working prediction interface.

Users can enter feature values and receive a prediction from the selected trained model.

ML results can also be included in generated reports.

---

# Background ML Training

ML training runs using a thread pool so that the web request does not remain blocked during model training.

The frontend can poll the job status.

Current implementation:

```text
ThreadPoolExecutor
```

This is documented as an MVP architecture.

For multi-worker production environments, the project can later migrate to:

```text
Celery / RQ
```

without changing the underlying ML training logic.

---

# Forecasting

The platform supports forecasting only when the dataset contains an appropriate:

* Date/time column
* Numeric column

The forecasting system automatically analyzes:

* Trends
* Seasonality

Supported forecasting approaches include:

* Holt-Winters
* Holt-linear
* Linear regression

Approximate confidence bands are provided where supported.

Forecasting results can be included in generated reports.

---

# Reports & Exports

The report generator combines major project results into one report.

Reports can contain:

* Dataset overview
* Data-quality information
* EDA results
* Saved charts
* AI-generated insights
* Machine-learning results
* Forecasting results

Supported export formats:

| Format | Supported |
| ------ | --------- |
| PDF    | Yes       |
| Excel  | Yes       |
| CSV    | Yes       |
| JSON   | Yes       |

---

# Saved Projects

Projects allow users to organize related resources.

A project can contain:

* Datasets
* Cleaned datasets
* Charts
* AI insights
* ML results
* Forecasting results
* Reports

Users also have a personal history page.

Administrators have access to global system activity logs.

---

# Multi-User Architecture

The application is designed around strict user ownership.

Every user-owned resource is accessed through ownership controls such as:

```text
get_owned_or_404()
owner_scoped_query()
```

These act as centralized ownership guards.

The goal is:

```text
User A
 ├── Dataset A
 ├── Charts A
 ├── Reports A
 └── ML Results A

User B
 ├── Dataset B
 ├── Charts B
 ├── Reports B
 └── ML Results B
```

User A cannot access, modify, or delete User B's resources.

Cross-user isolation is explicitly tested across the application.

---

# Architecture

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
        Analytics["analytics/<br/>profiling, cleaning, EDA,<br/>charts, anomalies, queries"]
        MLSvc["ml/<br/>pipelines, training,<br/>evaluation, SHAP"]
        ForecastSvc["forecasting/<br/>trend, seasonality,<br/>Holt-Winters"]
        ReportSvc["reports/<br/>PDF / Excel / CSV / JSON"]
        AISvc["ai/<br/>AIProviderManager"]
    end

    subgraph AIProviders["AI Providers"]
        Gemini[Gemini<br/>multi-key rotation]
        Groq[Groq]
        OpenRouter[OpenRouter]
        Claude[Claude]
        OpenAI[OpenAI]
    end

    DB[(PostgreSQL / SQLite)]
    FS[(Local File Storage<br/>uploads / models / reports)]
    Mail[SMTP]

    Browser <--> Routes
    Routes --> Forms
    Routes --> Services

    Analytics --> DB
    MLSvc --> DB
    MLSvc --> FS
    ReportSvc --> FS

    AISvc --> Gemini
    AISvc -. fallback .-> Groq
    AISvc -. fallback .-> OpenRouter
    AISvc -. fallback .-> Claude
    AISvc -. fallback .-> OpenAI

    Routes --> DB
    Routes --> Mail
```

---

# Key Design Decisions

## 1. Centralized AI Provider Manager

Every AI request goes through:

```text
AIProviderManager
```

No application route directly imports a provider.

This makes the AI layer provider-agnostic.

---

## 2. Centralized Ownership Protection

User-owned resources are accessed through:

```text
get_owned_or_404()
owner_scoped_query()
```

This provides a single ownership-control layer for the application.

---

## 3. Immutable Source Datasets

Cleaning never modifies the original uploaded dataset.

Instead:

```text
Source Dataset
      ↓
New Cleaned Dataset
```

The relationship is maintained using:

```text
source_dataset_id
```

---

## 4. Grounded AI Analytics

The AI does not generate executable Python/Pandas code.

Instead:

```text
Question
   ↓
Plan
   ↓
Validate
   ↓
Execute real analytics
   ↓
Return computed result
   ↓
AI explanation
```

This is the core mechanism behind the platform's **"never invent a number"** design.

---

## 5. Background ML Processing

ML training is separated from the request-response cycle using a thread pool.

The frontend receives a job and polls its status.

This keeps the web interface responsive during training.

---

# AI Architecture Flow

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

    M->>C: Cache lookup

    alt Cache hit
        C-->>M: Cached response
    else Cache miss
        M->>G: Try Gemini key

        alt Rate limited
            G->>G: Cool down key
            G->>G: Try next key
        end

        alt All Gemini keys exhausted
            G->>F: Fallback provider
        end

        G-->>M: Response
        M->>C: Store response
    end

    M-->>R: Plan JSON

    R->>R: Validate plan
    R->>R: Execute real Pandas computation

    R->>M: Analyze computed result
    M-->>R: Grounded explanation

    R-->>U: Final answer
```

---

# Machine Learning Architecture

```mermaid
flowchart LR

    A[Select Target] -->
    B[Detect Classification / Regression] -->

    C[Build Leakage-Safe Pipeline] -->

    D[Train/Test Split + Cross Validation] -->

    E[Train 9 Algorithms] -->

    F[Evaluate Models] -->

    G[SHAP Explainability] -->

    H[Rank Models] -->

    I[Best Model] -->

    J[Prediction Form]
```

---

# Project Structure

```text
ai-business-analytics/
│
├── app.py                         # WSGI entry point
├── config.py                      # Environment configuration
├── requirements.txt
├── .env.example
├── .gitignore
│
├── app/
│   ├── __init__.py                # Flask application factory
│   ├── extensions.py              # Shared Flask extensions
│   ├── cli.py                     # Flask CLI commands
│   │
│   ├── models/                    # SQLAlchemy models
│   │
│   ├── routes/                    # Flask blueprints
│   │
│   ├── forms/                     # WTForms
│   │
│   ├── services/
│   │   ├── ai/
│   │   │   ├── base_provider.py
│   │   │   ├── provider_manager.py
│   │   │   └── provider implementations
│   │   │
│   │   ├── analytics/
│   │   │   ├── profiling
│   │   │   ├── cleaning
│   │   │   ├── EDA
│   │   │   ├── charts
│   │   │   ├── anomalies
│   │   │   └── query_executor.py
│   │   │
│   │   ├── ml/
│   │   │   ├── pipelines
│   │   │   ├── training
│   │   │   ├── evaluation
│   │   │   ├── explainability
│   │   │   └── job runner
│   │   │
│   │   ├── forecasting/
│   │   │   ├── trend detection
│   │   │   ├── seasonality detection
│   │   │   └── forecasting models
│   │   │
│   │   └── reports/
│   │       ├── PDF
│   │       ├── Excel
│   │       ├── CSV
│   │       └── JSON
│   │
│   ├── templates/                 # Jinja2 templates
│   ├── static/                    # CSS / JavaScript
│   │
│   └── utils/
│       ├── tokens
│       ├── email
│       ├── ownership guards
│       └── activity logging
│
├── migrations/                    # Alembic migrations
│
├── tests/                         # Automated tests
│   └── 29 test files
│
├── data/
│   ├── uploads/
│   ├── processed/
│   ├── models/
│   └── reports/
│
└── logs/
```

---

# Installation

## Requirements

The project requires a modern Python environment compatible with the dependencies listed in `requirements.txt`.

### 1. Clone the repository

```bash
git clone <this-repo>
cd ai-business-analytics
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### macOS / Linux

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# Environment Configuration

Create your environment file:

```bash
cp .env.example .env
```

On Windows:

```powershell
copy .env.example .env
```

At minimum, configure:

```env
SECRET_KEY=your-production-secret-key
DATABASE_URL=
```

For AI functionality, configure at least one provider.

For example:

```env
GEMINI_API_KEY_1=your-gemini-key
```

Optional additional Gemini keys:

```env
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=
```

Configure the provider order using:

```env
AI_PROVIDER_ORDER=gemini,groq,openrouter,claude,openai
```

Mail configuration can be left blank during development.

When mail credentials are not configured, verification and password-reset emails are logged rather than sent.

Admin bootstrap configuration:

```env
ADMIN_EMAIL=
ADMIN_PASSWORD=
```

---

# Database Setup

## SQLite

SQLite is the default and requires no separate database server.

Run:

```bash
export FLASK_APP=app.py
flask db upgrade
```

On Windows PowerShell:

```powershell
$env:FLASK_APP="app.py"
flask db upgrade
```

The application automatically resolves the SQLite database path under the project's `data/` directory.

---

# PostgreSQL

For production or larger deployments, PostgreSQL can be used.

### 1. Create the database

```bash
createdb ai_analytics
```

### 2. Configure the database URL

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/ai_analytics
```

### 3. Run migrations

```bash
flask db upgrade
```

The same application code can be used with SQLite or PostgreSQL.

The PostgreSQL 16 setup has been verified against the application's database schema and end-to-end register → upload → dataset persistence flow.

---

# Create an Admin Account

Run:

```bash
flask create-admin
```

The command reads:

```text
ADMIN_EMAIL
ADMIN_PASSWORD
```

from the environment.

It is safe to run again.

If the email already belongs to an existing user, the account is promoted to administrator.

---

# Running Locally

Run:

```bash
flask run
```

or:

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

---

# Development Email Behavior

When:

```text
MAIL_USERNAME
```

is not configured, email sending is suppressed during development.

Verification and password-reset links are written to the application logs.

Check:

```text
logs/app.log
```

or the terminal.

Example:

```text
[EMAIL SUPPRESSED] to=[...] subject=Verify your email address

http://localhost/auth/verify-email/<token>
```

---

# Testing

Run the complete test suite:

```bash
python -m pytest tests/ -v
```

Current project status:

```text
332 tests
29 test files
All tests passing
```

---

# Test Coverage

The automated tests cover:

### Authentication

* Registration
* Email verification
* Login
* Password reset
* Password change
* Account deletion
* Cross-user data isolation

### Upload security

* Extension whitelist
* Magic-byte validation
* Empty-file rejection
* Binary-file rejection
* File-size limits

### Data processing

* Cleaning operations
* Individual cleaning actions
* Source-data immutability

### Analytics

* EDA
* Chart builder
* Known aggregation results
* Anomaly detection
* Injected known outliers

### AI

* Provider manager
* Gemini key rotation
* Provider fallback
* Cache hits/misses
* Usage-limit enforcement
* Database-backed `AIUsage` records
* AI "never invent a number" behavior

### Machine learning

* End-to-end background training
* Job kickoff
* Job polling
* Training completion
* Model ranking
* Prediction

### Forecasting

* Known trends
* Known seasonality
* Synthetic forecasting datasets

### Reports

* PDF validity
* PDF page count
* Excel sheet names
* JSON round-trip
* CSV generation

### Admin security

* Anonymous admin-route access
* Non-admin access
* Admin access
* API-key exposure checks

---

# Deployment

The project exposes:

```text
app.py
```

as the WSGI entry point.

It can be run with Gunicorn:

```bash
export FLASK_ENV=production

gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

A reverse proxy such as:

* Nginx
* Caddy

can be placed in front of the application for:

* HTTPS/TLS
* Static file serving
* Reverse proxying

---

# Production Checklist

Before deploying:

* [ ] Set `FLASK_ENV=production`
* [ ] Replace the development `SECRET_KEY`
* [ ] Use PostgreSQL
* [ ] Configure production SMTP credentials
* [ ] Configure AI provider keys
* [ ] Configure appropriate AI usage limits
* [ ] Configure a production WSGI server
* [ ] Use HTTPS
* [ ] Configure a reverse proxy
* [ ] Consider Redis for multi-worker coordination
* [ ] Configure production file/object storage
* [ ] Review application logs and monitoring

---

# Security

Security is a major part of the platform architecture.

## Password Security

* Passwords are hashed using Werkzeug.
* Passwords are never stored in plaintext.
* Passwords are never logged.

---

## Email Verification

Email verification is required before login.

Forgot-password and reset-password workflows are designed so that they do not reveal whether an email address exists in the system.

---

## CSRF Protection

CSRF protection is implemented using Flask-WTF.

This also covers AJAX requests through:

```text
X-CSRFToken
```

---

## Rate Limiting

Rate limiting is applied to resource-intensive and security-sensitive operations, including:

* Authentication endpoints
* Dataset uploads
* AI chat
* AI insights
* ML training kickoff

---

## Upload Security

Uploaded files are validated using:

* Extension whitelist
* Magic-byte sniffing
* File-size limits
* Empty-file detection
* Binary-file rejection
* Per-user temporary storage
* Per-user permanent storage

For example, simply renaming an executable file to:

```text
dataset.csv
```

does not make it a valid CSV upload.

---

## SQL Injection Protection

Database access uses SQLAlchemy ORM.

The codebase does not use raw SQL for application queries.

---

## XSS Protection

Server-rendered templates use Jinja2 auto-escaping.

User-controlled values inserted into JavaScript are passed through an explicit:

```text
escapeHtml()
```

helper.

This includes uploaded dataset column names and other dynamically generated values.

---

## Secure Cookies

Production cookies use:

```text
HttpOnly
SameSite=Lax
Secure
```

where appropriate.

---

## Secret Key Validation

The application validates the Flask secret key during startup.

Production mode refuses to start using the insecure development default.

---

## Secure Report Downloads

Report filenames are sanitized using:

```text
secure_filename
```

The sanitized filename is independent of the actual server-controlled file path.

---

## Error Handling

Internal exceptions are logged server-side.

Users are not shown raw stack traces.

Custom error pages are provided for:

```text
404
403
413
500
```

---

# AI Security

The AI layer follows additional security controls.

### The AI does not receive:

* Passwords
* Authentication credentials
* Session secrets
* API keys
* Unnecessary account information

### The AI does not execute generated code.

The AI only requests predefined analytics operations.

The application validates the requested operation before executing it.

### Dataset exposure is bounded.

The AI receives a bounded, pre-computed representation of relevant dataset information rather than the raw dataset itself.

---

# Admin Security

Every administrator route is protected by:

```text
is_admin
```

Admin access is tested for:

* Anonymous users
* Normal users
* Administrators

API keys are never displayed in full inside the admin UI.

Only a short key suffix may be displayed for identification.

---

# Known Multi-Worker Limitations

Some state currently lives in application processes.

This includes:

* Gemini key-rotation state
* AI response cache
* ML background thread pool

When running multiple Gunicorn workers, each worker has its own state.

This is currently considered correct but not perfectly coordinated behavior.

For example, a cooling-down Gemini key may be attempted again by another worker.

The planned solution is to move shared state to Redis.

---

# Future Improvements

The platform is designed to be extended further.

## 1. Redis-Based Coordination

Move the following to Redis:

* Gemini key rotation state
* AI response cache
* Rate-limit storage

This will improve coordination between multiple application workers.

---

## 2. Production Job Queue

Replace:

```text
ThreadPoolExecutor
```

with:

```text
Celery
```

or:

```text
RQ
```

This would provide:

* Persistent jobs
* Multi-process workers
* Better failure recovery
* Job retry support
* Scalable ML processing

---

## 3. Automated Temporary-File Cleanup

A configuration value already exists for temporary dataset lifetime:

```text
DATASET_TEMP_MAX_AGE_HOURS
```

A scheduled cleanup process can be added to automatically remove abandoned temporary uploads.

---

## 4. Object Storage

Add an S3-compatible storage backend for:

* Uploaded datasets
* Processed datasets
* ML models
* Reports

The storage layer is already abstracted behind:

```text
LocalStorage
```

making object storage a storage-layer replacement rather than a complete application rewrite.

---

## 5. Streaming AI Responses

The provider layer already supports:

```text
stream()
```

The current chat interface uses the blocking:

```text
generate()
```

path.

Future versions can expose real-time token streaming in the UI.

---

## 6. Improved SHAP Scalability

Future versions can improve SHAP sampling for very large datasets.

The current implementation uses a fixed sample-size cap.

A more adaptive strategy could select sample size based on:

* Dataset size
* Available memory
* Model complexity
* Processing time

---

## 7. Additional AI Providers

Because all providers implement a shared interface, additional providers can be integrated without rewriting the analytics system.

---

## 8. More Advanced Forecasting

Future versions could expand forecasting with additional models and capabilities such as:

* More statistical forecasting methods
* Advanced seasonality detection
* Automated model selection
* Improved confidence intervals
* Longer-horizon forecasting

---

## 9. Advanced Analytics

Possible future analytics capabilities include:

* More anomaly-detection algorithms
* Automated feature engineering
* Clustering
* Customer segmentation
* Time-series decomposition
* Automated business KPI detection
* Advanced cohort analysis

---

# Technology Stack

| Layer                | Technologies                                 |
| -------------------- | -------------------------------------------- |
| Backend              | Flask                                        |
| ORM                  | SQLAlchemy                                   |
| Forms                | WTForms / Flask-WTF                          |
| Database             | SQLite / PostgreSQL                          |
| Data Processing      | Pandas / NumPy                               |
| Machine Learning     | Scikit-learn                                 |
| Gradient Boosting    | XGBoost                                      |
| Explainability       | SHAP                                         |
| AI                   | Gemini / Groq / OpenRouter / Claude / OpenAI |
| Frontend             | Jinja2 / Bootstrap / JavaScript              |
| Charts               | JavaScript charting layer                    |
| Reports              | PDF / Excel / CSV / JSON                     |
| Authentication       | Flask authentication/session architecture    |
| Email                | SMTP                                         |
| Testing              | Pytest                                       |
| Production Server    | Gunicorn                                     |
| Reverse Proxy        | Nginx / Caddy                                |
| Cache / Coordination | Redis-ready architecture                     |

---

# Core Design Philosophy

The project is built around several principles:

### 🔒 Security First

User data, authentication information, uploads, AI credentials, and administrative functionality are isolated and protected.

### 🤖 Controlled AI

AI is used for reasoning and explanation, but actual numerical analytics are executed by deterministic application code.

### 📊 Real Data, Real Results

The platform computes analytical results from the actual dataset rather than allowing the AI to fabricate statistics.

### 🧩 Modular Architecture

Analytics, machine learning, forecasting, reports, and AI providers are separated into service modules.

### 👥 Multi-User Isolation

Every user's datasets and generated resources are protected by ownership-level access controls.

### 🚀 Production-Oriented Design

Although the application can run locally with SQLite, its architecture supports PostgreSQL, Gunicorn, Redis, object storage, and background job queues for future scaling.

---

# Project Status

```text
14 / 14 planned phases completed
332 automated tests passing
29 test files
SQLite supported
PostgreSQL supported
Multi-user authentication implemented
AI provider fallback implemented
Gemini multi-key rotation implemented
AI response caching implemented
AI usage limits implemented
Machine learning pipeline implemented
Forecasting implemented
Anomaly detection implemented
Report generation implemented
Admin panel implemented
Security controls implemented
```

---

# License

This project is licensed under the **MIT License**.

See the [`LICENSE`](LICENSE) file for the complete license text.

---

## Disclaimer

AI-generated insights are intended to assist with data analysis and should not automatically be treated as professional financial, legal, medical, or business advice.

Users remain responsible for validating important decisions against the underlying data and appropriate domain expertise.

---

## Author

**Abaid-ur-Rehman**

Built as a full-stack AI/data analytics project combining:

* Flask
* Data Analytics
* Machine Learning
* Generative AI
* Forecasting
* Anomaly Detection
* Multi-user SaaS Architecture
* Secure API Integration
* Automated Testing
* Production-oriented Backend Engineering
