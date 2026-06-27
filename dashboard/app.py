"""Streamlit dashboard for Enterprise DQ Monitoring Engine."""

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from anomaly_detection import VolumeAnomalyDetector
from audit import AuditLogger
from business_rules import BUSINESS_RULE_REGISTRY, BusinessRuleEngine
from db import get_engine
from dq_checks import CHECK_REGISTRY, DQCheckEngine

st.set_page_config(
    page_title="Enterprise DQ Monitoring",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

ALL_CHECKS = {
    **{k: ("Standard DQ", k) for k in CHECK_REGISTRY},
    **{k: ("Business Rule", k) for k in BUSINESS_RULE_REGISTRY},
    "volume_anomaly": ("Volume Anomaly", "volume_anomaly"),
}


@st.cache_data(ttl=60)
def load_customers() -> pd.DataFrame:
    """Load customer data from database."""
    with get_engine().connect() as conn:
        return pd.read_sql(text("SELECT * FROM customers"), conn)


@st.cache_data(ttl=60)
def load_transactions() -> pd.DataFrame:
    """Load transaction data from database."""
    with get_engine().connect() as conn:
        return pd.read_sql(text("SELECT * FROM transactions"), conn)


@st.cache_data(ttl=30)
def load_audit_log() -> pd.DataFrame:
    """Load audit log from database."""
    return AuditLogger.fetch_audit_log()


@st.cache_data(ttl=30)
def load_runs_summary() -> pd.DataFrame:
    """Load aggregated run summary."""
    return AuditLogger.fetch_runs_summary()


def run_selected_check(check_name: str) -> pd.DataFrame:
    """Execute a DQ check dynamically and return failed records."""
    customers = load_customers()
    transactions = load_transactions()

    if check_name in CHECK_REGISTRY:
        engine = DQCheckEngine(customers, transactions)
        outcome = CHECK_REGISTRY[check_name](engine)
        return outcome.failed_df

    if check_name in BUSINESS_RULE_REGISTRY:
        engine = BusinessRuleEngine(customers, transactions)
        outcome = BUSINESS_RULE_REGISTRY[check_name](engine)
        return outcome.failed_df

    if check_name == "volume_anomaly":
        detector = VolumeAnomalyDetector(transactions)
        outcome = detector.run_check()
        return outcome.failed_df

    return pd.DataFrame()


def render_metric_cards(summary: pd.DataFrame, audit: pd.DataFrame) -> None:
    """Render top-level KPI cards."""
    customers = load_customers()
    transactions = load_transactions()
    total_records = len(customers) + len(transactions)

    if summary.empty:
        avg_score = 0.0
        checks_executed = 0
        critical_issues = 0
    else:
        latest = summary.iloc[0]
        avg_score = float(latest["avg_dq_score"])
        checks_executed = int(latest["checks_executed"])
        latest_run = latest["run_id"]
        run_audit = audit[audit["run_id"] == latest_run]
        critical_issues = int((run_audit["severity"] == "P1").sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Records", f"{total_records:,}")
    col2.metric("DQ Score", f"{avg_score:.2f}")
    col3.metric("Checks Executed", checks_executed)
    col4.metric("Critical Issues (P1)", critical_issues)


def page_dashboard() -> None:
    """Main dashboard with KPIs and charts."""
    st.title("📊 Data Quality Dashboard")
    st.markdown("Real-time overview of enterprise data quality metrics.")

    audit = load_audit_log()
    summary = load_runs_summary()

    render_metric_cards(summary, audit)

    if audit.empty:
        st.warning("No audit data found. Run `python src/main.py` to execute DQ checks.")
        return

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("DQ Score Trend")
        summary_sorted = summary.sort_values("run_timestamp").copy()
        summary_sorted["date"] = pd.to_datetime(summary_sorted["run_timestamp"]).dt.date
        trend = summary_sorted.groupby("date", as_index=False)["avg_dq_score"].mean()
        fig_trend = px.line(
            trend, x="date", y="avg_dq_score",
            markers=True, title="Average DQ Score Over Time",
        )
        fig_trend.update_layout(yaxis_range=[0, 100])
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_right:
        st.subheader("Severity Distribution")
        latest_run = summary.iloc[0]["run_id"]
        latest_audit = audit[audit["run_id"] == latest_run]
        severity_counts = latest_audit["severity"].value_counts().reset_index()
        severity_counts.columns = ["severity", "count"]
        fig_pie = px.pie(
            severity_counts, names="severity", values="count",
            color="severity",
            color_discrete_map={"P1": "#e74c3c", "P2": "#f39c12", "P3": "#27ae60"},
            title="Latest Run - Severity Breakdown",
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    col_a, col_b = st.columns(2)

    with col_a:
        st.subheader("Failures by Check")
        latest_audit_sorted = latest_audit.sort_values("failed_records", ascending=True)
        fig_bar = px.bar(
            latest_audit_sorted,
            x="failed_records", y="check_name", orientation="h",
            title="Failed Records per Check (Latest Run)",
            color="severity",
            color_discrete_map={"P1": "#e74c3c", "P2": "#f39c12", "P3": "#27ae60"},
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_b:
        st.subheader("Top Violations")
        top_v = latest_audit.nlargest(10, "failed_records")[
            ["check_name", "failed_records", "dq_score", "severity"]
        ]
        st.dataframe(top_v, use_container_width=True, hide_index=True)


def page_audit_history() -> None:
    """Audit log explorer with search and filters."""
    st.title("📋 Audit History")
    audit = load_audit_log()

    if audit.empty:
        st.info("No audit records available.")
        return

    col1, col2, col3 = st.columns(3)
    search = col1.text_input("Search", placeholder="Check name, table, remarks...")
    severity_filter = col2.multiselect("Severity", ["P1", "P2", "P3"], default=["P1", "P2", "P3"])
    sort_by = col3.selectbox("Sort By", ["run_timestamp", "failed_records", "dq_score", "check_name"])

    filtered = audit[audit["severity"].isin(severity_filter)]

    if search:
        mask = filtered.apply(
            lambda row: search.lower() in " ".join(row.astype(str)).lower(), axis=1
        )
        filtered = filtered[mask]

    ascending = sort_by != "run_timestamp"
    filtered = filtered.sort_values(sort_by, ascending=ascending)

    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(filtered)} of {len(audit)} records")


def page_failed_records() -> None:
    """Display failed records for a selected DQ rule."""
    st.title("🔍 Failed Records Explorer")
    check_options = sorted(ALL_CHECKS.keys())
    selected = st.selectbox("Select DQ Rule", check_options)

    category, _ = ALL_CHECKS[selected]
    st.caption(f"Category: {category}")

    failed_df = run_selected_check(selected)

    if failed_df.empty:
        st.success(f"No failed records for check: **{selected}**")
    else:
        st.error(f"Found **{len(failed_df)}** failed record(s)")
        st.dataframe(failed_df, use_container_width=True, hide_index=True)

        csv_data = failed_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download Failed Records (CSV)",
            data=csv_data,
            file_name=f"failed_{selected}.csv",
            mime="text/csv",
        )


def page_trend_analysis() -> None:
    """Historical DQ score and failure trends."""
    st.title("📈 Trend Analysis")
    audit = load_audit_log()
    summary = load_runs_summary()

    if audit.empty:
        st.info("No historical data available.")
        return

    tab1, tab2 = st.tabs(["Score Trends", "Failure Trends"])

    with tab1:
        run_scores = summary.sort_values("run_timestamp")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=run_scores["run_timestamp"], y=run_scores["avg_dq_score"],
            mode="lines+markers", name="Avg DQ Score",
        ))
        fig.update_layout(title="Historical DQ Score", yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        check_trends = audit.groupby(["run_timestamp", "check_name"])["failed_records"].sum().reset_index()
        top_checks = (
            audit.groupby("check_name")["failed_records"].sum()
            .nlargest(5).index.tolist()
        )
        check_trends = check_trends[check_trends["check_name"].isin(top_checks)]
        fig2 = px.line(
            check_trends, x="run_timestamp", y="failed_records",
            color="check_name", markers=True,
            title="Failure Trends - Top 5 Checks",
        )
        st.plotly_chart(fig2, use_container_width=True)


def page_data_explorer() -> None:
    """Browse customers and transactions with filters."""
    st.title("🗂️ Data Explorer")
    tab1, tab2 = st.tabs(["Customers", "Transactions"])

    with tab1:
        customers = load_customers()
        search = st.text_input("Search customers", key="cust_search")
        status_filter = st.multiselect(
            "Status", sorted(customers["status"].dropna().unique()), key="cust_status"
        )
        filtered = customers.copy()
        if status_filter:
            filtered = filtered[filtered["status"].isin(status_filter)]
        if search:
            mask = filtered.apply(
                lambda row: search.lower() in " ".join(row.astype(str)).lower(), axis=1
            )
            filtered = filtered[mask]
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.caption(f"{len(filtered)} customer records")

    with tab2:
        transactions = load_transactions()
        search_txn = st.text_input("Search transactions", key="txn_search")
        status_txn = st.multiselect(
            "Status", sorted(transactions["status"].dropna().unique()), key="txn_status"
        )
        filtered_txn = transactions.copy()
        if status_txn:
            filtered_txn = filtered_txn[filtered_txn["status"].isin(status_txn)]
        if search_txn:
            mask = filtered_txn.apply(
                lambda row: search_txn.lower() in " ".join(row.astype(str)).lower(), axis=1
            )
            filtered_txn = filtered_txn[mask]
        st.dataframe(filtered_txn, use_container_width=True, hide_index=True)
        st.caption(f"{len(filtered_txn)} transaction records")


def main() -> None:
    """Render the Streamlit application."""
    st.sidebar.title("🏢 DQ Monitor")
    st.sidebar.markdown("Enterprise Data Quality Monitoring Engine")

    pages = {
        "Dashboard": page_dashboard,
        "Audit History": page_audit_history,
        "Failed Records": page_failed_records,
        "Trend Analysis": page_trend_analysis,
        "Data Explorer": page_data_explorer,
    }

    selection = st.sidebar.radio("Navigation", list(pages.keys()))
    st.sidebar.divider()
    st.sidebar.markdown("**Quick Actions**")
    st.sidebar.code("python src/main.py", language="bash")
    st.sidebar.caption("Re-run DQ checks to refresh dashboard data.")

    pages[selection]()


if __name__ == "__main__":
    main()
