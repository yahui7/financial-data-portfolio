"""
数据库连接与初始化
"""
import sqlite3
import os

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "financial_data.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = get_connection()
    cursor = conn.cursor()

    # 客户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100),
            id_type VARCHAR(20) DEFAULT '身份证',
            id_number VARCHAR(50),
            id_expiry_date DATE,
            nationality VARCHAR(50) DEFAULT '中国',
            birth_date DATE,
            occupation VARCHAR(100),
            risk_level VARCHAR(20) DEFAULT '低',
            phone VARCHAR(30),
            email VARCHAR(100),
            address VARCHAR(200),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 账户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id VARCHAR(50) UNIQUE NOT NULL,
            customer_id VARCHAR(50),
            product_id VARCHAR(50),
            account_type VARCHAR(50),
            status VARCHAR(20) DEFAULT '正常',
            balance DECIMAL(18, 2) DEFAULT 0,
            currency VARCHAR(10) DEFAULT 'CNY',
            open_date DATE,
            close_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 交易表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trans_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id VARCHAR(50) UNIQUE NOT NULL,
            account_id VARCHAR(50),
            customer_id VARCHAR(50),
            transaction_type VARCHAR(50),
            amount DECIMAL(18, 2),
            currency VARCHAR(10) DEFAULT 'CNY',
            counterparty_info VARCHAR(200),
            transaction_date DATETIME,
            channel VARCHAR(50),
            purpose VARCHAR(200),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 产品表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id VARCHAR(50) UNIQUE NOT NULL,
            product_name VARCHAR(100),
            product_type VARCHAR(50),
            risk_level VARCHAR(20),
            issuer VARCHAR(100),
            status VARCHAR(20) DEFAULT '存续',
            launch_date DATE,
            maturity_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 数据质量问题追踪表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quality_issue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id VARCHAR(50) UNIQUE NOT NULL,
            rule_id VARCHAR(50),
            dimension VARCHAR(20),
            table_name VARCHAR(50),
            field_name VARCHAR(50),
            description TEXT,
            severity VARCHAR(10),
            record_count INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT '待派发',
            assignee VARCHAR(50),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME
        )
    """)

    conn.commit()
    conn.close()
    print(f"[OK] 数据库已初始化: {DB_PATH}")
