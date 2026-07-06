"""客户风险监控 API"""
from fastapi import APIRouter, Query
from .engine import CustomerMonitor

router = APIRouter()


@router.get("/health")
async def health():
    return {"module": "customer-monitor", "status": "ok"}


@router.get("/customers")
async def list_customers(limit: int = Query(default=100, ge=1, le=200)):
    m = CustomerMonitor()
    return {"status": "ok", "customers": m.get_customer_list(limit)}


@router.get("/profile/{customer_id}")
async def profile(customer_id: str):
    m = CustomerMonitor()
    return m.profile(customer_id)


@router.get("/network")
async def network(min_amount: float = Query(default=0, ge=0)):
    m = CustomerMonitor()
    return m.network_analysis(min_amount)
