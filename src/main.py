"""Main orchestrator for the Enterprise DQ Monitoring Engine."""

import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from anomaly_detection import VolumeAnomalyDetector
from audit import AuditLogger
from business_rules import BusinessRuleEngine
from db import get_active_database_url, get_engine
from dq_checks import DQCheckEngine
from scoring import DQScorer
from sqlalchemy import text
from utils import current_timestamp, generate_run_id


def fetch_table_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load customers and transactions from the database."""
    engine = get_engine()
    with engine.connect() as conn:
        customers = pd.read_sql(text("SELECT * FROM customers"), conn)
        transactions = pd.read_sql(text("SELECT * FROM transactions"), conn)
    return customers, transactions


def run_dq_monitoring() -> str:
    """
    Execute all DQ checks, compute scores, and persist audit logs.

    Returns the run_id for the completed execution.
    """
    run_id = generate_run_id()
    run_ts = current_timestamp()

    customers, transactions = fetch_table_data()
    if customers.empty and transactions.empty:
        raise RuntimeError(
            "No data found. Run 'python src/load_data.py' first to load sample data."
        )

    AuditLogger.ensure_table()

    dq_engine = DQCheckEngine(customers, transactions)
    biz_engine = BusinessRuleEngine(customers, transactions)
    anomaly_detector = VolumeAnomalyDetector(transactions)

    all_outcomes: list[tuple] = []

    for outcome in dq_engine.run_all():
        all_outcomes.append((outcome.result, outcome.remarks))

    for outcome in biz_engine.run_all():
        all_outcomes.append((outcome.result, outcome.remarks))

    anomaly_outcome = anomaly_detector.run_check()
    all_outcomes.append((anomaly_outcome.result, anomaly_outcome.remarks))

    scores = [result.dq_score for result, _ in all_outcomes]
    aggregate = DQScorer.aggregate_score(scores)
    total_failures = sum(result.failed_records for result, _ in all_outcomes)

    from db import get_session

    with get_session() as session:
        for result, remarks in all_outcomes:
            AuditLogger.log_check_result(session, run_id, result, remarks, run_ts)

    print("=" * 60)
    print("Enterprise DQ Monitoring Engine - Execution Summary")
    print("=" * 60)
    print(f"Run ID:           {run_id}")
    print(f"Database:         {get_active_database_url()}")
    print(f"Checks Executed:  {len(all_outcomes)}")
    print(f"Aggregate Score:  {aggregate:.2f}")
    print(f"Total Failures:   {total_failures}")
    print("-" * 60)

    for result, remarks in all_outcomes:
        severity = "P1" if result.failed_records > 100 else (
            "P2" if result.failed_records > 20 else "P3"
        )
        print(
            f"[{severity}] {result.check_name:35s} | "
            f"Failed: {result.failed_records:5d} | Score: {result.dq_score:6.2f} | {remarks}"
        )

    print("=" * 60)
    return run_id


def main() -> None:
    """Entry point for DQ monitoring execution."""
    run_dq_monitoring()


if __name__ == "__main__":
    main()
