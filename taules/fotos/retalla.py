# Retalla i retoca fotos de jugador: quadrat 600x600, cap a la mateixa mida i posició a totes
import sys, numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
MIDA=600; CAP=0.45; AIRE=0.07   # cap (front->barbeta) = 45% de l'alçada; 7% d'aire a dalt
def processa(src,dst,cx,top,chin):
    im=ImageOps.exif_transpose(Image.open(src)).convert('RGB'); W,H=im.size
    h=chin-top; s=min(H,W,int(h/CAP))
    t=max(0,min(top-AIRE*s,H-s)); l=max(0,min(cx-s/2,W-s))
    im=im.crop((int(l),int(t),int(l)+s,int(t)+s))
    a=np.asarray(im).astype(np.float32)
    paret=a[:int(s*.35)].reshape(-1,3); paret=paret[paret.mean(1)>170]   # zones clares = paret blanca
    if len(paret)>500: m=paret.mean(0); a*=(m.mean()/m)**0.8               # treu dominant de color
    im=Image.fromarray(np.clip(a,0,255).astype(np.uint8))
    im=ImageOps.autocontrast(im,cutoff=0.4)
    im=ImageEnhance.Brightness(im).enhance(1.03); im=ImageEnhance.Contrast(im).enhance(1.05)
    im=im.resize((MIDA,MIDA),Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.0,50,2))
    im.save(dst,'JPEG',quality=90,optimize=True,progressive=True)
if __name__=='__main__':
    src,dst,cx,top,chin=sys.argv[1:6]; processa(src,dst,float(cx),float(top),float(chin))
