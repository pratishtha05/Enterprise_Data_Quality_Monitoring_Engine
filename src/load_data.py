"""Load CSV data into the database with duplicate-safe inserts."""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import Column, Date, Integer, Numeric, String, inspect, text
from sqlalchemy.orm import Session

# Ensure src is on path when run as script
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config import DATA_DIR, SQL_DIR, VALID_CUSTOMER_STATUSES, VALID_PAYMENT_MODES, VALID_TRANSACTION_STATUSES
from db import Base, execute_sql_file, get_active_database_url, get_engine, get_session


class Customer(Base):
    """Customer master table."""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String(32), nullable=False, index=True)
    customer_name = Column(String(128), nullable=False)
    email = Column(String(256))
    phone = Column(String(32))
    city = Column(String(64))
    join_date = Column(Date)
    status = Column(String(32))


class Transaction(Base):
    """Transaction fact table."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String(32), nullable=False, index=True)
    customer_id = Column(String(32))
    merchant = Column(String(128))
    amount = Column(Numeric(14, 2))
    transaction_date = Column(Date)
    payment_mode = Column(String(32))
    status = Column(String(32))


CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai",
    "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow",
]
MERCHANTS = [
    "Amazon", "Flipkart", "Swiggy", "Zomato", "Uber",
    "Ola", "Myntra", "BigBasket", "Paytm Mall", "Reliance Digital",
]
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Krishna",
    "Ishaan", "Shaurya", "Ananya", "Diya", "Aadhya", "Sara", "Myra", "Priya",
    "Neha", "Kavya", "Riya", "Pooja",
]
LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Gupta", "Reddy", "Iyer", "Nair",
    "Mehta", "Joshi", "Desai", "Rao", "Verma", "Chopra", "Malhotra", "Kapoor",
]


def _random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, max(delta, 1)))


def generate_customers(count: int = 1050) -> pd.DataFrame:
    """Generate realistic customer records with intentional DQ violations."""
    random.seed(42)
    records = []
    base_date = date.today() - timedelta(days=365 * 3)

    for i in range(1, count + 1):
        cid = f"CUST{i:05d}"
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        email = f"{fname.lower()}.{lname.lower()}{i}@email.com"
        phone = f"{random.randint(6000000000, 9999999999):010d}"[-10:]
        status = random.choices(
            list(VALID_CUSTOMER_STATUSES),
            weights=[85, 10, 5],
        )[0]
        records.append({
            "customer_id": cid,
            "customer_name": f"{fname} {lname}",
            "email": email,
            "phone": phone,
            "city": random.choice(CITIES),
            "join_date": _random_date(base_date, date.today()).isoformat(),
            "status": status,
        })

    # Intentional bad records
    bad_indices = {
        10: {"email": None},
        25: {"phone": None},
        40: {"email": "not-an-email"},
        55: {"phone": "12345"},
        70: {"status": "unknown_status"},
        100: {"customer_id": "CUST00100", "email": "duplicate@test.com"},
        101: {"customer_id": "CUST00100", "customer_name": "Duplicate Customer", "email": "duplicate@test.com"},
        150: {"email": ""},
        200: {"phone": "987654321"},
        250: {"status": "inactive"},
        300: {"email": "bad@domain"},
    }
    for idx, overrides in bad_indices.items():
        if idx < len(records):
            records[idx].update(overrides)

    # Additional inactive customers for business rule checks
    for idx in range(260, 280):
        records[idx]["status"] = "inactive"

    return pd.DataFrame(records)


def generate_transactions(count: int = 5200, customer_ids: list[str] | None = None) -> pd.DataFrame:
    """Generate realistic transaction records with intentional DQ violations."""
    random.seed(99)
    records = []
    if customer_ids is None:
        customer_ids = [f"CUST{i:05d}" for i in range(1, 1051)]

    base_date = date.today() - timedelta(days=400)
    today = date.today()

    for i in range(1, count + 1):
        tid = f"TXN{i:06d}"
        cid = random.choice(customer_ids)
        amount = round(random.uniform(10, 25000), 2)
        txn_date = _random_date(base_date, today)
        status = random.choices(
            list(VALID_TRANSACTION_STATUSES),
            weights=[70, 10, 8, 5, 7],
        )[0]
        records.append({
            "transaction_id": tid,
            "customer_id": cid,
            "merchant": random.choice(MERCHANTS),
            "amount": amount,
            "transaction_date": txn_date.isoformat(),
            "payment_mode": random.choice(list(VALID_PAYMENT_MODES)),
            "status": status,
        })

    # Spread transactions across days including today for volume anomaly
    for idx in range(5000, min(5200, len(records))):
        records[idx]["transaction_date"] = today.isoformat()

    # Intentional bad records
    bad_overrides = {
        15: {"amount": None},
        30: {"transaction_date": None},
        45: {"customer_id": None},
        60: {"amount": -150.50},
        75: {"transaction_date": (today + timedelta(days=30)).isoformat()},
        90: {"status": "invalid_txn_status"},
        105: {"transaction_id": "TXN000105", "amount": 75000.00},
        106: {"transaction_id": "TXN000105", "merchant": "Duplicate Txn"},
        120: {"customer_id": "CUST99999"},
        135: {"status": "refund", "amount": 500.00},
        140: {"status": "pending", "transaction_date": (today - timedelta(days=45)).isoformat()},
        155: {"customer_id": "CUST00250", "amount": 1200.00},
        170: {"status": "cancelled", "amount": 999.99},
        185: {"amount": 55000.00},
        200: {"customer_id": "ORPHAN001"},
    }
    for idx, overrides in bad_overrides.items():
        if idx < len(records):
            records[idx].update(overrides)

    return pd.DataFrame(records)


def ensure_csv_files() -> tuple[Path, Path]:
    """Create sample CSV files if they do not exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    customers_path = DATA_DIR / "customers.csv"
    transactions_path = DATA_DIR / "transactions.csv"

    if not customers_path.exists():
        customers_df = generate_customers()
        customers_df.to_csv(customers_path, index=False)
        print(f"Generated {len(customers_df)} customer records -> {customers_path}")

    if not transactions_path.exists():
        customers_df = pd.read_csv(customers_path)
        customer_ids = customers_df["customer_id"].tolist()
        transactions_df = generate_transactions(customer_ids=customer_ids)
        transactions_df.to_csv(transactions_path, index=False)
        print(f"Generated {len(transactions_df)} transaction records -> {transactions_path}")

    return customers_path, transactions_path


def initialize_schema() -> None:
    """Create database tables."""
    engine = get_engine()
    inspector = inspect(engine)

    if "sqlite" in get_active_database_url():
        Base.metadata.create_all(engine, tables=[Customer.__table__, Transaction.__table__])
    else:
        schema_path = SQL_DIR / "schema.sql"
        if schema_path.exists():
            try:
                execute_sql_file(str(schema_path))
            except Exception:
                Base.metadata.create_all(engine, tables=[Customer.__table__, Transaction.__table__])
        else:
            Base.metadata.create_all(engine, tables=[Customer.__table__, Transaction.__table__])

    # Ensure tables exist
    Base.metadata.create_all(engine, tables=[Customer.__table__, Transaction.__table__])


def _clean_for_db(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dates and convert NaN/NaT to None for database insertion."""
    df = df.copy()
    for col in ("join_date", "transaction_date"):
        if col in df.columns:
            parsed = pd.to_datetime(df[col], errors="coerce")
            df[col] = parsed.apply(lambda x: x.date() if pd.notna(x) else None)
    for col in df.columns:
        if col not in ("join_date", "transaction_date"):
            df[col] = df[col].apply(lambda x: None if pd.isna(x) else x)
    return df


def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize date columns."""
    return _clean_for_db(df)


def insert_dataframe(session: Session, model, df: pd.DataFrame, business_key: str) -> int:
    """Insert all rows when table is empty; skip on re-run to avoid duplicates."""
    existing_count = session.query(model).count()
    if existing_count >= len(df):
        return 0

    inserted = 0
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        record = model(**{k: (None if pd.isna(v) else v) for k, v in row_dict.items()})
        session.add(record)
        inserted += 1
    return inserted


def load_csv_data() -> dict[str, int]:
    """Load customer and transaction CSV files into the database."""
    customers_path, transactions_path = ensure_csv_files()
    initialize_schema()

    customers_df = _parse_dates(pd.read_csv(customers_path, dtype={"phone": str}))
    transactions_df = _parse_dates(pd.read_csv(transactions_path))

    with get_session() as session:
        cust_inserted = insert_dataframe(session, Customer, customers_df, "customer_id")
        txn_inserted = insert_dataframe(session, Transaction, transactions_df, "transaction_id")

    return {
        "customers_inserted": cust_inserted,
        "transactions_inserted": txn_inserted,
        "customers_total": len(customers_df),
        "transactions_total": len(transactions_df),
    }


def main() -> None:
    """Entry point for data loading."""
    print(f"Database URL: {get_active_database_url()}")
    stats = load_csv_data()
    print("Data load complete:")
    print(f"  Customers inserted: {stats['customers_inserted']} / {stats['customers_total']}")
    print(f"  Transactions inserted: {stats['transactions_inserted']} / {stats['transactions_total']}")


if __name__ == "__main__":
    main()
