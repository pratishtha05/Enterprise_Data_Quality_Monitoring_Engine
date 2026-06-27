# Enterprise Data Quality Monitoring Engine

A production-ready **Enterprise Data Quality (DQ) Monitoring Engine** that ingests customer and transaction data, executes 21 automated data quality checks, computes DQ scores, logs audit trails, and visualizes results through an interactive Streamlit dashboard.

---

## Project Overview

Modern enterprises depend on trustworthy data for analytics, reporting, and decision-making. This project simulates a real-world DQ monitoring pipeline that:

- Loads structured data from CSV into PostgreSQL (with SQLite fallback)
- Runs completeness, validity, uniqueness, referential integrity, business rule, and volume anomaly checks
- Calculates per-check and aggregate DQ scores
- Persists every run to an audit log with severity classification
- Presents actionable insights via a professional Streamlit dashboard

---

## Architecture

```text
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  CSV Files  │────▶│  load_data   │────▶│   PostgreSQL    │
│ customers   │     │     .py      │     │  / SQLite DB    │
│ transactions│     └──────────────┘     └────────┬────────┘
└─────────────┘                                  │
                                                 ▼
                                        ┌─────────────────┐
                                        │     main.py     │
                                        │  Orchestrator   │
                                        └────────┬────────┘
                    ┌────────────────────────────┼────────────────────────────┐
                    ▼                            ▼                            ▼
            ┌──────────────┐           ┌──────────────┐           ┌──────────────┐
            │  dq_checks   │           │business_rules│           │   anomaly    │
            │     .py      │           │     .py      │           │ _detection   │
            └──────┬───────┘           └──────┬───────┘           └──────┬───────┘
                   │                          │                          │
                   └──────────────────────────┼──────────────────────────┘
                                              ▼
                                    ┌─────────────────┐
                                    │ scoring + audit │
                                    └────────┬────────┘
                                             ▼
                                    ┌─────────────────┐
                                    │ Streamlit       │
                                    │ Dashboard       │
                                    └─────────────────┘
```

---

## Folder Structure

```text
enterprise-dq-monitoring-engine/
├── data/                   # Sample CSV datasets
├── sql/                    # Database schema and seed scripts
├── src/                    # Core Python modules
├── dashboard/              # Streamlit application
├── reports/                # Generated reports (future use)
├── screenshots/            # Dashboard screenshots
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Technology Stack

| Layer        | Technology                          |
|-------------|--------------------------------------|
| Language    | Python 3.12                          |
| Database    | PostgreSQL (SQLite fallback)         |
| ORM         | SQLAlchemy                           |
| Data        | Pandas, NumPy                        |
| Visualization | Plotly                             |
| Dashboard   | Streamlit                            |
| DB Driver   | psycopg2-binary                      |

---

## Features

- **21 automated DQ checks** across 6 categories
- **DQ scoring formula**: `100 - ((failed_records / total_records) × 100)`
- **Severity classification**: P1 (>100 failures), P2 (>20), P3 (otherwise)
- **Audit logging** with run_id, timestamp, check name, failures, score, remarks
- **Duplicate-safe data loading** from CSV
- **Interactive dashboard** with 5 pages
- **Environment-based configuration** via `.env` or environment variables
- **SQLite fallback** when PostgreSQL is unavailable

---

## DQ Checks (21 Total)

### Completeness (5)
| Check | Description |
|-------|-------------|
| `null_email` | Missing customer email |
| `null_phone` | Missing customer phone |
| `null_amount` | Missing transaction amount |
| `null_transaction_date` | Missing transaction date |
| `null_customer_id` | Missing transaction customer_id |

### Validity (5)
| Check | Description |
|-------|-------------|
| `invalid_email_format` | Email fails regex validation |
| `negative_amount` | Amount < 0 |
| `future_transaction` | Transaction date in the future |
| `invalid_status` | Status not in allowed values |
| `invalid_phone_length` | Phone not exactly 10 digits |

### Uniqueness (3)
| Check | Description |
|-------|-------------|
| `duplicate_customer_id` | Duplicate customer IDs |
| `duplicate_transaction_id` | Duplicate transaction IDs |
| `duplicate_email` | Duplicate email addresses |

### Referential Integrity (2)
| Check | Description |
|-------|-------------|
| `customer_missing_in_master` | customer_id not in customers table |
| `orphan_transaction` | Transaction without valid customer reference |

### Business Rules (5)
| Check | Description |
|-------|-------------|
| `amount_exceeds_50000` | Amount > 50,000 |
| `refund_with_positive_amount` | Refund with positive amount |
| `pending_over_30_days` | Pending transaction > 30 days old |
| `inactive_customer_transaction` | Transaction for inactive customer |
| `cancelled_with_positive_amount` | Cancelled transaction with amount > 0 |

### Volume Anomaly (1)
| Check | Description |
|-------|-------------|
| `volume_anomaly` | Today's volume < 70% or > 130% of average daily count |

---

## Dashboard

The Streamlit dashboard (`dashboard/app.py`) includes:

1. **Dashboard** — KPI cards, DQ score trend, severity pie chart, failures by check, top violations
2. **Audit History** — Searchable, sortable, filterable audit log
3. **Failed Records** — Select a DQ rule and view/download failed rows
4. **Trend Analysis** — Historical DQ scores and failure trends
5. **Data Explorer** — Browse customers and transactions with search/filter

---

## Setup & Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 14+ (optional — SQLite fallback enabled by default)

### 1. Create virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Load sample data

```bash
python src/load_data.py
```

### 4. Run DQ checks

```bash
python src/main.py
```

### 5. Launch dashboard

```bash
streamlit run dashboard/app.py
```

---

## Business Impact

- **Reduced data incidents** through proactive monitoring before data reaches downstream systems
- **Audit compliance** with timestamped, severity-classified DQ run logs
- **Faster root cause analysis** via failed-record drill-down in the dashboard
- **Operational visibility** into data health trends over time
- **Scalable architecture** ready for scheduling (Airflow/cron) and alerting integrations

---

---

## License

MIT License — free for educational and portfolio use.
