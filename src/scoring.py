"""Data quality score calculation."""

from dataclasses import dataclass


@dataclass
class DQScoreResult:
    """Result of a DQ score calculation."""

    check_name: str
    table_name: str
    total_records: int
    failed_records: int
    dq_score: float

    @property
    def pass_rate(self) -> float:
        """Return pass rate as a percentage."""
        if self.total_records == 0:
            return 100.0
        passed = self.total_records - self.failed_records
        return (passed / self.total_records) * 100


class DQScorer:
    """Calculate data quality scores for individual checks and aggregates."""

    @staticmethod
    def calculate_score(total_records: int, failed_records: int) -> float:
        """
        Compute DQ score: 100 - ((failed_records / total_records) * 100).

        Returns 100 when there are no records to evaluate.
        """
        if total_records <= 0:
            return 100.0
        failure_rate = (failed_records / total_records) * 100
        score = 100.0 - failure_rate
        return round(max(0.0, min(100.0, score)), 2)

    @staticmethod
    def aggregate_score(scores: list[float]) -> float:
        """Compute the average DQ score across multiple checks."""
        if not scores:
            return 100.0
        return round(sum(scores) / len(scores), 2)

    @classmethod
    def build_result(
        cls,
        check_name: str,
        table_name: str,
        total_records: int,
        failed_records: int,
    ) -> DQScoreResult:
        """Build a scored result for a single check."""
        dq_score = cls.calculate_score(total_records, failed_records)
        return DQScoreResult(
            check_name=check_name,
            table_name=table_name,
            total_records=total_records,
            failed_records=failed_records,
            dq_score=dq_score,
        )
