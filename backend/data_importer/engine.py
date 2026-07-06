"""
数据导入引擎
- CSV 文件解析与校验
- 数据写入数据库
- 导入后自动执行数据质量扫描
"""
import csv
import io
from datetime import datetime
from typing import Optional

from backend.database import get_connection


# ── 各表字段定义 ────────────────────────────────

TABLE_COLUMNS = {
    "customer": [
        "customer_id", "name", "id_type", "id_number", "id_expiry_date",
        "nationality", "birth_date", "occupation", "risk_level",
        "phone", "email", "address",
    ],
    "account": [
        "account_id", "customer_id", "product_id", "account_type",
        "status", "balance", "currency", "open_date", "close_date",
    ],
    "trans_record": [
        "transaction_id", "account_id", "customer_id", "transaction_type",
        "amount", "currency", "counterparty_info", "transaction_date",
        "channel", "purpose",
    ],
    "product": [
        "product_id", "product_name", "product_type", "risk_level",
        "issuer", "status", "launch_date", "maturity_date",
    ],
}

# 必填字段
REQUIRED_FIELDS = {
    "customer": ["customer_id", "name"],
    "account": ["account_id", "customer_id"],
    "trans_record": ["transaction_id", "account_id", "customer_id", "amount"],
    "product": ["product_id", "product_name"],
}

# 有效枚举值
VALID_ENUMS = {
    "risk_level": ["低", "中", "高"],
    "id_type": ["身份证", "护照", "港澳通行证", "台胞证"],
    "status": ["正常", "冻结", "销户", "存续", "到期", "终止"],
    "currency": ["CNY", "USD", "HKD", "EUR", "JPY", "GBP"],
}

TABLE_LABELS = {
    "customer": "客户表", "account": "账户表",
    "trans_record": "交易表", "product": "产品表",
}


class DataImporter:
    """CSV 数据导入器"""

    def __init__(self):
        pass

    # ── CSV 解析 ──

    def parse_csv(self, content: str) -> list[dict]:
        """解析 CSV 内容为字典列表"""
        reader = csv.DictReader(io.StringIO(content))
        return [dict(row) for row in reader]

    # ── 校验 ──

    def validate_rows(self, rows: list[dict], table_name: str) -> dict:
        """逐行校验，返回 {valid_rows, errors}"""
        cols = TABLE_COLUMNS.get(table_name, [])
        required = REQUIRED_FIELDS.get(table_name, [])
        errors = []
        valid = []

        for i, row in enumerate(rows, start=1):
            row_errors = []

            # 检查未知列
            for key in row:
                if key not in cols:
                    row_errors.append(f"未知字段: {key}")

            # 检查必填字段
            for f in required:
                val = (row.get(f) or "").strip()
                if not val:
                    row_errors.append(f"必填字段 '{f}' 为空")

            # 检查日期格式
            for f in [c for c in cols if "date" in c.lower()]:
                val = (row.get(f) or "").strip()
                if val:
                    try:
                        datetime.strptime(val[:10], "%Y-%m-%d")
                    except ValueError:
                        row_errors.append(f"日期格式错误 '{f}={val}'，应为 YYYY-MM-DD")

            # 检查枚举值
            for f, valid_vals in VALID_ENUMS.items():
                if f in cols:
                    val = (row.get(f) or "").strip()
                    if val and val not in valid_vals:
                        row_errors.append(
                            f"无效值 '{f}={val}'，允许: {', '.join(valid_vals)}"
                        )

            # 检查金额字段
            if "amount" in cols:
                val = (row.get("amount") or "").strip()
                if val:
                    try:
                        amt = float(val)
                        if amt <= 0:
                            row_errors.append(f"交易金额必须大于0 (当前={val})")
                    except ValueError:
                        row_errors.append(f"金额格式错误: {val}")
            if "balance" in cols:
                val = (row.get("balance") or "").strip()
                if val:
                    try:
                        float(val)
                    except ValueError:
                        row_errors.append(f"余额格式错误: {val}")

            if row_errors:
                errors.append({"row": i, "data": row, "errors": row_errors})
            else:
                valid.append(row)

        return {
            "total": len(rows),
            "valid_count": len(valid),
            "error_count": len(errors),
            "valid_rows": valid,
            "errors": errors,
        }

    # ── 预览 ──

    def preview(self, content: str, table_name: str) -> dict:
        """解析 CSV，校验全部数据，返回前10行预览 + 全部校验结果"""
        rows = self.parse_csv(content)
        preview_rows = rows[:10]
        full_validation = self.validate_rows(rows, table_name)

        return {
            "table_name": table_name,
            "table_label": TABLE_LABELS.get(table_name, table_name),
            "columns": TABLE_COLUMNS.get(table_name, []),
            "total_rows": len(rows),
            "preview_rows": preview_rows,
            "validation": {
                "valid_count": full_validation["valid_count"],
                "error_count": full_validation["error_count"],
                "errors": full_validation["errors"][:20],  # 最多展示20条错误
            },
        }

    # ── 写入数据库 ──

    def import_table(self, rows: list[dict], table_name: str) -> dict:
        """将全部行批量写入数据库，返回 {count, errors}"""
        result = {"count": 0, "errors": []}
        if not rows:
            return result

        cols = TABLE_COLUMNS.get(table_name, [])
        conn = get_connection()
        cursor = conn.cursor()

        placeholders = ", ".join("?" for _ in cols)
        col_names = ", ".join(cols)

        for i, row in enumerate(rows, start=1):
            try:
                values = []
                for c in cols:
                    val = (row.get(c) or "").strip()
                    if val == "":
                        val = None
                    values.append(val)
                cursor.execute(
                    f"INSERT OR REPLACE INTO {table_name} ({col_names}) "
                    f"VALUES ({placeholders})",
                    values,
                )
                result["count"] += 1
            except Exception as e:
                result["errors"].append({
                    "row": i,
                    "data": {c: (row.get(c) or "") for c in cols},
                    "error": str(e),
                })

        # 诊断：如果输入行数 != 成功行数 且没有错误记录，说明有隐藏问题
        if result["count"] != len(rows) and not result["errors"]:
            result["errors"].append({
                "row": 0,
                "data": {},
                "error": f"未知原因：输入{len(rows)}行，仅写入{result['count']}行，无异常抛出。可能是CSV解析行数与实际数据行数不一致",
            })

        conn.commit()
        conn.close()
        return result

    # ── 清空所有数据 ──

    def clear_all(self):
        """清空所有业务表数据"""
        conn = get_connection()
        cursor = conn.cursor()
        for table in ["trans_record", "account", "customer", "product"]:
            cursor.execute(f"DELETE FROM {table}")
        conn.commit()
        conn.close()

    # ── 导入后质量检查 ──

    def run_quality_check(self) -> dict:
        """导入完成后执行数据质量扫描"""
        from backend.data_quality.engine import QualityScanner
        scanner = QualityScanner()
        result = scanner.scan()
        return {
            "scan_time": result["scan_time"],
            "total_rules": result["total_rules"],
            "passed_rules": result["passed_rules"],
            "failed_rules": result["failed_rules"],
            "scores": result["scores"],
            "rules": [
                {
                    "rule_id": r["rule_id"],
                    "dimension": r["dimension"],
                    "description": r["description"],
                    "severity": r["severity"],
                    "record_count": r["record_count"],
                    "status": r["status"],
                }
                for r in result["rules"]
            ],
        }
