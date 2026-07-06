"""
数据质量监控 API 路由
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from .engine import QualityScanner, QUALITY_RULES

router = APIRouter()

_last_scan_result: Optional[dict] = None


class IssueUpdate(BaseModel):
    """问题状态更新请求"""
    status: str
    assignee: Optional[str] = None


@router.get("/health")
async def health():
    return {"module": "data-quality", "status": "ok"}


# ── 扫描 ──

@router.get("/scan")
async def scan():
    """执行全量数据质量扫描"""
    global _last_scan_result
    scanner = QualityScanner()
    result = scanner.scan()
    _last_scan_result = result
    return {
        "status": "ok",
        "scan_time": result["scan_time"],
        "total_rules": result["total_rules"],
        "passed_rules": result["passed_rules"],
        "failed_rules": result["failed_rules"],
        "scores": result["scores"],
        "rules": result["rules"],
    }


@router.get("/scores")
async def get_scores():
    """获取最新的质量评分"""
    global _last_scan_result
    if not _last_scan_result:
        scanner = QualityScanner()
        _last_scan_result = scanner.scan()

    return {
        "status": "ok",
        "scan_time": _last_scan_result["scan_time"],
        "scores": _last_scan_result["scores"],
    }


# ── 规则 ──

@router.get("/rules")
async def get_rules():
    """获取所有校验规则"""
    return {
        "status": "ok",
        "total": len(QUALITY_RULES),
        "rules": QUALITY_RULES,
    }


# ── 问题清单 ──

@router.get("/issues")
async def get_issues(
    dimension: Optional[str] = Query(default=None, description="按维度筛选: 完整性/准确性/一致性/逻辑性"),
    severity: Optional[str] = Query(default=None, description="按严重性筛选: 高/中/低"),
    status: Optional[str] = Query(default=None, description="按状态筛选: 待派发/已派发/整改中/待复核/已归档"),
):
    """查询问题清单（支持筛选）"""
    scanner = QualityScanner()
    issues = scanner.get_issues(dimension=dimension, severity=severity, status=status)
    return {
        "status": "ok",
        "total": len(issues),
        "issues": [dict(i) for i in issues],
    }


@router.put("/issues/{issue_id}")
async def update_issue(issue_id: str, update: IssueUpdate):
    """更新问题状态（工单流转）"""
    try:
        scanner = QualityScanner()  # 单次操作没问题
        # 直接操作——直接更新
        from backend.database import get_connection
        from datetime import datetime

        conn = get_connection()
        cursor = conn.cursor()
        valid_statuses = ["待派发", "已派发", "整改中", "待复核", "已归档"]

        if update.status not in valid_statuses:
            conn.close()
            return {"status": "error", "message": f"无效状态: {update.status}"}

        if update.status == "已归档":
            cursor.execute("""
                UPDATE quality_issue SET status = ?, resolved_at = ?
                WHERE issue_id = ?
            """, (update.status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), issue_id))
        else:
            q = "UPDATE quality_issue SET status = ?"
            p = [update.status]
            if update.assignee:
                q += ", assignee = ?"
                p.append(update.assignee)
            q += " WHERE issue_id = ?"
            p.append(issue_id)
            cursor.execute(q, p)

        conn.commit()
        conn.close()
        return {"status": "ok", "message": f"问题 {issue_id} 状态已更新为: {update.status}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── 问题样本 ──

@router.get("/samples")
async def get_violation_samples(
    rule_id: str = Query(..., description="规则ID"),
    limit: int = Query(default=8, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
):
    """获取某条规则的违规数据样本（支持分页）"""
    scanner = QualityScanner()
    result = scanner.get_violation_samples(rule_id, limit, offset)
    return {"status": "ok", "rule_id": rule_id, "samples": result["samples"], "total": result["total"], "count": len(result["samples"]), "offset": offset}


# ── 历史趋势 ──

@router.get("/history")
async def get_history(limit: int = Query(default=30, ge=1, le=90)):
    """获取历史扫描趋势"""
    scanner = QualityScanner()
    result = scanner.scan()
    # 将最新扫描结果附加到历史
    history = scanner.get_history(limit)
    if history:
        history[-1] = {
            "date": result["scan_time"][:10],
            "completeness": result["scores"].get("completeness", 0),
            "accuracy": result["scores"].get("accuracy", 0),
            "consistency": result["scores"].get("consistency", 0),
            "logical": result["scores"].get("logical", 0),
            "overall": result["scores"].get("overall", 0),
        }
    return {"status": "ok", "history": history[-limit:]}


# ── 数据概览 ──

@router.get("/overview")
async def get_overview():
    """获取数据概览（各表记录数）"""
    scanner = QualityScanner()
    counts = scanner.get_table_counts()
    return {"status": "ok", "counts": counts}
