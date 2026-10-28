from pathlib import Path
from docx import Document
import re
root=Path('.')
files=sorted(p for base in (root/'src',root/'backend'/'app') for p in base.rglob('*') if p.is_file() and p.suffix.lower() in {'.ts','.vue','.css','.py','.json'} and not any(part in {'node_modules','__pycache__'} for part in p.parts) and '.env' not in p.name and p.suffix.lower()!='.pyc')
doc=Document(next((root/'docs'/'copyright').glob('03_*.docx')))
groups=[0]
for p in doc.paragraphs:
    if any(el.tag.endswith('}br') and el.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type')=='page' for el in p._p.iter()):
        groups.append(0)
    elif p.text.strip() and not p.text.startswith('// '+chr(25991)+chr(20214)+chr(65306)):
        groups[-1]+=1
print('source_files',len(files),'source_physical_lines',sum(len(p.read_text(encoding='utf-8-sig',errors='replace').splitlines()) for p in files))
print('source_doc_page_groups',len(groups),'rows_per_page_min',min(groups),'max',max(groups),'all_pages_50plus',all(n>=50 for n in groups))
patterns=[re.compile(rb'sk-[A-Za-z0-9]{20,}'),re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}')]
hits=[]
for path in files:
    data=path.read_bytes()
    for pat in patterns:
        for m in pat.finditer(data):
            hits.append((path,data[:m.start()].count(b'\n')+1))
print('credential_like_literals',len(hits))
for path,line in hits: print(f'{path}:{line}')

