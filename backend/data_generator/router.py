"""
数据生成器 API 路由
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Optional

from .engine import DataGenerator, QUALITY_ISSUE_TYPES

router = APIRouter()

# 内存中保存最近一次生成的结果，供前端预览
_latest_result: Optional[dict] = None
_latest_generator: Optional[DataGenerator] = None


class IssuesConfig(BaseModel):
    """质量问题配置"""
    completeness: float = Field(default=0.05, ge=0, le=0.3, description="完整性缺失比例")
    accuracy: float = Field(default=0.05, ge=0, le=0.3, description="准确性错误比例")
    consistency: float = Field(default=0.05, ge=0, le=0.3, description="一致性错误比例")
    logical: float = Field(default=0.03, ge=0, le=0.3, description="逻辑性错误比例")
    duplicate: float = Field(default=0.03, ge=0, le=0.3, description="重复数据比例")


class GenerateRequest(BaseModel):
    """生成请求"""
    customer_count: int = Field(default=200, ge=10, le=5000, description="客户数量")
    account_count: int = Field(default=300, ge=10, le=10000, description="账户数量")
    transaction_count: int = Field(default=800, ge=10, le=50000, description="交易数量")
    product_count: int = Field(default=30, ge=5, le=200, description="产品数量")
    issues: IssuesConfig = Field(default_factory=IssuesConfig, description="质量问题配置")


@router.get("/health")
async def health():
    return {"module": "data-generator", "status": "ok"}


@router.get("/issue-types")
async def get_issue_types():
    """获取所有可配置的质量问题类型"""
    return {
        "issue_types": [
            {
                "key": k,
                "name": v["name"],
                "description": v["description"],
                "affected_fields": {table: fields for table, fields in v["fields"].items() if fields},
            }
            for k, v in QUALITY_ISSUE_TYPES.items()
        ]
    }


@router.post("/generate")
async def generate_data(req: GenerateRequest):
    """生成模拟数据集"""
    global _latest_result, _latest_generator

    gen = DataGenerator(
        customer_count=req.customer_count,
        account_count=req.account_count,
        transaction_count=req.transaction_count,
        product_count=req.product_count,
        issues_config=req.issues.model_dump(),
    )
    result = gen.generate()
    gen.save_to_db()

    _latest_result = result
    _latest_generator = gen

    return {
        "status": "ok",
        "message": f"数据生成完成：{result['summary']['customers']} 客户, "
                   f"{result['summary']['accounts']} 账户, "
                   f"{result['summary']['transactions']} 交易, "
                   f"{result['summary']['products']} 产品",
        "summary": result["summary"],
    }


@router.get("/preview")
async def preview_data(
    table: str = Query(default="customer", description="表名: customer/account/transactions/products"),
    limit: int = Query(default=20, ge=1, le=5000),
):
    """预览生成的数据（最多20条）"""
    global _latest_result

    if not _latest_result:
        return {"status": "empty", "message": "暂无数据，请先调用 POST /api/generator/generate"}

    table_map = {
        "customer": "customers",
        "account": "accounts",
        "transactions": "transactions",
        "product": "products",
    }

    key = table_map.get(table)
    if not key:
        return {"status": "error", "message": f"无效的表名: {table}"}

    data = _latest_result["data"][key]
    return {
        "status": "ok",
        "table": table,
        "total": len(data),
        "preview": data[:limit],
    }


@router.get("/download")
async def download_data(
    table: str = Query(default="customer", description="表名"),
):
    """下载完整数据集为 JSON"""
    global _latest_result

    if not _latest_result:
        return {"status": "empty", "message": "暂无数据"}

    table_map = {
        "customer": "customers",
        "account": "accounts",
        "transactions": "transactions",
        "product": "products",
    }

    key = table_map.get(table)
    if not key:
        return {"status": "error", "message": f"无效的表名: {table}"}

    return {
        "status": "ok",
        "table": table,
        "data": _latest_result["data"][key],
    }


@router.get("/summary")
async def get_summary():
    """获取生成概要"""
    global _latest_result

    if not _latest_result:
        return {"status": "empty", "message": "暂无数据"}

    return {
        "status": "ok",
        "summary": _latest_result["summary"],
    }
