"""Business rule validation checks."""

from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

from config import HIGH_AMOUNT_THRESHOLD, PENDING_DAYS_THRESHOLD
from scoring import DQScorer, DQScoreResult


@dataclass
class BusinessRuleOutcome:
    """Outcome of a business rule check."""

    result: DQScoreResult
    failed_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    remarks: str = ""


class BusinessRuleEngine:
    """Execute business rule checks against transaction and customer data."""

    def __init__(self, customers: pd.DataFrame, transactions: pd.DataFrame):
        self.customers = customers.copy()
        self.transactions = transactions.copy()
        self._inactive_ids = set(
            self.customers[
                self.customers["status"].str.lower() == "inactive"
            ]["customer_id"].astype(str)
        )

    def run_all(self) -> list[BusinessRuleOutcome]:
        """Run all business rule checks."""
        checks = [
            self.check_high_amount,
            self.check_refund_positive_amount,
            self.check_pending_over_30_days,
            self.check_inactive_customer_transaction,
            self.check_cancelled_with_positive_amount,
        ]
        return [check() for check in checks]

    def _build_outcome(
        self,
        check_name: str,
        table_name: str,
        total_records: int,
        failed_df: pd.DataFrame,
        remarks: str = "",
    ) -> BusinessRuleOutcome:
        """Helper to construct a BusinessRuleOutcome."""
        result = DQScorer.build_result(check_name, table_name, total_records, len(failed_df))
        return BusinessRuleOutcome(result=result, failed_df=failed_df, remarks=remarks)

    def check_high_amount(self) -> BusinessRuleOutcome:
        """Flag transactions with amount exceeding threshold."""
        mask = self.transactions["amount"].notna() & (
            self.transactions["amount"] > HIGH_AMOUNT_THRESHOLD
        )
        failed = self.transactions[mask]
        return self._build_outcome(
            "amount_exceeds_50000", "transactions", len(self.transactions), failed,
            f"Transactions with amount > {HIGH_AMOUNT_THRESHOLD:,.0f}",
        )

    def check_refund_positive_amount(self) -> BusinessRuleOutcome:
        """Flag refund transactions with positive amounts (should be negative or zero)."""
        mask = (
            self.transactions["status"].str.lower() == "refund"
        ) & (self.transactions["amount"].notna()) & (self.transactions["amount"] > 0)
        failed = self.transactions[mask]
        return self._build_outcome(
            "refund_with_positive_amount", "transactions", len(self.transactions), failed,
            "Refund transactions should not have positive amounts",
        )

    def check_pending_over_30_days(self) -> BusinessRuleOutcome:
        """Flag pending transactions older than threshold days."""
        today = pd.Timestamp.today().normalize()
        dates = pd.to_datetime(self.transactions["transaction_date"], errors="coerce")
        days_old = (today - dates).dt.days
        mask = (
            self.transactions["status"].str.lower() == "pending"
        ) & dates.notna() & (days_old > PENDING_DAYS_THRESHOLD)
        failed = self.transactions[mask]
        return self._build_outcome(
            "pending_over_30_days", "transactions", len(self.transactions), failed,
            f"Pending transactions older than {PENDING_DAYS_THRESHOLD} days",
        )

    def check_inactive_customer_transaction(self) -> BusinessRuleOutcome:
        """Flag transactions linked to inactive customers."""
        mask = self.transactions["customer_id"].astype(str).isin(self._inactive_ids)
        failed = self.transactions[mask]
        return self._build_outcome(
            "inactive_customer_transaction", "transactions", len(self.transactions), failed,
            "Transactions associated with inactive customers",
        )

    def check_cancelled_with_positive_amount(self) -> BusinessRuleOutcome:
        """Flag cancelled transactions that still have positive amounts."""
        mask = (
            self.transactions["status"].str.lower() == "cancelled"
        ) & (self.transactions["amount"].notna()) & (self.transactions["amount"] > 0)
        failed = self.transactions[mask]
        return self._build_outcome(
            "cancelled_with_positive_amount", "transactions", len(self.transactions), failed,
            "Cancelled transactions should have zero or null amount",
        )


BUSINESS_RULE_REGISTRY: dict[str, Callable[["BusinessRuleEngine"], BusinessRuleOutcome]] = {
    "amount_exceeds_50000": lambda e: e.check_high_amount(),
    "refund_with_positive_amount": lambda e: e.check_refund_positive_amount(),
    "pending_over_30_days": lambda e: e.check_pending_over_30_days(),
    "inactive_customer_transaction": lambda e: e.check_inactive_customer_transaction(),
    "cancelled_with_positive_amount": lambda e: e.check_cancelled_with_positive_amount(),
}
