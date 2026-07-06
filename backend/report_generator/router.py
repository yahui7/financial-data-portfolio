"""
报告生成 API 路由
"""
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from . import templates
from .engine import ReportEngine

router = APIRouter()


# ── 模板管理 ──

@router.get("/templates")
async def list_templates():
    """列出所有模板"""
    return {"status": "ok", "templates": templates.list_templates()}


@router.get("/templates/{tpl_id}")
async def get_template(tpl_id: str):
    """获取单个模板"""
    tpl = templates.get_template(tpl_id)
    if not tpl:
        return {"status": "error", "message": "模板不存在"}
    return {"status": "ok", "template": tpl}


@router.post("/templates")
async def save_template(data: dict):
    """保存自定义模板"""
    result = templates.save_template(data)
    return {"status": "ok", "template": result}


@router.delete("/templates/{tpl_id}")
async def delete_template(tpl_id: str):
    """删除自定义模板"""
    ok = templates.delete_template(tpl_id)
    if not ok:
        return {"status": "error", "message": "预设模板不可删除"}
    return {"status": "ok"}


@router.get("/data-sources")
async def data_sources():
    """获取可用的数据源列表"""
    return {"status": "ok", "sources": templates.get_data_sources()}


# ── 报告生成 ──

class ReportInfo(BaseModel):
    title: str = "数据质量报告"
    report_no: str = "RPT-2026-001"
    author: str = "王亚慧"
    date: str = ""
    template_id: str = "tpl_quality"


class ExportInfo(BaseModel):
    title: str = "报告"
    report_no: str = ""
    author: str = ""
    date: str = ""
    template_id: str = "tpl_quality"
    sections: list = []


@router.post("/generate")
async def generate_report(info: ReportInfo):
    """生成报告内容"""
    tpl = templates.get_template(info.template_id)
    if not tpl:
        return {"status": "error", "message": "模板不存在"}

    engine = ReportEngine()
    report = engine.generate(tpl, info.model_dump())
    return {"status": "ok", "report": report}


@router.post("/export-word")
async def export_word(data: ExportInfo):
    """导出为 Word 文档下载"""
    import traceback
    try:
        tpl = templates.get_template(data.template_id)
        if not tpl:
            return {"status": "error", "message": "模板不存在"}

        info = {"title": data.title, "report_no": data.report_no, "author": data.author, "date": data.date}
        engine = ReportEngine()

        report = {
            "title": data.title,
            "report_no": data.report_no,
            "author": data.author,
            "date": data.date,
            "sections": data.sections,
        }

        if not report["sections"]:
            report = engine.generate(tpl, info)

        buf = engine.export_word(report)
        from urllib.parse import quote
        safe_name = "report"
        filename = f"{data.date}_{safe_name}.docx"

        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
