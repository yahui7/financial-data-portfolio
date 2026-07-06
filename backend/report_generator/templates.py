"""
报告模板管理
- 系统预设模板 + 用户自定义模板
- 存储为 JSON 文件
"""
import os
import json
from datetime import datetime

TEMPLATES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "templates",
)

DATA_SOURCES = [
    {"key": "data_summary", "name": "数据概览"},
    {"key": "quality_scan", "name": "质量评分"},
    {"key": "aml_assessment", "name": "AML评估"},
    {"key": "manual", "name": "手动填写"},
]

PRESET_TEMPLATES = [
    {
        "id": "tpl_quality",
        "name": "数据质量报告",
        "preset": True,
        "sections": [
            {"title": "一、数据概况", "source": "data_summary"},
            {"title": "二、数据质量评估", "source": "quality_scan"},
            {"title": "三、主要问题发现", "source": "quality_scan"},
            {"title": "四、整改建议", "source": "quality_scan"},
            {"title": "五、结论", "source": "manual"},
        ],
    },
    {
        "id": "tpl_aml",
        "name": "反洗钱风险评估报告",
        "preset": True,
        "sections": [
            {"title": "一、评估概要", "source": "data_summary"},
            {"title": "二、综合风险评级", "source": "aml_assessment"},
            {"title": "三、四维度风险评估详情", "source": "aml_assessment"},
            {"title": "四、整改建议", "source": "aml_assessment"},
            {"title": "五、结论", "source": "manual"},
        ],
    },
]


def _ensure_dir():
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    # 写入预设模板
    for tpl in PRESET_TEMPLATES:
        path = os.path.join(TEMPLATES_DIR, f"{tpl['id']}.json")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(tpl, f, ensure_ascii=False, indent=2)


def list_templates() -> list[dict]:
    """列出所有模板"""
    _ensure_dir()
    templates = []
    for fname in os.listdir(TEMPLATES_DIR):
        if fname.endswith(".json"):
            with open(os.path.join(TEMPLATES_DIR, fname), "r", encoding="utf-8") as f:
                templates.append(json.load(f))
    return sorted(templates, key=lambda t: (not t.get("preset", False), t["name"]))


def get_template(tpl_id: str) -> dict | None:
    """获取单个模板"""
    path = os.path.join(TEMPLATES_DIR, f"{tpl_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_template(data: dict) -> dict:
    """保存自定义模板"""
    _ensure_dir()
    tpl_id = data.get("id") or f"tpl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data["id"] = tpl_id
    data["preset"] = False
    path = os.path.join(TEMPLATES_DIR, f"{tpl_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def delete_template(tpl_id: str) -> bool:
    """删除自定义模板"""
    path = os.path.join(TEMPLATES_DIR, f"{tpl_id}.json")
    if not os.path.exists(path):
        return False
    tpl = json.load(open(path, "r", encoding="utf-8"))
    if tpl.get("preset"):
        return False  # 预设模板不可删除
    os.remove(path)
    return True


def get_data_sources() -> list[dict]:
    return DATA_SOURCES
