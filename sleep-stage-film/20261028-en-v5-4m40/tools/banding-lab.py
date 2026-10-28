import numpy as np, subprocess, os, sys, time
W,H,N=1920,1080,90
rng=np.random.default_rng(42)
y,x=np.mgrid[0:H,0:W].astype(np.float32)
base=np.array([7,16,28],np.float32); top=np.array([10,20,34],np.float32)
t=(y/H)[...,None]
r=np.sqrt(((x-700)/1100)**2+((y-400)/700)**2)[...,None]
glow=np.clip(1-r,0,1)**2*np.array([3,6,10],np.float32)
ideal=base+(top-base)*t+glow            # float truth
tpdf=(rng.random((H,W,1),dtype=np.float32)+rng.random((H,W,1),dtype=np.float32)-1.0)  # +-1, triangular
variants={}
variants['plain']=np.clip(np.rint(ideal),0,255).astype(np.uint8)
variants['post_mask']=np.clip(np.rint(ideal)+np.rint(tpdf),0,255).astype(np.uint8)           # +-1 added AFTER 8-bit rounding
variants['pre_tpdf']=np.clip(np.rint(ideal+tpdf),0,255).astype(np.uint8)                       # dither BEFORE rounding
def enc(name,frames_fn):
    out=f'{name}.mp4'
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgba','-s','1920x1080','-r','30','-i','pipe:0','-an',
         '-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p','-c:v','libx264','-preset','slow','-crf','18','-tune','animation','-g','90',
         '-x264-params','aq-mode=3','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv','-threads','1','-movflags','+faststart',out]
    t0=time.time();p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for i in range(N): p.stdin.write(frames_fn(i).tobytes())
    p.stdin.close();p.wait();return out,time.time()-t0
def rgba(a):
    o=np.empty((H,W,4),np.uint8);o[...,:3]=a;o[...,3]=255;return o
def dec(out,n=60):
    c=['ffmpeg','-hide_banner','-loglevel','error','-i',out,'-vf',f'select=eq(n\\,{n}),scale=in_color_matrix=bt709:in_range=tv:out_range=full,format=rgb24','-frames:v','1','-f','rawvideo','-']
    return np.frombuffer(subprocess.run(c,capture_output=True).stdout,np.uint8).reshape(H,W,3)
def blockmean(a,b=24): return a.reshape(H//b,b,W//b,b,-1).mean(axis=(1,3))
res={}
for k,v in variants.items():
    fr=rgba(v)
    out,sec=enc(k,lambda i,fr=fr:fr)
    d=dec(out).astype(np.float32)
    err=blockmean(d-ideal)            # low-passed error vs float truth: banding shows as structured +-0.5
    res[k]=(os.path.getsize(out),float(np.abs(err).max()),float(np.abs(err).mean()),sec)
# per-frame varying noise (what NOT to do)
def vary(i):
    g=np.random.default_rng(1000+i);tp=(g.random((H,W,1),dtype=np.float32)+g.random((H,W,1),dtype=np.float32)-1.0)
    return rgba(np.clip(np.rint(ideal+tp),0,255).astype(np.uint8))
out,sec=enc('pre_tpdf_varying',vary);d=dec(out).astype(np.float32);err=blockmean(d-ideal)
res['pre_tpdf_varying']=(os.path.getsize(out),float(np.abs(err).max()),float(np.abs(err).mean()),sec)
# bg colour exactness: flat #07101C
flat=np.zeros((H,W,3),np.uint8);flat[:]=(7,16,28)
fr=rgba(flat);out,sec=enc('flat',lambda i:fr);d=dec(out)
print('flat #07101C decoded mean',d.reshape(-1,3).mean(0),'max abs dev',np.abs(d.astype(int)-np.array([7,16,28])).max())
print('%-18s %10s %10s %10s %6s'%('variant','bytes','maxLPerr','meanLPerr','sec'))
for k,(b,m,a,s) in res.items(): print('%-18s %10d %10.3f %10.3f %6.1f'%(k,b,m,a,s))
