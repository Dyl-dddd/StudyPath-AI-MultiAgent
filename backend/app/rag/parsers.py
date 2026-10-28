import re
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
import pymupdf as fitz
from docx import Document as WordDocument
from docx.table import Table
from docx.text.paragraph import Paragraph
from app.core.config import get_settings


@dataclass
class TextSegment:
    text: str
    page: int | None = None
    section: str = ""


def _clean(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _ocr_image(image: bytes, label: str) -> str:
    settings = get_settings()
    if not settings.ocr_enabled:
        return ""
    try:
        from io import BytesIO
        from PIL import Image
        import pytesseract
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        if settings.tessdata_dir:
            # pytesseract tokenizes config with Windows-specific shlex behavior
            # that leaves quotes in paths. Tesseract reads this environment
            # variable directly, preserving paths with spaces.
            os.environ["TESSDATA_PREFIX"] = str(Path(settings.tessdata_dir).resolve())
        with Image.open(BytesIO(image)) as source:
            if source.width * source.height > 40_000_000:
                raise ValueError("OCR image exceeds the 40 megapixel safety limit")
            text = pytesseract.image_to_string(source, lang=settings.ocr_languages, timeout=35)
        return _clean(text)
    except Exception as error:
        raise ValueError(f"{label} OCR 失败：{type(error).__name__}；请检查 Tesseract 及语言包配置") from None


def parse_pdf(path: Path) -> list[TextSegment]:
    segments: list[TextSegment] = []
    heading = ""
    ocr_pages = 0
    with fitz.open(path) as document:
        if document.page_count > 500:
            raise ValueError("PDF 超过 500 页索引上限")
        for index, page in enumerate(document, start=1):
            # Block extraction preserves paragraph-like boundaries and source page.
            blocks = page.get_text("blocks")
            text = _clean("\n\n".join(str(block[4]) for block in blocks if len(block) > 4))
            if len(text) < 50 and page.get_images(full=True) and get_settings().ocr_enabled:
                ocr_pages += 1
                if ocr_pages > get_settings().ocr_max_pages:
                    raise ValueError(f"PDF 超过 OCR 页数上限 {get_settings().ocr_max_pages}")
                pix = page.get_pixmap(dpi=get_settings().ocr_dpi, alpha=False)
                ocr_text = _ocr_image(pix.tobytes("png"), f"PDF 第 {index} 页")
                text = _clean(f"{text}\n\n{ocr_text}")
            if not text:
                if page.get_images(full=True):
                    raise ValueError(f"PDF 第 {index} 页未提取到文字，检测到扫描图像；请启用 OCR 并安装 Tesseract")
                continue
            for line in text.splitlines():
                candidate = _clean(line)
                if re.match(r"^(第.{1,30}[章节篇部]|[0-9一二三四五六七八九十]+[.、])", candidate):
                    heading = candidate[:500]
            for paragraph in re.split(r"\n\s*\n", text):
                paragraph = _clean(paragraph)
                if paragraph:
                    if re.match(r"^(第.{1,30}[章节篇部]|[0-9一二三四五六七八九十]+[.、])", paragraph):
                        heading = paragraph[:500]
                    segments.append(TextSegment(paragraph, index, heading))
    return segments


def _iter_docx_blocks(document):
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def parse_docx(path: Path) -> list[TextSegment]:
    if not zipfile.is_zipfile(path):
        raise ValueError("DOCX 文件结构无效")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        expanded_bytes = sum(item.file_size for item in entries)
        if len(entries) > 2500 or expanded_bytes > 120 * 1024 * 1024 or any(item.compress_size and item.file_size / item.compress_size > 250 for item in entries):
            raise ValueError("DOCX 解压内容超过安全限制")
    document = WordDocument(path)
    result: list[TextSegment] = []
    heading = ""
    for block in _iter_docx_blocks(document):
        if isinstance(block, Paragraph):
            text = _clean(block.text)
            if not text:
                continue
            style = (block.style.name if block.style else "").lower()
            if "heading" in style or "标题" in style:
                heading = text[:500]
                continue
            result.append(TextSegment(text, None, heading))
        else:
            for row in block.rows:
                cells = [_clean(cell.text) for cell in row.cells]
                text = " | ".join(value for value in cells if value)
                if text:
                    result.append(TextSegment(text, None, heading))
    if get_settings().ocr_enabled:
        from docx.oxml.ns import qn
        seen: set[str] = set()
        image_count = 0
        for blip in document.element.body.iter(qn("a:blip")):
            rid = blip.get(qn("r:embed"))
            if not rid or rid in seen:
                continue
            seen.add(rid)
            image_count += 1
            if image_count > get_settings().ocr_max_pages:
                raise ValueError(f"DOCX 图片 OCR 数量超过上限 {get_settings().ocr_max_pages}")
            part = document.part.related_parts.get(rid)
            if not part:
                continue
            text = _ocr_image(part.blob, f"DOCX 图片 {image_count}")
            if text:
                result.append(TextSegment(text, None, f"{heading}（图片 OCR）".strip()))
    return result


def parse_text(path: Path) -> list[TextSegment]:
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("文本中检测到二进制内容")
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("无法识别文本编码，请保存为 UTF-8 或 GB18030")
    result: list[TextSegment] = []
    heading = ""
    for paragraph in re.split(r"\n\s*\n", text):
        paragraph = _clean(paragraph)
        if not paragraph:
            continue
        if re.match(r"^(#{1,6}\s+|第.{1,30}[章节篇部]\s*$)", paragraph):
            heading = paragraph.lstrip("# ")[:500]
        else:
            result.append(TextSegment(paragraph, None, heading))
    return result


def parse_document(path: Path, file_type: str) -> list[TextSegment]:
    if file_type == "PDF":
        return parse_pdf(path)
    if file_type == "DOCX":
        return parse_docx(path)
    return parse_text(path)
