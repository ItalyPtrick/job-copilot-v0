# 我怎么跟上进度？—— W2-D5 AI 代码回顾与追赶指南

> **前置状态**：你已独立完成 W2-D4（含 `/kb/*` 4 个路由、`knowledge_documents` 记录入库、手工验收通过）。D5 的全部代码和文档由 AI 完成，你需要理解这些变动并能在面试中讲清楚。

---

## 一、AI 到底改了什么？（总览）

| 类别 | 文件数 | 行数 |
|---|---|---|
| 代码 | 5 | +230 / -50 |
| 测试 | 1 | +118 / -6 |
| 迁移 | 2 | 新增 + 修改 |
| 文档 | 4 | +70 / -30 |
| 计划/进度 | 4 | 状态同步 |
| 配置 | 1 | +1 |

---

## 二、代码变动详解

### 2.1 `app/database/models/knowledge.py`（模型扩展）

**改了什么**：
- 新增 `UniqueConstraint("collection_name", "file_hash")` —— 数据库层面保证同一集合内不会有两条相同 hash 的记录
- 新增 `updated_at` 字段（`default` + `onupdate` 双保险）—— 记录每次状态变更的时间
- 给 `file_hash` 和 `status` 字段补了语义注释

**你需要理解**：
- `UniqueConstraint` 是 SQLAlchemy 声明式约束，映射到数据库的 `UNIQUE` 索引
- `onupdate` 只在 `UPDATE` 语句时触发，`INSERT` 时靠 `default` 兜底
- 状态机三态：`uploading`（占位中）→ `completed`（成功）/ `failed`（失败）

### 2.2 `alembic/env.py`（迁移配置）

**改了什么**：在 `context.configure(...)` 中加了 `render_as_batch=True`

**你需要理解**：
- SQLite 不支持直接 `ALTER TABLE ... ADD CONSTRAINT`，Alembic 的 batch 模式会自动"建新表→复制数据→删旧表→重命名"来绕过限制
- 这是一次性配置，以后所有 SQLite 迁移都会自动用 batch 模式

### 2.3 `alembic/versions/8cd951190b78_...py`（新迁移文件）

**改了什么**：新增迁移脚本，用 `op.batch_alter_table` 添加 `updated_at` 列和 `uq_kb_collection_hash` 唯一约束

**你需要理解**：
- 这是 `alembic revision --autogenerate` 自动生成的，你不需要手写
- `upgrade()` 加列+加约束，`downgrade()` 反向操作
- 如果本地库有重复数据，需要先清理再 `alembic upgrade head`

### 2.4 `app/modules/knowledge_base/router.py`（核心重构，变动最大）

**改了什么**（原 upload 流程 vs 新流程）：

```
【D4 旧流程】
落盘 → load_and_split → add_documents → 创建 record → db.commit
失败时：rollback + 清理文件 + 补偿删除向量

【D5 新流程】
落盘 → 算 hash → 查 completed 记录？
  ├─ 命中 → 返回 reused:true，跳过 embedding（省钱！）
  └─ 未命中 → 写 uploading 占位 → db.commit①
                ├─ IntegrityError → rollback + 409（并发冲突）
                └─ 成功 → load_and_split → add_documents → status=completed → db.commit②
                           失败时：status=failed → db.commit③ + 补偿删除向量 + 清理文件
```

**你需要理解的 5 个关键点**：

1. **Hash 前移**：先落盘再算 hash，避免大文件全读进内存；hash 是幂等判重的基础
2. **Reused 短路**：同 `(collection_name, file_hash)` 已有 `completed` 记录 → 直接返回 `reused: true`，不调用 embedding API（降本核心）
3. **两阶段 commit**：第一次 commit 写 `uploading` 占位（让唯一约束立即对并发生效）；第二次 commit 更新为 `completed`
4. **409 并发**：第一次 commit 如果触发 `IntegrityError`（另一个请求已占位），返回 HTTP 409，让调用方自行重试
5. **Failed 保留**：真正失败时不删记录，标记 `status=failed` 便于排查；向量和文件都清理

### 2.5 `app/orchestrators/job_copilot_orchestrator.py`（RAG 注入）

**改了什么**：
- 新增 `_build_retriever_context(payload, top_k=3)` 函数
- 在 `execute_task` 成功路径末尾调用它，把结果注入 `TaskResult`

**你需要理解**：
- 三要素齐全才触发：`payload` 中同时有 `use_rag=True` + `rag_collection` + `rag_question`
- 检索失败不阻塞主任务，返回 `status="error"` 的空上下文（降级而非崩溃）
- 这是 D5 原计划里的 "Step 6：集成到 Orchestrator"

### 2.6 `app/types/task_result.py`（工厂方法扩展）

**改了什么**：`from_success` 新增可选参数 `retriever_context=None`

**你需要理解**：
- 默认值 `None` 保持向后兼容，不改变已有调用方的行为
- 只有 orchestrator 判定需要 RAG 时才传入非 None 值

---

## 三、测试变动

### `tests/test_kb_api.py`（+118 行）

| 测试函数 | 验证什么 | 关键断言 |
|---|---|---|
| `test_upload_returns_success_and_persists_record` | **更新**：初次上传含 `reused: False` 和 `updated_at` | `reused is False`，`updated_at is not None` |
| `test_upload_keeps_failed_record_and_cleans_file_when_vector_store_fails` | **重命名+更新**：失败时保留 `status=failed` 记录 | `records[0].status == "failed"`（不再是 count==0） |
| `test_upload_cleans_up_vectors_when_db_second_commit_fails` | **重命名+更新**：第二次 commit 失败的补偿 | `flaky_commit` 第 1/3 次放行、第 2 次抛错 |
| `test_upload_duplicate_returns_reused_and_skips_embedding` | **新增**：幂等短路 | 第二次上传 `reused is True`，`add_calls == 1` |
| `test_upload_returns_409_when_integrity_error_on_placeholder_commit` | **新增**：并发 409 | `status_code == 409`，`add_calls == 0` |

**你需要理解**：
- 所有测试用 `monkeypatch` 隔离真实向量库和文件系统
- `flaky_commit` 是一个精巧的 mock：用计数器控制哪一次 commit 成功、哪一次抛错
- 这些测试的思路可以直接在面试中讲

---

## 四、文档变动

| 文件                              | 改了什么                         |
| ------------------------------- | ---------------------------- |
| `docs/design-decisions.md`      | 追加 3 条 W2-D5 设计决策（见下方）       |
| `docs/02-rag-knowledge-base.md` | §3 集成点表、§4 upload 流程、§6 面试亮点 |
| `README.md`                     | 进度描述、功能亮点、手工验收段落             |
| `CLAUDE.md`                     | 进度描述、upload 幂等语义             |

---

## 五、3 条设计决策（面试必讲）

### 决策 1：上传幂等判重 —— `(collection_name, file_hash)` 唯一约束

> **面试话术**：我们用 SHA-256 对上传文件算指纹，配合数据库唯一约束做判重。命中已完成的记录就直接返回，跳过 embedding API 调用。约束下沉到数据库层，即使应用层有并发窗口也能兜底。

### 决策 2：两阶段 commit —— `uploading → completed`

> **面试话术**：第一次 commit 写占位记录，让唯一约束立即生效；第二次 commit 才真正标记完成。中间失败则保留 `failed` 记录便于排查。并发请求在第一次 commit 时就会触发 IntegrityError，我们转成 409 让调用方重试。

### 决策 3：Orchestrator RAG 上下文注入

> **面试话术**：我们在 orchestrator 层做条件注入——只有 payload 同时带 `use_rag`、`rag_collection`、`rag_question` 三个参数才触发检索。检索失败降级返回空上下文，不阻塞主任务。这样 RAG 是"辅助增强"而非"核心依赖"。

---

## 六、跟进行动清单（按优先级）

### 🔴 第一优先：读懂代码（~1 小时）

1. **打开 `router.py`**，对照上面的"新流程图"逐行走一遍，重点理解两阶段 commit 的三条分支
2. **打开 `knowledge.py`**，看 `UniqueConstraint` 和 `updated_at` 的声明方式
3. **打开 `job_copilot_orchestrator.py`**，找到 `_build_retriever_context` 函数，理解三要素判断和降级逻辑

### 🟡 第二优先：读懂测试（~30 分钟）

4. **打开 `test_kb_api.py`**，重点看两个新增测试：
   - `test_upload_duplicate_returns_reused_and_skips_embedding` —— 怎么验证"没调用 add_documents"
   - `test_upload_returns_409_when_integrity_error_on_placeholder_commit` —— 怎么 mock IntegrityError
5. 看 `flaky_commit` 的实现，理解计数器模式

### 🟢 第三优先：读设计决策（~15 分钟）

6. **打开 `docs/design-decisions.md`**，读最后 3 条 W2-D5 决策
7. 用自己的话复述每条决策的"问题→方案→理由"

### ⚪ 可选：动手验证（~15 分钟）

8. 跑一遍下面的验证命令，确认环境正常

---

## 七、验证命令

跑完以下命令全部通过，说明你的本地环境已经和 AI 的改动完全同步：

```bash
# 1. 数据库迁移
conda run -n job-copilot-v0 python -m alembic upgrade head

# 2. 验证表结构（应看到 updated_at 列和 uq_kb_collection_hash 约束）
conda run -n job-copilot-v0 python -c "from sqlalchemy import inspect; from app.database.connection import engine; insp=inspect(engine); print([c['name'] for c in insp.get_columns('knowledge_documents')]); print(insp.get_unique_constraints('knowledge_documents'))"

# 3. 验证 _build_retriever_context 可导入
conda run -n job-copilot-v0 python -c "from app.orchestrators.job_copilot_orchestrator import _build_retriever_context; print('OK')"

# 4. 跑全部测试（应 25 passed, 1 skipped）
conda run -n job-copilot-v0 pytest tests/ -v
```

---

## 八、D6 计划里哪些已经被 D5 提前做了？

原计划 D6 的任务是"测试编写 + Alembic 迁移"，但 D5 扩容后已经提前完成了大部分：

| D6 原任务              | 状态                                                      |
| ------------------- | ------------------------------------------------------- |
| Alembic 迁移          | ✅ D5 已做（含 `render_as_batch` 配置 + 迁移脚本 + `upgrade head`） |
| `test_rag_chain.py` | ✅ D4 已完成（5 个用例）                                         |
| `test_kb_api.py` 补齐 | ✅ D5 已做（11 个用例，含 2 个幂等新增）                               |
| 迁移回退验证              | ⬜ D6 可以快速跑一遍 `downgrade base && upgrade head`           |
| 手工验收复跑              | ⬜ D6 可以带着新的验收口径（reused / 409）再跑一遍                       |

> **结论**：D6 的核心编码任务已被 D5 覆盖。你可以把 D6 的时间用来"读代码 + 理解设计决策 + 模拟面试准备"。
