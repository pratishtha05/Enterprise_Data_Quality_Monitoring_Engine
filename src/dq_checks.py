"""Core data quality checks: completeness, validity, uniqueness, referential integrity."""

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from config import VALID_CUSTOMER_STATUSES, VALID_TRANSACTION_STATUSES
from scoring import DQScorer, DQScoreResult
from utils import is_valid_email, is_valid_phone


@dataclass
class CheckOutcome:
    """Outcome of a single DQ check including failed record details."""

    result: DQScoreResult
    failed_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    remarks: str = ""


class DQCheckEngine:
    """Execute standard data quality checks against customer and transaction data."""

    def __init__(self, customers: pd.DataFrame, transactions: pd.DataFrame):
        self.customers = customers.copy()
        self.transactions = transactions.copy()
        self._customer_ids = set(self.customers["customer_id"].dropna().astype(str))

    def run_all(self) -> list[CheckOutcome]:
        """Run all standard DQ checks and return outcomes."""
        checks: list[Callable[[], CheckOutcome]] = [
            self.check_null_email,
            self.check_null_phone,
            self.check_null_amount,
            self.check_null_transaction_date,
            self.check_null_customer_id,
            self.check_invalid_email_format,
            self.check_negative_amount,
            self.check_future_transaction,
            self.check_invalid_status,
            self.check_invalid_phone_length,
            self.check_duplicate_customer_id,
            self.check_duplicate_transaction_id,
            self.check_duplicate_email,
            self.check_customer_missing_in_master,
            self.check_orphan_transaction,
        ]
        return [check() for check in checks]

    def _build_outcome(
        self,
        check_name: str,
        table_name: str,
        total_records: int,
        failed_df: pd.DataFrame,
        remarks: str = "",
    ) -> CheckOutcome:
        """Helper to construct a CheckOutcome from failed records."""
        failed_count = len(failed_df)
        result = DQScorer.build_result(check_name, table_name, total_records, failed_count)
        return CheckOutcome(result=result, failed_df=failed_df, remarks=remarks)

    # --- COMPLETENESS ---

    def check_null_email(self) -> CheckOutcome:
        """Flag customers with missing email addresses."""
        mask = self.customers["email"].isna() | (self.customers["email"].astype(str).str.strip() == "")
        failed = self.customers[mask]
        return self._build_outcome(
            "null_email", "customers", len(self.customers), failed,
            "Customers with null or empty email",
        )

    def check_null_phone(self) -> CheckOutcome:
        """Flag customers with missing phone numbers."""
        mask = self.customers["phone"].isna() | (self.customers["phone"].astype(str).str.strip() == "")
        failed = self.customers[mask]
        return self._build_outcome(
            "null_phone", "customers", len(self.customers), failed,
            "Customers with null or empty phone",
        )

    def check_null_amount(self) -> CheckOutcome:
        """Flag transactions with missing amounts."""
        mask = self.transactions["amount"].isna()
        failed = self.transactions[mask]
        return self._build_outcome(
            "null_amount", "transactions", len(self.transactions), failed,
            "Transactions with null amount",
        )

    def check_null_transaction_date(self) -> CheckOutcome:
        """Flag transactions with missing transaction dates."""
        mask = self.transactions["transaction_date"].isna()
        failed = self.transactions[mask]
        return self._build_outcome(
            "null_transaction_date", "transactions", len(self.transactions), failed,
            "Transactions with null transaction_date",
        )

    def check_null_customer_id(self) -> CheckOutcome:
        """Flag transactions with missing customer_id."""
        mask = (
            self.transactions["customer_id"].isna()
            | (self.transactions["customer_id"].astype(str).str.strip() == "")
        )
        failed = self.transactions[mask]
        return self._build_outcome(
            "null_customer_id", "transactions", len(self.transactions), failed,
            "Transactions with null or empty customer_id",
        )

    # --- VALIDITY ---

    def check_invalid_email_format(self) -> CheckOutcome:
        """Flag customers with invalid email format (non-null emails only)."""
        valid_mask = self.customers["email"].notna() & (
            self.customers["email"].astype(str).str.strip() != ""
        )
        subset = self.customers[valid_mask]
        invalid = subset[~subset["email"].apply(is_valid_email)]
        return self._build_outcome(
            "invalid_email_format", "customers", len(self.customers), invalid,
            "Customers with invalid email format",
        )

    def check_negative_amount(self) -> CheckOutcome:
        """Flag transactions with negative amounts."""
        mask = self.transactions["amount"].notna() & (self.transactions["amount"] < 0)
        failed = self.transactions[mask]
        return self._build_outcome(
            "negative_amount", "transactions", len(self.transactions), failed,
            "Transactions with negative amount",
        )

    def check_future_transaction(self) -> CheckOutcome:
        """Flag transactions dated in the future."""
        today = pd.Timestamp.today().normalize()
        dates = pd.to_datetime(self.transactions["transaction_date"], errors="coerce")
        mask = dates.notna() & (dates > today)
        failed = self.transactions[mask]
        return self._build_outcome(
            "future_transaction", "transactions", len(self.transactions), failed,
            "Transactions with future transaction_date",
        )

    def check_invalid_status(self) -> CheckOutcome:
        """Flag records with invalid status values."""
        cust_invalid = self.customers[
            self.customers["status"].notna()
            & ~self.customers["status"].str.lower().isin(VALID_CUSTOMER_STATUSES)
        ].copy()
        cust_invalid["_source_table"] = "customers"

        txn_invalid = self.transactions[
            self.transactions["status"].notna()
            & ~self.transactions["status"].str.lower().isin(VALID_TRANSACTION_STATUSES)
        ].copy()
        txn_invalid["_source_table"] = "transactions"

        failed = pd.concat([cust_invalid, txn_invalid], ignore_index=True)
        total = len(self.customers) + len(self.transactions)
        return self._build_outcome(
            "invalid_status", "customers,transactions", total, failed,
            "Records with status not in allowed values",
        )

    def check_invalid_phone_length(self) -> CheckOutcome:
        """Flag customers with invalid phone number length."""
        valid_mask = self.customers["phone"].notna() & (
            self.customers["phone"].astype(str).str.strip() != ""
        )
        subset = self.customers[valid_mask]
        invalid = subset[~subset["phone"].apply(is_valid_phone)]
        return self._build_outcome(
            "invalid_phone_length", "customers", len(self.customers), invalid,
            "Customers with phone not exactly 10 digits",
        )

    # --- UNIQUENESS ---

    def check_duplicate_customer_id(self) -> CheckOutcome:
        """Flag duplicate customer_id values."""
        dup_ids = self.customers["customer_id"][self.customers["customer_id"].duplicated(keep=False)]
        failed = self.customers[self.customers["customer_id"].isin(dup_ids)]
        return self._build_outcome(
            "duplicate_customer_id", "customers", len(self.customers), failed,
            "Duplicate customer_id values detected",
        )

    def check_duplicate_transaction_id(self) -> CheckOutcome:
        """Flag duplicate transaction_id values."""
        dup_ids = self.transactions["transaction_id"][
            self.transactions["transaction_id"].duplicated(keep=False)
        ]
        failed = self.transactions[self.transactions["transaction_id"].isin(dup_ids)]
        return self._build_outcome(
            "duplicate_transaction_id", "transactions", len(self.transactions), failed,
            "Duplicate transaction_id values detected",
        )

    def check_duplicate_email(self) -> CheckOutcome:
        """Flag duplicate email addresses (excluding nulls)."""
        emails = self.customers["email"].dropna()
        emails = emails[emails.astype(str).str.strip() != ""]
        dup_emails = emails[emails.str.lower().duplicated(keep=False)]
        dup_emails_lower = dup_emails.str.lower()
        email_lower = self.customers["email"].astype(str).str.lower()
        failed = self.customers[
            self.customers["email"].notna()
            & (self.customers["email"].astype(str).str.strip() != "")
            & email_lower.isin(dup_emails_lower)
        ]
        return self._build_outcome(
            "duplicate_email", "customers", len(self.customers), failed,
            "Duplicate email addresses detected",
        )

    # --- REFERENTIAL INTEGRITY ---

    def check_customer_missing_in_master(self) -> CheckOutcome:
        """Flag transactions referencing customer_id not present in customers table."""
        txn_ids = self.transactions["customer_id"].dropna().astype(str)
        mask = self.transactions["customer_id"].notna() & ~txn_ids.isin(self._customer_ids)
        failed = self.transactions[mask]
        return self._build_outcome(
            "customer_missing_in_master", "transactions", len(self.transactions), failed,
            "Transactions referencing non-existent customer_id",
        )

    def check_orphan_transaction(self) -> CheckOutcome:
        """Flag transactions with customer_id that does not exist in master (orphans)."""
        mask = self.transactions["customer_id"].notna()
        orphan_mask = mask & ~self.transactions["customer_id"].astype(str).isin(self._customer_ids)
        failed = self.transactions[orphan_mask]
        return self._build_outcome(
            "orphan_transaction", "transactions", len(self.transactions), failed,
            "Orphan transactions without valid customer reference",
        )


# Registry for dashboard failed-records lookup
CHECK_REGISTRY: dict[str, Callable[["DQCheckEngine"], CheckOutcome]] = {
    "null_email": lambda e: e.check_null_email(),
    "null_phone": lambda e: e.check_null_phone(),
    "null_amount": lambda e: e.check_null_amount(),
    "null_transaction_date": lambda e: e.check_null_transaction_date(),
    "null_customer_id": lambda e: e.check_null_customer_id(),
    "invalid_email_format": lambda e: e.check_invalid_email_format(),
    "negative_amount": lambda e: e.check_negative_amount(),
    "future_transaction": lambda e: e.check_future_transaction(),
    "invalid_status": lambda e: e.check_invalid_status(),
    "invalid_phone_length": lambda e: e.check_invalid_phone_length(),
    "duplicate_customer_id": lambda e: e.check_duplicate_customer_id(),
    "duplicate_transaction_id": lambda e: e.check_duplicate_transaction_id(),
    "duplicate_email": lambda e: e.check_duplicate_email(),
    "customer_missing_in_master": lambda e: e.check_customer_missing_in_master(),
    "orphan_transaction": lambda e: e.check_orphan_transaction(),
}
