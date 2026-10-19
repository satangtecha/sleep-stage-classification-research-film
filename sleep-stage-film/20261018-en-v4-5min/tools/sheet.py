#!/usr/bin/env python3
"""contact sheet: python3 tools/sheet.py out.jpg cols img1 img2 ... (each scaled to 960x540)"""
import sys
from PIL import Image
out,cols,files=sys.argv[1],int(sys.argv[2]),sys.argv[3:]
ims=[Image.open(f).convert('RGB').resize((960,540)) for f in files]
rows=(len(ims)+cols-1)//cols
sh=Image.new('RGB',(960*cols,540*rows),'black')
for i,im in enumerate(ims): sh.paste(im,((i%cols)*960,(i//cols)*540))
sh.save(out,quality=88)
