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
        "id": "tpl_aml",
        "name": "反洗钱风险评估报告-V0",
        "preset": True,
        "sections": [
            {
                "title": "一、评估概要",
                "content": "评估机构：{{公司名称}}\n评估期间：{{报告期间}}\n密级：{{密级}}\n编制部门：{{编制部门}}\n评估日期：{{评估日期}}\n\n本次反洗钱风险自评估覆盖数据范围如下：\n  · 客户数量：{{客户数}}\n  · 账户数量：{{账户数}}\n  · 交易数量：{{交易数}}\n  · 产品数量：{{产品数}}\n\n评估依据：《法人金融机构洗钱和恐怖融资风险自评估指引》及相关监管要求。"
            },
            {
                "title": "二、综合风险评级",
                "content": "经四维评估模型（客户风险·产品/业务风险·渠道风险·地域风险）综合计算，本次评估结果如下：\n\n综合风险评分：{{综合评分}}\n风险等级：{{风险等级}}\n\n各维度得分详见第三章。"
            },
            {
                "title": "三、四维度风险评估详情",
                "content": "{{四维详情}}"
            },
            {
                "title": "四、整改建议",
                "content": "根据本次评估结果，提出以下整改建议：\n\n{{整改建议}}"
            },
            {
                "title": "五、结论与后续计划",
                "content": "综合来看，{{公司名称}}在{{报告期间}}的反洗钱风险等级为{{风险等级}}（综合评分{{综合评分}}分）。\n\n针对上述风险点和整改建议，本机构将制定详细的整改计划，明确责任人和完成时限，并在下一次评估中对整改效果进行跟踪验证。\n\n编制人：{{编制部门}}\n日期：{{评估日期}}"
            },
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
