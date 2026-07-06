"""
反洗钱风险自评估 API 路由（公司层面）
"""
from fastapi import APIRouter
from .engine import AMLEngine

router = APIRouter()


@router.get("/health")
async def health():
    return {"module": "aml-assessment", "status": "ok"}


@router.get("/assess")
async def assess_company():
    """执行公司层面反洗钱风险自评估"""
    engine = AMLEngine()
    result = engine.assess()
    return result
