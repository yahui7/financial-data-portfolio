"""
数据生成器引擎
- 生成模拟金融机构数据（客户、账户、交易、产品）
- 可配置的数据质量问题注入
"""
import random
import uuid
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict

from faker import Faker

fake = Faker("zh_CN")


# ── 数据质量问题定义 ────────────────────────────

QUALITY_ISSUE_TYPES = {
    "completeness": {
        "name": "完整性",
        "description": "关键字段缺失（如 id_number 为空）",
        "fields": {
            "customer": ["id_number", "phone", "email", "id_expiry_date"],
            "account": ["close_date", "product_id"],
            "trans_record": ["counterparty_info", "purpose"],
            "product": ["maturity_date", "issuer"],
        },
    },
    "accuracy": {
        "name": "准确性",
        "description": "数据类型错误、金额为负、日期在未来",
        "fields": {
            "customer": ["birth_date", "id_expiry_date"],
            "account": ["balance"],
            "trans_record": ["amount", "transaction_date"],
            "product": ["launch_date", "maturity_date"],
        },
    },
    "consistency": {
        "name": "一致性",
        "description": "同一客户在不同表里信息不一致",
        "fields": {
            "customer": ["name", "phone", "address"],
        },
    },
    "logical": {
        "name": "逻辑性",
        "description": "年龄与身份证号不匹配、金额逻辑错误",
        "fields": {
            "customer": ["birth_date"],
            "account": ["balance", "close_date"],
            "trans_record": ["amount"],
        },
    },
    "duplicate": {
        "name": "重复",
        "description": "记录完全或部分重复",
        "fields": {},
    },
}

SEVERITY_MAP = {"completeness": "高", "accuracy": "高", "consistency": "中", "logical": "中", "duplicate": "中"}


# ── 数据生成器 ──────────────────────────────────

class DataGenerator:
    """金融数据生成器"""

    def __init__(
        self,
        customer_count: int = 200,
        account_count: int = 300,
        transaction_count: int = 800,
        product_count: int = 30,
        issues_config: Optional[dict] = None,
    ):
        self.customer_count = customer_count
        self.account_count = account_count
        self.transaction_count = transaction_count
        self.product_count = product_count
        # 默认：每种问题 5%
        self.issues_config = issues_config or {
            "completeness": 0.05,
            "accuracy": 0.05,
            "consistency": 0.05,
            "logical": 0.03,
            "duplicate": 0.03,
        }

        # 内存中暂存生成的数据
        self.customers: list[dict] = []
        self.accounts: list[dict] = []
        self.transactions: list[dict] = []
        self.products: list[dict] = []
        self.issues_summary: list[dict] = []

    # ── 第1步：生成干净数据 ──────────────────────

    def _generate_products(self):
        """生成产品数据"""
        product_types = [
            ("公募-股票型", "中"),
            ("公募-债券型", "低"),
            ("公募-混合型", "中"),
            ("公募-货币型", "低"),
            ("私募-股票多头", "高"),
            ("私募-量化对冲", "高"),
            ("专户-固收", "中"),
            ("专户-权益", "高"),
            ("资管计划-集合", "中"),
            ("资管计划-定向", "中"),
        ]
        for i in range(self.product_count):
            ptype, risk = random.choice(product_types)
            name_prefix = random.choice(["安信", "稳盈", "进取", "恒泰", "优选", "价值", "成长", "稳健", "丰盈", "致远"])
            launch = fake.date_between(start_date="-5y", end_date="today")
            maturity = launch + timedelta(days=random.choice([365, 730, 1095, 1825]))
            self.products.append({
                "product_id": f"PRD{str(i+1).zfill(4)}",
                "product_name": f"{name_prefix}{ptype.split('-')[-1]}{random.randint(1,99)}号",
                "product_type": ptype,
                "risk_level": risk,
                "issuer": random.choice(["华中证券", "江汉基金", "楚天资管", "长江信托", "武汉银行理财子公司"]),
                "status": random.choice(["存续"] * 8 + ["终止"]),
                "launch_date": str(launch),
                "maturity_date": str(maturity),
            })

    def _generate_customers(self):
        """生成客户数据"""
        occupations = ["企业员工", "个体工商户", "自由职业者", "企业高管", "退休人员",
                       "教师", "医生", "律师", "会计师", "工程师", "公务员", "学生"]
        id_types = ["身份证"] * 95 + ["护照"] * 4 + ["营业执照"] * 1

        for i in range(self.customer_count):
            birth = fake.date_of_birth(minimum_age=18, maximum_age=80)
            id_num = self._fake_id_number(birth)
            self.customers.append({
                "customer_id": f"CUST{str(i+1).zfill(5)}",
                "name": fake.name(),
                "id_type": random.choice(id_types),
                "id_number": id_num,
                "id_expiry_date": str(fake.date_between(start_date="today", end_date="+10y")),
                "nationality": random.choice(["中国"] * 90 + ["美国", "英国", "新加坡", "香港"] * 10),
                "birth_date": str(birth),
                "occupation": random.choice(occupations),
                "risk_level": random.choice(["低"] * 50 + ["中"] * 30 + ["高"] * 20),
                "phone": fake.phone_number(),
                "email": fake.email(),
                "address": fake.address().replace("\n", " "),
            })

    def _generate_accounts(self):
        """生成账户数据"""
        statuses = ["正常"] * 85 + ["冻结"] * 10 + ["销户"] * 5
        types = ["活期"] * 30 + ["定期"] * 20 + ["理财"] * 25 + ["基金"] * 15 + ["信托"] * 10
        product_ids = [p["product_id"] for p in self.products] if self.products else ["PRD0001"]

        for i in range(self.account_count):
            customer = random.choice(self.customers)
            open_d = fake.date_between(start_date="-3y", end_date="today")
            close_d = str(open_d + timedelta(days=random.randint(365, 1095))) if random.random() < 0.05 else None
            self.accounts.append({
                "account_id": f"ACCT{str(i+1).zfill(6)}",
                "customer_id": customer["customer_id"],
                "product_id": random.choice(product_ids),
                "account_type": random.choice(types),
                "status": random.choice(statuses),
                "balance": round(random.uniform(0, 5000000), 2),
                "currency": random.choice(["CNY"] * 90 + ["USD"] * 7 + ["HKD"] * 3),
                "open_date": str(open_d),
                "close_date": close_d,
            })

    def _generate_transactions(self):
        """生成交易数据"""
        txn_types = ["申购"] * 30 + ["赎回"] * 25 + ["分红"] * 10 + ["转账"] * 20 + ["缴费"] * 10 + ["退款"] * 5
        channels = ["柜面"] * 20 + ["手机银行"] * 40 + ["网银"] * 25 + ["代销"] * 10 + ["ATM"] * 5

        for i in range(self.transaction_count):
            account = random.choice(self.accounts)
            txn_d = fake.date_time_between(start_date="-1y", end_date="now")
            self.transactions.append({
                "transaction_id": f"TXN{str(i+1).zfill(8)}",
                "account_id": account["account_id"],
                "customer_id": account["customer_id"],
                "transaction_type": random.choice(txn_types),
                "amount": round(abs(random.gauss(50000, 100000)), 2),
                "currency": random.choice(["CNY"] * 92 + ["USD"] * 6 + ["HKD"] * 2),
                "counterparty_info": f"对手方-{fake.company()}" if random.random() > 0.3 else None,
                "transaction_date": str(txn_d),
                "channel": random.choice(channels),
                "purpose": random.choice(["日常消费", "投资理财", "工资发放", "贷款偿还", "费用缴纳", "投资收益", None]),
            })

    # ── 第2步：注入质量问题 ──────────────────────

    def _inject_completeness(self, ratio: float):
        """注入完整性问题：随机清空关键字段"""
        count = 0
        for table_name, records in [("customer", self.customers), ("account", self.accounts),
                                     ("trans_record", self.transactions), ("product", self.products)]:
            fields = QUALITY_ISSUE_TYPES["completeness"]["fields"][table_name]
            for record in records:
                for field in fields:
                    if field in record and random.random() < ratio * 0.5:
                        record[field] = None
                        count += 1
        if count:
            self.issues_summary.append({
                "issue_type": "completeness", "name": "完整性",
                "description": f"共 {count} 处关键字段缺失",
                "severity": "高", "affected_records": count,
            })

    def _inject_accuracy(self, ratio: float):
        """注入准确性问题：数据类型错误、金额为负、日期异常"""
        count = 0
        # 金额为负 (account balance, transaction amount)
        for record in self.accounts:
            if random.random() < ratio:
                record["balance"] = -abs(record["balance"])
                count += 1
        for record in self.transactions:
            if random.random() < ratio:
                record["amount"] = -abs(record["amount"])
                count += 1
        # 未来日期
        future = str(datetime.now() + timedelta(days=random.randint(30, 365)))
        for record in self.customers:
            if random.random() < ratio * 0.3:
                record["birth_date"] = future
                count += 1
        if count:
            self.issues_summary.append({
                "issue_type": "accuracy", "name": "准确性",
                "description": f"共 {count} 处数据不准确",
                "severity": "高", "affected_records": count,
            })

    def _inject_consistency(self, ratio: float):
        """注入一致性问题：同一 customer_id 在不同表间的 name 不一致"""
        count = 0
        customer_names = {c["customer_id"]: c["name"] for c in self.customers}
        for record in self.accounts:
            if random.random() < ratio:
                cid = record["customer_id"]
                if cid in customer_names and customer_names[cid]:
                    # 修改客户表中的name为不同值
                    orig = next(c for c in self.customers if c["customer_id"] == cid)
                    orig["name"] = fake.name()
                    count += 1
        if count:
            self.issues_summary.append({
                "issue_type": "consistency", "name": "一致性",
                "description": f"共 {count} 个客户的姓名在不同表间不一致",
                "severity": "中", "affected_records": count,
            })

    def _inject_logical(self, ratio: float):
        """注入逻辑性问题：年龄与证件不匹配、销户日期早于开户日期"""
        count = 0
        for record in self.customers:
            if random.random() < ratio:
                # 设置出生日期为未来，产生年龄逻辑错误
                record["birth_date"] = str(datetime.now() + timedelta(days=random.randint(365, 3650)))
                count += 1
        for record in self.accounts:
            if record["close_date"] and random.random() < ratio:
                # 销户日期设置为早于开户日期
                record["close_date"] = str(
                    datetime.strptime(record["open_date"], "%Y-%m-%d") - timedelta(days=random.randint(30, 365))
                )
                record["balance"] = round(random.uniform(1, 100000), 2)
                count += 1
        if count:
            self.issues_summary.append({
                "issue_type": "logical", "name": "逻辑性",
                "description": f"共 {count} 处逻辑错误",
                "severity": "中", "affected_records": count,
            })

    def _inject_duplicate(self, ratio: float):
        """注入重复数据：随机复制记录"""
        count = 0
        for records, id_field in [
            (self.customers, "customer_id"),
            (self.accounts, "account_id"),
            (self.transactions, "transaction_id"),
        ]:
            if records and random.random() < ratio:
                dup_count = max(1, int(len(records) * ratio))
                for _ in range(dup_count):
                    orig = random.choice(records)
                    dup = dict(orig)
                    dup[id_field] = orig[id_field]  # 相同的 ID
                    records.append(dup)
                    count += 1
        if count:
            self.issues_summary.append({
                "issue_type": "duplicate", "name": "重复",
                "description": f"共 {count} 条重复记录",
                "severity": "中", "affected_records": count,
            })

    # ── 主流程 ─────────────────────────────────

    def generate(self) -> dict:
        """执行完整的数据生成流程"""
        self.issues_summary = []

        # 1. 生成干净数据
        self._generate_products()
        self._generate_customers()
        self._generate_accounts()
        self._generate_transactions()

        # 2. 按配置注入质量问题
        if self.issues_config.get("completeness", 0) > 0:
            self._inject_completeness(self.issues_config["completeness"])
        if self.issues_config.get("accuracy", 0) > 0:
            self._inject_accuracy(self.issues_config["accuracy"])
        if self.issues_config.get("consistency", 0) > 0:
            self._inject_consistency(self.issues_config["consistency"])
        if self.issues_config.get("logical", 0) > 0:
            self._inject_logical(self.issues_config["logical"])
        if self.issues_config.get("duplicate", 0) > 0:
            self._inject_duplicate(self.issues_config["duplicate"])

        return {
            "summary": {
                "customers": len(self.customers),
                "accounts": len(self.accounts),
                "transactions": len(self.transactions),
                "products": len(self.products),
                "issues": self.issues_summary,
            },
            "data": {
                "customers": self.customers,
                "accounts": self.accounts,
                "transactions": self.transactions,
                "products": self.products,
            },
        }

    def save_to_db(self):
        """将生成的数据保存到 SQLite"""
        import sqlite3
        import os

        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "financial_data.db",
        )
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 清空旧数据
        for table in ["trans_record", "account", "customer", "product", "quality_issue"]:
            cursor.execute(f"DELETE FROM {table}")

        # 插入数据
        for p in self.products:
            cursor.execute("""
                INSERT INTO product (product_id, product_name, product_type, risk_level,
                    issuer, status, launch_date, maturity_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p["product_id"], p["product_name"], p["product_type"], p["risk_level"],
                  p["issuer"], p["status"], p["launch_date"], p["maturity_date"]))

        for c in self.customers:
            cursor.execute("""
                INSERT INTO customer (customer_id, name, id_type, id_number,
                    id_expiry_date, nationality, birth_date, occupation, risk_level,
                    phone, email, address)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (c["customer_id"], c["name"], c["id_type"], c["id_number"],
                  c["id_expiry_date"], c["nationality"], c["birth_date"],
                  c["occupation"], c["risk_level"], c["phone"], c["email"], c["address"]))

        for a in self.accounts:
            cursor.execute("""
                INSERT INTO account (account_id, customer_id, product_id, account_type,
                    status, balance, currency, open_date, close_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (a["account_id"], a["customer_id"], a["product_id"], a["account_type"],
                  a["status"], a["balance"], a["currency"], a["open_date"], a["close_date"]))

        for t in self.transactions:
            cursor.execute("""
                INSERT INTO trans_record (transaction_id, account_id, customer_id,
                    transaction_type, amount, currency, counterparty_info,
                    transaction_date, channel, purpose)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (t["transaction_id"], t["account_id"], t["customer_id"],
                  t["transaction_type"], t["amount"], t["currency"],
                  t["counterparty_info"], t["transaction_date"], t["channel"], t["purpose"]))

        # 保存问题概要
        for issue in self.issues_summary:
            cursor.execute("""
                INSERT INTO quality_issue (issue_id, rule_id, dimension, table_name,
                    field_name, description, severity, record_count, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '待派发')
            """, (str(uuid.uuid4())[:8],
                  issue["issue_type"],
                  issue["name"],
                  "-",
                  "-",
                  issue["description"],
                  issue["severity"],
                  issue["affected_records"]))

        conn.commit()
        conn.close()

    @staticmethod
    def _fake_id_number(birth_date) -> str:
        """生成类身份证号（形如 42010619900315xxxx）"""
        area = random.choice(["420106", "420102", "420103", "110101", "310101",
                              "440103", "510104", "320102", "330102", "350102"])
        birth_str = birth_date.strftime("%Y%m%d")
        suffix = str(random.randint(1000, 9999))
        return area + birth_str + suffix
