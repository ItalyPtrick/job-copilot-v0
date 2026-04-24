import hashlib
import re
from collections import Counter
from pathlib import Path

from sqlalchemy.orm import Session

from app.database.models.knowledge import KnowledgeDocument
from app.modules.knowledge_base.document_loader import SUPPORTED_EXTENSIONS


SIMHASH_BITS = 64
SIMHASH_THRESHOLD = 3


# 近重复检测独立于切块：这里只抽整份文档纯文本，不做 split。
def extract_text(file_path: str | Path) -> str:
    path = Path(file_path)
    loader_class = SUPPORTED_EXTENSIONS.get(path.suffix.lower())
    if loader_class is None:
        raise ValueError(f"不支持的文件格式: {path.suffix.lower()}")

    documents = loader_class(str(path)).load()
    return "\n\n".join(document.page_content for document in documents)


# 规范化只压平格式噪声，尽量不损失正文语义。
def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip().lower()
    return re.sub(r"\s+", " ", normalized)


# 64-bit SimHash 以 16 位十六进制字符串落库；无有效词元时返回 None，避免空文本互相误报。
def compute_fingerprint(text: str) -> str | None:
    tokens = re.findall(r"\w+", text)
    if not tokens:
        return None

    weights = Counter(tokens)
    vector = [0] * SIMHASH_BITS

    for token, weight in weights.items():
        token_hash = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:16], 16)
        for bit_index in range(SIMHASH_BITS):
            bit_mask = 1 << bit_index
            vector[bit_index] += weight if token_hash & bit_mask else -weight

    fingerprint = 0
    for bit_index, score in enumerate(vector):
        if score >= 0:
            fingerprint |= 1 << bit_index

    return f"{fingerprint:016x}"


# 返回同 collection 下最接近的 completed 文档及相似度分数；未命中阈值则返回 None。
def find_near_duplicate(
    db: Session,
    *,
    collection_name: str,
    similarity_fingerprint: str,
) -> tuple[KnowledgeDocument, float] | None:
    target = int(similarity_fingerprint, 16)
    candidates = (
        db.query(KnowledgeDocument)
        .filter(
            KnowledgeDocument.collection_name == collection_name,
            KnowledgeDocument.status == "completed",
            KnowledgeDocument.similarity_fingerprint.isnot(None),
        )
        .all()
    )

    best_match: tuple[KnowledgeDocument, float] | None = None
    best_distance: int | None = None

    for candidate in candidates:
        if candidate.similarity_fingerprint is None:
            continue

        distance = _hamming_distance(target, int(candidate.similarity_fingerprint, 16))
        if distance > SIMHASH_THRESHOLD:
            continue

        similarity_score = round(1 - distance / SIMHASH_BITS, 2)
        if best_distance is None or distance < best_distance:
            best_distance = distance
            best_match = (candidate, similarity_score)

    return best_match


def _hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()
