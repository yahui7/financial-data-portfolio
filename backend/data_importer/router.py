"""
数据导入 API 路由
"""
import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import Optional

from .engine import DataImporter, TABLE_COLUMNS, TABLE_LABELS

router = APIRouter()

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "templates", "csv",
)

# 暂存上传的文件内容（简单实现，生产环境应改为临时文件或Redis）
_uploaded_files: dict = {}


@router.get("/templates/{table_name}")
async def download_template(table_name: str):
    """下载指定表的CSV模板文件"""
    if table_name not in TABLE_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"无效表名: {table_name}，可选: {', '.join(TABLE_COLUMNS.keys())}",
        )

    file_path = os.path.join(TEMPLATE_DIR, f"{table_name}_template.csv")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="模板文件不存在")

    return FileResponse(
        file_path,
        media_type="text/csv",
        filename=f"{table_name}_template.csv",
    )


@router.post("/upload")
async def upload_csv(table: str, file: UploadFile = File(...)):
    """上传单个CSV文件"""
    if table not in TABLE_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"无效表名: {table}，可选: {', '.join(TABLE_COLUMNS.keys())}",
        )

    content = await file.read()
    text = content.decode("utf-8-sig")  # 兼容带BOM的UTF-8

    importer = DataImporter()
    try:
        result = importer.preview(text, table)
        # 暂存内容供后续确认导入
        _uploaded_files[table] = {
            "content": text,
            "valid_count": result["validation"]["valid_count"],
            "total_rows": result["total_rows"],
        }
        return {"status": "ok", "table": table, "preview": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV解析失败: {e}")


@router.post("/preview")
async def preview_csv(table: str, file: UploadFile = File(...)):
    """预览CSV文件（不暂存，仅返回前10行+校验结果）"""
    if table not in TABLE_COLUMNS:
        raise HTTPException(
            status_code=400,
            detail=f"无效表名: {table}，可选: {', '.join(TABLE_COLUMNS.keys())}",
        )

    content = await file.read()
    text = content.decode("utf-8-sig")

    importer = DataImporter()
    return {"status": "ok", "table": table, "preview": importer.preview(text, table)}


@router.post("/confirm")
async def confirm_import(table: Optional[str] = None):
    """
    确认导入已上传的数据
    - 指定 table: 只导入该表
    - 不指定 table: 导入所有已上传的表
    """
    importer = DataImporter()

    if table:
        if table not in _uploaded_files:
            raise HTTPException(
                status_code=400,
                detail=f"表 '{table}' 尚未上传，请先调用 /upload",
            )
        tables_to_import = [table]
    else:
        tables_to_import = list(_uploaded_files.keys())
        if not tables_to_import:
            raise HTTPException(
                status_code=400,
                detail="没有已上传的数据，请先调用 /upload",
            )

    results = {}
    total_imported = 0
    for t in tables_to_import:
        uploaded = _uploaded_files[t]
        rows = importer.parse_csv(uploaded["content"])
        validation = importer.validate_rows(rows, t)
        # 全部导入，不过滤 —— 数据质量问题留给质量扫描来标记
        import_result = importer.import_table(rows, t)
        results[t] = {
            "label": TABLE_LABELS.get(t, t),
            "total_rows": len(rows),
            "imported": import_result["count"],
            "warnings": validation["error_count"],
            "import_errors": import_result["errors"],
        }
        total_imported += import_result["count"]

    # 导入后执行质量检查
    quality = importer.run_quality_check()

    # 清空暂存
    for t in tables_to_import:
        _uploaded_files.pop(t, None)

    return {
        "status": "ok",
        "imported": total_imported,
        "tables": results,
        "quality_check": quality,
    }


@router.get("/status")
async def import_status():
    """查看当前数据库中各表的数据量"""
    from backend.database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    counts = {}
    for table in ["customer", "account", "trans_record", "product"]:
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
        counts[table] = cursor.fetchone()["cnt"]
    conn.close()
    return {"status": "ok", "counts": counts}


@router.post("/clear")
async def clear_data():
    """清空所有业务数据（reset）"""
    importer = DataImporter()
    importer.clear_all()
    # 同时清空评估历史（数据都没了，历史也失去意义）
    from backend.database import get_connection
    conn = get_connection()
    conn.cursor().execute("DELETE FROM assessment_history")
    conn.commit()
    conn.close()
    _uploaded_files.clear()
    return {"status": "ok", "message": "所有数据和评估历史已清空"}
