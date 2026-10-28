from app.rag.chunker import chunk_segments, token_count
from app.rag.parsers import TextSegment


def test_heading_aware_chunking_is_stable_and_preserves_pages():
    segments = [TextSegment("进程是运行中的程序实例。" * 80, 3, "第三章 进程"), TextSegment("线程共享进程资源。" * 80, 4, "第三章 进程")]
    first = chunk_segments(segments, document_id="doc-1", file_hash="hash")
    second = chunk_segments(segments, document_id="doc-1", file_hash="hash")
    assert first
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert first[0].page_start == 3
    assert all(chunk.page_start in (3, 4) and chunk.page_end in (3, 4) for chunk in first)
    assert all(chunk.section_title == "第三章 进程" for chunk in first)
    assert all(chunk.token_count == token_count(chunk.content) for chunk in first)


def test_chunking_splits_long_paragraph_without_losing_text():
    text = "".join(f"操作系统管理进程和内存，第{i}节。" for i in range(1800))
    chunks = chunk_segments([TextSegment(text)], document_id="doc", file_hash="hash", max_tokens=120, overlap_tokens=15)
    assert len(chunks) > 2
    joined = "".join(chunk.content for chunk in chunks)
    assert "第1799节" in joined
    assert all(chunk.token_count <= 150 for chunk in chunks)
