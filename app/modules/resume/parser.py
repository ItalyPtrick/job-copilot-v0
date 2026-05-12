"""简历文档解析器 — PDF/DOCX/TXT 统一入口"""
from pathlib import Path


def parse_pdf(file_path: str) -> str:
    """解析 PDF 文件，提取全部页面文本"""
    import fitz  # PyMuPDF

    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()


def parse_docx(file_path: str) -> str:
    """解析 DOCX 文件，拼接非空段落"""
    from docx import Document

    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def parse_txt(file_path: str) -> str:
    """解析 TXT 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()


# 策略模式：扩展名 → 解析函数
# .doc 是旧版 Word 格式，python-docx 不支持，故不纳入
PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".txt": parse_txt,
}


def parse_resume(file_path: str) -> str:
    """统一入口：根据文件扩展名选择解析器"""
    ext = Path(file_path).suffix.lower()
    parser = PARSERS.get(ext)
    if not parser:
        raise ValueError(f"不支持的文件格式: {ext}")
    return parser(file_path)
