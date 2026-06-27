"""Audit log persistence for DQ monitoring runs."""

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, text
from sqlalchemy.orm import Session

from db import Base, get_engine, get_session
from scoring import DQScoreResult
from utils import assign_severity, current_timestamp


class DQAuditLog(Base):
    """ORM model for the dq_audit_log table."""

    __tablename__ = "dq_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, index=True)
    run_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    check_name = Column(String(128), nullable=False)
    table_name = Column(String(64), nullable=False)
    failed_records = Column(Integer, nullable=False, default=0)
    severity = Column(String(8), nullable=False)
    dq_score = Column(Float, nullable=False)
    remarks = Column(Text, nullable=True)


class AuditLogger:
    """Persist and retrieve DQ audit log entries."""

    @staticmethod
    def ensure_table() -> None:
        """Create audit log table if it does not exist."""
        Base.metadata.create_all(get_engine(), tables=[DQAuditLog.__table__])

    @staticmethod
    def log_check_result(
        session: Session,
        run_id: str,
        result: DQScoreResult,
        remarks: str = "",
        run_timestamp: datetime | None = None,
    ) -> DQAuditLog:
        """Insert a single check result into the audit log."""
        severity = assign_severity(result.failed_records)
        entry = DQAuditLog(
            run_id=run_id,
            run_timestamp=run_timestamp or current_timestamp(),
            check_name=result.check_name,
            table_name=result.table_name,
            failed_records=result.failed_records,
            severity=severity,
            dq_score=result.dq_score,
            remarks=remarks,
        )
        session.add(entry)
        return entry

    @staticmethod
    def log_batch(
        run_id: str,
        results: list[tuple[DQScoreResult, str]],
        run_timestamp: datetime | None = None,
    ) -> None:
        """Log multiple check results in a single transaction."""
        ts = run_timestamp or current_timestamp()
        with get_session() as session:
            for result, remarks in results:
                AuditLogger.log_check_result(session, run_id, result, remarks, ts)

    @staticmethod
    def fetch_audit_log(limit: int | None = None) -> pd.DataFrame:
        """Return audit log records as a DataFrame."""
        AuditLogger.ensure_table()
        query = """
            SELECT run_id, run_timestamp, check_name, table_name,
                   failed_records, severity, dq_score, remarks
            FROM dq_audit_log
            ORDER BY run_timestamp DESC, check_name ASC
        """
        if limit:
            query += f" LIMIT {int(limit)}"
        with get_engine().connect() as conn:
            return pd.read_sql(text(query), conn)

    @staticmethod
    def fetch_runs_summary() -> pd.DataFrame:
        """Return aggregated metrics per run_id."""
        AuditLogger.ensure_table()
        query = """
            SELECT
                run_id,
                MIN(run_timestamp) AS run_timestamp,
                COUNT(*) AS checks_executed,
                AVG(dq_score) AS avg_dq_score,
                SUM(failed_records) AS total_failures,
                SUM(CASE WHEN severity = 'P1' THEN 1 ELSE 0 END) AS p1_count,
                SUM(CASE WHEN severity = 'P2' THEN 1 ELSE 0 END) AS p2_count,
                SUM(CASE WHEN severity = 'P3' THEN 1 ELSE 0 END) AS p3_count
            FROM dq_audit_log
            GROUP BY run_id
            ORDER BY MIN(run_timestamp) DESC
        """
        with get_engine().connect() as conn:
            return pd.read_sql(text(query), conn)

    @staticmethod
    def get_latest_run_id() -> str | None:
        """Return the most recent run_id."""
        df = AuditLogger.fetch_runs_summary()
        if df.empty:
            return None
        return str(df.iloc[0]["run_id"])
