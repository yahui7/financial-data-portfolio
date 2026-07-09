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

    # 评估指标配置表（替代硬编码的评估项）
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessment_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_key VARCHAR(50) UNIQUE NOT NULL,
            dimension VARCHAR(20) NOT NULL,
            name VARCHAR(100) NOT NULL,
            description TEXT,
            category VARCHAR(30) DEFAULT 'data_driven',
            data_source TEXT,
            default_risk VARCHAR(10),
            threshold_high DECIMAL(5,2),
            threshold_mid DECIMAL(5,2),
            score_high INTEGER DEFAULT 85,
            score_mid INTEGER DEFAULT 50,
            score_low INTEGER DEFAULT 15,
            weight DECIMAL(3,2) DEFAULT 0.20,
            sort_order INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            preset_id VARCHAR(50) DEFAULT 'preset_securities',
            severity VARCHAR(10) DEFAULT '中',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 评估历史记录表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assessment_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assess_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            preset_id VARCHAR(50),
            overall_score DECIMAL(5,1),
            risk_level VARCHAR(10),
            customer_score DECIMAL(5,1),
            product_score DECIMAL(5,1),
            channel_score DECIMAL(5,1),
            geography_score DECIMAL(5,1),
            customer_count INTEGER,
            account_count INTEGER,
            trans_count INTEGER,
            product_count INTEGER,
            dimensions_json TEXT,
            recommendations_json TEXT,
            items_detail_json TEXT
        )
    """)

    # 报告历史表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS report_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200),
            report_no VARCHAR(50),
            author VARCHAR(50),
            date VARCHAR(20),
            template_id VARCHAR(50),
            sections_json TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 预置评估模板（INSERT OR IGNORE 避免重复写入）
    _seed_assessment_templates(cursor)

    conn.commit()
    conn.close()
    print(f"[OK] 数据库已初始化: {DB_PATH}")


def _seed_assessment_templates(cursor):
    """预置三套行业评估模板：银行 / 基金 / 保险"""
    templates = []

    # ═══════════════════════════════════════════════
    # 通用：三套模板共享的基础结构
    # 差异体现在 threshold / weight / severity 和行业特有指标
    # ═══════════════════════════════════════════════

    # ── 客户风险维度（6项）─────────────────────────
    customer_items = [
        {
            "item_key": "cust_high_risk_occupation",
            "name": "高风险职业客户",
            "description": "统计高风险职业（个体工商户、自由职业者、企业高管）客户占比",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM customer WHERE occupation IN ('个体工商户','自由职业者','企业高管')",
            "threshold_high": 0.30, "threshold_mid": 0.10,
            "weight": 0.25, "sort_order": 1,
        },
        {
            "item_key": "cust_risk_level_dist",
            "name": "客户风险等级分布",
            "description": "统计高/中风险等级客户占比",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM customer WHERE risk_level IN ('高','中')",
            "threshold_high": 0.20, "threshold_mid": 0.05,
            "weight": 0.20, "sort_order": 2,
        },
        {
            "item_key": "cust_foreign_id",
            "name": "非居民客户（护照开户）",
            "description": "统计使用护照开户的非居民客户数量",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM customer WHERE id_type = '护照'",
            "threshold_high": 0.10, "threshold_mid": 0.01,
            "weight": 0.10, "sort_order": 3,
        },
        {
            "item_key": "cust_info_completeness",
            "name": "客户九要素信息完整性",
            "description": "统计关键身份信息缺失的客户比例",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM customer WHERE id_number IS NULL OR id_number = '' OR phone IS NULL OR phone = '' OR email IS NULL OR email = ''",
            "threshold_high": 0.10, "threshold_mid": 0.01,
            "weight": 0.15, "sort_order": 4,
        },
        {
            "item_key": "cust_ubo",
            "name": "受益所有人穿透识别",
            "description": "核查受益所有人是否穿透至最终自然人，是否存在复杂股权结构",
            "category": "framework",
            "data_source": None,
            "default_risk": "中",
            "weight": 0.15, "sort_order": 5,
        },
        {
            "item_key": "cust_txn_concentration",
            "name": "大额交易集中度",
            "description": "前5名客户交易金额占总交易金额的比例",
            "category": "data_driven",
            "data_source": "func:top5_concentration",
            "threshold_high": 0.50, "threshold_mid": 0.30,
            "weight": 0.15, "sort_order": 6,
        },
    ]

    # ── 产品/业务风险维度（5项）─────────────────────
    product_items = [
        {
            "item_key": "prod_high_risk",
            "name": "高风险产品占比",
            "description": "统计私募股票多头、量化对冲、专户权益等高风险产品占比",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM product WHERE product_type IN ('私募-股票多头','私募-量化对冲','专户-权益')",
            "threshold_high": 0.20, "threshold_mid": 0.05,
            "weight": 0.25, "sort_order": 1,
        },
        {
            "item_key": "prod_type_dist",
            "name": "产品类型多样性",
            "description": "产品类型越多样，风险复杂度越高",
            "category": "data_driven",
            "data_source": "SELECT COUNT(DISTINCT product_type) AS cnt FROM product",
            "threshold_high": 8, "threshold_mid": 5,
            "weight": 0.15, "sort_order": 2,
        },
        {
            "item_key": "prod_new_launch",
            "name": "新产品上线洗钱风险评估",
            "description": "核查新产品上线前是否完成洗钱风险评估并留痕",
            "category": "framework",
            "data_source": None,
            "default_risk": "中",
            "weight": 0.20, "sort_order": 3,
        },
        {
            "item_key": "prod_avg_accounts",
            "name": "人均持账户数",
            "description": "人均多账户可能被用于分层交易规避监测",
            "category": "data_driven",
            "data_source": "func:avg_accounts_per_customer",
            "threshold_high": 3.0, "threshold_mid": 2.0,
            "weight": 0.15, "sort_order": 4,
        },
        {
            "item_key": "prod_new_ratio",
            "name": "新产品占比",
            "description": "统计上线不足6个月的新产品数量占比，新产品风险认知不充分",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM product WHERE launch_date > date('now', '-6 months')",
            "threshold_high": 0.30, "threshold_mid": 0.15,
            "weight": 0.25, "sort_order": 5,
        },
    ]

    # ── 渠道风险维度（4项）─────────────────────────
    channel_items = [
        {
            "item_key": "chan_non_face",
            "name": "非面对面业务渠道占比",
            "description": "网银、手机银行、代销、ATM等非面对面渠道交易占比",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM trans_record WHERE channel IN ('手机银行','网银','代销','ATM')",
            "threshold_high": 0.70, "threshold_mid": 0.40,
            "weight": 0.30, "sort_order": 1,
        },
        {
            "item_key": "chan_dist",
            "name": "渠道分布多样性",
            "description": "多渠道并存需确保各渠道风控措施一致",
            "category": "data_driven",
            "data_source": "SELECT COUNT(DISTINCT channel) AS cnt FROM trans_record",
            "threshold_high": 6, "threshold_mid": 3,
            "weight": 0.20, "sort_order": 2,
        },
        {
            "item_key": "chan_daixiao",
            "name": "代销渠道风险",
            "description": "代销渠道客户识别依赖第三方，信息不对称风险高",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM trans_record WHERE channel = '代销'",
            "threshold_high": 0.15, "threshold_mid": 0.05,
            "weight": 0.25, "sort_order": 3,
        },
        {
            "item_key": "chan_amount_cross",
            "name": "渠道×金额交叉风险",
            "description": "非面对面渠道中大额交易（>100万）的占比",
            "category": "data_driven",
            "data_source": "func:channel_amount_cross",
            "threshold_high": 0.15, "threshold_mid": 0.05,
            "weight": 0.25, "sort_order": 4,
        },
    ]

    # ── 地域风险维度（5项）─────────────────────────
    geography_items = [
        {
            "item_key": "geo_high_risk_country",
            "name": "高风险/FATF名单国家关联客户",
            "description": "统计国籍为FATF高风险国家/地区的客户数量",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM customer WHERE nationality IN ('伊朗','朝鲜','缅甸','叙利亚','也门','阿富汗','伊拉克','刚果','南苏丹','苏丹','索马里','利比亚','马里','巴哈马','巴巴多斯','保加利亚','布基纳法索','喀麦隆','克罗地亚','直布罗陀','海地','牙买加','莫桑比克','尼日利亚','菲律宾','塞内加尔','坦桑尼亚','土耳其','乌干达','阿联酋','越南')",
            "threshold_high": 0.05, "threshold_mid": 0.01,
            "weight": 0.25, "sort_order": 1,
        },
        {
            "item_key": "geo_cross_border",
            "name": "跨境交易占比",
            "description": "统计非人民币交易占比，关注资金来源与去向",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM trans_record WHERE currency != 'CNY'",
            "threshold_high": 0.10, "threshold_mid": 0.03,
            "weight": 0.25, "sort_order": 2,
        },
        {
            "item_key": "geo_province_dist",
            "name": "客户地域分布广度",
            "description": "统计客户覆盖的省级行政区数量，地域越分散风险越分散",
            "category": "data_driven",
            "data_source": "func:province_diversity",
            "threshold_high": 3, "threshold_mid": 5,
            "weight": 0.15, "sort_order": 3,
        },
        {
            "item_key": "geo_fatf",
            "name": "FATF声明与制裁名单更新",
            "description": "是否建立制裁名单定期更新与回溯筛查机制",
            "category": "framework",
            "data_source": None,
            "default_risk": "中",
            "weight": 0.15, "sort_order": 4,
        },
        {
            "item_key": "geo_cross_region_txn",
            "name": "异地交易占比",
            "description": "统计客户所在地与交易发生地不一致的交易比例",
            "category": "data_driven",
            "data_source": "func:cross_region_ratio",
            "threshold_high": 0.20, "threshold_mid": 0.10,
            "weight": 0.20, "sort_order": 5,
        },
    ]

    # ── 组装三套模板 ──────────────────────────────
    dim_map = {
        "cust": "customer", "prod": "product",
        "chan": "channel", "geo": "geography",
    }
    dimension_labels = {
        "customer": "客户风险", "product": "产品/业务风险",
        "channel": "渠道风险", "geography": "地域风险",
    }

    # 基金模板（默认）- 强调私募产品、代销渠道
    for item in customer_items + product_items + channel_items + geography_items:
        dim = dim_map.get(item["item_key"].split("_")[0], "customer")
        templates.append({
            "item_key": f"preset_securities_{item['item_key']}",
            "dimension": dim,
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "data_source": item["data_source"],
            "default_risk": item.get("default_risk"),
            "threshold_high": item.get("threshold_high"),
            "threshold_mid": item.get("threshold_mid"),
            "weight": item["weight"],
            "sort_order": item["sort_order"],
            "preset_id": "preset_securities",
            "severity": "中",
        })

    # 银行模板 - 增加对公客户、柜面渠道、现金交易的关注
    bank_overrides = {
        "cust_high_risk_occupation": {"threshold_high": 0.25, "name": "高风险职业/行业客户", "description": "含个体工商户、自由职业者、企业高管、外贸行业等"},
        "prod_high_risk": {"threshold_high": 0.15, "threshold_mid": 0.05, "data_source": "SELECT COUNT(*) AS cnt FROM product WHERE product_type IN ('私募-股票多头','私募-量化对冲','结构性存款','跨境理财通')"},
        "chan_non_face": {"threshold_high": 0.60, "name": "非面对面渠道占比（含ATM）", "description": "网银、手机银行、ATM等非柜面渠道交易占比"},
        "chan_daixiao": {"severity": "低", "weight": 0.15, "description": "银行代销渠道风险相对可控"},
        "geo_cross_border": {"threshold_high": 0.08, "threshold_mid": 0.02, "name": "跨境交易与汇款占比"},
    }
    # 银行特有指标
    bank_extra = [
        {
            "item_key": "cust_corporate", "dimension": "customer",
            "name": "对公客户穿透识别",
            "description": "对公客户的受益所有人识别与股权穿透完成率",
            "category": "framework", "default_risk": "中",
            "weight": 0.15, "sort_order": 7, "preset_id": "preset_bank",
        },
        {
            "item_key": "chan_counter", "dimension": "channel",
            "name": "柜面大额现金交易",
            "description": "柜面渠道中大额现金交易（>20万）的占比",
            "category": "data_driven",
            "data_source": "SELECT COUNT(*) AS cnt FROM trans_record WHERE channel = '柜面' AND amount > 200000",
            "threshold_high": 0.05, "threshold_mid": 0.02,
            "weight": 0.20, "sort_order": 5, "preset_id": "preset_bank",
        },
    ]

    for item in customer_items + product_items + channel_items + geography_items:
        dim = dim_map.get(item["item_key"].split("_")[0], "customer")
        ov = bank_overrides.get(item["item_key"], {})
        templates.append({
            "item_key": f"preset_bank_{item['item_key']}",
            "dimension": dim,
            "name": ov.get("name", item["name"]),
            "description": ov.get("description", item["description"]),
            "category": item["category"],
            "data_source": ov.get("data_source", item["data_source"]),
            "default_risk": item.get("default_risk"),
            "threshold_high": ov.get("threshold_high", item.get("threshold_high")),
            "threshold_mid": ov.get("threshold_mid", item.get("threshold_mid")),
            "weight": ov.get("weight", item["weight"]),
            "sort_order": item["sort_order"],
            "preset_id": "preset_bank",
            "severity": ov.get("severity", "中"),
        })
    for item in bank_extra:
        templates.append({
            "item_key": f"preset_bank_{item['item_key']}",
            "dimension": item["dimension"],
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "data_source": item.get("data_source"),
            "default_risk": item.get("default_risk"),
            "threshold_high": item.get("threshold_high"),
            "threshold_mid": item.get("threshold_mid"),
            "weight": item["weight"],
            "sort_order": item["sort_order"],
            "preset_id": "preset_bank",
            "severity": "中",
        })

    # 保险模板 - 强调投保人/受益人、退保交易
    insurance_overrides = {
        "cust_high_risk_occupation": {"threshold_high": 0.20, "name": "高风险职业投保人", "description": "含个体工商户、企业高管、自由职业者等投保人"},
        "prod_high_risk": {"threshold_high": 0.25, "threshold_mid": 0.10, "name": "高风险保险产品占比", "data_source": "SELECT COUNT(*) AS cnt FROM product WHERE product_type IN ('投连险','万能险','分红险','跨境保险')"},
        "chan_non_face": {"threshold_high": 0.80, "threshold_mid": 0.50, "description": "网销、银保通、代理等非面对面渠道占比"},
        "chan_daixiao": {"weight": 0.30, "threshold_high": 0.25, "threshold_mid": 0.10, "name": "代理/经纪渠道风险", "description": "保险代理和经纪渠道客户识别依赖第三方"},
        "prod_new_launch": {"default_risk": "高", "description": "新产品上线需评估洗钱风险，特别是投连险、万能险等"},
    }
    insurance_extra = [
        {
            "item_key": "cust_beneficiary", "dimension": "customer",
            "name": "投保人与受益人关系核查",
            "description": "核查投保人与受益人是否一致，非直系亲属关系需加强尽调",
            "category": "framework", "default_risk": "中",
            "weight": 0.15, "sort_order": 7, "preset_id": "preset_insurance",
        },
        {
            "item_key": "prod_surrender", "dimension": "product",
            "name": "退保交易风险",
            "description": "统计短期内退保交易占比，关注洗钱风险",
            "category": "data_driven",
            "data_source": "func:surrender_ratio",
            "threshold_high": 0.10, "threshold_mid": 0.05,
            "weight": 0.20, "sort_order": 6, "preset_id": "preset_insurance",
        },
    ]

    for item in customer_items + product_items + channel_items + geography_items:
        dim = dim_map.get(item["item_key"].split("_")[0], "customer")
        ov = insurance_overrides.get(item["item_key"], {})
        templates.append({
            "item_key": f"preset_insurance_{item['item_key']}",
            "dimension": dim,
            "name": ov.get("name", item["name"]),
            "description": ov.get("description", item["description"]),
            "category": item["category"],
            "data_source": ov.get("data_source", item["data_source"]),
            "default_risk": ov.get("default_risk", item.get("default_risk")),
            "threshold_high": ov.get("threshold_high", item.get("threshold_high")),
            "threshold_mid": ov.get("threshold_mid", item.get("threshold_mid")),
            "weight": ov.get("weight", item["weight"]),
            "sort_order": item["sort_order"],
            "preset_id": "preset_insurance",
            "severity": "中",
        })
    for item in insurance_extra:
        templates.append({
            "item_key": f"preset_insurance_{item['item_key']}",
            "dimension": item["dimension"],
            "name": item["name"],
            "description": item["description"],
            "category": item["category"],
            "data_source": item.get("data_source"),
            "default_risk": item.get("default_risk"),
            "threshold_high": item.get("threshold_high"),
            "threshold_mid": item.get("threshold_mid"),
            "weight": item["weight"],
            "sort_order": item["sort_order"],
            "preset_id": "preset_insurance",
            "severity": "中",
        })

    # ── 批量写入 ──────────────────────────────────
    for t in templates:
        cursor.execute("""
            INSERT OR IGNORE INTO assessment_item
                (item_key, dimension, name, description, category,
                 data_source, default_risk, threshold_high, threshold_mid,
                 weight, sort_order, preset_id, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            t["item_key"], t["dimension"], t["name"], t["description"],
            t["category"], t["data_source"], t["default_risk"],
            t["threshold_high"], t["threshold_mid"],
            t["weight"], t["sort_order"], t["preset_id"], t["severity"],
        ))

    total = cursor.rowcount if hasattr(cursor, 'rowcount') else len(templates)
    print(f"[OK] 评估模板已预置: 基金({20}项) / 银行({20 + len(bank_extra)}项) / 保险({20 + len(insurance_extra)}项)")
