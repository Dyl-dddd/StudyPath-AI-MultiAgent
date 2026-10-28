import threading
import uuid
from functools import lru_cache
from pathlib import Path
from qdrant_client import QdrantClient, models
from app.core.config import DATA_DIR, get_settings
from app.rag.embeddings import vector_size

_lock = threading.RLock()
_point_ns = uuid.UUID("eb65a66b-9222-4500-977e-89d33ce395da")


@lru_cache(maxsize=1)
def client() -> QdrantClient:
    settings = get_settings()
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=30)
    configured_path = settings.qdrant_local_path.strip()
    path = Path(configured_path) if configured_path else DATA_DIR / "qdrant"
    if not path.is_absolute():
        path = DATA_DIR.parent / path
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


def ensure_collection() -> None:
    settings = get_settings()
    qdrant = client()
    with _lock:
        if qdrant.collection_exists(settings.collection_name):
            actual = qdrant.get_collection(settings.collection_name).config.params.vectors.size
            expected = vector_size()
            if actual != expected:
                raise RuntimeError(f"Qdrant 集合维度 {actual} 与当前模型维度 {expected} 不匹配；请配置新的集合名或按备份流程迁移")
            return
        qdrant.create_collection(collection_name=settings.collection_name, vectors_config=models.VectorParams(size=vector_size(), distance=models.Distance.COSINE))
        if settings.qdrant_url:
            for field in ("owner_id", "knowledge_base_id", "document_id"):
                qdrant.create_payload_index(settings.collection_name, field, field_schema=models.PayloadSchemaType.KEYWORD)


def upsert_chunks(chunks: list[dict]) -> None:
    from app.rag.embeddings import embed_texts
    if not chunks:
        return
    ensure_collection()
    vectors = embed_texts([item["content"] for item in chunks])
    settings = get_settings()
    points = [models.PointStruct(id=str(uuid.uuid5(_point_ns, item["chunk_id"])), vector=vector, payload={**item, "chunk_id": item["chunk_id"]}) for item, vector in zip(chunks, vectors, strict=True)]
    with _lock:
        client().upsert(collection_name=settings.collection_name, points=points, wait=True)


def search(query_vector: list[float], owner_id: str, knowledge_base_id: str, limit: int) -> list[dict]:
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    settings = get_settings()
    ensure_collection()
    result = client().query_points(collection_name=settings.collection_name, query=query_vector, query_filter=Filter(must=[FieldCondition(key="owner_id", match=MatchValue(value=owner_id)), FieldCondition(key="knowledge_base_id", match=MatchValue(value=knowledge_base_id))]), limit=limit, with_payload=True).points
    return [{**(point.payload or {}), "score": float(point.score)} for point in result]


def delete_document(document_id: str, owner_id: str | None = None) -> None:
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    settings = get_settings()
    if not client().collection_exists(settings.collection_name):
        return
    conditions = [FieldCondition(key="document_id", match=MatchValue(value=document_id))]
    if owner_id:
        conditions.append(FieldCondition(key="owner_id", match=MatchValue(value=owner_id)))
    with _lock:
        client().delete(collection_name=settings.collection_name, points_selector=models.FilterSelector(filter=Filter(must=conditions)), wait=True)


def delete_owner(owner_id: str) -> None:
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    settings = get_settings()
    if not client().collection_exists(settings.collection_name):
        return
    with _lock:
        client().delete(collection_name=settings.collection_name, points_selector=models.FilterSelector(filter=Filter(must=[FieldCondition(key="owner_id", match=MatchValue(value=owner_id))])), wait=True)


def delete_knowledge_base(knowledge_base_id: str, owner_id: str) -> None:
    from qdrant_client.models import FieldCondition, Filter, MatchValue
    settings = get_settings()
    if not client().collection_exists(settings.collection_name):
        return
    with _lock:
        client().delete(collection_name=settings.collection_name, points_selector=models.FilterSelector(filter=Filter(must=[FieldCondition(key="knowledge_base_id", match=MatchValue(value=knowledge_base_id)), FieldCondition(key="owner_id", match=MatchValue(value=owner_id))])), wait=True)


def delete_chunks(chunk_ids: list[str]) -> None:
    if not chunk_ids:
        return
    settings = get_settings()
    if not client().collection_exists(settings.collection_name):
        return
    with _lock:
        points = [str(uuid.uuid5(_point_ns, chunk_id)) for chunk_id in chunk_ids]
        client().delete(collection_name=settings.collection_name, points_selector=models.PointIdsList(points=points), wait=True)
