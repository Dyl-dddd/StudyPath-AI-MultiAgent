import hashlib
import re
import uuid
from dataclasses import dataclass
from app.rag.parsers import TextSegment

NAMESPACE = uuid.UUID("706bbaf2-2ccf-464a-88b6-7537f8b75d72")


def token_count(text: str) -> int:
    # Reproducible multilingual estimate: CJK characters count individually,
    # Latin words and punctuation count as separate tokenizer-like units.
    return len(re.findall(r"[\u3400-\u9fff]|[A-Za-z0-9]+|[^\w\s]", text))


@dataclass
class Chunk:
    id: str
    content: str
    page_start: int | None
    page_end: int | None
    section_title: str
    chunk_index: int
    token_count: int
    content_hash: str


def _split_long(text: str, size: int) -> list[str]:
    # Prefer sentence boundaries; if a single sentence is oversized, recurse at
    # punctuation, then at whitespace, and finally at Unicode character spans.
    parts = re.split(r"(?<=[。！？；.!?;])\s*", text)
    if len(parts) <= 1:
        parts = re.split(r"(?<=[，,、：:])", text)
    if len(parts) <= 1:
        parts = re.split(r"\s+", text)
    if len(parts) <= 1:
        return [text[i:i + size] for i in range(0, len(text), size)]
    output: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if token_count(part) > size:
            if current:
                output.append(current)
                current = ""
            output.extend(_split_long(part, size))
        elif not current or token_count(current + " " + part) <= size:
            current = f"{current} {part}".strip()
        else:
            output.append(current)
            current = part
    if current:
        output.append(current)
    return output


def chunk_segments(segments: list[TextSegment], *, document_id: str, file_hash: str, max_tokens: int = 650, overlap_tokens: int = 90) -> list[Chunk]:
    if not segments:
        return []
    normalized: list[TextSegment] = []
    for segment in segments:
        for part in _split_long(segment.text, max_tokens):
            normalized.append(TextSegment(part, segment.page, segment.section))
    groups: list[list[TextSegment]] = []
    current: list[TextSegment] = []
    current_text = ""
    current_section = ""
    for segment in normalized:
        candidate = f"{current_text}\n\n{segment.text}".strip()
        section_change = bool(current and segment.section and segment.section != current_section)
        if current and (token_count(candidate) > max_tokens or section_change):
            groups.append(current)
            carry: list[TextSegment] = []
            carried = 0
            for prior in reversed(current):
                count = token_count(prior.text)
                if carried + count > overlap_tokens:
                    break
                carry.insert(0, prior)
                carried += count
            current = carry
            current_text = "\n\n".join(item.text for item in carry)
            current_section = carry[-1].section if carry else ""
            while current and token_count(f"{current_text}\n\n{segment.text}") > max_tokens:
                current.pop(0)
                current_text = "\n\n".join(item.text for item in current)
                current_section = current[-1].section if current else ""
        current.append(segment)
        current_text = f"{current_text}\n\n{segment.text}".strip()
        current_section = segment.section or current_section
    if current:
        groups.append(current)
    chunks: list[Chunk] = []
    seen: set[str] = set()
    for index, group in enumerate(groups):
        content = "\n\n".join(segment.text for segment in group).strip()
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        pages = [segment.page for segment in group if segment.page is not None]
        section = next((segment.section for segment in reversed(group) if segment.section), "")
        stable_id = str(uuid.uuid5(NAMESPACE, f"{document_id}:{index}:{file_hash}:{digest}"))
        chunks.append(Chunk(stable_id, content, min(pages) if pages else None, max(pages) if pages else None, section, len(chunks), token_count(content), digest))
    return chunks
