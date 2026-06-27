-- Enterprise DQ Monitoring Engine - Database Schema
-- Compatible with PostgreSQL and SQLite (via SQLAlchemy create_all)

DROP TABLE IF EXISTS dq_audit_log;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     VARCHAR(32) NOT NULL,
    customer_name   VARCHAR(128) NOT NULL,
    email           VARCHAR(256),
    phone           VARCHAR(32),
    city            VARCHAR(64),
    join_date       DATE,
    status          VARCHAR(32)
);

CREATE TABLE transactions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id   VARCHAR(32) NOT NULL,
    customer_id      VARCHAR(32),
    merchant         VARCHAR(128),
    amount           DECIMAL(14, 2),
    transaction_date DATE,
    payment_mode     VARCHAR(32),
    status           VARCHAR(32)
);

CREATE TABLE dq_audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          VARCHAR(64) NOT NULL,
    run_timestamp   TIMESTAMP NOT NULL,
    check_name      VARCHAR(128) NOT NULL,
    table_name      VARCHAR(64) NOT NULL,
    failed_records  INTEGER NOT NULL DEFAULT 0,
    severity        VARCHAR(8) NOT NULL,
    dq_score        REAL NOT NULL,
    remarks         TEXT
);

CREATE INDEX idx_audit_run_id ON dq_audit_log(run_id);
CREATE INDEX idx_audit_timestamp ON dq_audit_log(run_timestamp);
CREATE INDEX idx_customers_customer_id ON customers(customer_id);
CREATE INDEX idx_transactions_transaction_id ON transactions(transaction_id);
CREATE INDEX idx_transactions_customer ON transactions(customer_id);
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
