import asyncio
import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from app.modules.knowledge_base.vector_store import search

load_dotenv()

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


def _build_context(documents):
    return "\n\n---\n\n".join(document.page_content for document in documents)


def _build_sources(documents):
    return [
        {
            "content": document.page_content[:200],
            "source_file": document.metadata.get("source_file"),
            "chunk_index": document.metadata.get("chunk_index"),
        }
        for document in documents
    ]


def _build_chain():
    prompt = ChatPromptTemplate.from_template(RAG_PROMPT_TEMPLATE)
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0, streaming=True)
    parser = StrOutputParser()
    return prompt | llm | parser


def rag_query(collection_name: str, question: str, top_k: int = 5) -> dict:
    documents = search(collection_name, question, top_k)
    if not documents:
        return {"answer": FALLBACK_ANSWER, "sources": []}

    chain = _build_chain()
    answer = chain.invoke({"context": _build_context(documents), "question": question})
    return {"answer": answer, "sources": _build_sources(documents)}


async def rag_query_stream(collection_name: str, question: str, top_k: int = 5):
    documents = await asyncio.to_thread(search, collection_name, question, top_k)
    if not documents:
        yield FALLBACK_ANSWER
        return

    chain = _build_chain()
    async for chunk in chain.astream({"context": _build_context(documents), "question": question}):
        yield chunk
