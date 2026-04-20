import asyncio
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.modules.knowledge_base.vector_store import search

load_dotenv()

# 空检索结果直接短路，避免把空 context 送给模型自由发挥。
FALLBACK_ANSWER = "根据现有知识库内容，我无法回答这个问题"
RAG_PROMPT_TEMPLATE = """你是一个知识库问答助手。
请根据以下检索到的文档内容回答用户问题。
如果文档中没有相关信息，请明确说明“根据现有知识库内容，我无法回答这个问题”。

文档内容：
{context}

用户问题：
{question}
"""
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


# 把多个命中文档块拼成一个上下文字符串，交给 prompt 统一喂给模型。
def _build_context(documents):
    # 用显式分隔符保留 chunk 边界，减少模型把相邻块混成一段。
    return "\n\n---\n\n".join(document.page_content for document in documents)


def _build_sources(documents):
    # sources 来自检索层，不依赖模型生成，后续接口层才能稳定展示依据。
    return [
        {
            "content": document.page_content[:200],
            "source_file": document.metadata.get("source_file"),
            "chunk_index": document.metadata.get("chunk_index"),
        }
        for document in documents
    ]


# 这里延迟创建链对象，避免模块导入时就触发 LLM 初始化副作用。
def _build_chain():
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0, streaming=True)
    parser = StrOutputParser()
    return prompt | llm | parser


# 非流式查询走“检索 -> 拼 context -> 一次性生成 -> 回 sources”的完整路径。
def rag_query(collection_name: str, question: str, top_k: int = 5) -> dict:
    documents = search(collection_name, question, top_k)
    if not documents:
        return {"answer": FALLBACK_ANSWER, "sources": []}

    chain = _build_chain()
    answer = chain.invoke({"context": _build_context(documents), "question": question})
    return {"answer": answer, "sources": _build_sources(documents)}


# 流式查询只负责把模型输出逐块往外送，sources 留给非流式接口返回。
async def rag_query_stream(collection_name: str, question: str, top_k: int = 5):
    # 检索还是同步 I/O，这里切到线程池，避免卡住事件循环。
    documents = await asyncio.to_thread(search, collection_name, question, top_k)
    if not documents:
        yield FALLBACK_ANSWER
        return

    chain = _build_chain()
    async for chunk in chain.astream({"context": _build_context(documents), "question": question}):
        yield chunk
