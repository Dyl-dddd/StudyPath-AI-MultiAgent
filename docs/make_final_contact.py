from PIL import Image,ImageDraw
import glob,os,math
files=sorted(glob.glob('docs/final-slide-*.jpg')); ts=[]
for f in files:
 im=Image.open(f).convert('RGB');im.thumbnail((400,225));tile=Image.new('RGB',(420,255),'white');tile.paste(im,((420-im.width)//2,5));ImageDraw.Draw(tile).text((10,234),os.path.basename(f),fill='black');ts.append(tile)
cols=4;rows=math.ceil(len(ts)/cols);sheet=Image.new('RGB',(cols*420,rows*255),(230,228,238))
for i,t in enumerate(ts):sheet.paste(t,((i%cols)*420,(i//cols)*255))
sheet.save('docs/final-contact.jpg',quality=88);print('slides',len(files))
