"""Generate the public Chinese course PDF used by the upload smoke test."""
import os
import re
import textwrap
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "operating_systems_sample.md"
DESTINATION = ROOT / "examples" / "operating_systems_sample.pdf"


def main():
    font = Path(os.getenv("STUDYPATH_CJK_FONT", r"C:\Windows\Fonts\msyh.ttc"))
    if not font.is_file():
        raise RuntimeError("Set STUDYPATH_CJK_FONT to an installed Chinese TrueType font before generating the sample PDF")
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    sections, heading, paragraphs = [], "", []
    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            if heading:
                sections.append((heading, paragraphs))
            heading, paragraphs = line[3:], []
        elif line and not line.startswith("# "):
            paragraphs.append(line)
    if heading:
        sections.append((heading, paragraphs))
    pdf = pymupdf.open()
    for section_title, section_paragraphs in sections:
        page = pdf.new_page(width=595, height=842)
        page.insert_text((46, 53), "操作系统基础课程资料 · 公开验证样例", fontname="zh", fontfile=str(font), fontsize=10, color=(.47, .43, .57))
        page.insert_textbox(pymupdf.Rect(46, 82, 545, 121), section_title, fontname="zh", fontfile=str(font), fontsize=17, color=(.26, .21, .42))
        body = "\n\n".join("\n".join(textwrap.wrap(paragraph, width=38, break_long_words=True, break_on_hyphens=False)) for paragraph in section_paragraphs)
        remaining = page.insert_textbox(pymupdf.Rect(48, 142, 545, 785), body, fontname="zh", fontfile=str(font), fontsize=11, lineheight=1.55, color=(.18, .17, .22))
        if remaining < 0:
            raise RuntimeError(f"Sample page overflow: {section_title}")
        page.insert_text((500, 817), f"第 {len(pdf)} 页", fontname="zh", fontfile=str(font), fontsize=9, color=(.55, .52, .60))
    pdf.set_metadata({"title": "操作系统基础课程资料", "author": "StudyPath AI public test material", "subject": "RAG document parsing and citation test"})
    pdf.save(DESTINATION, garbage=4, deflate=True)
    pdf.close()
    print(f"Created sample PDF ({DESTINATION.stat().st_size} bytes, {len(sections)} pages)")


if __name__ == "__main__":
    main()
