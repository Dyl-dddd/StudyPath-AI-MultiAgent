import zipfile, os
from PIL import Image, ImageOps, ImageDraw
from io import BytesIO
src='docs/copyright/02_软件说明书与用户手册_修订版.docx'
out='docs/ppt-assets/manual'
os.makedirs(out,exist_ok=True)
thumbs=[]
with zipfile.ZipFile(src) as z:
 for n in [x for x in z.namelist() if x.startswith('word/media/')]:
  data=z.read(n); name=os.path.basename(n); p=os.path.join(out,name);open(p,'wb').write(data)
  im=Image.open(BytesIO(data)).convert('RGB'); size=im.size
  im.thumbnail((420,240)); tile=Image.new('RGB',(440,290),'white');tile.paste(im,((440-im.width)//2,8));
  d=ImageDraw.Draw(tile);d.text((12,258),f'{name}  {size}',fill='black');thumbs.append(tile)
cols=4; rows=(len(thumbs)+cols-1)//cols
sheet=Image.new('RGB',(cols*440,rows*290),(235,232,244))
for i,t in enumerate(thumbs):sheet.paste(t,((i%cols)*440,(i//cols)*290))
sheet.save('docs/ppt-assets/manual-contact-sheet.jpg',quality=90)
print('saved',len(thumbs),'contact sheet')
