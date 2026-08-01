# FinQuery — Financial Analytics Platform

<div align="center">

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?style=flat-square&logo=postgresql)](https://www.postgresql.org/)
[![LangChain](https://img.shields.io/badge/LangChain-SQL%20Agent-1C3C3C?style=flat-square&logo=chainlink)](https://www.langchain.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![LangSmith](https://img.shields.io/badge/LangSmith-Observability-FF6B35?style=flat-square)](https://smith.langchain.com/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=flat-square&logo=docker)](https://www.docker.com/)

**Production data warehouse + live analytics dashboard + self-correcting NL-to-SQL agent**

[Architecture](#architecture) • [Data Warehouse](#data-warehouse) • [Application Layer](#application-layer) • [Tech Stack](#tech-stack) • [Setup](#setup)

</div>

---

## Overview

FinQuery is a full-stack financial analytics platform built on a production-style PostgreSQL data warehouse. It combines a **live KPI dashboard** backed by precomputed MOLAP tables with a **natural language SQL agent** that lets users query the warehouse in plain English.

The underlying dataset is the [CaixaBank Tech 2024 AI Hackathon](https://www.kaggle.com/) financial transactions dataset — approximately 40M transactions spanning the 2010s decade, covering transaction records, customer demographics, card data, merchant category codes, and fraud labels.

---

## Architecture

### Current Warehouse Flow

```mermaid
flowchart TD
    U[User / Analyst] --> Q[SQL Analysis / BI Queries]
    U --> H[Helper Script]
    H --> D[Source Data Files]
    D --> S[Schema and ETL Scripts]
    S --> W[(dw_etl Warehouse)]
    W --> M[MOLAP Summary Tables]
    W --> O[OLAP Queries]
    W --> P[Performance and Indexing Scripts]
    M --> R[Reporting and Analysis]
    O --> R
    P --> R
```

### Planned Application Layer

```mermaid
flowchart TD
    U[User in Browser] --> UI[Streamlit or Next.js UI]
    UI --> DASH[Dashboard Tab]
    UI --> ASK[Ask AI Tab]
    DASH --> API[FastAPI Backend]
    ASK --> API
    API --> MOLAP[MOLAP Tables]
    API --> AGENT[LangChain SQL Agent]
    AGENT --> VALIDATE[SQL Safety Validator]
    VALIDATE --> EXECUTE[Query Executor]
    EXECUTE --> DB[(dw_etl Database)]
    EXECUTE --> RETRY[LangGraph Retry Loop]
    RETRY --> AGENT
    MOLAP --> CHARTS[Charts / Tables / KPI Cards]
    DB --> CHARTS
```

The dashboard and agent are **isolated paths**. The dashboard runs direct SQL against precomputed MOLAP tables — no LLM involvement, no latency variance. The agent path handles open-ended questions through a validated, self-correcting execution pipeline.

---

## Data Warehouse

The warehouse follows a **Kimball star schema** design, with the pipeline flowing through three schemas:

```
staging → etl → dw_etl
```

### Schema

| Table | Type | Description |
|:---|:---|:---|
| `fact_transactions` | Fact | Core transaction grain: amount, fraud label, chip usage |
| `dim_customer` | Dimension | Demographics, income, credit score |
| `dim_card` | Dimension | Card brand, type, limits, expiry |
| `dim_merchant` | Dimension | Merchant identity (chain/brand grain) |
| `dim_location` | Dimension | City, state, zip — conformed, reusable |
| `dim_date` | Dimension | Full calendar with quarter, week, weekend flags |
| `dim_mcc` | Dimension | Merchant category codes and descriptions |
| `dim_error` | Dimension | Transaction error classification |

> **Note on `dim_merchant` vs `dim_location`:** An audit revealed that `merchant_id` is a brand/chain identifier, not a storefront identifier — 21.6% of merchant IDs span multiple cities (one spans 2,579). Treating it as a location key silently corrupted all city and state aggregations. The fix was to introduce a separate `dim_location` dimension at the city-state-zip grain, keeping `dim_merchant` as a pure identity table. Full details in [`WAREHOUSE_REDESIGN_NOTES.md`](SQL/docs/WAREHOUSE_REDESIGN_NOTES.md).

### MOLAP Summary Tables

Five precomputed summary tables power the dashboard:

| Table | Aggregation |
|:---|:---|
| `molap_monthly_transactions` | Monthly volume, total amount, fraud count |
| `molap_top_customers` | Top 10 customers by total spend |
| `molap_fraud_by_state` | Fraud rate per state |
| `molap_card_brand_performance` | Transactions and fraud rate by card brand |
| `molap_transactions_by_city` | Average, min, max spend per city |

### Indexing & Partitioning

- **B-Tree indexes** on `date_key`, `customer_key`, `location_key`, `card_key`, `mcc_key` for range scans and join acceleration
- **Partial index** on `fraud_label = TRUE` — compact and fast for fraud-only queries
- **Materialized view** (`mv_monthly_fraud_summary`) with a unique index for concurrent refresh
- **Range partitioning** by year (2010–2019 + DEFAULT catch-all) on a benchmark copy for partition pruning validation

---

## Application Layer

### Dashboard
- Five chart views backed directly by MOLAP tables via FastAPI endpoints
- Monthly transaction trends, top customers, fraud by state, card brand breakdown, city-level spend
- No LLM dependency — queries are prewritten, fast, and deterministic

### NL-to-SQL Agent

- **LangGraph** is used in exactly one place: the retry loop. Nothing else uses it.
- **LangSmith** traces every run — prompts, SQL generations, retries, execution time, and token cost.
- Evaluation framework measures query accuracy with self-correction off vs. on.

---

## Tech Stack

| Layer | Technology |
|:---|:---|
| **Database** | PostgreSQL 18, Star Schema, Kimball dimensional modeling |
| **ETL** | Pure SQL pipeline (`staging → etl → dw_etl`) |
| **OLAP / MOLAP** | Precomputed summary tables, materialized views, range partitioning |
| **Agent** | LangChain (SQL generation), LangGraph (retry loop), Claude API |
| **Validation** | Custom SQL safety layer + read-only DB role |
| **Backend** | FastAPI, SQLAlchemy, Uvicorn |
| **Frontend** | Streamlit or Next.js + Tailwind + Recharts |
| **Observability** | LangSmith (trace capture, evaluation, cost tracking) |
| **Deployment** | Docker, Azure App Service / Render, GitHub Actions |

---

## Project Phases

| Phase | Scope | Status |
|:---|:---|:---|
| **1 — Data Warehouse** | Star schema design, ETL pipeline, MOLAP tables, indexing, partitioning | ✅ Complete |
| **2 — Application Layer** | FastAPI backend, dashboard endpoints, NL-to-SQL agent, LangGraph retry loop | 🔧 In Progress |
| **3 — Observability** | LangSmith tracing, evaluation pairs, before/after accuracy benchmarking | 🔧 In Progress |
| **4 — Deployment** | Docker, cloud hosting, CI/CD pipeline, read-only role, secrets management | ⏳ Planned |

---

## Repository Structure

```
FinQuery/
├── SQL/
│   ├── 01_schema/
│   │   └── schema.sql                  # Star schema — 8 dimensions + fact table
│   ├── 02_etl/
│   │   └── etl.sql                     # Staging → cleaned → dimensional load
│   ├── 03_molap/
│   │   └── molap_tables.sql            # 5 precomputed KPI summary tables
│   ├── 04_indexing_partitioning/
│   │   └── indexing_partitioning.sql   # Indexes, materialized view, range partitions
│   ├── 05_olap_queries/
│   │   └── olap_queries.sql            # Analytics queries
│   ├── 06_performance/
│   │   └── join_performance.sql        # Join strategy benchmarks
│   └── docs/
│       ├── schema_justification.sql       # Modeling decisions and rationale
│       ├── WAREHOUSE_REDESIGN_NOTES.md    # Full audit trail and redesign notes
│       └── schema_diagram.pdf             # ER diagram
└── README.md
```

---

## Setup

### Prerequisites

- PostgreSQL 18
- Python 3.10+
- Docker (for deployment)

### Run the Warehouse

```bash
git clone https://github.com/yourusername/finquery.git
cd finquery

# Load in order — each file depends on the one before it
psql -U postgres -f SQL/01_schema/schema.sql
psql -U postgres -f SQL/02_etl/etl.sql
psql -U postgres -f SQL/03_molap/molap_tables.sql
psql -U postgres -f SQL/04_indexing_partitioning/indexing_partitioning.sql

# Verify with OLAP queries
psql -U postgres -f SQL/05_olap_queries/olap_queries.sql
```

### Environment Variables (Application Layer)

```env
DATABASE_URL=postgresql://user:password@host:5432/finquery
ANTHROPIC_API_KEY=your_api_key
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
```

---

## Data Source

Dataset: [CaixaBank Tech — 2024 AI Hackathon](https://www.kaggle.com/) (Kaggle)
Five files: `transactions_data.csv`, `users_data.csv`, `cards_data.csv`, `mcc_codes.json`, `train_fraud_labels.json`

---

## License

For portfolio and educational use. Dataset credit: CaixaBank Tech, 2024 AI Hackathon.
