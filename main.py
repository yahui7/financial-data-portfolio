"""
金融数据产品作品集 — 后端主应用
FastAPI + SQLite
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.database import init_db
from backend.data_generator.router import router as generator_router
from backend.data_quality.router import router as quality_router
from backend.aml_assessment.router import router as aml_router
from backend.report_generator.router import router as report_router
from backend.customer_monitor.router import router as monitor_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化数据库"""
    init_db()
    print("[OK] 数据库初始化完成")
    yield


app = FastAPI(
    title="金融数据产品作品集",
    description="数据生成器 · 数据质量监控 · 反洗钱风险评估",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册各模块路由
app.include_router(generator_router, prefix="/api/generator", tags=["数据生成器"])
app.include_router(quality_router, prefix="/api/quality", tags=["数据质量监控"])
app.include_router(aml_router, prefix="/api/aml", tags=["反洗钱风险评估"])
app.include_router(report_router, prefix="/api/report", tags=["报告生成"])
app.include_router(monitor_router, prefix="/api/monitor", tags=["客户风险监控"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "message": "金融数据产品作品集运行中"}


# 前端静态文件 — 放在最后，避免拦截 API 路由
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
