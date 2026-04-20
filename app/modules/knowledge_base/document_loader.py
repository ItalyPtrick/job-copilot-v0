from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_core.documents import Document

# 扩展名 -> Loader 类：先把不同文档统一转成 LangChain Document。
SUPPORTED_EXTENSIONS = {
    ".pdf": PyMuPDFLoader,
    ".docx": Docx2txtLoader,
    ".txt": TextLoader,
    ".md": UnstructuredMarkdownLoader,
}

# 递归分块：优先按段落/句子切，超长时再继续细分。
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
    separators=["\n\n", "\n", "。", "！", "？", ".", " ", ""],
)


# 流程：识别格式 -> 加载文档 -> 分块 -> 补充检索元数据。
def load_and_split(file_path: str) -> list[Document]:
    extension = Path(file_path).suffix.lower()  # suffix.lower() 统一处理扩展名大小写。
    loader_class = SUPPORTED_EXTENSIONS.get(extension)

    if loader_class is None:
        raise ValueError(f"不支持的文件格式: {extension}")

    documents = loader_class(file_path).load()  # 先把原文件解析成 Document 列表。
    chunks = text_splitter.split_documents(documents)  # 再切成适合 embedding / 检索的小块。
    source_file = Path(file_path).name  # 只保留文件名，便于命中后回溯来源。

    # 记录块序号与来源文件，后续命中时能定位“第几个块来自哪个文件”。
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["source_file"] = source_file

    return chunks
