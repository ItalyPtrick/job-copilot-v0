import pytest

from app.modules.resume.report_export import export_report_pdf


@pytest.fixture
def sample_result():
    """analyzer 返回的全字段完整结果。"""
    return {
        "basic_info": {
            "name": "张三",
            "education": "本科",
            "years_of_experience": 3,
            "skills": ["Python", "FastAPI", "SQL"],
        },
        "strengths": ["技术栈匹配度高", "项目经验丰富"],
        "weaknesses": ["缺少大厂经验"],
        "suggestions": ["补充系统设计知识", "增加开源贡献"],
        "overall_score": 78,
        "match_analysis": "整体匹配度较高，技术栈与岗位要求吻合。",
    }


def test_export_report_pdf_creates_file(sample_result, tmp_path):
    """生成文件存在且非空。"""
    output = tmp_path / "report.pdf"
    result_path = export_report_pdf(sample_result, str(output))

    assert result_path == str(output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_report_pdf_content(sample_result, tmp_path):
    """PyMuPDF 提取文本，验证关键字段写入了 PDF。"""
    import fitz  # PyMuPDF

    output = tmp_path / "report.pdf"
    export_report_pdf(sample_result, str(output))

    text = ""
    with fitz.open(output) as doc:
        for page in doc:
            text += page.get_text()

    assert "简历分析报告" in text
    assert "张三" in text


def test_export_report_pdf_empty_result(tmp_path):
    """最少字段时不崩溃。"""
    output = tmp_path / "minimal.pdf"
    result_path = export_report_pdf({}, str(output))

    assert result_path == str(output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_report_pdf_escapes_markup_characters(tmp_path):
    """LLM 输出可能含 <>&，验证不破坏生成。"""
    output = tmp_path / "escaped.pdf"
    result_path = export_report_pdf(
        {
            "basic_info": {
                "name": "李<四>&王五",
                "education": "本科",
                "years_of_experience": 2,
                "skills": ["Python", "A&B", "<SQL>"],
            },
            "strengths": ["熟悉 A<B & C>D"],
            "weaknesses": [],
            "suggestions": [],
            "overall_score": 80,
            "match_analysis": "可胜任 <后端> & 数据岗位",
        },
        str(output),
    )

    assert result_path == str(output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_report_export_import_does_not_register_font():
    """延迟注册：仅 import 模块不触发字体注册。"""
    import importlib

    from app.modules.resume import report_export

    reloaded = importlib.reload(report_export)

    assert reloaded._FONT_REGISTERED is False

    importlib.reload(report_export)


def test_export_report_pdf_falls_back_when_font_registration_fails(monkeypatch, sample_result, tmp_path):
    """验证字体文件存在但注册失败时回退到内置中文字体。"""
    from app.modules.resume import report_export

    output = tmp_path / "fallback.pdf"

    # 模拟字体文件存在但注册失败（如文件损坏），迫使走 except 回退
    def fail_on_font_registration(*args, **kwargs):
        raise OSError("bad font")

    monkeypatch.setattr(report_export.os.path, "exists", lambda path: path == report_export._FONT_PATH)
    monkeypatch.setattr(report_export, "TTFont", fail_on_font_registration)
    report_export._FONT_REGISTERED = False

    result_path = export_report_pdf(sample_result, str(output))

    assert result_path == str(output)
    assert report_export._ACTIVE_FONT_NAME == report_export._FALLBACK_FONT_NAME
    assert output.exists()
    assert output.stat().st_size > 0


def test_export_report_pdf_rejects_non_pdf_path(sample_result, tmp_path):
    """非 .pdf 后缀必须拒绝。"""
    with pytest.raises(ValueError, match=r"\.pdf"):
        export_report_pdf(sample_result, str(tmp_path / "report.txt"))


def test_export_report_pdf_rejects_missing_parent_dir(sample_result, tmp_path):
    """父目录不存在时必须报错，而非静默创建。"""
    missing_output = tmp_path / "missing" / "report.pdf"

    with pytest.raises(ValueError, match="输出目录不存在"):
        export_report_pdf(sample_result, str(missing_output))
