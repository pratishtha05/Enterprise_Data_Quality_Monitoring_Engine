"""Statistical volume anomaly detection for transaction data."""

from dataclasses import dataclass, field

import pandas as pd

from config import VOLUME_ANOMALY_LOWER, VOLUME_ANOMALY_UPPER
from scoring import DQScorer, DQScoreResult


@dataclass
class AnomalyOutcome:
    """Outcome of a volume anomaly check."""

    result: DQScoreResult
    failed_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    remarks: str = ""


class VolumeAnomalyDetector:
    """Detect daily transaction volume anomalies using statistical thresholds."""

    def __init__(self, transactions: pd.DataFrame):
        self.transactions = transactions.copy()

    def run_check(self) -> AnomalyOutcome:
        """
        Flag if today's volume is below 70% or above 130% of average daily count.

        Uses historical daily counts excluding today for the baseline average.
        """
        df = self.transactions.copy()
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        df = df[df["transaction_date"].notna()]

        if df.empty:
            result = DQScorer.build_result("volume_anomaly", "transactions", 0, 0)
            return AnomalyOutcome(
                result=result,
                remarks="No dated transactions available for volume analysis",
            )

        daily_counts = df.groupby(df["transaction_date"].dt.date).size()
        today = pd.Timestamp.today().date()
        today_count = int(daily_counts.get(today, 0))

        historical = daily_counts[daily_counts.index != today]
        if historical.empty:
            avg_daily = float(today_count) if today_count > 0 else 1.0
        else:
            avg_daily = float(historical.mean())

        lower_bound = avg_daily * VOLUME_ANOMALY_LOWER
        upper_bound = avg_daily * VOLUME_ANOMALY_UPPER

        is_anomaly = today_count < lower_bound or today_count > upper_bound
        failed_count = 1 if is_anomaly else 0

        anomaly_rows = pd.DataFrame([{
            "check_date": str(today),
            "today_volume": today_count,
            "avg_daily_volume": round(avg_daily, 2),
            "lower_bound": round(lower_bound, 2),
            "upper_bound": round(upper_bound, 2),
            "anomaly_detected": is_anomaly,
        }])

        if not is_anomaly:
            anomaly_rows = pd.DataFrame()

        remarks = (
            f"Today: {today_count}, Avg: {avg_daily:.1f}, "
            f"Bounds: [{lower_bound:.1f}, {upper_bound:.1f}]"
        )
        if is_anomaly:
            if today_count < lower_bound:
                remarks += " — Volume below lower threshold"
            else:
                remarks += " — Volume above upper threshold"

        result = DQScorer.build_result(
            "volume_anomaly", "transactions", 1, failed_count
        )
        return AnomalyOutcome(result=result, failed_df=anomaly_rows, remarks=remarks)
