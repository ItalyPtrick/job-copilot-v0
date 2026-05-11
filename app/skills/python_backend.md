# skill: python_backend.md

## 考察范围
- Python 基础：可变/不可变类型、装饰器原理与应用、生成器与迭代器协议、GIL 与多线程局限
- Web 框架：FastAPI 路由与依赖注入、中间件执行顺序、请求生命周期、Pydantic 校验
- 数据库：SQLAlchemy ORM 映射与 Session 管理、事务隔离级别、连接池配置与泄漏排查
- 异步编程：asyncio 事件循环、协程与线程区别、async/await 适用场景、并发控制（Semaphore/gather）
- 系统设计：缓存策略（穿透/击穿/雪崩）、消息队列选型与消费语义、服务拆分边界与通信方式

## 难度分布
- easy：40%（能说出定义和基本用法，给出简单代码示例）
- medium：40%（能解释底层原理，对比备选方案优劣，识别常见陷阱）
- hard：20%（能设计完整方案并论证权衡，分析故障根因，评估性能瓶颈与扩展边界）

## 参考知识库
- collection: python_docs