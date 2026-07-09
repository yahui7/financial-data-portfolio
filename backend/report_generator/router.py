"""
报告生成 API 路由
"""
import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Any
from pydantic import BaseModel

from . import templates as tmpl_mgr
from .engine import ReportEngine
from backend.database import get_connection

router = APIRouter()


# ═══════════════════════════════════════════════
#  模板管理
# ═══════════════════════════════════════════════

@router.get("/templates")
async def list_templates():
    """列出所有模板"""
    return {"status": "ok", "templates": tmpl_mgr.list_templates()}


@router.get("/templates/{tpl_id}")
async def get_template(tpl_id: str):
    """获取单个模板详情，含占位符列表"""
    tpl = tmpl_mgr.get_template(tpl_id)
    if not tpl:
        return {"status": "error", "message": "模板不存在"}
    placeholders = ReportEngine.extract_placeholders(tpl)
    return {"status": "ok", "template": tpl, "placeholders": placeholders}


@router.post("/templates")
async def create_template(data: dict):
    """新建模板"""
    if not data.get("name"):
        return {"status": "error", "message": "模板名称不能为空"}
    if not data.get("sections"):
        return {"status": "error", "message": "至少需要一个章节"}
    result = tmpl_mgr.save_template(data)
    return {"status": "ok", "template": result}


@router.put("/templates/{tpl_id}")
async def update_template(tpl_id: str, data: dict):
    """编辑模板"""
    existing = tmpl_mgr.get_template(tpl_id)
    if not existing:
        return {"status": "error", "message": "模板不存在"}
    data["id"] = tpl_id
    result = tmpl_mgr.save_template(data)
    return {"status": "ok", "template": result}


@router.delete("/templates/{tpl_id}")
async def delete_template(tpl_id: str):
    """删除模板"""
    ok = tmpl_mgr.delete_template(tpl_id)
    if not ok:
        return {"status": "error", "message": "预设模板不可删除"}
    return {"status": "ok"}


# ═══════════════════════════════════════════════
#  报告生成
# ═══════════════════════════════════════════════

@router.post("/csv-template")
async def download_csv_template(data: dict):
    """下载 CSV 模板文件，含占位符表头"""
    tpl_id = data.get("template_id")
    tpl = tmpl_mgr.get_template(tpl_id)
    if not tpl:
        return JSONResponse({"status": "error", "message": "模板不存在"}, status_code=404)

    placeholders = ReportEngine.extract_placeholders(tpl)
    if not placeholders:
        return JSONResponse({"status": "error", "message": "该模板没有占位符"}, status_code=400)

    buf = ReportEngine.generate_csv_template(placeholders)
    safe_name = quote(tpl["name"].replace(" ", "_")[:20])
    filename = f"{safe_name}_填写模板.csv"

    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post("/upload-csv")
async def upload_csv(template_id: str = Query(...), file: UploadFile = File(...)):
    """上传填好的 CSV，返回解析后的数据"""
    tpl = tmpl_mgr.get_template(template_id)
    if not tpl:
        return JSONResponse({"status": "error", "message": "模板不存在"}, status_code=404)

    try:
        csv_bytes = await file.read()
        data = ReportEngine.parse_csv(csv_bytes)
        # 校验：CSV 列名是否与模板占位符匹配
        placeholders = set(ReportEngine.extract_placeholders(tpl))
        csv_keys = set(data.keys())
        if not csv_keys.issubset(placeholders):
            extra = csv_keys - placeholders
            return JSONResponse(
                {"status": "error", "message": f"CSV 包含模板中不存在的字段: {', '.join(extra)}"},
                status_code=400,
            )
        return {"status": "ok", "data": data}
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"CSV 解析失败: {str(e)}"}, status_code=400)


class GenerateRequest(BaseModel):
    template_id: str
    data: dict[str, Any]  # {占位符: 值}
    title: str = "报告"
    author: str = ""
    date: str = ""


@router.post("/generate")
async def generate_report(req: GenerateRequest):
    """生成报告预览"""
    tpl = tmpl_mgr.get_template(req.template_id)
    if not tpl:
        return JSONResponse({"status": "error", "message": "模板不存在"}, status_code=404)

    report = ReportEngine.fill_placeholders(tpl, req.data)

    result = {
        "title": req.title,
        "template_id": req.template_id,
        "template_name": tpl["name"],
        "author": req.author,
        "date": req.date or datetime.now().strftime("%Y-%m-%d"),
        "sections": report["sections"],
    }
    return {"status": "ok", "report": result}


class ExportRequest(BaseModel):
    title: str = "报告"
    author: str = ""
    date: str = ""
    sections: list[dict[str, Any]] = []


@router.post("/export")
async def export_word(req: ExportRequest):
    """导出为 Word 文档下载"""
    try:
        report = {
            "title": req.title,
            "author": req.author,
            "date": req.date or datetime.now().strftime("%Y-%m-%d"),
            "sections": req.sections,
        }
        buf = ReportEngine.export_word(report)

        safe_name = quote(req.title.replace(" ", "_")[:20])
        filename = f"{req.date}_{safe_name}.docx"

        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
        )
    except Exception as e:
        return JSONResponse({"status": "error", "message": f"导出失败: {str(e)}"}, status_code=500)


# ═══════════════════════════════════════════════
#  历史报告
# ═══════════════════════════════════════════════

class SaveHistoryRequest(BaseModel):
    title: str = "报告"
    template_id: str = ""
    template_name: str = ""
    author: str = ""
    date: str = ""
    sections: list[dict[str, Any]] = []


@router.get("/history")
async def list_history():
    """历史报告列表"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, template_name, author, date, created_at FROM report_history ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return {"status": "ok", "history": [dict(r) for r in rows]}


# ═══════════════════════════════════════════════
#  报告对比（必须在 /history/{history_id} 前注册）
# ═══════════════════════════════════════════════

@router.get("/history/compare")
async def compare_history(ids: str = Query(..., description="逗号分隔的两个ID，如 1,2")):
    """对比两份历史报告"""
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    if len(id_list) != 2:
        return JSONResponse({"status": "error", "message": "请提供恰好两个历史报告ID"}, status_code=400)

    conn = get_connection()
    cursor = conn.cursor()

    reports_data = []
    for hid in id_list:
        cursor.execute("SELECT * FROM report_history WHERE id = ?", (hid,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return JSONResponse({"status": "error", "message": f"记录 {hid} 不存在"}, status_code=404)
        record = dict(row)
        record["content_json"] = json.loads(record["content_json"])
        reports_data.append(record)

    conn.close()

    report_a = {
        "title": reports_data[0]["title"],
        "sections": reports_data[0]["content_json"].get("sections", []),
    }
    report_b = {
        "title": reports_data[1]["title"],
        "sections": reports_data[1]["content_json"].get("sections", []),
    }

    diff = ReportEngine.compare_reports(report_a, report_b)

    return {
        "status": "ok",
        "report_a": {"id": id_list[0], "title": reports_data[0]["title"], "date": reports_data[0]["date"]},
        "report_b": {"id": id_list[1], "title": reports_data[1]["title"], "date": reports_data[1]["date"]},
        "diff": diff,
    }


@router.get("/history/{history_id}")
async def get_history(history_id: int):
    """历史报告详情"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM report_history WHERE id = ?", (history_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return JSONResponse({"status": "error", "message": "记录不存在"}, status_code=404)
    record = dict(row)
    record["content_json"] = json.loads(record["content_json"])
    return {"status": "ok", "record": record}


@router.post("/history")
async def save_history(req: SaveHistoryRequest):
    """保存报告到历史"""
    conn = get_connection()
    cursor = conn.cursor()
    content_json = json.dumps({
        "title": req.title,
        "template_id": req.template_id,
        "template_name": req.template_name,
        "author": req.author,
        "date": req.date,
        "sections": req.sections,
    }, ensure_ascii=False)
    cursor.execute(
        "INSERT INTO report_history (title, template_id, template_name, author, date, content_json) VALUES (?, ?, ?, ?, ?, ?)",
        (req.title, req.template_id, req.template_name, req.author, req.date, content_json),
    )
    conn.commit()
    hid = cursor.lastrowid
    conn.close()
    return {"status": "ok", "id": hid, "message": "报告已保存"}


@router.delete("/history/{history_id}")
async def delete_history(history_id: int):
    """删除历史报告"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM report_history WHERE id = ?", (history_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "已删除"}


@router.get("/history/{history_id}/export")
async def export_history(history_id: int):
    """从历史记录导出 Word"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM report_history WHERE id = ?", (history_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return JSONResponse({"status": "error", "message": "记录不存在"}, status_code=404)

    content = json.loads(row["content_json"])
    report = {
        "title": row["title"],
        "author": content.get("author", ""),
        "date": content.get("date", ""),
        "sections": content.get("sections", []),
    }
    buf = ReportEngine.export_word(report)

    safe_name = quote(row["title"].replace(" ", "_")[:20])
    filename = f"{content.get('date', 'report')}_{safe_name}.docx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )

