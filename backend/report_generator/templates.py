"""
报告模板管理
- 系统预设模板 + 用户自定义模板
- 存储为 JSON 文件
"""
import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMPLATES_DIR = os.path.join(BASE_DIR, "data", "templates")

# 预设通用模板
PRESET_TEMPLATES = [
    {
        "id": "tpl_weekly",
        "name": "项目周报",
        "preset": True,
        "description": "适用于项目进度汇报的周报模板",
        "sections": [
            {
                "title": "一、本周工作概述",
                "content": "项目名称：{{项目名称}}\n报告周期：{{报告周期}}\n汇报人：{{汇报人}}\n\n本周主要工作内容：\n{{本周工作内容}}"
            },
            {
                "title": "二、关键成果",
                "content": "本周完成的关键成果：\n{{关键成果}}\n\n完成率：{{完成率}}"
            },
            {
                "title": "三、遇到的问题",
                "content": "遇到的主要问题和风险：\n{{问题与风险}}\n\n应对措施：\n{{应对措施}}"
            },
            {
                "title": "四、下周计划",
                "content": "下周工作计划：\n{{下周计划}}\n\n需要协调的事项：\n{{协调事项}}"
            },
            {
                "title": "五、总结与建议",
                "content": "总体评价：{{总体评价}}\n\n改进建议：\n{{改进建议}}"
            },
        ],
    },
    {
        "id": "tpl_meeting",
        "name": "会议纪要",
        "preset": True,
        "description": "适用于各类会议的纪要模板",
        "sections": [
            {
                "title": "一、会议基本信息",
                "content": "会议主题：{{会议主题}}\n会议日期：{{会议日期}}\n会议地点：{{会议地点}}\n主持人：{{主持人}}\n记录人：{{记录人}}\n参会人员：{{参会人员}}"
            },
            {
                "title": "二、会议议程",
                "content": "本次会议主要议程：\n{{会议议程}}"
            },
            {
                "title": "三、讨论内容",
                "content": "主要讨论内容：\n{{讨论内容}}\n\n各方意见：\n{{各方意见}}"
            },
            {
                "title": "四、决议事项",
                "content": "会议形成的决议：\n{{决议事项}}"
            },
            {
                "title": "五、行动计划",
                "content": "后续行动计划：\n{{行动计划}}\n\n下次会议时间：{{下次会议时间}}"
            },
        ],
    },
    {
        "id": "tpl_summary",
        "name": "工作总结",
        "preset": True,
        "description": "适用于月度/季度/年度工作总结",
        "sections": [
            {
                "title": "一、工作综述",
                "content": "总结人：{{总结人}}\n总结周期：{{总结周期}}\n所属部门：{{所属部门}}\n\n工作综述：\n{{工作综述}}"
            },
            {
                "title": "二、重点工作完成情况",
                "content": "各项重点工作完成情况：\n{{重点工作}}"
            },
            {
                "title": "三、数据与成果",
                "content": "关键数据指标：\n{{数据指标}}\n\n取得的成果和亮点：\n{{成果亮点}}"
            },
            {
                "title": "四、经验与反思",
                "content": "经验总结：\n{{经验总结}}\n\n不足之处：\n{{不足之处}}"
            },
            {
                "title": "五、下阶段展望",
                "content": "下阶段目标：\n{{下阶段目标}}\n\n个人成长计划：\n{{成长计划}}"
            },
        ],
    },
    {
        "id": "tpl_plan",
        "name": "项目计划书",
        "preset": True,
        "description": "适用于项目启动阶段的计划书模板",
        "sections": [
            {
                "title": "一、项目背景",
                "content": "项目名称：{{项目名称}}\n编制日期：{{编制日期}}\n编制人：{{编制人}}\n\n项目背景与目标：\n{{项目背景}}"
            },
            {
                "title": "二、项目范围",
                "content": "项目范围：\n{{项目范围}}\n\n主要交付物：\n{{交付物}}\n\n不在范围内的事项：\n{{范围外事项}}"
            },
            {
                "title": "三、项目计划",
                "content": "里程碑计划：\n{{里程碑计划}}\n\n详细时间安排：\n{{时间安排}}"
            },
            {
                "title": "四、资源与预算",
                "content": "所需资源：\n{{所需资源}}\n\n项目预算：{{项目预算}}\n\n团队成员：\n{{团队成员}}"
            },
            {
                "title": "五、风险管理",
                "content": "主要风险及应对：\n{{风险管理}}\n\n沟通计划：\n{{沟通计划}}"
            },
        ],
    },
]


def _ensure_dir():
    """确保模板目录存在并初始化预设模板"""
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
    for tpl in PRESET_TEMPLATES:
        path = os.path.join(TEMPLATES_DIR, f"{tpl['id']}.json")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(tpl, f, ensure_ascii=False, indent=2)


def list_templates() -> list:
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
    """保存模板（新建或更新）"""
    _ensure_dir()
    tpl_id = data.get("id") or f"tpl_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    data["id"] = tpl_id
    data["preset"] = data.get("preset", False)

    # 检查是否覆盖预设模板
    existing = get_template(tpl_id)
    if existing and existing.get("preset"):
        # 不允许直接覆盖预设，生成新ID
        tpl_id = f"{tpl_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        data["id"] = tpl_id
        data["preset"] = False

    path = os.path.join(TEMPLATES_DIR, f"{tpl_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return data


def delete_template(tpl_id: str) -> bool:
    """删除模板（预设模板不可删除）"""
    path = os.path.join(TEMPLATES_DIR, f"{tpl_id}.json")
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as f:
        tpl = json.load(f)
    if tpl.get("preset"):
        return False
    os.remove(path)
    return True


def extract_placeholders(tpl_id: str) -> list[str] | None:
    """从模板中提取所有占位符"""
    import re

    tpl = get_template(tpl_id)
    if not tpl:
        return None

    placeholders = set()
    for section in tpl.get("sections", []):
        content = section.get("content", "")
        found = re.findall(r"\{\{(.+?)\}\}", content)
        placeholders.update(found)

    return sorted(placeholders)
