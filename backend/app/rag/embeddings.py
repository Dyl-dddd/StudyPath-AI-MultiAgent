from functools import lru_cache
from fastembed import TextEmbedding
from app.core.config import get_settings


@lru_cache(maxsize=1)
def model() -> TextEmbedding:
    settings = get_settings()
    return TextEmbedding(model_name=settings.embedding_model, cache_dir=settings.fastembed_cache_path or None, threads=2)


def vector_size() -> int:
    return int(model().embedding_size)


def embed_texts(texts: list[str]) -> list[list[float]]:
    return [vector.astype(float).tolist() for vector in model().embed(texts, batch_size=16)]


def embed_query(text: str) -> list[float]:
    return [vector.astype(float).tolist() for vector in model().query_embed(text)][0]
