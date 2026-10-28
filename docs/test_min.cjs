const P=require('pptxgenjs');const p=new P();p.layout='LAYOUT_WIDE';let s=p.addSlide();s.addText('Hello',{x:1,y:1,w:4,h:1});p.writeFile({fileName:'docs/test_min.pptx'});
