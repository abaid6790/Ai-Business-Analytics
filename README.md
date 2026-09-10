# 🤖 AI Business Analytics Platform

> **Turn raw data into insights, predictions, forecasts, and decisions — without writing code.**

A full-stack, multi-user SaaS analytics platform that allows users to upload **CSV and Excel datasets**, automatically clean and analyze their data, ask questions using natural language, detect anomalies, train machine-learning models, generate forecasts, and export professional reports.

Built with **Flask, Pandas, scikit-learn, XGBoost, SHAP, PostgreSQL/SQLite, and a provider-agnostic AI architecture** with Google Gemini as the default provider.

---

## ✨ Overview

The **AI Business Analytics Platform** brings the complete data-analysis workflow into one web application.

Instead of manually moving between spreadsheets, Python notebooks, visualization tools, and AI assistants, users can:

**Upload → Clean → Explore → Ask → Analyze → Predict → Forecast → Report**

### Why this project?

Traditional business analytics often requires:

* Python or SQL knowledge
* Manual data cleaning
* Separate visualization tools
* Data-science expertise
* Machine-learning knowledge
* Manual report preparation

This platform automates those workflows through an easy-to-use web interface.

---

## 🚀 Key Highlights

| Capability                   | Included |
| ---------------------------- | -------- |
| 📂 CSV / Excel Upload        | ✅        |
| 🧹 Automatic Data Cleaning   | ✅        |
| 📊 Exploratory Data Analysis | ✅        |
| 📈 Interactive Charts        | ✅        |
| 🤖 AI Data Q&A               | ✅        |
| 💡 Automatic AI Insights     | ✅        |
| 🚨 Anomaly Detection         | ✅        |
| 🧠 Machine Learning          | ✅        |
| 🔮 Forecasting               | ✅        |
| 📑 Report Generation         | ✅        |
| 👤 Multi-user Data Isolation | ✅        |
| 🔐 Authentication & Security | ✅        |
| ⚙️ Admin Panel               | ✅        |
| 🔄 AI Provider Fallback      | ✅        |
| 🔑 Gemini Multi-Key Rotation | ✅        |
| 💾 SQLite / PostgreSQL       | ✅        |
| 🐳 Docker Deployment         | ✅        |
| 🧪 Automated Testing         | ✅        |

**Project status:** `14/14 planned phases complete`
**Automated tests:** `332 passing`

---

# 🖥️ Screenshots

> Screenshots are stored inside the project's `screenshots/` directory.

### Dashboard

![AI Business Analytics Dashboard](screenshots/Dashboard.png)

### Dataset Analysis

![Dataset Analysis](screenshots/Analytics.png)

### Exploratory Data Analysis

![Exploratory Data Analysis](screenshots/eda.png)

### AI Data Q&A

![AI Data Q\&A](screenshots/AI_Analysts.png)

### Machine Learning

![Machine Learning](screenshots/ml-models.png)

### Forecasting

![Forecasting](screenshots/Forecasting.png)

### Reports

![Reports](screenshots/Reports.png)

> **Screenshot path convention:** all images use relative paths such as `screenshots/Dashboard.png`, so they work correctly on GitHub and when the repository is cloned locally.
> Replace the filenames above with the **exact filenames already present in your `screenshots/` folder** if they differ.

---

# 🧩 Core Features

## 👤 Authentication & Workspace

Complete account management system with isolated user workspaces.

* User registration
* Email verification
* Login / logout
* Forgot password
* Password reset
* Change password
* Account deletion
* Session management
* User-specific datasets
* User-specific projects
* User-specific charts
* User-specific reports
* Cross-user data isolation

Every user-owned resource is protected through centralized ownership checks.

---

## 🗂️ Data Management

Upload business datasets directly from the browser.

### Supported formats

* CSV
* XLSX
* XLS

### Upload workflow

```text
Upload Dataset
      ↓
File Validation
      ↓
Preview
      ↓
Data Quality Analysis
      ↓
Commit Dataset
      ↓
Analytics
```

The upload system includes:

* Drag-and-drop upload
* File preview
* Column detection
* Data-type detection
* Missing-value analysis
* Duplicate detection
* Outlier detection
* File-size validation
* Extension validation
* Magic-byte validation
* User-isolated storage

---

# 🧹 Automatic Data Cleaning

The platform can automatically clean datasets without modifying the original uploaded file.

### Cleaning operations

* Missing-value handling
* Duplicate removal
* Outlier handling
* Data-type conversion
* Column removal
* Data normalization where applicable

### Immutable source data

Cleaning always creates a **new processed dataset**.

```text
Original Dataset
      │
      ├── remains unchanged
      │
      └── Clean Dataset
              │
              ├── EDA
              ├── Charts
              ├── AI Analysis
              ├── ML
              └── Forecasting
```

This preserves the original dataset for auditing and comparison.

---

# 📊 Exploratory Data Analysis

Automatically generate useful statistical information from uploaded datasets.

### Includes

* Dataset overview
* Row and column counts
* Data types
* Missing values
* Duplicate counts
* Descriptive statistics
* Numerical summaries
* Categorical summaries
* Correlation analysis
* Correlation heatmap
* Automatic chart suggestions

The system identifies suitable visualizations based on column types.

---

# 📈 Interactive Chart Builder

Users can create and save reusable charts directly from the application.

### Supported visualizations

* Bar charts
* Line charts
* Area charts
* Pie charts
* Scatter plots
* Histograms

### Chart capabilities

* Column selection
* Aggregation
* Filtering
* Grouping
* Saved charts
* Reusable visualizations

---

# 🤖 AI Data Analyst

One of the core features of the platform is the **AI Data Analyst**.

Users can ask questions about their dataset using natural language.

### Example questions

```text
Which product has the highest revenue?

What is the average sales value?

Show me the top 10 customers.

Which month had the highest sales?

What is the correlation between price and quantity?

Are there unusual transactions?

What trend can you see in the data?
```

The system does **not** simply ask an LLM to guess an answer.

Instead:

```text
User Question
      ↓
AI creates computation plan
      ↓
Plan validation
      ↓
Whitelist verification
      ↓
Real Pandas computation
      ↓
Computed result
      ↓
AI explanation
      ↓
Final answer
```

### 🔒 Anti-hallucination design

The AI does not generate arbitrary Python or Pandas code.

It can only request predefined analytical operations such as:

* `aggregate`
* `top_n`
* `correlation`
* `trend`
* `summary`
* and other whitelisted operations

The requested operation and columns are validated against the actual dataset before execution.

The final explanation receives the **real computed result**, not an AI-generated number.

---

# 💡 Automatic AI Insights

Users can generate insights automatically with one click.

Insights are grounded using the same controlled computation pipeline used by AI Q&A.

This allows the system to identify meaningful patterns while keeping numerical claims tied to actual dataset calculations.

---

# 🔌 Provider-Agnostic AI Architecture

The application is designed so that AI providers can be changed without rewriting the application.

### Supported providers

* Google Gemini
* Groq
* OpenRouter
* Anthropic Claude
* OpenAI

Every provider follows the same interface:

```text
generate()
generate_json()
stream()
analyze()
```

All AI calls are routed through:

```text
AIProviderManager
```

Routes and business services never directly depend on a specific AI provider.

---

# 🔑 Gemini Multi-Key Rotation

The platform supports up to four Gemini API keys:

```env
GEMINI_API_KEY_1=
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=
```

Keys are selected using deterministic round-robin rotation.

```text
Request
   ↓
Gemini Key 1
   ↓
Rate Limited?
   ├── No → Response
   │
   └── Yes
        ↓
     Key 2
        ↓
     Key 3
        ↓
     Key 4
```

A rate-limited or authentication-failing key enters cooldown and is temporarily skipped.

---

# 🔄 AI Provider Fallback

The provider order can be configured through:

```env
AI_PROVIDER_ORDER=gemini,groq,openrouter,claude,openai
```

Example:

```text
Gemini
   ↓
Groq
   ↓
OpenRouter
   ↓
Claude
   ↓
OpenAI
```

Fallback occurs for appropriate transient, rate-limit, or authentication failures.

Invalid user requests are not blindly retried against every provider.

---

# ⚡ AI Response Caching

Repeated AI requests can be served from cache.

Cache identity is based on relevant request information such as:

```text
Provider
Model
Prompt
Context
```

### Cache behavior

```text
AI Request
    ↓
Cache lookup
    ├── Hit → Return cached result
    │
    └── Miss
          ↓
       Provider
          ↓
       Response
          ↓
       Cache
```

The cache can use:

* In-process storage for simple deployments
* Redis for multi-worker deployments

Configure Redis with:

```env
REDIS_URL=redis://localhost:6379/0
```

---

# 🚨 Anomaly Detection

The platform provides multiple anomaly-detection techniques.

### Available methods

#### IQR

Useful for identifying statistical outliers in numerical data.

#### Z-Score

Identifies observations that significantly deviate from the mean.

#### Isolation Forest

Supports multivariate anomaly detection.

Results include:

* Anomaly status
* Per-row scoring
* Visualization
* Identified unusual records

---

# 🧠 Machine Learning

The ML module automatically detects whether a problem is primarily:

* Classification
* Regression

The platform trains and compares multiple algorithms.

### Classification

* Logistic Regression
* Decision Tree
* Random Forest
* Gradient Boosting
* XGBoost

### Regression

* Linear Regression
* Random Forest
* Gradient Boosting
* XGBoost

---

# 🧪 Leakage-Safe ML Pipeline

Preprocessing is implemented inside the machine-learning pipeline.

```text
Dataset
   ↓
Target Selection
   ↓
Classification / Regression Detection
   ↓
ColumnTransformer
   ├── Missing-value imputation
   ├── Numerical scaling
   └── Categorical encoding
   ↓
Estimator
   ↓
Cross Validation
   ↓
Evaluation
   ↓
Model Ranking
```

This prevents preprocessing from leaking information from the test set into training.

---

# 📏 Model Evaluation

### Classification metrics

* Accuracy
* F1 Score
* ROC-AUC

### Regression metrics

* MAE
* RMSE
* R²

Models are ranked automatically so users can identify the strongest candidate.

---

# 🔍 Explainable AI

The platform integrates **SHAP-based feature importance**.

Users can understand which features contribute most to model predictions.

A built-in fallback is available when SHAP cannot be used for a particular model or dataset.

---

# 🎯 Prediction Form

After training a model, users can enter new feature values through a web-based prediction interface.

```text
Select Trained Model
        ↓
Enter Feature Values
        ↓
Validate Input
        ↓
Run Prediction
        ↓
Display Result
```

---

# 🔮 Forecasting

Forecasting is available for datasets containing:

* A valid date/time column
* A numerical target column

The system analyzes:

* Trend
* Seasonality
* Historical behavior

### Forecasting methods

* Holt-Winters
* Holt Linear
* Linear Regression

Approximate confidence bands are displayed where appropriate.

---

# 📁 Projects & Organization

Users can organize analytical work into saved projects.

Projects can contain related:

* Datasets
* Charts
* AI insights
* ML results
* Forecasting results
* Reports

This makes the platform suitable for repeated business-analysis workflows.

---

# 📑 Report Generation

The report generator combines analytical results into a single exportable report.

Reports can include:

* Dataset overview
* Data quality
* EDA
* Charts
* AI insights
* ML results
* Forecasting results

### Export formats

| Format | Supported |
| ------ | --------- |
| PDF    | ✅         |
| Excel  | ✅         |
| CSV    | ✅         |
| JSON   | ✅         |

---

# 🛡️ Security

Security is treated as a first-class part of the application.

### Authentication

* Werkzeug password hashing
* Email verification
* Secure password reset
* Session protection

### CSRF protection

Flask-WTF CSRF protection is applied to forms and AJAX requests.

### Rate limiting

Rate limits protect resource-intensive endpoints including:

* Authentication
* Dataset uploads
* AI Q&A
* AI insights
* ML training

### File security

Uploads are validated using:

* Extension whitelist
* Magic-byte inspection
* File-size limits
* Isolated temporary storage
* Per-user permanent storage

A renamed executable pretending to be a CSV is rejected.

### XSS protection

* Jinja2 auto-escaping
* Explicit JavaScript `escapeHtml()` handling for dynamically inserted values

### Secure cookies

Production cookies support:

```text
HttpOnly
SameSite=Lax
Secure
```

### AI security

The AI layer:

* Does not receive passwords
* Does not receive authentication secrets
* Does not execute generated Python
* Does not execute generated Pandas code
* Receives bounded/pre-computed dataset information rather than unrestricted raw data

---

# 👑 Admin Panel

Administrators have access to a dedicated management area.

### Admin capabilities

* User management
* Disable users
* Delete users
* Global activity logs
* AI provider monitoring
* Usage-limit management
* Provider fallback configuration

API keys are never displayed directly in the admin interface.

Only a short identifying suffix is exposed where required.

---

# 🏗️ Architecture

```mermaid
flowchart TB

    Browser["Browser / Bootstrap UI"]

    subgraph Flask["Flask Application"]
        Routes["Blueprints / Routes"]
        Forms["WTForms"]
        Services["Service Layer"]
    end

    subgraph Core["Application Services"]
        Analytics["Analytics<br/>Cleaning / EDA / Charts / Anomalies"]
        ML["Machine Learning<br/>Training / Evaluation / SHAP"]
        Forecast["Forecasting<br/>Trend / Seasonality"]
        Reports["Reports<br/>PDF / Excel / CSV / JSON"]
        AI["AIProviderManager"]
    end

    subgraph Providers["AI Providers"]
        Gemini["Google Gemini"]
        Groq["Groq"]
        OpenRouter["OpenRouter"]
        Claude["Anthropic Claude"]
        OpenAI["OpenAI"]
    end

    Database[("PostgreSQL / SQLite")]
    Storage[("Local File Storage")]
    Redis[("Redis")]
    SMTP["SMTP"]

    Browser --> Routes
    Routes --> Forms
    Routes --> Services

    Services --> Analytics
    Services --> ML
    Services --> Forecast
    Services --> Reports
    Services --> AI

    Analytics --> Database
    ML --> Database
    ML --> Storage
    Reports --> Storage

    AI --> Gemini
    AI -. fallback .-> Groq
    AI -. fallback .-> OpenRouter
    AI -. fallback .-> Claude
    AI -. fallback .-> OpenAI

    Routes --> Database
    Routes --> SMTP

    AI -. optional .-> Redis
```

---

# 🧠 AI Request Architecture

```mermaid
sequenceDiagram

    participant User
    participant Flask
    participant Manager as AIProviderManager
    participant Cache
    participant Gemini
    participant Fallback
    participant Pandas

    User->>Flask: Ask data question

    Flask->>Manager: Generate computation plan

    Manager->>Cache: Check cache

    alt Cache hit
        Cache-->>Manager: Cached result
    else Cache miss
        Manager->>Gemini: Request plan

        alt Gemini key fails
            Manager->>Gemini: Try next available key
        end

        alt All Gemini keys fail
            Manager->>Fallback: Try configured provider
        end

        Manager->>Cache: Store response
    end

    Manager-->>Flask: Validated plan

    Flask->>Flask: Validate whitelist

    Flask->>Pandas: Execute real computation

    Pandas-->>Flask: Computed result

    Flask->>Manager: Explain computed result

    Manager-->>Flask: Grounded explanation

    Flask-->>User: Final answer
```

---

# 🤖 ML Pipeline

```mermaid
flowchart LR

    A["Select Target"] --> B["Detect Task Type"]

    B --> C["Build Leakage-Safe Pipeline"]

    C --> D["Train/Test Split"]

    D --> E["Cross Validation"]

    E --> F["Train Multiple Models"]

    F --> G["Evaluate Models"]

    G --> H["SHAP Explainability"]

    H --> I["Rank Models"]

    I --> J["Prediction Form"]

    J --> K["Report"]
```

---

# 📂 Project Structure

```text
ai-business-analytics/
│
├── app.py
├── config.py
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
│
├── app/
│   ├── __init__.py
│   ├── extensions.py
│   ├── cli.py
│   │
│   ├── models/
│   │
│   ├── routes/
│   │
│   ├── forms/
│   │
│   ├── services/
│   │   ├── ai/
│   │   ├── analytics/
│   │   ├── ml/
│   │   ├── forecasting/
│   │   └── reports/
│   │
│   ├── templates/
│   │
│   ├── static/
│   │
│   └── utils/
│
├── migrations/
│
├── tests/
│
├── data/
│   ├── uploads/
│   ├── processed/
│   ├── models/
│   └── reports/
│
├── screenshots/
│   ├── dashboard.png
│   ├── dataset-analysis.png
│   ├── eda.png
│   ├── ai-qa.png
│   ├── ml-models.png
│   ├── forecasting.png
│   └── reports.png
│
└── logs/
```

---

# ⚙️ Technology Stack

### Backend

* Python
* Flask
* Flask-SQLAlchemy
* Flask-WTF
* Flask-Migrate
* Gunicorn

### Data Science

* Pandas
* NumPy
* scikit-learn
* XGBoost
* SHAP
* Matplotlib
* Seaborn

### Database

* SQLite
* PostgreSQL

### AI

* Google Gemini
* Groq
* OpenRouter
* Anthropic Claude
* OpenAI

### Frontend

* HTML5
* CSS3
* JavaScript
* Bootstrap
* Jinja2

### Infrastructure

* Docker
* Docker Compose
* Redis
* SMTP

---

# 💻 Installation

## 1. Clone the repository

```bash
git clone <your-repository-url>
cd ai-business-analytics
```

## 2. Create a virtual environment

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows

```powershell
python -m venv venv
venv\Scripts\activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

# 🔐 Environment Configuration

Create the environment file:

```bash
cp .env.example .env
```

On Windows:

```powershell
copy .env.example .env
```

At minimum configure:

```env
SECRET_KEY=your-secure-secret-key

DATABASE_URL=

GEMINI_API_KEY_1=your-gemini-key
GEMINI_API_KEY_2=
GEMINI_API_KEY_3=
GEMINI_API_KEY_4=

AI_PROVIDER_ORDER=gemini,groq,openrouter,claude,openai

ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-this-password
```

Optional Redis:

```env
REDIS_URL=redis://localhost:6379/0
```

Optional email configuration:

```env
MAIL_SERVER=
MAIL_PORT=
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_USE_TLS=
MAIL_DEFAULT_SENDER=
```

> Never commit `.env` or real API keys to Git.

---

# 🗄️ Database Setup

## SQLite

SQLite is the default and requires no external database server.

```bash
flask db upgrade
```

## PostgreSQL

Create a database:

```bash
createdb ai_analytics
```

Configure:

```env
DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/ai_analytics
```

Then run:

```bash
flask db upgrade
```

---

# 👑 Create Administrator

Set:

```env
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=your-secure-password
```

Then:

```bash
flask create-admin
```

The command is safe to run again and can promote an existing account.

---

# ▶️ Running Locally

Start the application:

```bash
flask run
```

Or:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

---

# 📧 Development Email Behavior

If SMTP credentials are not configured during development, verification and password-reset emails are logged instead of being sent.

Check:

```text
logs/app.log
```

You may see:

```text
[EMAIL SUPPRESSED]
```

along with the generated verification/reset URL.

---

# 🧪 Testing

Run the complete test suite:

```bash
python -m pytest tests/ -v
```

Current test status:

```text
332 tests
29 test files
```

The test suite covers:

* Authentication lifecycle
* Email verification
* Password reset
* Password changes
* Account deletion
* Cross-user data isolation
* File validation
* Magic-byte validation
* Data cleaning
* Dataset immutability
* EDA
* Chart calculations
* AI provider rotation
* AI fallback
* AI caching
* AI usage limits
* AI numerical-grounding behavior
* Anomaly detection
* ML training
* Model ranking
* Prediction
* Forecasting
* Report generation
* PDF validation
* Excel validation
* JSON round-tripping
* Admin authorization
* API-key exposure prevention

---

# 🐳 Docker Deployment

Docker Compose provides an application and PostgreSQL database.

```bash
cp .env.example .env
```

Configure your environment and then:

```bash
docker compose up --build
```

The application will be available at:

```text
http://localhost:8000
```

The stack includes:

```text
┌──────────────────────────────┐
│          Docker              │
│                              │
│  ┌────────────┐              │
│  │ Flask/Web  │              │
│  │ Gunicorn   │              │
│  └─────┬──────┘              │
│        │                     │
│  ┌─────▼──────┐              │
│  │ PostgreSQL │              │
│  └────────────┘              │
│                              │
└──────────────────────────────┘
```

Data is persisted using Docker volumes.

Stop the application:

```bash
docker compose down
```

To remove volumes as well:

```bash
docker compose down -v
```

---

# 🌐 Production Deployment

For production:

1. Set a strong `SECRET_KEY`
2. Use PostgreSQL
3. Configure SMTP
4. Configure production AI providers
5. Use HTTPS
6. Put Nginx or Caddy in front of Gunicorn
7. Configure Redis for shared caching
8. Configure shared rate-limit storage
9. Schedule temporary-upload cleanup
10. Back up the database and application data

Example Gunicorn command:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

---

# ⚠️ Known Architecture Limitation

The current ML job runner uses an in-process `ThreadPoolExecutor`.

This means that with multiple Gunicorn workers, an ML training job belongs to the worker that started it.

For a larger production deployment, the recommended improvement is:

```text
Flask
  ↓
Celery / RQ
  ↓
Redis
  ↓
ML Worker
```

The ML business logic is already separated from the invocation mechanism, so moving to Celery/RQ does not require rewriting the core training pipeline.

---

# 📊 Production Considerations

For larger deployments, consider:

* PostgreSQL
* Redis
* Celery/RQ
* S3-compatible object storage
* Nginx/Caddy
* Horizontal worker scaling
* Centralized logging
* Monitoring
* Automated database backups

---

# 🛣️ Future Improvements

Planned improvements include:

* [ ] Celery/RQ-based persistent ML jobs
* [ ] S3-compatible object storage
* [ ] More advanced SHAP sampling
* [ ] Larger-dataset optimization
* [ ] More forecasting algorithms
* [ ] Additional AI providers
* [ ] Advanced dashboard customization
* [ ] Scheduled reports
* [ ] More business-specific analytics templates

---

# 🏆 Project Highlights

This project demonstrates practical implementation of:

```text
Full-Stack Web Development
        +
Data Engineering
        +
Exploratory Data Analysis
        +
Artificial Intelligence
        +
Machine Learning
        +
Time-Series Forecasting
        +
Explainable AI
        +
Secure SaaS Architecture
        +
Multi-Provider LLM Architecture
```

It is designed not merely as an AI demo, but as a complete analytical application with authentication, data isolation, security, background processing, testing, reporting, and deployment considerations.

---

# 📌 Design Principles

### 1. Data First

All numerical answers should originate from actual dataset computations.

### 2. Security by Default

User data, credentials, uploaded files, and AI credentials are isolated and protected.

### 3. Provider Independence

AI functionality should not depend on a single LLM provider.

### 4. Original Data Preservation

Cleaning operations never overwrite the source dataset.

### 5. Leakage-Safe Machine Learning

Preprocessing belongs inside the ML pipeline.

### 6. Production-Oriented Architecture

The project is structured so individual components can be replaced or scaled independently.

---

# 📜 License

This project is licensed under the **MIT License**.

---

# 👨‍💻 Author

**Abaid-ur-Rehman**

Machine Learning Engineer | Python Developer | AI & Computer Vision Enthusiast

---

## ⭐ Support the Project

If you find this project useful:

* ⭐ Star the repository
* 🍴 Fork the project
* 🐛 Report issues
* 💡 Suggest improvements
* 🔧 Submit pull requests

---

<p align="center">

**Built with Python • Flask • Pandas • scikit-learn • XGBoost • SHAP • Google Gemini**

**Smarter Data. Deeper Insights. Better Decisions.**

</p>
