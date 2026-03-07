# Olist E-Commerce Intelligence Platform

End-to-end data engineering and ML platform built on the [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) — 100k real orders, 27 Brazilian states, 2016–2018.

Built as a portfolio project for **Zallpy Digital** demonstrating a production-grade AWS data stack with local-first development.

---

## Architecture

```
CSV files → S3 (raw)
              ↓
         AWS Glue PySpark
         Bronze → Silver → Gold
              ↓
    Redshift Serverless (dbt models)
         staging → intermediate → marts
              ↓
    ┌─────────────────────────────┐
    │  ML Models (ECS Fargate)    │
    │  XGBoost · BG/NBD · LightGBM│
    └─────────────────────────────┘
              ↓
    Streamlit Dashboard (ECS + ALB)
```

**Orchestration:** AWS Step Functions (nightly at 02:00 UTC via EventBridge Scheduler)  
**CI/CD:** GitHub Actions → ECR → Terraform → ECS  
**Local dev:** DuckDB + CSVs — no Docker, no AWS account needed to run notebooks

---

## Local Setup (Notebooks & Dashboard)

**Requirements:** Python 3.11+, the 9 Olist CSV files in `data/`

```bash
git clone https://github.com/your-org/olist-ecommerce-platform
cd olist-ecommerce-platform

pip install -r requirements.txt
cp .env.example .env        # defaults work out of the box

# Launch notebooks
jupyter lab

# Launch dashboard
streamlit run dashboard/app.py
```

The loader detects CSVs automatically — `USE_DUCKDB=true` in `.env` means everything runs in-memory with no database.

### PostgreSQL + pgAdmin (optional)

```bash
docker compose up -d
# pgAdmin → http://localhost:5050  (admin@olist.local / admin)
# Postgres → localhost:5432        (olist / olist_dev)
```

---

## Project Structure

```
olist-ecommerce-platform/
├── data/                        # Olist CSVs — git-ignored
├── data_loader.py               # Single entry point for all data access
├── requirements.txt
├── .env
│
├── etl/                         # AWS Glue PySpark jobs
│   ├── bronze_ingestion.py      # CSV → Parquet, schema enforcement
│   ├── silver_transform.py      # Timestamps, delay calc, DQ flags
│   └── gold_aggregation.py      # KPI tables, feature store
│
├── dbt_project/                 # dbt on Redshift Serverless
│   ├── models/staging/          # Views — always fresh
│   ├── models/intermediate/     # Tables — expensive joins
│   ├── models/marts/            # fct_orders, fct_customer_ltv, dim_geography …
│   ├── seeds/                   # br_states.csv, ltv_predictions.csv
│   └── tests/                   # Custom SQL data quality tests
│
├── ml/                          # Three production ML models
│   ├── delivery_delay_model.py  # XGBoost binary classifier
│   ├── customer_ltv_model.py    # BG/NBD + Gamma-Gamma CLV
│   ├── demand_forecast_model.py # LightGBM quantile regression
│   └── train_all.py             # python -m ml.train_all
│
├── notebooks/                   # Jupyter EDA + model walkthroughs
│   ├── 01_eda.ipynb
│   ├── 02_delivery_delay_model.ipynb
│   ├── 03_customer_ltv.ipynb
│   └── 04_demand_forecast.ipynb
│
├── dashboard/                   # Streamlit multi-page dashboard
│   ├── app.py                   # Entry point + sidebar
│   ├── charts.py                # Shared Plotly builders
│   └── pages/
│       ├── 01_market_overview.py
│       ├── 02_delivery_performance.py
│       ├── 03_customer_ltv.py
│       ├── 04_demand_forecast.py
│       └── 05_ml_predictions.py
│
├── Dockerfile.dashboard
├── Dockerfile.ml
├── Dockerfile.dbt
├── docker-compose.yml           # PostgreSQL + pgAdmin only
│
├── infra/
│   ├── postgres/init/           # Schema DDL, runs on first docker compose up
│   ├── pgadmin/servers.json     # Pre-registers postgres connection
│   ├── stepfunctions/
│   │   ├── pipeline.asl.json    # State machine definition
│   │   └── schedule.json        # EventBridge nightly trigger
│   └── terraform/
│       ├── main.tf              # Provider, backend, locals
│       ├── networking.tf        # VPC, subnets, NAT
│       ├── s3.tf                # Data lake + Glue scripts buckets
│       ├── glue.tf              # 3 PySpark jobs + IAM
│       ├── redshift.tf          # Serverless namespace + workgroup
│       ├── ecs.tf               # Cluster, task defs, ALB, service
│       ├── step_functions.tf    # State machine, DynamoDB log, scheduler
│       ├── variables.tf
│       ├── outputs.tf
│       └── terraform.tfvars.example
│
└── .github/workflows/
    ├── ci.yml                   # Lint + tests + dbt compile on every PR
    └── deploy.yml               # Build images → Terraform → ECS redeploy
```

---

## ML Models

### Delivery Delay Classifier (XGBoost)
Predicts at order placement time whether a delivery will arrive late. Features are restricted to information available before dispatch — no leakage.

- Optuna hyperparameter tuning (30 trials)
- F1-optimal threshold sweep (handles ~20% class imbalance)
- SHAP feature attribution
- **~0.78 AUC** on held-out test set

### Customer LTV (BG/NBD + Gamma-Gamma)
Industry-standard probabilistic CLV framework used at Shopify, iFood, and most serious e-commerce teams. Requires only RFM data — no clickstream needed.

- BG/NBD models purchase frequency and churn probability separately
- Gamma-Gamma models expected revenue per future transaction
- Outputs P(alive), predicted purchases (90d / 365d), present-value CLV
- Writes `ltv_predictions.csv` → loaded by `dbt seed` → joined in `fct_customer_ltv`

### Demand Forecast (LightGBM)
Weekly order volume forecast across all 27 states × 70+ product categories as a single multi-entity model.

- Walk-forward expanding-window cross-validation (5 folds)
- Lag features: 1w / 2w / 4w / 8w + rolling mean/std
- Brazilian public holidays as binary features
- Three quantile models (p10 / p50 / p90) for uncertainty bands
- 4-week-ahead iterative forecasting

---

## AWS Deployment

### Prerequisites
- AWS CLI configured (`aws configure`)
- Terraform ≥ 1.7
- Docker
- GitHub repository with the 4 secrets set (see CI/CD section)

### First deploy

```bash
# 1. Create ECR repositories
aws ecr create-repository --repository-name olist-dashboard --region us-east-1
aws ecr create-repository --repository-name olist-ml       --region us-east-1
aws ecr create-repository --repository-name olist-dbt      --region us-east-1

# 2. Fill in tfvars
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set your account ID in image URIs, set Redshift password

# 3. Deploy infrastructure
terraform init
terraform plan
terraform apply

# 4. Upload CSVs to S3
aws s3 cp data/ s3://olist-prod-data-lake-<account_id>/raw/ --recursive

# 5. Trigger first pipeline run
aws stepfunctions start-execution \
  --state-machine-arn $(terraform output -raw state_machine_arn) \
  --input '{"trigger":"manual","force_retrain":true}'
```

After the first run completes, the dashboard is live at the ALB URL:

```bash
terraform output dashboard_url
```

### CI/CD

Every push to `main`:
1. Lints and tests the codebase
2. Builds all 3 Docker images, tags with commit SHA, pushes to ECR
3. Runs `terraform apply` with image URIs injected as `TF_VAR_*`
4. Forces a new ECS deployment and waits for stability

To trigger the full pipeline with ML retraining: go to Actions → Deploy → Run workflow → tick **force_retrain**.

### GitHub Secrets required

| Secret | How to get it |
|---|---|
| `AWS_ACCESS_KEY_ID` | `aws iam create-access-key --user-name <user>` |
| `AWS_SECRET_ACCESS_KEY` | same command output |
| `AWS_ACCOUNT_ID` | `aws sts get-caller-identity --query Account --output text` |
| `REDSHIFT_ADMIN_PASSWORD` | the password set in `terraform.tfvars` |

---

## dbt Models

| Model | Layer | Description |
|---|---|---|
| `stg_orders` | Staging | Clean column names, type casts |
| `stg_sellers` | Staging | Seller state + region |
| `int_customer_orders` | Intermediate | Customer aggregation, RFM inputs |
| `int_delivery_features` | Intermediate | ML feature engineering |
| `int_state_metrics` | Intermediate | State KPIs with rankings |
| `fct_orders` | Marts | One row per delivered order |
| `fct_revenue` | Marts | Monthly GMV by state, MoM growth |
| `fct_delivery_performance` | Marts | SLA bands (on-time / minor / moderate / severe) |
| `fct_customer_ltv` | Marts | RFM scores, 6 segments, BG/NBD predictions |
| `dim_geography` | Marts | 27 states with lat/lng, GMV share, rankings |

---

## Key Design Decisions

**DuckDB for local dev** — zero-dependency analytics. The same `OlistLoader` class reads CSVs locally and Redshift in production, controlled by `USE_DUCKDB` env var.

**No local Spark** — Previous iteration used bitnami/spark in Docker which broke due to image removal. All PySpark runs on managed AWS Glue — no local Spark installation, no Kubernetes.

**ML predictions via dbt seed** — The BG/NBD model writes `ltv_predictions.csv`, `dbt seed` loads it into Redshift, and `fct_customer_ltv` joins it. This decouples Python ML from SQL without requiring an API or shared database connection.

**Step Functions Parallel state** — dbt and ML retraining run concurrently after Gold is built. They're independent branches that both depend on Gold but not on each other — cutting total pipeline wall-clock time by roughly half.

**ECS `ignore_changes = [task_definition]`** — Terraform manages infrastructure; CI/CD manages deployments. Without this, every `terraform apply` would roll back to the version Terraform knows about, fighting with GitHub Actions.

---

## License

MIT
