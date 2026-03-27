# 后端验收测试

---

## 成功主链路

### JD分析示例

**输入**

```json
{
  "task_type": "jd_analyze",
  "payload": {
    "jd_text": "Python后端开发工程师，需熟练掌握FastAPI、MySQL，有3年以上开发经验"
  }
}
```

**期望输出**

```json
{
  "status": "success",
  "task_type": "jd_analyze",
  "result": {
    "role_summary": "Python后端开发工程师",
    "hard_requirements": [
      "3年以上开发经验",
      "熟练掌握FastAPI",
      "熟练掌握MySQL"
    ],
    "key_skills": ["Python", "FastAPI", "MySQL"],
    "nice_to_have": []
  },
  "error": null,
  "retriever_context": null,
  "trace": [
    {
      "node_name": "任务识别完成",
      "status": "success",
      "remark": "任务类型: jd_analyze"
    },
    { "node_name": "prompt 加载完成", "status": "success" },
    { "node_name": "调用 LLM", "status": "success" },
    { "node_name": "结果汇总完成", "status": "success" }
  ]
}
```

---

### 简历优化示例

**输入**

```json
{
  "task_type": "resume_optimize",
  "payload": {
    "resume_item": "负责用户中心后端开发，使用Python+Flask+MySQL",
    "target_jd_keywords": ["Python", "FastAPI", "MySQL"],
    "hard_requirements": ["3年以上开发经验", "熟练掌握FastAPI"],
    "role_summary": "Python后端开发工程师"
  }
}
```

**期望输出**

```json
{
  "status": "success",
  "task_type": "resume_optimize",
  "result": {
    "original_version": "负责用户中心后端开发，使用Python+Flask+MySQL",
    "suggestions": [
      {
        "issue": "技术栈与JD不匹配",
        "reason": "JD要求FastAPI，简历使用Flask",
        "rewrite": "使用FastAPI替代Flask"
      },
      {
        "issue": "缺乏技术亮点",
        "reason": "没有体现工作成果和个人技能",
        "rewrite": "增加RESTful API设计和Git版本控制技能"
      }
    ],
    "optimized_version": "负责用户中心后端开发，使用Python+FastAPI+MySQL，设计RESTful API接口，熟练使用Git进行版本控制"
  },
  "error": null,
  "retriever_context": null,
  "trace": [
    { "node_name": "任务识别完成", "status": "success" },
    { "node_name": "prompt 加载完成", "status": "success" },
    { "node_name": "调用 LLM", "status": "success" },
    { "node_name": "结果汇总完成", "status": "success" }
  ]
}
```

---

### 个人介绍生成示例

**输入**

```json
{
  "task_type": "self_intro_generate",
  "payload": {
    "tone": "formal",
    "resume_item": "负责用户中心后端开发，使用Python+FastAPI+MySQL，设计RESTful API接口，熟练使用Git进行版本控制",
    "target_jd_keywords": ["Python", "FastAPI", "MySQL"],
    "role_summary": "Python后端开发工程师"
  }
}
```

**期望输出**

```json
{
  "status": "success",
  "task_type": "self_intro_generate",
  "result": {
    "version_30s": "您好，我叫张三，3年后端开发经验，熟练Python+FastAPI+MySQL，负责过用户中心后端开发",
    "version_60s": "您好，我叫张三，3年后端开发经验，熟练Python+FastAPI+MySQL。我负责过用户中心后端开发，使用FastAPI设计RESTful API接口，使用MySQL进行数据存储，同时熟练使用Git进行版本控制。",
    "key_points": [
      "3年经验",
      "Python",
      "FastAPI",
      "MySQL",
      "RESTful API",
      "Git"
    ]
  },
  "error": null,
  "retriever_context": null,
  "trace": [
    { "node_name": "任务识别完成", "status": "success" },
    { "node_name": "prompt 加载完成", "status": "success" },
    { "node_name": "调用 LLM", "status": "success" },
    { "node_name": "结果汇总完成", "status": "success" }
  ]
}
```

---

## 工具调用

- 当前版本未实现
- 第 5 月对接点：预计在文档切分阶段补充

---

## session连续改写

- 设计上需要的三个组件:
  1. session ID — 标识同一个会话
  2. 历史窗口 — 存储上一轮的结果
  3. 调 LLM 时带上历史 — 让模型能感知上下文
  - 当前版本均未实现。
- 第 5 月对接点: 预计在检索与生成阶段补充

---

## 异常场景

### 路径1：无效任务类型（主动 return）

**触发条件**：task_type 不在有效任务类型列表中

**输入**

```json
{
  "task_type": "invalid_task",
  "payload": {}
}
```

**期望输出**

```json
{
  "status": "error",
  "task_type": "invalid_task",
  "result": null,
  "error": {
    "error_type": "InvalidTaskType",
    "error_message": "无效的任务类型: invalid_task"
  },
  "retriever_context": null,
  "trace": [
    {
      "node_name": "任务识别完成",
      "status": "error",
      "remark": "无效的任务类型: invalid_task"
    }
  ]
}
```

---

### 路径2：运行时异常（except 捕获）

**触发条件**：prompt 加载失败 / LLM 调用失败 / 结果汇总失败

**输入**

```json
{
  "task_type": "jd_analyze",
  "payload": {
    "jd_text": "Python后端开发工程师"
  }
}
```

**期望输出**（以 LLM 调用失败为例）

```json
{
  "status": "error",
  "task_type": "jd_analyze",
  "result": null,
  "error": {
    "error_type": "APIError",
    "error_message": "OpenAI API 调用失败: ..."
  },
  "retriever_context": null,
  "trace": [
    { "node_name": "任务识别完成", "status": "success" },
    { "node_name": "prompt 加载完成", "status": "success" },
    {
      "node_name": "调用 LLM",
      "status": "error",
      "remark": "错误: OpenAI API 调用失败: ..."
    }
  ]
}
```

---
