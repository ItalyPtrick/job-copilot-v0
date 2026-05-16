# 设计决策笔记

> 项目开发过程中的技术选型、架构权衡、踩坑解决记录。面试前回顾此文件。

---

## 知识库（W2）

### RAG 基础设施选型

- **问题**：W2 需要快速打通知识库索引、检索和生成链路，先定基础设施。
- **解法**：`langchain + langchain-openai + chromadb`。LangChain 提供统一的 Document / Splitter / Retriever 抽象，ChromaDB 本地持久化零运维。
- **为什么不用其他方案**：pgvector 需要 PostgreSQL 实例，部署和调试成本高于当前原型阶段需要；LlamaIndex 的抽象层级更高但灵活性不如 LangChain 的 LCEL 组合方式。后续如果需要统一数据库运维，再迁移到 pgvector。

### 百炼 Embedding API 适配

- **问题**：阿里云百炼兼容接口与 LangChain `OpenAIEmbeddings` 默认行为不完全兼容。
- **踩坑**：最初直接用 `OpenAIEmbeddings` 默认配置对接百炼，写入 Chroma 时报 tiktoken 编码错误——百炼不支持客户端预分词。第二次尝试关闭 `check_embedding_ctx_length` 后单条能过，但批量 embed 超过 10 条时 API 返回 400。
- **解法**：两个参数配合——`check_embedding_ctx_length=False` 禁用客户端 token 预切分（百炼不支持 tiktoken 分词），`chunk_size=10` 限制每批发送条数（百炼单次上限 10 条）。
- **为什么这样够用**：上游已做文档切块，embedding 输入本就是小块字符串，不需要客户端再切分；分批对性能影响 <100ms（I/O bound，非 CPU bound）。

### 文档加载与切块策略

- **问题**：知识库文档格式不一，embedding 和检索要求输入块大小可控、来源可追踪。
- **解法**：`document_loader.py` 按扩展名选 Loader 统一转 `Document`，再用 `RecursiveCharacterTextSplitter`（chunk_size=500, overlap=100）递归分块，每个 chunk 补 `chunk_index` + `source_file` 元数据。
- **为什么选这个参数**：500 字符约 200-250 中文字，一个完整段落的典型长度；overlap=100 保证跨块边界的句子不丢失语义。`RecursiveCharacterTextSplitter` 优先按段落/句子边界切，只有超长内容才强制切分，比固定长度切分语义断裂更少。

### 上传幂等与数据一致性

- **问题**：同一份文件重复上传会重复调用 embedding API（费用浪费）+ 向量库留重复记录；向量写入和 DB 记录无法原子完成。
- **踩坑**：V1 只做了 file_hash 唯一约束。上线后两个问题暴露：① 两个请求同时上传同文件，第二个在 hash 查询和 INSERT 之间的窗口通过了检查，导致向量库出现重复 chunk；② 用户改了简历里一个错别字重新上传，hash 不同绕过去重，知识库内容膨胀。
- **解法**：三层防护——
  1. `(collection_name, file_hash)` 唯一约束，upload 前先算 SHA-256 查库（<5ms），命中 `completed` 直接返回 `reused: true`，节省一次完整 embedding 调用链（10+ chunk × embedding API）
  2. 两阶段 commit：先插 `uploading` 占位（唯一约束立即拦并发）→ 分块 + 向量写入 → 更新 `completed`。失败保留 `failed` + 补偿删向量
  3. 近重复确认：文件级 SimHash 指纹检测高度相似文档，命中返回 `confirmation_required`，用户带 `confirm_upload=true` 重试后才入库
- **为什么分三层**：file_hash 拦完全重复（零成本）；两阶段 commit 解决写入原子性（占位让不一致窗口从整个上传缩短到两次 commit 之间）；SimHash 拦"改了几个字就重传"的场景（避免知识库内容膨胀）。三层各自独立，任一层失败不影响其他层。
  - **子：failed 记录可重试** — `failed` 占住唯一约束会导致重传永远 409。解法：创建新占位前先 DELETE 同 hash 的 `failed` 记录释放名额。旧 failed 记录的排查价值在用户主动重传时已失效。
  - **子：并发冲突处理** — 两个请求同时上传同文件，第二个的 `uploading` commit 触发 `IntegrityError` → 返回 409。不需要分布式锁，数据库约束本身就是最可靠的并发控制。

### RAG 问答链输出边界

- **问题**：非流式和流式两条链路的职责容易混淆。
- **解法**：明确分工——`rag_query()` 一次性返回 `answer + sources`；`rag_query_stream()` 只输出文本 chunk（SSE `event: message` + `event: done`），不在流式路径返回 sources。检索阶段用 `asyncio.to_thread` 避免阻塞事件循环，但对当前请求仍是"先检索后生成"的串行语义。
- **为什么流式不返回 sources**：流式的价值是逐 chunk 推送让用户感知快，sources 是结构化元数据不适合混在文本流里。如果后续需要，在路由层单独扩展 SSE 事件类型，不改底层 chain。

---

## 模拟面试（W3）

### Session 暂存 Redis

- **问题**：模拟面试是多轮短生命周期状态，需要高频读写 config / messages / 题序 / 表现记录。
- **解法**：`session_manager.py` 复用现有 `redis_client`，key 前缀 `interview:session:`，session 整体 JSON 序列化存取，TTL 7200 秒。`current_question_index` 始终等于 `questions_asked` 长度作为不变量。
- **为什么不用数据库**：面试 session 生命周期短（最多 2 小时）、读写频率高（每次回答都更新）、过期后无保留价值。Redis 天然适合这类场景。把整份 session 作为单对象存取，避免提前陷入关系型拆表设计，D2 阶段的关注点是"多轮会话能否稳定创建/读取/更新"。

### Skill 蓝图化出题

- **问题**：每轮出题都传完整 Skill Markdown 会重复消耗上下文 token，也不利于控制难度和避免重复题。
- **解法**：`build_skill_blueprint` 从 Markdown 提取 topics / difficulty_distribution / difficulty_rubric；`generate_question` 只注入蓝图摘要 + 目标难度 rubric + 已问题目 + 已覆盖考点。返回结构用 `InterviewQuestion` schema 校验，包含 `difficulty_reason` 和 `assessment_focus` 为评估引擎提供上下文。
- **为什么不每次传全文**：全文约 2000 token，5 题面试重复传 5 次浪费 ~7500 token（约 ¥0.03）；更关键的是 prompt 越长注意力越稀释，出题质量反而下降。蓝图化后每次 prompt 约 500 token，且能精确控制"这次该出什么难度、什么考点"。
  - **子：Skill 文件外置** — 面试方向定义用 Markdown 文件（`app/skills/python_backend.md`），新增方向只需加文件不改代码。Markdown 易读易维护，也方便面试时展示系统的可配置性。

### 评估引擎按主问题轮次评分

- **问题**：追问策略让一道主问题下有 0~N 条追问，如果等权处理每条 assistant 问句，追问会被当独立题重复计分。
- **解法**：以"主问题轮次"为评估单元——一道主问题 + 初答 + 追问链归为一个 turn，LLM 综合评分。评估引擎保持无状态纯函数链路：`messages → _extract_interview_turns → evaluate_batch → generate_report`。每批评审 `_BATCH_SIZE=3` 个轮次，5 题面试分 2 次 LLM 调用，单次 prompt ~1500 token。
- **为什么按 turn 而非按消息**：真实面试官不会把追问当新题打分，而是综合主答和追问表现给总评。无状态设计让 evaluation 可独立测试，不耦合 session 管理或数据库。
  - **子：消息契约 InterviewMessageMetadata** — assistant 消息带 `question_type`(main/follow_up) + `question_id` + `parent_question_id`；user 消息带 `answer_to_question_id`。三个模块（出题/评估/路由）共享同一套协议，避免各自猜测消息格式。
  - **子：LLM 解析失败降级** — `evaluate_batch` 按 batch_size=3 分批调用 LLM，某批解析失败时 warning + skip，不拖垮其他批次。用户仍能获得部分有效评估结果。
  - **子：question_id 映射修复** — prompt 给了 UUID 但 LLM 可能返回序号。**踩坑**：最初 prompt 只在末尾列出 UUID 列表，实测发现 LLM 稳定返回 `"question_id": "1"` / `"2"` 序号而非 UUID，导致评分无法关联回具体题目。双层防御：prompt 中每道题前标注实际 UUID 引导正确返回 + `_parse_evaluations` 增加序号→UUID 兜底映射。

### 自适应追问 planner

- **问题**：`/interview/answer` 需要决定"追问/下一题/结束"，但出题引擎和评估引擎都不包含这个决策逻辑。
- **解法**：`interview_planner.py` 作为纯函数决策层，输入 session 状态 + 最新回答，输出 `next_action` + `next_difficulty` + `performance_signal`。规则：追问次数未满且回答非 strong → follow_up；否则 next_question；主问题出完 → complete。难度基于最近表现信号调节，最多调一档。
- **为什么用纯函数而非 LLM 决策**：决策逻辑是确定性规则（次数、表现阈值），不需要 LLM 的灵活性；纯函数可单元测试、无 API 成本、响应延迟 <1ms（vs LLM 决策 ~1.5-2s + ~500 token/次）。把"何时追问"和"追问什么"分开——前者是规则，后者才需要 LLM。
  - **子：session 扩展字段** — 新增 `current_main_question` / `current_follow_up_count` / `covered_topics` / `recent_performance`（最近 3 轮）。这些是 planner 决策输入，放 session 比每次从 messages 重新推导更高效。`_normalize_session_data` 对新字段做向后兼容（缺失给默认值），旧 session 不会报错。

### 路由层 session 回滚

- **问题**：`/interview/answer` 链路较长（追加消息 → 评估 → planner → 出题），中途异常时 session 已被部分修改，写回 Redis 会导致下次请求基于不一致状态继续。
- **解法**：进入 try 块前拷贝 `original_messages` 和 `original_recent_performance` 快照；异常时用快照回滚 session 再写回 Redis，然后抛 503。
- **为什么不用事务**：Redis 没有跨 key 事务语义，session 是单 key JSON 整体覆写。快照回滚是最简单有效的方式——用户可以重新提交同一回答，不会产生重复消息或题序错乱。

### call_llm 统一异常处理

- **问题**：`call_llm` 是出题、追问、评估的共同底层，LLM API 可能抛网络超时、限流、认证失败等异常。
- **解法**：在 `call_llm` 内部统一捕获 `APIError` / `APIConnectionError` / `RateLimitError` / `AuthenticationError` + choices 为空，返回 `{"error": "...", "raw": ""}` 结构化错误对象。调用方只需检查返回值是否含 `error` 字段。
- **为什么收敛到一个出口**：避免每个调用方各自写 try/except 且覆盖不全。错误信息保留异常类型名便于日志排查；`raw` 为空字符串而非 None，避免下游 `str(None)` 隐性 bug。

### 面试邀请解析器合并策略

- **问题**：面试邀请文本包含格式化字段（时间/链接）和自由文本字段（公司/岗位/面试官），两类信息的最佳提取方式不同。
- **解法**：三层结构——`parse_invite_rule_based` 用正则提取时间和会议链接；`parse_invite_ai` 调用 LLM 提取公司/岗位/面试官；`parse_invite` 合并时规则结果优先，AI 只补充空位。
- **为什么规则优先而非全交给 LLM**：时间和链接是硬字段，正则确定性高、零 API 成本；LLM 对这类格式化数据反而容易"创造性发挥"（比如把会议号拼成假 URL）。规则兜底 + AI 补充，比纯 AI 更可靠也更便宜。

---

## 简历分析（W4）

### PDF 解析库选型：PyMuPDF

- **问题**：简历解析需要从 PDF 提取文本，Python 生态有 PyMuPDF / pdfplumber / PyPDF2。
- **解法**：选用 PyMuPDF (fitz)，`page.get_text()` 逐页提取，3 行代码完成。
- **为什么不用其他库**：PyMuPDF 基于 C 底层解析速度最快，中文 PDF 支持好；pdfplumber 擅长表格提取但简历场景不需要表格结构化，且速度更慢；PyPDF2 已停止维护（2023 年归档）。

### 结构化 Prompt 的 JSON schema 约束

- **问题**：LLM 分析简历后需要返回可程序化处理的结构化数据。
- **解法**：system prompt 中直接给出完整 JSON schema 示例（字段名 + 类型 + 取值范围），末尾加"只返回 JSON"约束。复用 `call_llm` 已有的 markdown 代码块清理 + `json.loads` 解析。
- **为什么不用 function calling / response_format**：直接 prompt 约束对任意兼容端点（DeepSeek、百炼等）通用性最好，不依赖 OpenAI 特有功能。`call_llm` 已有容错解析兜底，偶尔格式异常时返回 `{"error": "格式异常"}` 而非崩溃。后续如果切到原生支持 structured output 的模型，可以无缝升级。

### Alembic 迁移 NOT NULL 字段的 backfill 策略

- **问题**：`ResumeRecord` 新增 `filename` / `content_hash` / `status` 三个 NOT NULL 字段，SQLite 不允许对已有行直接 `ADD COLUMN ... NOT NULL`。
- **踩坑**：最初写 `op.add_column(Column('filename', String(255), nullable=False))`，`alembic upgrade head` 直接报错——SQLite 不允许对已有数据的表添加 NOT NULL 列（没有 DEFAULT 值时无法填充历史行）。
- **解法**：迁移脚本分三阶段——① nullable=True 添加字段；② backfill 历史行（filename='legacy_resume'，status='pending'，content_hash=sha256('legacy-resume-record:{id}') 确保唯一）；③ alter_column 改 NOT NULL + 建唯一索引。
- **为什么不直接 server_default**：SQLite 的 `ALTER TABLE ADD COLUMN` 支持 server_default，但 content_hash 需要每行唯一值（不能用固定默认值），必须逐行计算。三阶段策略兼容空表（新部署直接通过）和有数据表（已运行环境安全迁移）。

### 简历分析去重：content_hash 幂等

- **问题**：同一份简历重复上传会重复调用 LLM 分析（单次约 2000 input + 500 output token），浪费 API 费用且产生重复记录。
- **踩坑**：最初按 filename 去重，但用户经常用相同文件名上传不同版本简历，导致新版本被误判为重复。
- **解法**：上传接口只保存原文件、创建 `pending` 记录并提交 Celery 任务；去重发生在 Worker 内部。任务先用 `parser.py` 提取 raw_text，再对 `{raw_text, target_role}` 做结构化 JSON 编码后计算 SHA-256，写入带唯一索引的 `content_hash` 字段。命中 `completed` 记录时直接复用分析结果；命中 `pending/analyzing` 记录时短延迟重试等待；命中 `failed` 记录时释放旧记录占用的 hash，让新记录重新分析。
- **为什么 hash 文本 + 目标岗位而非文件二进制**：同一份简历的 PDF 元数据（创建时间、PDF 版本号）可能不同导致二进制 hash 不同，但文本内容完全一致；同时同一简历投递不同岗位时，LLM 的匹配度分析应不同，必须把 `target_role` 纳入 hash。对提取后的文本和目标岗位一起 hash，能识别“内容与岗位都相同”的重复任务，也不会误复用不同岗位的分析结果。

### Parser 策略模式与格式边界

- **问题**：简历文件格式多样（PDF/DOCX/TXT），需要统一入口但各格式解析逻辑完全不同。
- **解法**：`PARSERS = {".pdf": parse_pdf, ".docx": parse_docx, ".txt": parse_txt}` 扩展名→函数映射，`parse_resume()` 统一入口按后缀分发。新增格式只需加一个函数 + 一行映射。
- **为什么不支持 .doc**：.doc 是 OLE2 二进制格式，python-docx 只支持 .docx（Office Open XML）。支持 .doc 需要引入 `antiword` 或 `libreoffice` 命令行依赖，对当前原型阶段引入的运维复杂度不值得。明确拒绝（raise ValueError）比静默失败更好。
- **为什么不用 unstructured 库**：unstructured 是重量级依赖（安装体积 >500MB，依赖 poppler/tesseract），简历场景只需要纯文本提取，3 行 PyMuPDF 代码足够。YAGNI。

### Celery 异步架构：Broker 隔离与 Windows 适配

- **问题**：简历 LLM 分析耗时 10-30 秒，同步执行会阻塞 API 请求。
- **解法**：Celery + Redis 做异步任务队列。Broker 和 Result Backend 均用 Redis DB 1，与主应用缓存（DB 0）隔离，避免任务消息与业务缓存 key 冲突。Worker 独立进程执行，API 只负责 `task.delay()` 提交和状态查询。
- **为什么选 Celery 而非 asyncio.create_task**：`create_task` 是进程内协程，进程重启任务丢失、无自动重试、无监控面板。Celery 提供：① 队列化投递（Redis broker，可通过 Redis 持久化配置提升崩溃恢复能力）；② 内置重试机制（`max_retries=3, default_retry_delay=10`，LLM 偶发超时自动恢复）；③ DB 状态追踪（任务写回 `resume_records.status`，API 通过 DB 查询状态）；④ 生产可扩展（多 Worker 水平扩展、Flower 监控）。对求职项目来说，"面试时能讲清异步架构全貌"比"少一个依赖"更有价值。
- **为什么用 Redis DB 1 而非独立 Redis 实例**：单机开发阶段无需额外进程，DB 编号隔离足够；生产环境可通过环境变量切换到独立实例，零代码改动。
  - **Windows 约束**：Celery 4+ 不支持 Windows 多进程 prefork pool，开发环境用 `--pool=solo`（单进程顺序执行）。不影响功能正确性，仅吞吐量受限；部署到 Linux 时切回默认 prefork 即可。
  - **去重竞态处理**：`content_hash` 列 unique 约束 + `update_content_hash` 返回 bool。并发任务解析出相同内容时，后到者 commit 触发 IntegrityError → rollback → Celery 短延迟重试；下一次执行会重新查询相同 `content_hash`，若先到任务已 completed，则直接复用结果。若先到任务 failed，则释放 failed 记录占用的 hash，让后到任务重新分析，避免永久 pending、重复 LLM 调用和 failed 记录长期占住去重键。

### ResumeRecord 外部标识：UUID resume_id

- **问题**：异步任务提交后需要立即返回可查询的 ID，但自增 `id` 在 `db.commit()` 后才确定，无法在 `task.delay()` 前使用。
- **解法**：新增 `resume_id` 字段（UUID4 字符串），由路由层在提交前生成，作为任务追踪和 API 查询的唯一标识。自增 `id` 保留为内部主键。
- **为什么不直接用 UUID 做主键**：SQLite 对整数主键有 rowid 优化，UUID 主键会导致 B-tree 随机插入和索引膨胀。外部标识和内部主键分离，各取所长。

### PDF 报告生成：ReportLab + 中文字体延迟注册

- **问题**：LLM 分析结果需要导出为可下载的 PDF 报告，中文内容必须正确渲染。
- **解法**：ReportLab 的 `SimpleDocTemplate` + `Paragraph` + `Table` 组合排版，生成 PDF 时延迟注册中文字体。Windows 下优先使用 `C:\Windows\Fonts\simhei.ttf`，缺失或注册失败时回退到 ReportLab 内置 `STSong-Light`，避免模块导入阶段因字体问题崩溃。LLM 文本进入 `Paragraph` 前统一 XML 转义，避免 `<`、`&` 等字符触发 ReportLab 标记解析。
- **为什么不用 WeasyPrint / wkhtmltopdf**：ReportLab 纯 Python 实现无外部系统依赖（WeasyPrint 依赖 Cairo/Pango，wkhtmltopdf 需要 Qt WebKit），对服务端异步生成场景部署最轻量。ReportLab 对 PDF 布局的精确控制也更适合固定模板式报告。
  - **字体选择**：SimHei（黑体）是 Windows 系统自带字体，覆盖率高，笔画均匀在小字号下可读性好。SimSun（宋体）衬线在屏幕 PDF 阅读器中渲染效果不如黑体。

---

## Docker 部署（W5）

### 基础镜像选择：python:3.11-slim

- **问题**：容器化需要选 Python 基础镜像。
- **解法**：`python:3.11-slim`，基于 Debian slim 变体，比完整版小 ~800MB。
- **为什么不用 alpine**：Alpine 用 musl libc，PyMuPDF / psycopg2 等 C 扩展需要额外编译适配，构建时间反而更长。slim 版够用，兼容性好。

### Dockerfile 分层缓存策略 + multi-stage build + uv

- **问题**：每次 `docker build` 如果重新安装全部依赖，构建时间 >5 分钟（pip 依赖解析慢 + 下载慢）。
- **解法**：Dockerfile 改为两阶段构建——Stage 1 (builder) 临时安装 uv 并安装依赖，随后卸载 uv；Stage 2 (runtime) 通过 `COPY --from=builder /usr/local /usr/local` 复制已安装的运行依赖。uv 是 Rust 写的 pip 替代品，依赖解析从几分钟降到数秒，整体构建从 500s+ 降到约 150s。`--mount=type=cache,target=/root/.cache/uv` 跨构建保留下载缓存。
- **踩坑**：如果只在 builder 里 `pip install uv`，再把 `/usr/local` 整体复制到 runtime，uv 也会进入最终镜像。安装依赖后执行 `pip uninstall -y uv`，让“runtime 不含 uv”的设计与镜像内容一致。
- **为什么用 multi-stage**：运行镜像只保留运行依赖和应用代码，不保留构建期工具，体积更小、攻击面更小。

### 依赖瘦身：移除 Streamlit 及专属依赖

- **问题**：`requirements.txt` 包含 Streamlit 及其 27 个专属依赖（altair/pandas/numpy/pyarrow 等），Docker 构建时 pip install 耗时 >5 分钟，且这些包在后端服务中完全不使用。
- **解法**：移除 streamlit 及仅被 streamlit 使用的 10 个直接依赖（altair/blinker/cachetools/gitdb/GitPython/narwhals/pydeck/smmap/tornado/watchdog），以及 17 个数据栈残留包。构建上下文从 1.73MB 降到 100KB。
- **为什么移除而非拆分 requirements**：Streamlit 前端本地运行即可（`streamlit run`），不需要打包进后端镜像。单一 requirements.txt 维护成本最低，后续需要 Streamlit 时单独加回。

### .dockerignore 提前创建

- **问题**：Docker 构建上下文扫描 `.pytest_tmp` 目录时遇到 Windows 权限错误（Access is denied），导致构建失败。
- **踩坑**：原计划 D2 创建 .dockerignore，但 D1 构建时就需要。
- **解法**：将 .dockerignore 创建提前到 D1，排除 `.git`/`.env`/`__pycache__`/`.pytest_tmp`/`data/`/`*.db` 等目录。

### docker-compose 服务编排

- **问题**：项目有 4 个服务（FastAPI API、Celery Worker、PostgreSQL、Redis），需要一键启动并控制启动顺序。
- **解法**：`docker-compose.yml` 定义 4 个服务 + 4 个命名卷。api 和 worker 共用 Dockerfile，worker 覆盖 `command` 启动 Celery。postgres/redis 配 `healthcheck`，api/worker 用 `depends_on` + `condition: service_healthy` 确保依赖就绪后再启动。
- **为什么用 PostgreSQL 替换 SQLite**：SQLite 是文件级数据库，容器内多进程（api + worker）并发写入有锁冲突风险；PostgreSQL 是服务级数据库，天然支持并发。Docker 环境下 PostgreSQL 零额外运维成本（Compose 一条命令启动），且与生产环境一致。
  - **踩坑**：`psycopg2-binary` 未在 requirements.txt 中，首次启动报 `ModuleNotFoundError: No module named 'psycopg2'`。SQLAlchemy 的 PostgreSQL 方言依赖此驱动。
- **环境变量覆盖**：`environment` 中的 `DATABASE_URL` / `REDIS_URL` / `CELERY_BROKER_URL` 覆盖 `.env` 中的本地值，容器内用服务名（`postgres:5432`、`redis:6379`）通信，不用 localhost。
- **移除 `version: "3.8"`**：Compose V2 已废弃 version 属性，保留会产生 warning。

### SQLAlchemy 多数据库适配

- **问题**：本地开发用 SQLite，Docker 部署用 PostgreSQL，代码层需要兼容两种数据库。
- **解法**：`connection.py` 根据 `DATABASE_URL` 前缀判断是否为 SQLite，条件添加 `check_same_thread=False`；`alembic/env.py` 从环境变量读取 DATABASE_URL 覆盖 alembic.ini 的硬编码值；移除 `.dockerignore` 中对 `alembic.ini` 的误排除，确保容器内可运行迁移。
- **为什么不用 SQLAlchemy 的 `connect_args` 自动检测**：SQLAlchemy 不会自动为 SQLite 添加 `check_same_thread`，这是 Python sqlite3 模块的限制（默认不允许跨线程共享连接），必须显式设置。
  - **踩坑**：`.dockerignore` 误排 `alembic.ini`，容器内 `alembic upgrade head` 报 `No 'script_location' key found`。移除排除项后解决。
  - **踩坑**：PostgreSQL 容器首次启动时表已存在（D1 手动创建），`alembic upgrade head` 报 `DuplicateTable`。用 `alembic stamp head` 标记当前状态解决。

### Volume 权限与 entrypoint 脚本

- **问题**：Dockerfile 中 `USER appuser` 切换非特权用户后，Docker named volume 挂载的 `data/uploads`、`data/resumes`、`data/chroma` 目录仍由 root 拥有，容器内文件上传全部报 `PermissionError`。
- **踩坑**：Dockerfile 中 `chown -R appuser:appuser /app` 只影响镜像层，volume 挂载发生在容器启动时，覆盖镜像中的目录权限。
- **解法**：新增 `docker-entrypoint.sh`，以 root 运行 `mkdir -p` + `chown -R` 确保 volume 目录可写，再 `gosu appuser` 切换到非特权用户执行 CMD。Dockerfile 中 `ENTRYPOINT` 放在 `USER appuser` 之前，确保 entrypoint 以 root 身份运行。
- **为什么用 gosu 而非 su/sudo**：`gosu` 专为容器设计，直接 exec 替换进程（无 shell 包裹），信号传递正确；`su` 会残留父 shell 进程，`sudo` 需要额外配置。

### 健康检查端点：/health

- **问题**：Docker Compose healthcheck 原来用 `urllib.request.urlopen('http://localhost:8000/')` 检查根路径，只验证进程存活，不验证 PG/Redis 连通性。
- **解法**：新增 `GET /health` 端点，分别执行 `SELECT 1`（PG）和 `redis_client.ping()`（Redis），任一异常返回 503。PostgreSQL 连接设置 `connect_timeout=3`，Redis 设置 `socket_timeout=3`，docker-compose.yml healthcheck 指向 `/health` 且 `urlopen(..., timeout=4)`。
- **为什么不在根路径做 healthcheck**：根路径只验证 uvicorn 进程活着，PG 连接池耗尽或 Redis 宕机时根路径仍返回 200，但服务实际不可用。`/health` 验证依赖组件连通性，让 Compose 的 `depends_on: condition: service_healthy` 真正生效。
  - **踩坑**：`redis.from_url()` 默认无 socket_timeout，`ping()` 在 Redis 未就绪时无限阻塞，导致 `/health` 返回空响应。加 `socket_timeout=3` 解决。

### docker compose build 与 docker build -t 镜像 tag 不一致

- **问题**：`docker build -t job-copilot .` 构建的镜像 tag 是 `job-copilot:latest`，但未显式配置 `image:` 时，`docker compose up -d` 使用自动命名的 `job-copilot-v0-api:latest`（项目名-服务名）。两者是不同镜像，手动 build 的代码不会进入 Compose 容器。
- **踩坑**：反复 `docker build --no-cache` + `docker compose up -d`，容器里始终是旧代码，`/health` 端点一直 404。排查多次构建才发现是镜像 tag 不一致。
- **解法**：在 `docker-compose.yml` 中给 `api` 和 `worker` 显式指定 `image: job-copilot:latest`，让手动 `docker build -t job-copilot .` 与 Compose 使用同一 tag。日常仍推荐 `docker compose build` 或 `docker compose up -d --build`，因为它会按 Compose 文件中的服务配置构建。
