"""
报告生成引擎
- 自动运行数据扫描和评估
- 填充报告各章节内容
- 导出 Word 文档
"""
from datetime import datetime
from io import BytesIO

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

from backend.database import get_connection
from backend.data_generator.engine import DataGenerator
from backend.data_quality.engine import QualityScanner
from backend.aml_assessment.engine import AMLEngine


class ReportEngine:
    """报告生成引擎"""

    def __init__(self):
        pass

    # ── 数据源 ──

    def _get_data_summary(self) -> str:
        """生成数据概览"""
        conn = get_connection()
        cursor = conn.cursor()
        counts = {}
        for table in ["customer", "account", "trans_record", "product"]:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
            counts[table] = cursor.fetchone()["cnt"]
        conn.close()

        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        return (
            f"评估时间：{ts}\n\n"
            f"本次评估覆盖数据范围如下：\n"
            f"  · 客户数量：{counts['customer']} 人\n"
            f"  · 账户数量：{counts['account']} 个\n"
            f"  · 交易数量：{counts['trans_record']} 笔\n"
            f"  · 产品数量：{counts['product']} 只\n\n"
            f"以上数据来源于金融数据生成器模拟产生的测试数据集。"
        )

    def _get_quality_scan(self) -> str:
        """生成数据质量评估内容"""
        scanner = QualityScanner()
        result = scanner.scan()
        scores = result["scores"]

        text = (
            f"扫描时间：{result['scan_time']}\n"
            f"扫描规则：{result['total_rules']} 条 | 通过：{result['passed_rules']} 条 | 失败：{result['failed_rules']} 条\n\n"
            f"综合质量评分：{scores['overall']}%\n\n"
            f"各维度得分：\n"
            f"  · 完整性：{scores['completeness']}%\n"
            f"  · 准确性：{scores['accuracy']}%\n"
            f"  · 一致性：{scores['consistency']}%\n"
            f"  · 逻辑性：{scores['logical']}%\n"
        )
        return text

    def _get_quality_issues(self) -> str:
        """生成问题发现内容"""
        scanner = QualityScanner()
        result = scanner.scan()
        failed = [r for r in result["rules"] if r["record_count"] > 0]
        failed.sort(key=lambda r: (0 if r["severity"] == "高" else 1 if r["severity"] == "中" else 2))

        if not failed:
            return "本次扫描未发现数据质量问题。"

        lines = ["本次扫描发现以下数据质量问题：\n"]
        for i, r in enumerate(failed[:10], 1):
            lines.append(
                f"{i}. [{r['severity']}] {r['rule_id']} {r['description']} "
                f"— {r['table_name']}.{r['field_name']}，影响 {r['record_count']} 条记录"
            )
        return "\n".join(lines)

    def _get_quality_recommendations(self) -> str:
        """生成质量整改建议"""
        scanner = QualityScanner()
        result = scanner.scan()
        failed = [r for r in result["rules"] if r["record_count"] > 0]

        if not failed:
            return "当前数据质量良好，建议持续监控。\n\n建议：\n1. 定期执行数据质量扫描\n2. 保持数据质量标准的持续维护"

        high = [r for r in failed if r["severity"] == "高"]
        lines = ["根据质量扫描结果，提出以下整改建议：\n"]
        idx = 1
        if high:
            lines.append(f"{idx}. 优先处理 {len(high)} 项高严重性问题，特别是：")
            for r in high[:3]:
                idx += 1
                lines.append(f"   · {r['rule_id']} {r['description']}")
        lines.append(f"{len(failed)}. 建立数据质量问题追踪机制，确保每个问题有责任人、有整改期限")
        lines.append(f"{len(failed)+1}. 定期回顾数据质量标准，根据业务变化及时调整校验规则")
        return "\n".join(lines)

    def _get_aml_assessment(self) -> str:
        """生成AML评估内容"""
        engine = AMLEngine()
        result = engine.assess()

        text = (
            f"评估时间：{result['assessment_time']}\n\n"
            f"综合风险评分：{result['overall_score']} 分\n"
            f"风险等级：{result['risk_level_name']}\n\n"
        )

        dims = result["dimensions"]
        for dk in ["customer", "product", "channel", "geography"]:
            dim = dims[dk]
            text += f"{dim['name']}：{dim['score']} 分\n"
            for item in dim["items"]:
                text += f"  · {item['name']}：{item['risk']} — {item['detail']}\n"
            text += "\n"
        return text

    def _get_aml_recommendations(self) -> str:
        """生成AML整改建议"""
        engine = AMLEngine()
        result = engine.assess()
        if not result["recommendations"]:
            return "未发现需要整改的高风险项。"

        lines = ["根据反洗钱风险评估结果，提出以下整改建议：\n"]
        for i, rec in enumerate(result["recommendations"][:10], 1):
            lines.append(f"{i}. {rec}")
        return "\n".join(lines)

    # ── 生成报告 ──

    def generate(self, template: dict, info: dict) -> dict:
        """根据模板生成报告内容"""
        source_handlers = {
            "data_summary": self._get_data_summary,
            "quality_scan": self._get_quality_scan,
            "quality_issues": self._get_quality_issues,
            "quality_recommendations": self._get_quality_recommendations,
            "aml_assessment": self._get_aml_assessment,
            "aml_recommendations": self._get_aml_recommendations,
        }

        # 为预设模板扩展实际的数据源映射
        preset_map = {
            "tpl_quality": {
                "一、数据概况": "data_summary",
                "二、数据质量评估": "quality_scan",
                "三、主要问题发现": "quality_issues",
                "四、整改建议": "quality_recommendations",
                "五、结论": "manual",
            },
            "tpl_aml": {
                "一、评估概要": "data_summary",
                "二、综合风险评级": "aml_assessment",
                "三、四维度风险评估详情": "aml_assessment",
                "四、整改建议": "aml_recommendations",
                "五、结论": "manual",
            },
        }

        sections = []
        # 如果是预设模板，用预设映射
        if template.get("preset") and template["id"] in preset_map:
            for title, source in preset_map[template["id"]].items():
                content = ""
                if source != "manual":
                    handler = source_handlers.get(source)
                    if handler:
                        content = handler()
                sections.append({"title": title, "source": source, "content": content})
        else:
            # 自定义模板
            for sec in template.get("sections", []):
                source = sec.get("source", "manual")
                content = ""
                if source != "manual":
                    handler = source_handlers.get(source)
                    if handler:
                        content = handler()
                sections.append({"title": sec["title"], "source": source, "content": content})

        return {
            "title": info.get("title", ""),
            "report_no": info.get("report_no", ""),
            "author": info.get("author", ""),
            "date": info.get("date", datetime.now().strftime("%Y-%m-%d")),
            "sections": sections,
        }

    # ── 导出 Word ──

    def export_word(self, report: dict) -> BytesIO:
        """将报告导出为 Word 文档"""
        doc = Document()

        # 标题
        title = doc.add_heading(report.get("title", "报告"), level=0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 报告信息
        info_text = f"报告编号：{report.get('report_no', '')}　　编制人：{report.get('author', '')}　　日期：{report.get('date', '')}"
        info_p = doc.add_paragraph(info_text)
        info_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in info_p.runs:
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(128, 128, 128)

        doc.add_paragraph()  # 空行

        # 各章节
        for sec in report.get("sections", []):
            doc.add_heading(sec["title"], level=1)
            content = sec.get("content", "")
            if content:
                for line in content.split("\n"):
                    p = doc.add_paragraph(line)
                    for run in p.runs:
                        run.font.size = Pt(11)

        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf
