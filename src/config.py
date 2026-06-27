"""Application configuration with environment variable support."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SQL_DIR = BASE_DIR / "sql"
REPORTS_DIR = BASE_DIR / "reports"

# PostgreSQL defaults; override via environment variables
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "dq_monitoring")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
)

# SQLite fallback when PostgreSQL is unavailable
SQLITE_PATH = BASE_DIR / "dq_monitoring.db"
SQLITE_URL = f"sqlite:///{SQLITE_PATH.as_posix()}"

USE_SQLITE_FALLBACK = os.getenv("USE_SQLITE_FALLBACK", "true").lower() == "true"

# DQ thresholds
VOLUME_ANOMALY_LOWER = float(os.getenv("VOLUME_ANOMALY_LOWER", "0.70"))
VOLUME_ANOMALY_UPPER = float(os.getenv("VOLUME_ANOMALY_UPPER", "1.30"))
HIGH_AMOUNT_THRESHOLD = float(os.getenv("HIGH_AMOUNT_THRESHOLD", "50000"))
PENDING_DAYS_THRESHOLD = int(os.getenv("PENDING_DAYS_THRESHOLD", "30"))

# Severity thresholds
SEVERITY_P1_THRESHOLD = int(os.getenv("SEVERITY_P1_THRESHOLD", "100"))
SEVERITY_P2_THRESHOLD = int(os.getenv("SEVERITY_P2_THRESHOLD", "20"))

VALID_CUSTOMER_STATUSES = {"active", "inactive", "suspended"}
VALID_TRANSACTION_STATUSES = {"completed", "pending", "cancelled", "refund", "failed"}
VALID_PAYMENT_MODES = {"credit_card", "debit_card", "upi", "net_banking", "cash"}
