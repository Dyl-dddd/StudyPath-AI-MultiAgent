from pathlib import Path
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from unicodedata import east_asian_width
import re

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / '03_源程序鉴别材料.docx'
VERSION = 'V1.0'
SOFTWARE = '智学研途 AI 个性化学习平台（StudyPath AI）'
WIDTH = 96

def display_width(text):
    return sum(2 if east_asian_width(char) in {'F', 'W', 'A'} else 1 for char in text)

def split_display_width(text, limit):
    chunks, current, width = [], [], 0
    for char in text:
        char_width = 2 if east_asian_width(char) in {'F', 'W', 'A'} else 1
        if current and width + char_width > limit:
            chunks.append(''.join(current))
            current, width = [], 0
        current.append(char)
        width += char_width
    if current or not chunks:
        chunks.append(''.join(current))
    return chunks

files = sorted([p for base in (ROOT / 'src', ROOT / 'backend' / 'app') for p in base.rglob('*')
                if p.is_file() and p.suffix.lower() in {'.ts','.vue','.css','.py','.json'}
                and not any(part in {'node_modules','__pycache__'} for part in p.parts)
                and '.env' not in p.name and p.suffix.lower() != '.pyc'])
rows = []
for path in files:
    try:
        content = path.read_text(encoding='utf-8-sig').splitlines()
    except UnicodeDecodeError:
        content = path.read_text(encoding='utf-8', errors='replace').splitlines()
    relative = path.relative_to(ROOT).as_posix()
    for line_no, line in enumerate(content, 1):
        if not line.strip():
            continue
        if display_width(line) <= WIDTH:
            rows.append((relative, line_no, line, False))
        else:
            chunks = split_display_width(line, WIDTH)
            for index, chunk in enumerate(chunks):
                rows.append((relative, line_no, chunk, index > 0))

# 50 source display rows per page. The first 30 and last 30 pages are selected.
page_size = 50
page_count = len(rows) // page_size
if page_count <= 60:
    raise SystemExit(f'源代码不足 61 页，当前整理为 {page_count} 页；应交全部鉴别材料而非前后各 30 页。')
# Distribute remainder rows across the first pages so every page has at least 50 source rows.
page_offsets = [0]
for page_index in range(page_count):
    page_offsets.append(page_offsets[-1] + page_size + (1 if page_index < len(rows) % page_size else 0))
front = list(range(30))
back = list(range(page_count - 30, page_count))
selected_pages = front + back

doc = Document()
section = doc.sections[0]
section.page_width, section.page_height = Cm(21), Cm(29.7)
section.top_margin, section.bottom_margin = Cm(1.65), Cm(1.45)
section.left_margin, section.right_margin = Cm(1.55), Cm(1.35)
normal = doc.styles['Normal']
normal.font.name = 'Consolas'
normal._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
normal.font.size = Pt(8)
normal.paragraph_format.space_after = Pt(0)
normal.paragraph_format.line_spacing = Pt(9.5)
header = section.header.paragraphs[0]
header.alignment = 1
r=header.add_run(f'{SOFTWARE}　{VERSION}　源程序鉴别材料')
r.font.name='Microsoft YaHei'; r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); r.font.size=Pt(8); r.font.color.rgb=RGBColor(80,80,80)
footer = section.footer.paragraphs[0]
footer.alignment = 1
r=footer.add_run('著作权人：戴云龙　·　第')
r.font.name='Microsoft YaHei'; r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); r.font.size=Pt(8)
fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'),'PAGE'); footer._p.append(fld)
r=footer.add_run('页'); r.font.name='Microsoft YaHei'; r._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Microsoft YaHei'); r.font.size=Pt(8)

for output_page_index, source_page_index in enumerate(selected_pages):
    if output_page_index:
        doc.add_page_break()
    begin = page_offsets[source_page_index]
    end = page_offsets[source_page_index + 1]
    chunk = rows[begin:end]
    # File name labels are placed in the header margin as gray small text.
    active_file = None
    for relative, line_no, text, continuation in chunk:
        if relative != active_file:
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = Pt(9.5)
            rr = p.add_run(f'// 文件：{relative}')
            rr.font.name='Consolas'; rr.font.size=Pt(8); rr.font.color.rgb=RGBColor(80,80,80)
            active_file = relative
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = Pt(9.5)
        p.paragraph_format.keep_together = True
        prefix = '    ↳ ' if continuation else ''
        rr = p.add_run(prefix + text)
        rr.font.name='Consolas'; rr._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Consolas'); rr.font.size=Pt(8)
        rr.font.color.rgb=RGBColor(40,39,45)

doc.core_properties.title = f'{SOFTWARE} {VERSION} 源程序鉴别材料'
doc.core_properties.author = '戴云龙'
doc.core_properties.subject = '软件著作权登记源程序鉴别材料；请提交前核验连续页数及官方格式'
doc.save(OUT)
physical_lines = sum(len(path.read_text(encoding='utf-8-sig', errors='replace').splitlines()) for path in files)
print(f'file_count={len(files)} source_physical_lines={physical_lines} source_display_rows={len(rows)} total_pages={page_count} selected_pages={len(selected_pages)} output={OUT}')
