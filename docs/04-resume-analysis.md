# 简历智能分析模块

本模块实现多格式简历上传、解析、AI 智能分析、异步处理队列和 PDF 报告导出。对标 interview-guide 的简历管理模块。

---

## 1. 概念学习

### 文档解析

简历通常是 PDF 或 DOCX 格式，需要先提取纯文本才能送给 LLM 分析。

| 格式 | 解析库 | 特点 |
|---|---|---|
| PDF | PyMuPDF (fitz) | 速度快，支持表格/图片提取 |
| PDF | pdfplumber | 表格提取更好 |
| DOCX | python-docx | 微软 Word 格式，结构化提取 |
| TXT | 内置 open() | 直接读取 |

**本项目选择：** PyMuPDF（PDF）+ python-docx（DOCX），与 RAG 模块的 Document Loader 复用。

### 异步任务处理

简历分析涉及 LLM 调用（耗时 5-30 秒），不能让用户同步等待。需要异步处理：

```
用户上传简历 → 立即返回 "已收到，分析中"
    ↓ (后台)
Celery Worker 取出任务 → 解析文档 → 调用 LLM 分析 → 存储结果
    ↓
用户查询状态 → 返回 "已完成" + 分析结果
```

**为什么选 Celery？**

| 方案 | 优缺点 |
|---|---|
| **Celery + Redis** | 成熟稳定，支持重试/监控/定时任务，Python 事实标准 |
| asyncio.create_task | 简单但不持久化，worker 重启任务丢失 |
| Redis Stream 手动消费 | 灵活但需要自己实现重试/监控 |
| RQ (Redis Queue) | 轻量但功能少于 Celery |

interview-guide 用 Redis Stream 实现异步。我们用 Celery（功能更全，面试可讲的更多）。

### 重试机制

LLM API 可能超时或返回格式错误。需要重试策略：

```python
# Celery 内置重试
@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_resume_task(self, resume_id: str):
    try:
        # ... 分析逻辑
    except Exception as e:
        raise self.retry(exc=e)
```

interview-guide 的策略：最多重试 3 次，与我们的 Celery 配置一致。

### 内容哈希去重

避免同一份简历被重复分析（浪费 LLM 调用）：

```python
import hashlib

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
```

上传时计算内容哈希，如果数据库中已有相同哈希的记录，直接返回已有结果。

---

## 2. 技术选型

| 组件 | 选择 | 版本 | 理由 |
|---|---|---|---|
| PDF 解析 | PyMuPDF | 1.24+ | 速度快，功能全面 |
| DOCX 解析 | python-docx | 1.1+ | 标准库，稳定 |
| 异步任务 | Celery | 5.4+ | Python 异步任务事实标准 |
| 任务 Broker | Redis | 7+ | 复用现有 Redis |
| PDF 导出 | ReportLab | 4.2+ | 中文支持好，可编程性强 |
| 中文字体 | 思源黑体 / 文泉驿 | — | 开源免费 |

**新增依赖：**
```
celery>=5.4
reportlab>=4.2
pymupdf>=1.24
python-docx>=1.1
```

---

## 3. 与现有代码的集成点

### 新增文件

```
app/
├── modules/
│   └── resume/
│       ├── __init__.py
│       ├── router.py           # FastAPI 路由（/resume）
│       ├── service.py          # 简历业务逻辑
│       ├── parser.py           # 文档解析（PDF/DOCX/TXT）
│       ├── analyzer.py         # LLM 分析逻辑
│       ├── report_export.py    # PDF 报告导出
│       └── tasks.py            # Celery 异步任务
├── database/models/
│   └── resume.py               # 简历记录 SQLAlchemy 模型
celery_app.py                   # Celery 应用配置（项目根目录）
```

### 修改现有文件

| 文件 | 修改内容 |
|---|---|
| `app/main.py` | 注册 `/resume` 路由 |
| `requirements.txt` | 添加 celery, reportlab 等 |
| `.env` | 添加 `CELERY_BROKER_URL`（可复用 REDIS_URL） |

### 与现有功能的关系

- `resume_optimize` 任务（已有）可以复用简历解析结果
- 分析结果可以接入 RAG 知识库，作为面试准备的参考材料
- 评估报告可以与模拟面试评估报告使用相同的导出模板

---

## 4. 分步实现方案

### Step 1：简历解析器

```python
# app/modules/resume/parser.py
from pathlib import Path

def parse_pdf(file_path: str) -> str:
    """解析 PDF 文件"""
    import fitz  # PyMuPDF
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text.strip()

def parse_docx(file_path: str) -> str:
    """解析 DOCX 文件"""
    from docx import Document
    doc = Document(file_path)
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

def parse_txt(file_path: str) -> str:
    """解析 TXT 文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

PARSERS = {
    ".pdf": parse_pdf,
    ".docx": parse_docx,
    ".doc": parse_docx,
    ".txt": parse_txt,
}

def parse_resume(file_path: str) -> str:
    """统一入口：根据文件扩展名选择解析器"""
    ext = Path(file_path).suffix.lower()
    parser = PARSERS.get(ext)
    if not parser:
        raise ValueError(f"不支持的文件格式: {ext}")
    return parser(file_path)
```

### Step 2：LLM 分析器

```python
# app/modules/resume/analyzer.py
from app.services.llm_service import call_llm

def analyze_resume(resume_text: str, target_role: str = "") -> dict:
    """AI 分析简历"""
    system_prompt = """你是专业的简历分析师。分析以下简历内容，返回 JSON 格式的结构化分析报告：
{
  "basic_info": {
    "name": "姓名",
    "education": "最高学历",
    "years_of_experience": "工作/项目年限",
    "skills": ["技能1", "技能2", ...]
  },
  "strengths": ["亮点1", "亮点2", ...],
  "weaknesses": ["不足1", "不足2", ...],
  "suggestions": ["优化建议1", "优化建议2", ...],
  "overall_score": 1-100 的评分,
  "match_analysis": "与目标岗位的匹配度分析（如果提供了目标岗位）"
}
"""
    payload = {"resume_text": resume_text}
    if target_role:
        payload["target_role"] = target_role

    return call_llm(system_prompt, payload)
```

### Step 3：Celery 配置与异步任务

```python
# celery_app.py（项目根目录）
import os
from celery import Celery

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")

celery = Celery("job_copilot", broker=CELERY_BROKER_URL)
celery.conf.update(
    result_backend=CELERY_BROKER_URL,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    task_track_started=True,
)

# 自动发现任务
celery.autodiscover_tasks(["app.modules.resume"])
```

```python
# app/modules/resume/tasks.py
import hashlib
from celery_app import celery
from app.modules.resume.parser import parse_resume
from app.modules.resume.analyzer import analyze_resume

@celery.task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_resume_task(self, resume_id: str, file_path: str, target_role: str = ""):
    """异步简历分析任务"""
    try:
        # 1. 解析文档
        text = parse_resume(file_path)

        # 2. 内容哈希去重（检查数据库是否已有相同内容的分析）
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        # TODO: 查询数据库是否已有 content_hash 相同的记录

        # 3. LLM 分析
        result = analyze_resume(text, target_role)

        # 4. 存储结果到数据库
        # TODO: 更新 resume 记录的 status 和 result

        return {"status": "success", "resume_id": resume_id, "result": result}

    except Exception as e:
        # 重试
        raise self.retry(exc=e)
```

### Step 4：PDF 报告导出

```python
# app/modules/resume/report_export.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# 注册中文字体（需要提前下载放到 fonts/ 目录）
FONT_PATH = os.path.join(os.path.dirname(__file__), "../../../fonts")
if os.path.exists(os.path.join(FONT_PATH, "SourceHanSans-Regular.ttf")):
    pdfmetrics.registerFont(TTFont("Chinese", os.path.join(FONT_PATH, "SourceHanSans-Regular.ttf")))

def export_resume_report(analysis: dict, output_path: str):
    """将分析结果导出为 PDF 报告"""
    doc = SimpleDocTemplate(output_path, pagesize=A4)
    styles = getSampleStyleSheet()

    # 如果有中文字体，使用中文样式
    cn_style = ParagraphStyle("Chinese", parent=styles["Normal"], fontName="Chinese", fontSize=12)
    cn_title = ParagraphStyle("ChineseTitle", parent=styles["Title"], fontName="Chinese", fontSize=18)

    elements = []

    # 标题
    elements.append(Paragraph("简历分析报告", cn_title))
    elements.append(Spacer(1, 1 * cm))

    # 基本信息
    basic = analysis.get("basic_info", {})
    elements.append(Paragraph(f"姓名: {basic.get('name', '未知')}", cn_style))
    elements.append(Paragraph(f"学历: {basic.get('education', '未知')}", cn_style))
    elements.append(Paragraph(f"综合评分: {analysis.get('overall_score', 'N/A')}/100", cn_style))
    elements.append(Spacer(1, 0.5 * cm))

    # 亮点
    elements.append(Paragraph("亮点:", cn_style))
    for s in analysis.get("strengths", []):
        elements.append(Paragraph(f"  • {s}", cn_style))
    elements.append(Spacer(1, 0.5 * cm))

    # 改进建议
    elements.append(Paragraph("优化建议:", cn_style))
    for s in analysis.get("suggestions", []):
        elements.append(Paragraph(f"  • {s}", cn_style))

    doc.build(elements)
    return output_path
```

### Step 5：FastAPI 路由

```python
# app/modules/resume/router.py
from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
import shutil, os, uuid

router = APIRouter(prefix="/resume", tags=["简历分析"])

UPLOAD_DIR = "./data/resumes"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    target_role: str = Form(default=""),
):
    """上传简历并触发异步分析"""
    resume_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename)[1]
    save_path = os.path.join(UPLOAD_DIR, f"{resume_id}{ext}")

    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 触发异步分析
    from app.modules.resume.tasks import analyze_resume_task
    analyze_resume_task.delay(resume_id, save_path, target_role)

    return {
        "resume_id": resume_id,
        "status": "analyzing",
        "message": "简历已上传，正在分析中...",
    }

@router.get("/{resume_id}/status")
async def get_resume_status(resume_id: str):
    """查询分析状态"""
    # TODO: 从数据库查询状态
    return {"resume_id": resume_id, "status": "analyzing"}

@router.get("/{resume_id}/report")
async def get_resume_report(resume_id: str):
    """获取分析结果"""
    # TODO: 从数据库查询结果
    return {"resume_id": resume_id, "result": {}}

@router.get("/{resume_id}/export")
async def export_resume_report_pdf(resume_id: str):
    """导出 PDF 报告"""
    # TODO: 从数据库获取分析结果，生成 PDF
    output_path = f"./data/reports/{resume_id}.pdf"
    # from app.modules.resume.report_export import export_resume_report
    # export_resume_report(analysis, output_path)
    return FileResponse(output_path, filename=f"resume_report_{resume_id}.pdf")
```

---

## 5. 测试方案

```python
# tests/test_resume.py
import pytest
from pathlib import Path

def test_parse_txt():
    """测试 TXT 简历解析"""
    from app.modules.resume.parser import parse_resume

    test_file = Path("tests/fixtures/test_resume.txt")
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("张三\n学历：本科\n技能：Python, FastAPI", encoding="utf-8")

    text = parse_resume(str(test_file))
    assert "张三" in text
    assert "Python" in text

def test_content_hash():
    """测试内容哈希去重"""
    import hashlib
    text = "测试简历内容"
    hash1 = hashlib.sha256(text.encode()).hexdigest()
    hash2 = hashlib.sha256(text.encode()).hexdigest()
    assert hash1 == hash2  # 相同内容哈希一致

def test_analyze_resume_structure():
    """测试分析结果结构（需要 LLM API）"""
    from app.modules.resume.analyzer import analyze_resume

    result = analyze_resume("张三，本科，3年Python开发经验", "Python开发工程师")
    assert "basic_info" in result or "error" in result
```

### 验证命令

```bash
# 运行简历相关测试
pytest tests/test_resume.py -v

# 启动 Celery Worker（单独终端）
celery -A celery_app worker --loglevel=info

# 上传简历测试
curl -X POST http://localhost:8000/resume/upload \
  -F "file=@your_resume.pdf" \
  -F "target_role=Python开发工程师"
```

---

## 6. 面试要点

### 常见问题

**Q: 简历分析为什么要异步处理？**
> LLM 调用耗时 5-30 秒，同步处理会让用户一直等待，HTTP 连接可能超时。异步处理让用户立即得到"分析中"的反馈，后台 Celery Worker 完成分析后更新状态。用户可以通过轮询或 WebSocket 获取结果。

**Q: Celery 的重试机制是怎么工作的？**
> `@celery.task(max_retries=3, default_retry_delay=10)` 表示最多重试 3 次，每次间隔 10 秒。在 task 中 `raise self.retry(exc=e)` 触发重试。Celery 还支持指数退避（exponential backoff）策略。如果 3 次都失败，任务标记为 FAILURE，更新数据库状态为"分析失败"。

**Q: 内容哈希去重的作用？**
> 避免同一份简历被重复分析。上传时计算文本的 SHA-256 哈希，查数据库是否已有相同哈希的分析记录。如果有，直接返回已有结果，节省 LLM 调用成本。

**Q: PDF 导出的中文支持怎么做的？**
> ReportLab 默认不支持中文。需要注册中文字体（如思源黑体），在样式中指定字体名称。interview-guide 用 iText + 珠圆玉润仿宋字体，思路一致。

### 能讲出的亮点

- **异步处理管道**：Celery + Redis 实现简历分析队列，支持进度查询
- **自动重试**：LLM 调用失败自动重试 3 次，提高可靠性
- **内容哈希去重**：避免重复分析相同简历
- **多格式统一解析**：PDF/DOCX/TXT 统一处理管道
- **PDF 报告导出**：结构化分析结果 → 可下载的 PDF 报告
