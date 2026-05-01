# 设计决策笔记

> 项目开发过程中的技术选型、架构权衡、踩坑解决记录。面试前回顾此文件。

---

### W2-D1 RAG 基础设施选型
- **问题**：W2 需要尽快打通知识库索引、检索和后续生成链路，先确定 RAG 基础设施选型。
- **方案**：使用 `langchain + langchain-openai + chromadb` 作为当前阶段的 RAG 底座。
- **理由**：`langchain` 提供统一的 `Document`、`splitter`、`retriever` 抽象，便于 D2-D4 持续复用；`langchain-openai` 能直接接入现有 OpenAI 兼容环境变量；`chromadb` 支持本地持久化，部署和调试成本低，比一开始上 `PGVector` / `Elasticsearch` 更适合当前学习和原型阶段。

### W2-D1 知识库模块边界
- **问题**：W2 后续会连续扩展向量存储、文档加载、RAG chain 和接口层，需要先固定知识库相关代码的边界。
- **方案**：新增 `app/modules/knowledge_base/` 作为知识库能力模块，先创建模块目录和 `__init__.py`，并将 `data/chroma/`、`data/uploads/` 加入 `.gitignore`。
- **理由**：按业务能力收口比把代码分散到 `services/`、`tools/` 更清晰，也能提前隔离向量索引和上传文件等本地产物，避免后续职责混乱和误提交。

### W2-D1 百炼 Embedding 兼容性适配
- **问题**：阿里云百炼兼容 embeddings 接口与 `langchain_openai` 默认的 token 预切分输入不完全兼容，快速验证时写入 Chroma 失败。
- **方案**：保留百炼兼容接口与 `text-embedding-v4`，在 `OpenAIEmbeddings` 初始化中设置 `check_embedding_ctx_length=False`。
- **理由**：当前项目在上游已经做文档切块，embedding 输入本就应为小块字符串；关闭客户端 token 预切分不影响当前基础 RAG 链路，却能以最小改动适配百炼兼容接口。

### W2-D2 向量存储阶段性选型
- **问题**：W2-D2 既要尽快跑通本地索引与检索链路，又要为后续正式部署保留可演进的向量存储方案。
- **方案**：当前阶段继续使用 ChromaDB 完成原型验证；后续在统一数据库基础设施、服务化部署需求更明确时，再评估迁移到 pgvector。
- **理由**：ChromaDB 嵌入式、依赖轻、调试成本低，适合当前学习和原型阶段；pgvector 更适合复用 PostgreSQL 生态、统一运维与业务数据体系。这次选择是按阶段目标做取舍，不是一开始就引入重型部署。

### W2-D2 检索策略选型
- **问题**：纯向量检索能覆盖语义相似，但对术语、缩写、技能名和精确关键词的命中不够稳定。
- **方案**：当前先保留相似度检索作为基础检索方式，后续演进到“关键词召回 + 向量召回”的混合检索，再统一排序后送入生成链路。
- **理由**：向量检索擅长找“意思接近”的内容，关键词检索擅长找“字面精确匹配”的内容；两路结合通常比纯向量更稳，尤其适合岗位术语和技能名较多的场景。当前先记录演进方向，不把未实现能力写成既成事实。

### W2-D2 文档加载与切块策略
- **问题**：知识库文档格式不一，且 embedding 与检索都要求输入块大小可控、来源可追踪。
- **方案**：在 `document_loader.py` 中先按扩展名选择 Loader，把 PDF、DOCX、TXT、Markdown 统一转成 `Document`，再用 `RecursiveCharacterTextSplitter` 按 `chunk_size=500`、`chunk_overlap=100` 递归分块，并为每个 chunk 补充 `chunk_index` 与 `source_file` 元数据。
- **理由**：这套流程先统一格式，再统一切块粒度，能直接复用到后续向量化与检索；分块时优先保留段落和句子边界，只有超长内容才继续细分，既减少语义断裂，也方便命中后回看文件名与块序号。

### W2-D3 RAG 问答链输出边界
- **问题**：RAG 问答链需要明确非流式、流式与来源信息的职责边界，避免接口层和前端对返回结构产生误解。
- **方案**：`rag_query()` 在无检索结果时直接短路，返回固定兜底文案和空 `sources`；`rag_query_stream()` 当前只输出文本 chunk，不在流式路径返回 `sources`；`sources` 仅由检索层的 `Document` 元数据构造，字段保持为 `content`、`source_file`、`chunk_index`。
- **理由**：这样可以保持流式链路轻量、来源信息稳定可追溯，并避免把模型生成内容和引用元数据耦合在一起，方便后续在 D4 路由层单独扩展 SSE 事件结构。

### W2-D4 Upload 数据形状与落点
- **问题**：文件上传链路同时涉及 HTTP 参数、本地文件、文档块、向量库记录和查询来源，若不先明确“数据形状怎么变、去了哪里”，后续路由实现和来源展示很容易混淆。
- **方案**：将 upload 链路固定为 `UploadFile -> data/uploads/ 原文件 -> Document[] -> chunk[] + metadata(source_file, chunk_index) -> Chroma collection records -> query sources[]`，并在 D5 开始补上 `knowledge_documents` 这条文件级 upload record 分支。当前原文件保存在 `data/uploads/`，chunk 文本、metadata 与 embedding 持久化到 `data/chroma/`；查询命中后再由 `rag_query()` 将检索结果映射成 `sources`。当前 `sources.source_file` 指向保存后的文件名体系，`knowledge_documents` 负责记录这次上传对应的原始文件名、保存路径与分块结果，但尚未和 chunk 建立稳定强关联。
- **理由**：这条链把“HTTP 接收”“文件落盘”“分块”“向量化”“来源展示”“上传记录”拆成清晰阶段，既方便理解 D4/D5 的职责分界，也便于后续定位问题时判断数据当前停留在哪一层，以及当前哪些关联已经存在、哪些仍是后续增强项。

```mermaid
flowchart TD
    A[UploadFile<br/>file + collection_name] --> B[data/uploads/file_id.ext<br/>原始文件落盘]
    B --> C[Document 列表<br/>Loader 解析]
    C --> D[chunk 列表<br/>metadata: source_file, chunk_index]
    D --> E[data/chroma / Chroma collection<br/>document + metadata + embedding]
    E --> F[rag_query / search 命中结果]
    F --> G[sources 列表<br/>content + source_file + chunk_index]

    B -. D5 开始补充 .-> H[knowledge_documents<br/>upload record: 原始文件名/保存路径/chunks_count]
    H -. 当前未与 chunk 建立稳定强关联 .-> E
```

### W2-D4 可追溯性边界
- **问题**：知识库问答需要“可展示来源”，但 D4 的目标是先打通上传、检索和 SSE 路由；如果在这一天同时引入完整 upload record、document 级标识和 chunk 强关联，范围会从路由编排扩成数据模型设计。
- **方案**：D4 采用弱追溯：chunk metadata 只保留 `source_file` 与 `chunk_index`，查询结果只承诺返回这两级定位信息；强追溯延后到 D5 及之后，再通过 `knowledge_documents` / upload record 为文件级与 chunk 级关系补上稳定锚点。
- **理由**：弱追溯已经足够支持“命中了哪个文件的第几个块”，能满足当前学习和最小 RAG 演示；把强追溯后置，可以避免在 D4 提前承诺尚未落地的数据库字段与关联关系，同时保持 `ChromaDB（当前）-> pgvector（后续演进）` 的路线不变。

### W2-D4 query / query_stream 执行边界
- **问题**：知识库已经同时具备非流式 `rag_query()` 与流式 `rag_query_stream()`，但两者在“什么时候返回结果”“返回什么形状”“检索阶段是否并行”上很容易被混淆，进而影响路由层实现与前端预期。
- **方案**：固定这两条链路的边界：`rag_query()` 走“先检索 -> 一次性生成 -> 返回 `answer + sources`”；`rag_query_stream()` 走“先检索 -> 再流式生成 -> 逐 chunk 输出文本”。当前流式路径只负责回答文本，不返回 `sources`；如果后续要在 `/kb/query/stream` 中展示来源，应在路由层单独扩展 SSE 事件结构，而不是把现有 `rag_query_stream()` 误当成完整 JSON 返回接口。
- **理由**：非流式与流式的核心差异不在“函数名不同”，而在控制流和输出契约不同。非流式天然适合一次性返回结构化结果；流式则更适合把模型输出按 chunk 推送给前端。先把职责边界固定，后续接 `/kb/query/stream` 路由时就不会把文本流、来源信息和结束信号混成一个返回体。

### W2-D4 流式 query 的异步语义
- **问题**：`rag_query_stream()` 中用了 `await asyncio.to_thread(search, ...)`，容易误以为“检索和生成是并行的”或“search 已经变成原生异步函数”。
- **方案**：明确当前流式 RAG 的执行顺序仍然是“先检索，后生成”。其中 `search(...)` 本身仍是同步阻塞函数，只是通过 `asyncio.to_thread(...)` 被派发到线程池执行；当前协程异步等待检索结果返回，拿到完整 `documents` 后，才进入 `chain.astream(...)` 的逐 chunk 流式生成阶段。
- **理由**：这样做的目的不是让检索和生成并行，而是避免同步检索阻塞事件循环。对当前请求来说，仍然必须先等检索完成，才能拼接 context 并开始生成；但对整个 FastAPI 服务来说，事件循环线程不会被同步检索卡死，仍能继续调度其它协程与流式响应。

### W2-D4 /kb/collections 的观测口径
- **问题**：`/kb/collections` 既可以从数据库里的 `knowledge_documents` 理解为“上传过什么文件”，也可以从 Chroma 理解为“向量库里当前实际有什么 collection”，如果不先固定口径，接口会把业务记录和索引状态混在一起。
- **方案**：`/kb/collections` 作为纯读接口，直接访问 `chromadb.PersistentClient(path="./data/chroma")`，通过 `list_collections()` 列出当前 Chroma 中的 collection，并返回每个 collection 的 `name` 与 `count()`；不从 `knowledge_documents` 表推导 collection 列表。
- **理由**：这个接口要回答的是“当前向量库的真实状态”，而不是“业务上记录过哪些上传行为”。`knowledge_documents` 记录的是文件级 upload record，`collection.count()` 统计的是 collection 中实际存放的 document/chunk 记录数。两者口径不同，直接读 Chroma 才能准确反映当前可检索的索引状态。

### W2-D4 知识库路由集成方式
- **问题**：D4 需要把 upload、query、query/stream、collections 四个接口正式接入 FastAPI 主应用，同时明确流式接口在 HTTP 层的最小协议；否则即使底层能力已实现，`/docs` 和实际请求也无法稳定反映当前知识库能力。
- **方案**：新增 `app/modules/knowledge_base/router.py` 作为知识库接口层，并在 `app/main.py` 中通过 `app.include_router(kb_router)` 统一注册。`/kb/query/stream` 在路由层使用 `EventSourceResponse` 包装 `rag_query_stream()`，当前协议固定为两类 SSE 事件：逐 chunk 输出 `event: message`，结束时输出 `event: done` + `[DONE]`；本轮不在流式路径返回 `sources`。
- **理由**：把知识库接口收口到独立 router，能保持 `main.py` 只负责应用入口和路由挂载，避免把知识库细节塞回主文件；同时先固定最小 SSE 协议，可以让流式链路稳定可测，不把文本流、来源信息和结束信号混成一个返回体。

### W2-D4 upload 手工调试与验收口径
- **问题**：`/kb/upload` 第一次手工测试返回 500，后续又出现"Swagger UI 里看起来失败，但数据库记录和落盘文件显示实际成功"的现象，如果不区分"真实服务端失败"和"手工观测口径不可靠"，很容易误判 D4 仍被 upload 阻塞。
- **方案**：先按服务端真实链路排查 upload 500。最终确认第一次稳定失败的根因是本地 `job_copilot.db` 中 `knowledge_documents` 仍停留在占位表结构，缺少 `filename`、`collection_name`、`file_path`、`file_hash`、`chunks_count`、`status`、`file_size` 等字段；修复路径采用 Alembic 对齐本地版本：先把数据库 `stamp` 到已存在的占位迁移，再生成并应用补字段迁移。修复后，将 upload 的手工验收口径固定为"以服务端可观测结果为准"：同时检查 HTTP 响应、`knowledge_documents` 记录、`data/uploads/` 落盘文件，而不是只看 Swagger UI 中的单一展示结果。
- **理由**：这次故障先是标准的数据库 schema 落后问题，根因在 ORM 模型与本地实际表结构不一致；它修好后，服务端真实链路已经能成功完成"落盘 -> 分块 -> 向量写入 -> 记录入库"。Swagger UI 的示例 curl 只是文档展示，不是浏览器真实发包的精确回显；而 UI 中单次显示结果若和数据库记录、上传文件痕迹冲突，应优先相信服务端状态。把手工验收口径明确成"响应 + 数据库 + 文件系统"三点交叉验证，能避免把文档展示噪音误判成接口本身失败。

### W2-D5 上传幂等判重：(collection_name, file_hash) 唯一约束
- **问题**：同一份文件重复上传会重复调用 embedding API（费用浪费）、写入重复向量记录、数据库出现多条相同 hash 的 upload record；如果不在数据层拦截，重复上传只能靠前端防抖或人工约束。
- **方案**：在 `knowledge_documents` 表上新增 `UniqueConstraint("collection_name", "file_hash", name="uq_kb_collection_hash")`；upload 接口先计算文件 SHA-256 hash，再查 DB 是否已有 `status=completed` 的同 hash 记录——命中则直接返回 `reused: true` 并跳过 embedding；未命中再走正常写入流程。
- **理由**：唯一约束把判重责任下沉到数据库层，即使应用层查询-写入之间存在并发窗口，约束依然能兜底。hash 前移到写入前计算，虽然多了一次文件读取，但相比 embedding API 调用的成本微乎其微。`reused` 字段显式返回让调用方知道本次上传是真实处理还是缓存命中。

### W2-D5 两阶段 commit：uploading → completed
- **问题**：D4 的 upload 流程是"先写向量、后写 DB 记录"，如果向量写入成功但 DB 提交失败，向量库里会留下脏数据需要补偿删除；但如果反过来"先写 DB、再写向量"，DB 记录会短暂处于 completed 状态而实际向量还没落地，造成查询时检索为空。
- **方案**：引入两阶段 commit 模式。第一次 commit 写入 `status=uploading` 的占位记录；然后执行分块与向量写入；第二次 commit 把 status 更新为 `completed`。如果中间任何一步失败，走不同的补偿路径：`ValueError`（格式不支持）→ 删除占位 + 400；其他异常 → 保留 `status=failed` 记录 + 补偿删除向量 + 500。
- **理由**：占位记录让唯一约束对并发请求立即生效（第二个请求的 commit 会触发 `IntegrityError` → 409）；`failed` 记录保留便于排查失败原因和后续批量清理，比直接删除更可观测。两阶段模式虽然多一次 DB 往返，但把"数据一致性窗口"从整个上传过程缩短到了两次 commit 之间，是当前 SQLite 单进程场景下最小代价的方案。

### W2-D5 Orchestrator RAG 上下文注入
- **问题**：`TaskResult` 已预留 `retriever_context` 字段，但 orchestrator 一直没有真正从知识库检索上下文填充它；如果不实现注入点，前端/下游永远拿不到 RAG 检索结果，知识库模块和任务系统之间就只有"各自独立"的状态。
- **方案**：在 orchestrator 中新增 `_build_retriever_context(payload, top_k=3)` 函数，仅当 payload 同时包含 `use_rag=True`、`rag_collection` 和 `rag_question` 三个参数时才调用 `kb_search` 获取检索结果，构造 `RetrieverContext` 并注入 `TaskResult.from_success`（from_success 新增可选 `retriever_context` 参数）。检索失败不拖垮主任务，返回 `status="error"` 的空上下文。
- **理由**：三要素齐全才触发，避免在不需要 RAG 的任务类型上产生无效检索开销和意外报错。检索失败降级而非阻塞，符合"辅助增强而非核心依赖"的 RAG 定位。`from_success` 接受可选参数而非全量重构，保持向后兼容。

### W2-D5 failed 记录可重试：重传前清理 failed 占位
- **问题**：`status=failed` 的记录占住 `(collection_name, file_hash)` 唯一约束名额；用户重传同文件时，新的 `uploading` 占位 commit 会触发 `IntegrityError` 并返回 409，形成"失败后永远无法重试"的死状态。
- **方案**：在创建 `uploading` 占位之前，先 `DELETE` 同 `(collection_name, file_hash)` 且 `status=failed` 的记录并 commit，释放约束名额后再走正常两阶段流程。
- **理由**：`failed` 记录的排查价值在"被新一次上传覆盖前"——一旦用户主动重传，说明已知晓失败并决定重试，旧 failed 记录不再有保留必要。先删后插比 `UPDATE` 更简单，也避免了复用旧记录的 `file_path` 字段指向已被清理的文件路径。

### W2-D6 近重复确认：`similarity_fingerprint` + `confirm_upload`
- **问题**：仅靠 `(collection_name, file_hash)` 只能拦截完全相同的文件；文档只改少量内容时，系统仍会重新切分、重新 embedding、重新入库，既增加成本，也会在知识库里留下高度相似的重复内容。
- **方案**：继续保留 `file_hash` 负责精确幂等；新增文件级 `similarity_fingerprint` 存储 64-bit SimHash。`/kb/upload` 在精确判重之后、清理 `failed` 记录之前执行近重复检查：命中则返回 HTTP 200 + `status=confirmation_required`，前端带 `confirm_upload=true` 重试后才继续正式上传；`completed` 提交时同步写入 `similarity_fingerprint`。
- **理由**：文件 hash 和近似指纹分别承担两层职责：前者保证完全重复不重复 embedding，后者把“高度相似但不完全相同”改成可解释、可确认的人机协作流程。复用 `/kb/upload` 的 `confirm_upload` 比新增独立确认接口改动更小，也更贴合当前前端尚未成型的状态。检测异常或空文本时降级放行，避免体验增强逻辑反过来破坏既有上传正确性。

### W2-D7 百炼 Embedding API 批量上限适配（chunk_size=10）
- **问题**：阿里云百炼 Embedding API 单次批量上限为 10 条；文档切分出 10 个以上 chunk 时，`add_documents` 批量发送全部 chunk，API 返回 400（batch size invalid），导致 upload 500。
- **方案**：在 `OpenAIEmbeddings` 初始化中额外设置 `chunk_size=10`，让 LangChain 的 `embed_documents` 自动分批调用，每批不超过 10 条。
- **理由**：`check_embedding_ctx_length=False` 只禁用了 token 预切分，不控制 `embed_documents` 的批量大小；`chunk_size` 是 LangChain `OpenAIEmbeddings` 独立的分批粒度参数，两者职责正交。设为 10 满足百炼接口限制，不影响 string 格式输入，也不破坏已有的 `check_embedding_ctx_length=False` 适配。

### W3-D2 模拟面试 Session 暂存到 Redis
- **问题**：模拟面试是典型的多轮短生命周期状态：需要持续保存 `config`、当前状态、消息历史、已出题列表和当前题序；如果一开始就落数据库，会在 D2 阶段提前引入表结构设计、迁移和会话清理问题，拖慢链路验证。
- **方案**：在 `app/modules/interview/session_manager.py` 中复用现有 `redis_client`，以 `interview:session:` 为 key 前缀，把 session 整体序列化成 JSON 写入 Redis；统一使用 `create_session` / `get_session` / `update_session` 管理，TTL 固定为 7200 秒，并要求 `current_question_index` 始终等于 `questions_asked` 长度，避免进度字段彼此失配。
- **理由**：Redis 更适合这类高频读写、可过期、面向会话的中间状态；把整份 session 作为单对象存取，能先把 D2 的关注点收敛在“多轮会话是否能稳定创建/读取/更新”，而不是提前陷入关系型拆表。独立前缀也能和现有其它缓存 key 做清晰隔离，便于后续排查和批量清理；把题序和已出题数绑定成同一个不变量后，后续出题引擎可以直接信任 session 进度，不必额外兜底矫正。

### W3-D2 面试方向先用 Markdown Skill 文件外置
- **问题**：面试出题需要同时约束考察范围、难度分布和参考知识库；如果把这些配置直接硬编码进 `question_engine.py`，后续新增岗位方向时会变成改代码而不是加配置，扩展成本高，也不利于面试时说明系统的可配置性。
- **方案**：先在 `app/skills/python_backend.md` 落地首个 Skill 文件，把考察范围、难度分布和参考知识库 collection 作为 Markdown 配置保存；Session 里仅保留 `skill` 标识，后续出题引擎再按该标识读取对应 Skill 内容。
- **理由**：把”面试方向定义”和”出题执行逻辑”分开后，新增方向时只需补一个 Skill 文件，不必改核心流程代码；同时 Markdown 形态天然易读、易维护，也更适合当前学习阶段快速迭代和人工审查。

### W3 模拟面试真实感优先：Skill 蓝图 + 自适应追问
- **问题**：原 W3 计划把 Skill Markdown 每次全文传给出题 prompt，并把追问简化成固定函数；这能快速打通链路，但会带来 token 重复、prompt 注意力稀释、追问节奏机械的问题，和“像真人面试官”的目标不完全一致。
- **方案**：W3-D3 起把 Skill 从 Markdown 配置源转成运行时蓝图，出题时只传当前相关考点、难度 rubric、已问列表和已覆盖考点；D5 在 `/interview/answer` 后增加 planner，基于回答质量、追问次数上限和进度决定 `follow_up` / `next_question` / `complete`；D4 评估时按主问题轮次聚合主问题、初答和追问回答。
- **理由**：当前阶段优先级调整为真实感 > 成本与稳定性 > 严格可控性。蓝图化能降低重复 token 并让 prompt 更聚焦；planner 能避免每题机械追问，让节奏更接近真实面试；按主问题轮次评估能避免把追问当成独立题重复计分。

### W3-D3 Skill 蓝图化出题与结构化校验
- **问题**：每轮出题都传完整 Skill Markdown 会重复消耗上下文，也不利于稳定控制难度、覆盖考点和避免重复题。
- **方案**：`question_engine.py` 先用 `load_skill` 读取 Markdown，再用 `build_skill_blueprint` 提取 topics / difficulty_distribution / reference_collections / difficulty_rubric；`generate_question` 只注入蓝图摘要、目标难度 rubric、已问题目、已覆盖考点，并用 `InterviewQuestion` 校验返回结构。
- **理由**：蓝图让 prompt 更聚焦；`difficulty_reason` 和 `assessment_focus` 为后续评估引擎提供难度解释与考察点；难度一致性和重复题拒绝放在应用层，能把不稳定的 LLM 输出限制在出题模块边界内。对应测试已覆盖 D3 出题引擎，并通过 session + question 回归。

### W3-D4 评估引擎按主问题轮次评分
- **问题**：D3 的追问策略让一道主问题下出现 0~N 条追问；如果把每条 assistant 问句等权处理，追问会被当成独立题目重复计分，评估结果失真。
- **方案**：`evaluation.py` 以"主问题轮次"为评估单元——一道主问题 + 初答 + 追问链归为一个 turn，LLM 综合评分；消息通过 `metadata.question_type`（main/follow_up）和 `parent_question_id` 区分主问题和追问。评估引擎保持无状态（不写数据库），纯函数链路：`messages → _extract_interview_turns → evaluate_batch → generate_report`。
- **理由**：按 turn 评估更接近真实面试评分逻辑——面试官不会把追问当新题打分，而是综合主答和追问表现给一个总评。无状态设计让 evaluation 可以独立测试、被路由层自由调用，不耦合 session 管理或数据库写入。LLM 解析失败时记录 warning 并跳过该批，不静默吞掉全部评分，保证可调试性。

### W3-D4 InterviewMessageMetadata 消息契约
- **问题**：评估引擎需要区分主问题、追问和用户回答，但 session messages 原始结构只有 role + content，缺少结构化标识。
- **方案**：在 `schemas.py` 新增 `InterviewMessageMetadata` 模型，约定 assistant 消息带 `question_type`（main/follow_up）、`question_id`、`parent_question_id`、`category`、`difficulty`、`assessment_focus`；user 消息带 `answer_to_question_id`。D4 测试用此契约构造 fixture，D5 路由按同一契约写入 session。
- **理由**：把消息结构契约提前固定在 schemas 中，让评估、出题和路由三个模块共享同一套数据协议，避免各模块各自猜测消息格式。metadata 字段全部可选（默认 None），不破坏现有 session_manager 的校验逻辑。

### W3-D4 评估引擎消息三遍扫描模式
- **问题**：评估引擎需要从 session messages 中提取结构化面试轮次（主问题 + 初答 + 追问链），但 messages 乱序且数据分散——主问题、追问、回答各自存储在不同的 message 记录中。
- **方案**：采用三遍扫描模式：第一遍收集所有 `role="assistant" + question_type="main"` 的主问题记录；第二遍收集所有 `role="assistant" + question_type="follow_up"` 的追问记录；第三遍收集所有 `role="user" + answer_to_question_id` 的用户回答。最后按 `question_id` 和 `parent_question_id` 关联，把主问题、追问、回答组装成完整的 turn。
- **理由**：messages 来自多轮交互，乱序是常态；一遍扫描无法正确关联分散的数据。分类索引后再组装，既能容错乱序，也能高效查询；同时为每个 turn 填充完整上下文（category、difficulty、assessment_focus），为后续 LLM 评估提供足够的语义信息。

### W3-D4 LLM 解析失败降级跳过
- **问题**：`evaluate_batch` 按 `_BATCH_SIZE=3` 分批调用 LLM 评估，当某批 LLM 返回格式错误或 `_parse_evaluations` 解析失败时，应该如何处理——是否要拖垮整体评估结果？
- **方案**：当某批评估失败时，记录 `warning` 日志并 `continue` 跳过该批（不插入 `all_evaluations`），继续处理后续批次。所有成功解析的批次评估结果最后汇总到 `generate_report`。
- **理由**：不同批次评估相互独立，某批失败不应阻塞其他批；记录 warning 便于后续排查 LLM 返回格式问题和调试提示语。同时用户仍能获得部分有效评估结果（如 12 题中前 3 题失败，仍保留 9 题结果），而不是因为格式错误导致全量失败。这种降级策略更符合"评估辅助而非关键路径"的定位。