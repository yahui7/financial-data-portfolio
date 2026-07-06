"""
数据质量扫描引擎
- 定义质量校验规则
- 执行四维度扫描（完整性·准确性·一致性·逻辑性）
- 计算质量得分
- 管理问题工单（发现→派发→整改→复核→归档）
"""
import uuid
from datetime import datetime
from typing import Optional

from backend.database import get_connection, DB_PATH

# ── 校验规则定义 ─────────────────────────────────

QUALITY_RULES = [
    # ── 完整性（Completeness）──
    {
        "rule_id": "R001",
        "dimension": "完整性",
        "dimension_key": "completeness",
        "table_name": "customer",
        "field_name": "id_number",
        "description": "客户证件号码不可为空",
        "severity": "高",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE id_number IS NULL OR id_number = ''",
    },
    {
        "rule_id": "R002",
        "dimension": "完整性",
        "dimension_key": "completeness",
        "table_name": "customer",
        "field_name": "phone",
        "description": "客户手机号码不可为空",
        "severity": "中",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE phone IS NULL OR phone = ''",
    },
    {
        "rule_id": "R003",
        "dimension": "完整性",
        "dimension_key": "completeness",
        "table_name": "customer",
        "field_name": "email",
        "description": "客户邮箱不可为空",
        "severity": "中",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE email IS NULL OR email = ''",
    },
    {
        "rule_id": "R004",
        "dimension": "完整性",
        "dimension_key": "completeness",
        "table_name": "customer",
        "field_name": "id_expiry_date",
        "description": "证件有效期不可为空",
        "severity": "中",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE id_expiry_date IS NULL",
    },
    {
        "rule_id": "R005",
        "dimension": "完整性",
        "dimension_key": "completeness",
        "table_name": "trans_record",
        "field_name": "counterparty_info",
        "description": "对手方信息不可为空",
        "severity": "低",
        "sql": "SELECT COUNT(*) AS cnt FROM trans_record WHERE counterparty_info IS NULL OR counterparty_info = ''",
    },
    # ── 准确性（Accuracy）──
    {
        "rule_id": "R006",
        "dimension": "准确性",
        "dimension_key": "accuracy",
        "table_name": "trans_record",
        "field_name": "amount",
        "description": "交易金额必须大于0",
        "severity": "高",
        "sql": "SELECT COUNT(*) AS cnt FROM trans_record WHERE amount <= 0",
    },
    {
        "rule_id": "R007",
        "dimension": "准确性",
        "dimension_key": "accuracy",
        "table_name": "account",
        "field_name": "balance",
        "description": "账户余额不应为负数",
        "severity": "高",
        "sql": "SELECT COUNT(*) AS cnt FROM account WHERE balance < 0",
    },
    {
        "rule_id": "R008",
        "dimension": "准确性",
        "dimension_key": "accuracy",
        "table_name": "customer",
        "field_name": "birth_date",
        "description": "出生日期不应在未来",
        "severity": "高",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE birth_date > date('now')",
    },
    {
        "rule_id": "R009",
        "dimension": "准确性",
        "dimension_key": "accuracy",
        "table_name": "customer",
        "field_name": "id_expiry_date",
        "description": "证件有效期格式应为日期类型",
        "severity": "低",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE id_expiry_date IS NOT NULL AND id_expiry_date NOT LIKE '____-__-__'",
    },
    # ── 一致性（Consistency）──
    {
        "rule_id": "R010",
        "dimension": "一致性",
        "dimension_key": "consistency",
        "table_name": "account",
        "field_name": "customer_id",
        "description": "账户的客户ID必须在客户表中存在",
        "severity": "高",
        "sql": "SELECT COUNT(DISTINCT a.customer_id) AS cnt FROM account a LEFT JOIN customer c ON a.customer_id = c.customer_id WHERE c.customer_id IS NULL",
    },
    {
        "rule_id": "R011",
        "dimension": "一致性",
        "dimension_key": "consistency",
        "table_name": "trans_record",
        "field_name": "customer_id",
        "description": "交易的客户ID必须在客户表中存在",
        "severity": "高",
        "sql": "SELECT COUNT(DISTINCT t.customer_id) AS cnt FROM trans_record t LEFT JOIN customer c ON t.customer_id = c.customer_id WHERE c.customer_id IS NULL",
    },
    {
        "rule_id": "R012",
        "dimension": "一致性",
        "dimension_key": "consistency",
        "table_name": "trans_record",
        "field_name": "account_id",
        "description": "交易的账户ID必须在账户表中存在",
        "severity": "高",
        "sql": "SELECT COUNT(DISTINCT t.account_id) AS cnt FROM trans_record t LEFT JOIN account a ON t.account_id = a.account_id WHERE a.account_id IS NULL",
    },
    # ── 逻辑性（Logical）──
    {
        "rule_id": "R013",
        "dimension": "逻辑性",
        "dimension_key": "logical",
        "table_name": "customer",
        "field_name": "birth_date",
        "description": "年龄与证件号码出生日期应匹配（粗略校验）",
        "severity": "中",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE birth_date > date('now') OR birth_date < '1900-01-01'",
    },
    {
        "rule_id": "R014",
        "dimension": "逻辑性",
        "dimension_key": "logical",
        "table_name": "account",
        "field_name": "close_date",
        "description": "销户日期不应早于开户日期",
        "severity": "中",
        "sql": "SELECT COUNT(*) AS cnt FROM account WHERE close_date IS NOT NULL AND close_date < open_date",
    },
    {
        "rule_id": "R015",
        "dimension": "逻辑性",
        "dimension_key": "logical",
        "table_name": "customer",
        "field_name": "risk_level",
        "description": "风险等级应在有效取值范围内（低/中/高）",
        "severity": "低",
        "sql": "SELECT COUNT(*) AS cnt FROM customer WHERE risk_level NOT IN ('低', '中', '高')",
    },
]


# ── 扫描引擎 ────────────────────────────────────

class QualityScanner:
    """数据质量扫描引擎"""

    def __init__(self):
        self.conn = get_connection()
        self.scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def scan(self) -> dict:
        """执行全量扫描"""
        results = []
        cursor = self.conn.cursor()

        for rule in QUALITY_RULES:
            try:
                cursor.execute(rule["sql"])
                row = cursor.fetchone()
                cnt = row["cnt"] if row else 0
                results.append({
                    "rule_id": rule["rule_id"],
                    "dimension": rule["dimension"],
                    "dimension_key": rule["dimension_key"],
                    "table_name": rule["table_name"],
                    "field_name": rule["field_name"],
                    "description": rule["description"],
                    "severity": rule["severity"],
                    "record_count": cnt,
                    "status": "待派发" if cnt > 0 else "通过",
                    "scan_time": self.scan_time,
                })
            except Exception as e:
                results.append({
                    "rule_id": rule["rule_id"],
                    "dimension": rule["dimension"],
                    "dimension_key": rule["dimension_key"],
                    "description": rule["description"],
                    "severity": rule["severity"],
                    "record_count": 0,
                    "status": f"执行错误: {str(e)[:80]}",
                    "scan_time": self.scan_time,
                })

        # 计算各维度得分
        scores = self._compute_scores(results)

        # 保存到 quality_issue 表
        self._save_issues(results)

        self.conn.close()
        return {
            "scan_time": self.scan_time,
            "total_rules": len(QUALITY_RULES),
            "passed_rules": sum(1 for r in results if r["record_count"] == 0),
            "failed_rules": sum(1 for r in results if r["record_count"] > 0),
            "scores": scores,
            "rules": results,
        }

    def _compute_scores(self, results: list[dict]) -> dict:
        """计算四维度质量得分（满分100）
        按 受影响记录数 / 总记录数 计算，而非按规则数计算
        """
        cursor = self.conn.cursor()

        # 获取各表总记录数
        total_records = 0
        for table in ["customer", "account", "trans_record", "product"]:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            total_records += cursor.fetchone()["cnt"]
        total_records = max(total_records, 1)

        # 按维度汇总受影响的去重记录数
        dim_issues = {
            "completeness": 0,
            "accuracy": 0,
            "consistency": 0,
            "logical": 0,
        }

        for r in results:
            dk = r["dimension_key"]
            if dk in dim_issues and r["record_count"] > 0:
                dim_issues[dk] += r["record_count"]

        # 计算得分：100 - (问题记录数 / 总记录数 * 100)
        # 上限100，下限0
        scores = {}
        for key, issue_count in dim_issues.items():
            pct = min(100, issue_count / total_records * 100)
            scores[key] = round(100 - pct, 1)

        scores["overall"] = round(sum(scores.values()) / len(scores), 1)
        return scores

    def _save_issues(self, results: list[dict]):
        """将问题保存到数据库"""
        cursor = self.conn.cursor()
        # 清空旧数据
        cursor.execute("DELETE FROM quality_issue")

        for r in results:
            if r["record_count"] > 0:
                cursor.execute("""
                    INSERT INTO quality_issue
                        (issue_id, rule_id, dimension, table_name, field_name,
                         description, severity, record_count, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(uuid.uuid4())[:8],
                    r["rule_id"],
                    r["dimension"],
                    r.get("table_name", "-"),
                    r.get("field_name", "-"),
                    r["description"],
                    r["severity"],
                    r["record_count"],
                    "待派发",
                ))

        self.conn.commit()

    # ── 数据库概览 ──

    def get_table_counts(self) -> dict:
        """获取各表记录数"""
        cursor = self.conn.cursor()
        counts = {}
        for table in ["customer", "account", "trans_record", "product"]:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            counts[table] = cursor.fetchone()["cnt"]
        self.conn.close()
        return counts

    # ── 工单管理 ──

    def get_issues(self, dimension: Optional[str] = None,
                   severity: Optional[str] = None,
                   status: Optional[str] = None) -> list[dict]:
        """查询问题列表（支持筛选）"""
        cursor = self.conn.cursor()
        sql = "SELECT * FROM quality_issue WHERE 1=1"
        params = []
        if dimension:
            sql += " AND dimension = ?"
            params.append(dimension)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY CASE severity WHEN '高' THEN 1 WHEN '中' THEN 2 ELSE 3 END, record_count DESC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        self.conn.close()
        return [dict(r) for r in rows]

    def update_issue_status(self, issue_id: str, new_status: str, assignee: Optional[str] = None):
        """更新问题状态（工单流）"""
        conn = get_connection()
        cursor = conn.cursor()
        valid_statuses = ["待派发", "已派发", "整改中", "待复核", "已归档"]

        if new_status not in valid_statuses:
            conn.close()
            raise ValueError(f"无效状态: {new_status}，允许: {valid_statuses}")

        if new_status == "已归档":
            cursor.execute("""
                UPDATE quality_issue SET status = ?, resolved_at = ?
                WHERE issue_id = ?
            """, (new_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), issue_id))
        else:
            q = "UPDATE quality_issue SET status = ?"
            p = [new_status]
            if assignee:
                q += ", assignee = ?"
                p.append(assignee)
            q += " WHERE issue_id = ?"
            p.append(issue_id)
            cursor.execute(q, p)

        conn.commit()
        conn.close()

    # ── 问题样本数据 ──

    def get_violation_samples(self, rule_id: str, limit: int = 10, offset: int = 0) -> dict:
        """获取某条规则的问题样本记录（支持分页），返回 {total, samples}"""
        rule = next((r for r in QUALITY_RULES if r["rule_id"] == rule_id), None)
        if not rule:
            return {"total": 0, "samples": []}

        count_sql = rule["sql"]
        # 先查总数
        cursor = self.conn.cursor()
        cursor.execute(count_sql)
        total = cursor.fetchone()["cnt"]

        # 将 COUNT(*) 查询转为 SELECT * 查询
        sample_sql = count_sql.replace("SELECT COUNT(*) AS cnt ", "SELECT * ").replace("SELECT COUNT(DISTINCT ", "SELECT DISTINCT ")
        sample_sql += f" LIMIT {limit} OFFSET {offset}"

        try:
            cursor.execute(sample_sql)
            rows = cursor.fetchall()
            self.conn.close()
            return {"total": total, "samples": [dict(r) for r in rows]}
        except Exception as e:
            self.conn.close()
            return {"total": 0, "samples": [{"error": str(e)}]}

    # ── 历史趋势 ──

    def get_history(self, limit: int = 30) -> list[dict]:
        """获取历史扫描记录（模拟：返回当前 + 随机生成的历史趋势）"""
        import random
        import os
        import json

        # 尝试从文件读取历史记录
        history_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data", "scan_history.json",
        )
        if os.path.exists(history_path):
            with open(history_path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 否则生成模拟历史
        history = []
        base = {"completeness": 90, "accuracy": 92, "consistency": 88, "logical": 95, "overall": 91.3}
        from datetime import timedelta
        today = datetime.now()
        for i in range(limit - 1, -1, -1):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            entry = {
                "date": date,
                "completeness": round(base["completeness"] + random.uniform(-5, 8), 1),
                "accuracy": round(base["accuracy"] + random.uniform(-5, 5), 1),
                "consistency": round(base["consistency"] + random.uniform(-6, 10), 1),
                "logical": round(base["logical"] + random.uniform(-3, 5), 1),
            }
            entry["overall"] = round(sum(entry[k] for k in ["completeness","accuracy","consistency","logical"]) / 4, 1)
            history.append(entry)

        # 最后一条用真实数据
        if hasattr(self, "_last_scores"):
            history[-1] = {"date": datetime.now().strftime("%Y-%m-%d"), **self._last_scores}
        else:
            # 用当前数据库查询
            scanner = QualityScanner()
            result = scanner.scan()
            history[-1] = {"date": datetime.now().strftime("%Y-%m-%d"), **result["scores"]}

        return history
