"""简历分析报告 PDF 导出模块。"""

import os
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


_FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"
_FONT_NAME = "SimHei"
_FALLBACK_FONT_NAME = "STSong-Light"
_FONT_REGISTERED = False
_ACTIVE_FONT_NAME = _FONT_NAME

_MAX_TEXT_LENGTH = 2000
_MAX_LIST_ITEMS = 20


def _ensure_font_registered() -> str:
    """延迟注册中文字体，避免模块导入阶段因字体缺失崩溃。"""
    global _ACTIVE_FONT_NAME, _FONT_REGISTERED

    if _FONT_REGISTERED:
        return _ACTIVE_FONT_NAME

    if os.path.exists(_FONT_PATH):
        try:
            pdfmetrics.registerFont(TTFont(_FONT_NAME, _FONT_PATH))
            _ACTIVE_FONT_NAME = _FONT_NAME
        except Exception:
            pdfmetrics.registerFont(UnicodeCIDFont(_FALLBACK_FONT_NAME))
            _ACTIVE_FONT_NAME = _FALLBACK_FONT_NAME
    else:
        pdfmetrics.registerFont(UnicodeCIDFont(_FALLBACK_FONT_NAME))
        _ACTIVE_FONT_NAME = _FALLBACK_FONT_NAME

    _FONT_REGISTERED = True
    return _ACTIVE_FONT_NAME


def _build_styles(font_name: str) -> dict[str, ParagraphStyle]:
    """按当前可用中文字体构建样式。"""
    return {
        "title": ParagraphStyle("Title", fontName=font_name, fontSize=18, alignment=1, spaceAfter=20),
        "section": ParagraphStyle("Section", fontName=font_name, fontSize=14, spaceAfter=8, spaceBefore=16),
        "body": ParagraphStyle("Body", fontName=font_name, fontSize=11, leading=16, spaceAfter=4),
    }


def _safe_text(value: object) -> str:
    """转义 ReportLab Paragraph 会解析的 XML 特殊字符。"""
    text = "" if value is None else str(value)
    if len(text) > _MAX_TEXT_LENGTH:
        text = f"{text[:_MAX_TEXT_LENGTH]}..."
    return escape(text)


def _paragraph(value: object, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_safe_text(value), style)


def _list_items(value: object) -> list[object]:
    if not isinstance(value, list):
        return []
    return value[:_MAX_LIST_ITEMS]


def _format_skills(value: object) -> str:
    if isinstance(value, list):
        return "、".join(str(item) for item in value[:_MAX_LIST_ITEMS])
    return "" if value is None else str(value)


def _append_list_section(story: list, title: str, items: object, styles: dict[str, ParagraphStyle]) -> None:
    """空数据则跳过。"""
    section_items = _list_items(items)
    if not section_items:
        return

    story.append(_paragraph(title, styles["section"]))
    for item in section_items:
        story.append(Paragraph(f"• {_safe_text(item)}", styles["body"]))
    story.append(Spacer(1, 8))


def _validate_output_path(output_path: str) -> None:
    path = Path(output_path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("PDF 报告输出路径必须以 .pdf 结尾")
    if not path.parent.exists():
        raise ValueError(f"PDF 报告输出目录不存在: {path.parent}")


def export_report_pdf(analysis_result: dict, output_path: str) -> str:
    """将 analyzer 返回的分析结果生成 PDF 报告。

    Args:
        analysis_result: analyzer.py 返回的分析结果 dict
        output_path: PDF 输出路径

    Returns:
        输出文件路径
    """
    _validate_output_path(output_path)
    font_name = _ensure_font_registered()
    styles = _build_styles(font_name)

    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    story: list = []

    # 标题
    story.append(_paragraph("简历分析报告", styles["title"]))
    story.append(Spacer(1, 12))

    # 基本信息表格
    basic = analysis_result.get("basic_info", {})
    if basic:
        story.append(_paragraph("基本信息", styles["section"]))
        table_data = [
            ["姓名", _paragraph(basic.get("name", ""), styles["body"])],
            ["学历", _paragraph(basic.get("education", ""), styles["body"])],
            ["工作年限", _paragraph(basic.get("years_of_experience", ""), styles["body"])],
            ["技能", _paragraph(_format_skills(basic.get("skills", [])), styles["body"])],
        ]
        table = Table(table_data, colWidths=[3 * cm, 13 * cm])
        table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("BACKGROUND", (0, 0), (0, -1), "#f0f0f0"),
            ("GRID", (0, 0), (-1, -1), 0.5, "#cccccc"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
        story.append(Spacer(1, 12))

    # 综合评分
    score = analysis_result.get("overall_score")
    if score is not None:
        story.append(_paragraph("综合评分", styles["section"]))
        story.append(_paragraph(f"{score} / 100", styles["body"]))
        story.append(Spacer(1, 8))

    _append_list_section(story, "优势", analysis_result.get("strengths", []), styles)
    _append_list_section(story, "不足", analysis_result.get("weaknesses", []), styles)
    _append_list_section(story, "优化建议", analysis_result.get("suggestions", []), styles)

    # 岗位匹配分析
    match = analysis_result.get("match_analysis")
    if match:
        story.append(_paragraph("岗位匹配分析", styles["section"]))
        story.append(_paragraph(match, styles["body"]))

    doc.build(story)
    return output_path
