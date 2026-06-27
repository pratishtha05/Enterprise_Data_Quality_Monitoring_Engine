"""Shared utility functions for the DQ monitoring engine."""

import re
import uuid
from datetime import datetime
from typing import Any

import pandas as pd

from config import SEVERITY_P1_THRESHOLD, SEVERITY_P2_THRESHOLD

EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PHONE_PATTERN = re.compile(r"^\d{10}$")


def generate_run_id() -> str:
    """Generate a unique run identifier."""
    return str(uuid.uuid4())


def current_timestamp() -> datetime:
    """Return the current UTC-naive timestamp."""
    return datetime.utcnow()


def is_valid_email(email: Any) -> bool:
    """Validate email format."""
    if pd.isna(email) or email is None:
        return False
    return bool(EMAIL_PATTERN.match(str(email).strip()))


def is_valid_phone(phone: Any) -> bool:
    """Validate phone number length (10 digits)."""
    if pd.isna(phone) or phone is None:
        return False
    cleaned = re.sub(r"\D", "", str(phone).split(".")[0] if isinstance(phone, float) else str(phone))
    return bool(PHONE_PATTERN.match(cleaned))


def assign_severity(failed_records: int) -> str:
    """Assign severity based on failure count thresholds."""
    if failed_records > SEVERITY_P1_THRESHOLD:
        return "P1"
    if failed_records > SEVERITY_P2_THRESHOLD:
        return "P2"
    return "P3"


def safe_str(value: Any) -> str:
    """Convert value to string safely for display."""
    if pd.isna(value) or value is None:
        return ""
    return str(value)


def format_percentage(value: float) -> str:
    """Format a float as a percentage string."""
    return f"{value:.2f}%"


def ensure_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Return an empty DataFrame with no columns when records list is empty."""
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)
