from functools import lru_cache
import threading
from app.core.config import get_settings

_semaphore_lock = threading.Lock()
_semaphore = None
_semaphore_capacity = None


@lru_cache(maxsize=1)
def _model():
    name = get_settings().reranker_model.strip()
    if not name:
        return None
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    return TextCrossEncoder(model_name=name, cache_dir=get_settings().fastembed_cache_path or None, threads=2)


def rerank(query: str, candidates: list[dict]) -> tuple[list[dict], str]:
    model = _model()
    if not model or not candidates:
        return candidates, "dense"
    try:
        global _semaphore, _semaphore_capacity
        capacity = max(1, get_settings().reranker_concurrency)
        with _semaphore_lock:
            if _semaphore is None or _semaphore_capacity != capacity:
                _semaphore = threading.BoundedSemaphore(capacity)
                _semaphore_capacity = capacity
            gate = _semaphore
        with gate:
            scores = list(model.rerank(query, [item["content"] for item in candidates]))
        ordered = sorted(zip(candidates, scores, strict=True), key=lambda item: float(item[1]), reverse=True)
        return [{**item, "score": float(score), "dense_score": item["score"]} for item, score in ordered], "dense+rerank"
    except Exception:
        # Reranking is optional; keep a valid dense result if its optional model fails.
        return candidates, "dense (reranker unavailable)"
