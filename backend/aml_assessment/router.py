"""
反洗钱风险自评估 API 路由（公司层面）
- 评估模板管理
- 评估指标 CRUD
- 评估执行 + 历史存档
- 评估历史 / 趋势 / 对比
"""
import json
from datetime import datetime

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

from .engine import AMLEngine
from backend.database import get_connection

router = APIRouter()


# ═══════════════════════════════════════════════
# 健康检查
# ═══════════════════════════════════════════════

@router.get("/health")
async def health():
    return {"module": "aml-assessment", "status": "ok"}


# ═══════════════════════════════════════════════
# 评估模板
# ═══════════════════════════════════════════════

@router.get("/presets")
async def list_presets():
    """列出所有可用的评估模板"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT preset_id, COUNT(*) as item_count "
        "FROM assessment_item WHERE enabled = 1 "
        "GROUP BY preset_id ORDER BY preset_id"
    )
    rows = cursor.fetchall()
    conn.close()

    preset_names = {
        "preset_securities": "基金模板",
        "preset_bank": "银行模板",
        "preset_insurance": "保险模板",
    }
    return {
        "status": "ok",
        "presets": [
            {
                "id": r["preset_id"],
                "name": preset_names.get(r["preset_id"], r["preset_id"]),
                "item_count": r["item_count"],
            }
            for r in rows
        ],
    }


# ═══════════════════════════════════════════════
# 评估指标 CRUD
# ═══════════════════════════════════════════════

@router.get("/items")
async def list_items(
    preset_id: str = Query("preset_securities",
                           description="模板ID"),
    dimension: Optional[str] = Query(None,
                                     description="筛选维度: customer/product/channel/geography"),
):
    """获取某模板的评估指标列表"""
    conn = get_connection()
    cursor = conn.cursor()
    if dimension:
        cursor.execute(
            "SELECT * FROM assessment_item "
            "WHERE preset_id = ? AND dimension = ? AND enabled = 1 "
            "ORDER BY sort_order",
            (preset_id, dimension),
        )
    else:
        cursor.execute(
            "SELECT * FROM assessment_item "
            "WHERE preset_id = ? AND enabled = 1 "
            "ORDER BY dimension, sort_order",
            (preset_id,),
        )
    items = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "ok", "preset_id": preset_id, "items": items, "count": len(items)}


class ItemCreate(BaseModel):
    item_key: str
    dimension: str
    name: str
    description: str = ""
    category: str = "data_driven"
    data_source: Optional[str] = None
    default_risk: Optional[str] = None
    threshold_high: Optional[float] = None
    threshold_mid: Optional[float] = None
    score_high: int = 85
    score_mid: int = 50
    score_low: int = 15
    weight: float = 0.20
    sort_order: int = 99
    preset_id: str = "preset_securities"
    severity: str = "中"


@router.post("/items")
async def create_item(data: ItemCreate):
    """新增一条自定义评估指标"""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO assessment_item
                (item_key, dimension, name, description, category,
                 data_source, default_risk, threshold_high, threshold_mid,
                 score_high, score_mid, score_low,
                 weight, sort_order, preset_id, severity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.item_key, data.dimension, data.name, data.description,
            data.category, data.data_source, data.default_risk,
            data.threshold_high, data.threshold_mid,
            data.score_high, data.score_mid, data.score_low,
            data.weight, data.sort_order, data.preset_id, data.severity,
        ))
        conn.commit()
        conn.close()
        return {"status": "ok", "item_key": data.item_key,
                "message": f"指标 '{data.name}' 已添加"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/items/{item_key}")
async def update_item(item_key: str, data: dict):
    """修改某条评估指标（支持部分更新）"""
    conn = get_connection()
    cursor = conn.cursor()

    allowed_fields = [
        "name", "description", "category", "data_source", "default_risk",
        "threshold_high", "threshold_mid", "score_high", "score_mid",
        "score_low", "weight", "sort_order", "enabled", "severity",
    ]
    updates = {k: data[k] for k in data if k in allowed_fields}
    if not updates:
        conn.close()
        raise HTTPException(status_code=400, detail="无有效更新字段")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [item_key]
    cursor.execute(
        f"UPDATE assessment_item SET {set_clause} WHERE item_key = ?",
        values,
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"指标 '{item_key}' 不存在")
    return {"status": "ok", "item_key": item_key, "updated_fields": list(updates.keys())}


@router.delete("/items/{item_key}")
async def disable_item(item_key: str):
    """禁用某条评估指标（软删除，设置 enabled=0）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE assessment_item SET enabled = 0 WHERE item_key = ?",
        (item_key,),
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()

    if affected == 0:
        raise HTTPException(status_code=404, detail=f"指标 '{item_key}' 不存在")
    return {"status": "ok", "item_key": item_key, "message": "指标已禁用"}


# ═══════════════════════════════════════════════
# 评估执行（含历史存档）
# ═══════════════════════════════════════════════

@router.post("/assess")
async def run_assessment(
    preset_id: str = Query("preset_securities",
                           description="评估模板ID"),
):
    """执行一次反洗钱风险自评估，结果自动写入评估历史"""
    engine = AMLEngine(preset_id=preset_id)
    result = engine.assess()

    if result.get("status") != "ok":
        raise HTTPException(status_code=500, detail="评估执行失败")

    # 保存到评估历史
    conn = get_connection()
    cursor = conn.cursor()
    ds = result["data_summary"]
    dims = result["dimensions"]
    cursor.execute("""
        INSERT INTO assessment_history
            (preset_id, overall_score, risk_level,
             customer_score, product_score, channel_score, geography_score,
             customer_count, account_count, trans_count, product_count,
             dimensions_json, recommendations_json, items_detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        preset_id,
        result["overall_score"],
        result["risk_level"],
        dims["customer"]["score"],
        dims["product"]["score"],
        dims["channel"]["score"],
        dims["geography"]["score"],
        ds["customers"], ds["accounts"],
        ds["transactions"], ds["products"],
        json.dumps(dims, ensure_ascii=False),
        json.dumps(result["recommendations"], ensure_ascii=False),
        json.dumps({
            dk: [{"name": i["name"], "risk": i["risk"], "detail": i["detail"]}
                 for i in dims[dk]["items"]]
            for dk in ["customer", "product", "channel", "geography"]
        }, ensure_ascii=False),
    ))
    history_id = cursor.lastrowid
    conn.commit()
    conn.close()

    result["history_id"] = history_id
    return result


# 兼容旧 GET 接口
@router.get("/assess")
async def assess_company_compat(
    preset_id: str = Query("preset_securities",
                           description="评估模板ID"),
):
    """执行评估（GET 兼容接口，不存档）"""
    engine = AMLEngine(preset_id=preset_id)
    return engine.assess()


# ═══════════════════════════════════════════════
# 评估历史（具体路由 /trend /compare 需放在 /{id} 之前）
# ═══════════════════════════════════════════════

@router.get("/history")
async def list_history(
    preset_id: Optional[str] = Query(None, description="筛选模板"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """获取评估历史列表（按日期倒序）"""
    conn = get_connection()
    cursor = conn.cursor()
    if preset_id:
        cursor.execute(
            "SELECT * FROM assessment_history "
            "WHERE preset_id = ? ORDER BY assess_date DESC LIMIT ? OFFSET ?",
            (preset_id, limit, offset),
        )
    else:
        cursor.execute(
            "SELECT * FROM assessment_history "
            "ORDER BY assess_date DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
    rows = cursor.fetchall()
    conn.close()

    return {
        "status": "ok",
        "history": [
            {
                "id": r["id"],
                "assess_date": r["assess_date"],
                "preset_id": r["preset_id"],
                "overall_score": r["overall_score"],
                "risk_level": r["risk_level"],
                "customer_score": r["customer_score"],
                "product_score": r["product_score"],
                "channel_score": r["channel_score"],
                "geography_score": r["geography_score"],
                "customer_count": r["customer_count"],
                "trans_count": r["trans_count"],
            }
            for r in rows
        ],
    }


@router.get("/history/trend")
async def get_trend(
    preset_id: Optional[str] = Query(None, description="筛选模板"),
    limit: int = Query(12, ge=2, le=100, description="最近N次评估"),
):
    """获取评分趋势数据（供前端折线图）"""
    conn = get_connection()
    cursor = conn.cursor()
    if preset_id:
        cursor.execute(
            "SELECT assess_date, overall_score, risk_level, "
            "customer_score, product_score, channel_score, geography_score "
            "FROM assessment_history WHERE preset_id = ? "
            "ORDER BY assess_date ASC LIMIT ?",
            (preset_id, limit),
        )
    else:
        cursor.execute(
            "SELECT assess_date, overall_score, risk_level, "
            "customer_score, product_score, channel_score, geography_score "
            "FROM assessment_history "
            "ORDER BY assess_date ASC LIMIT ?",
            (limit,),
        )
    rows = cursor.fetchall()
    conn.close()

    return {
        "status": "ok",
        "trend": [
            {
                "date": r["assess_date"],
                "overall": r["overall_score"],
                "risk_level": r["risk_level"],
                "customer": r["customer_score"],
                "product": r["product_score"],
                "channel": r["channel_score"],
                "geography": r["geography_score"],
            }
            for r in rows
        ],
    }


@router.get("/compare")
async def compare_assessments(
    id1: int = Query(..., description="第一次评估ID"),
    id2: int = Query(..., description="第二次评估ID"),
):
    """对比两次评估结果"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM assessment_history WHERE id IN (?, ?)",
        (id1, id2),
    )
    rows = {r["id"]: dict(r) for r in cursor.fetchall()}
    conn.close()

    if id1 not in rows or id2 not in rows:
        missing = [str(i) for i in (id1, id2) if i not in rows]
        raise HTTPException(
            status_code=404,
            detail=f"评估记录不存在: {', '.join(missing)}",
        )

    def get_diff(new_val, old_val):
        """计算差值"""
        diff = round(new_val - old_val, 1)
        if diff > 0:
            return {"value": diff, "direction": "up", "label": f"↑ +{diff}"}
        elif diff < 0:
            return {"value": diff, "direction": "down", "label": f"↓ {diff}"}
        else:
            return {"value": 0, "direction": "flat", "label": "→ 持平"}

    r1, r2 = rows[id1], rows[id2]
    return {
        "status": "ok",
        "assessment_a": {
            "id": id1, "date": r1["assess_date"],
            "overall_score": r1["overall_score"],
            "risk_level": r1["risk_level"],
        },
        "assessment_b": {
            "id": id2, "date": r2["assess_date"],
            "overall_score": r2["overall_score"],
            "risk_level": r2["risk_level"],
        },
        "comparison": {
            "overall": get_diff(r1["overall_score"], r2["overall_score"]),
            "customer": get_diff(r1["customer_score"], r2["customer_score"]),
            "product": get_diff(r1["product_score"], r2["product_score"]),
            "channel": get_diff(r1["channel_score"], r2["channel_score"]),
            "geography": get_diff(r1["geography_score"], r2["geography_score"]),
        },
    }


@router.get("/history/{history_id}")
async def get_history_detail(history_id: int):
    """获取某次历史评估的完整详情"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM assessment_history WHERE id = ?", (history_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="评估记录不存在")

    r = dict(row)
    return {
        "status": "ok",
        "record": {
            "id": r["id"],
            "assess_date": r["assess_date"],
            "preset_id": r["preset_id"],
            "overall_score": r["overall_score"],
            "risk_level": r["risk_level"],
            "scores": {
                "customer": r["customer_score"],
                "product": r["product_score"],
                "channel": r["channel_score"],
                "geography": r["geography_score"],
            },
            "data_summary": {
                "customers": r["customer_count"],
                "accounts": r["account_count"],
                "transactions": r["trans_count"],
                "products": r["product_count"],
            },
            "dimensions": json.loads(r["dimensions_json"] or "{}"),
            "recommendations": json.loads(r["recommendations_json"] or "[]"),
            "items_detail": json.loads(r["items_detail_json"] or "[]"),
        },
    }
