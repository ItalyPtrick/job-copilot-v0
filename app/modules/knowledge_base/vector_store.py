import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

# Chroma 本地持久化目录。
CHROMA_DIR = "./data/chroma"

# 统一 embedding 配置，优先读取独立的向量模型环境变量。
EMBEDDING_API_KEY = os.getenv("OPENAI_EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY"))
EMBEDDING_BASE_URL = os.getenv(
    "OPENAI_EMBEDDING_BASE_URL", os.getenv("OPENAI_BASE_URL")
)
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-v4")

embeddings = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=EMBEDDING_API_KEY,
    base_url=EMBEDDING_BASE_URL,
    check_embedding_ctx_length=False,  # 百炼兼容 embeddings 接口接受字符串输入，不兼容 LangChain 默认的 token 预切分数组输入
    chunk_size=10, # 百炼 API 单批最多 10 条
)


def get_vector_store(collection_name: str) -> Chroma:
    """获取或创建指定 collection 的 Chroma 向量库。"""
    Path(CHROMA_DIR).mkdir(
        parents=True, exist_ok=True
    )  # 允许递归创建目录、目录已存在时不报错

    return Chroma(
        collection_name=collection_name,
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
    )


def add_documents(collection_name: str, documents: list[Document]) -> None:
    """向指定 collection 写入文档块。"""
    vector_store = get_vector_store(collection_name)
    vector_store.add_documents(
        documents
    )  # 调用Chroma写入文档，内部做embedding计算和存储


def delete_source_file(collection_name: str, source_file: str) -> None:
    """按来源文件名删除指定 collection 中的文档块。"""
    vector_store = get_vector_store(collection_name)
    # upload 回滚按 chunk metadata 里的 source_file 删除；这里复用同一键，保证向量补偿与 loader 约定一致。
    vector_store._collection.delete(where={"source_file": source_file})


def search(collection_name: str, query: str, top_k: int = 5) -> list[Document]:
    """在指定 collection 中执行相似度检索。"""
    vector_store = get_vector_store(collection_name)
    return vector_store.similarity_search(
        query, k=top_k
    )  # 执行相似度检索，返回最相关的 top_k 个文档块
