// Spectrogram, CNN plates, 128-cell embedding bars
import {createCanvas} from '@napi-rs/canvas';
import {P,clamp,lerp,rgba,shade,mixCol,smooth,cubic,outBack,T,heat,rnd,poly} from '../lib.mjs';
import {surface} from '../light.mjs';
const specCache=new Map();
/** value in 0..1 for column u (0..1) and row v (0 = low freq) of an illustrative N2 epoch */
export const specVal=(u,v,seed=2)=>{const base=Math.exp(-v*5.5)*.85;const spindle=Math.exp(-((v-.28)**2)/.004)*Math.exp(-((u-.62)**2)/.01)*.9;const tex=(rnd(Math.floor(u*29)*131+Math.floor(v*64)*17+seed)-.5)*.25*(1-v*.6);return clamp(base+spindle+tex+.05)};
function specImg(w,h,cols=29,rows=43,seed=2){const key=[w,h,cols,rows,seed].join();if(specCache.has(key))return specCache.get(key);const cv=createCanvas(w,h),g=cv.getContext('2d'),cw=w/cols,rh=h/rows;
  for(let i=0;i<cols;i++)for(let j=0;j<rows;j++){g.fillStyle=heat(specVal(i/(cols-1),j/(rows-1),seed));g.fillRect(i*cw,h-(j+1)*rh,cw+.6,rh+.6)}
  specCache.set(key,cv);return cv}
/** Spectrogram: columns revealed p in 0..1 */
export function Spectrogram(c,o){const {k,el,x,y,w,h,p=1,alpha=1,r=10,cols=29,rows=43,seed=2}=o;k&&k.rec('Spectrogram',{el,x,y,w,h});if(alpha<=0||p<=0)return;
  c.save();c.globalAlpha*=alpha;surface(c,[x-6,y-6,w+12,h+12],'#0C1A2E',{level:'E2',r:r+4,gradient:.03});c.save();c.beginPath();c.roundRect(x,y,w,h,r);c.clip();
  const img=specImg(Math.round(w),Math.round(h),cols,rows,seed),vis=Math.round(cols*clamp(p))/cols*w;c.drawImage(img,0,0,vis,h,x,y,vis,h);c.restore();c.restore()}
/** three stacked CNN plates (32 -> 64 -> 128), slow shear oscillation. p appears per plate */
export function Plates(c,o){const {k,el,cx,cy,t=0,p=[1,1,1],alpha=1,squeeze=0}=o;k&&k.rec('Plates',{el,cx,cy});c.save();c.globalAlpha*=alpha;
  const cfg=[{n:32,w:260,h:210},{n:64,w:190,h:150},{n:128,w:120,h:90}],gap=260;
  cfg.forEach((q,i)=>{const pp=clamp(p[i]);if(pp<=0)return;const x=cx+(i-1)*gap,sh=Math.sin(t*.9+i)*.12+.28,ww=q.w*(1-.55*squeeze*(i/2)),hh=q.h;
    c.save();c.globalAlpha*=smooth(pp*2);c.translate(x,cy);const dx=lerp(40,0,outBack(pp));c.translate(dx,0);
    for(let L=5;L>=0;L--){const off=L*10;c.save();c.transform(1,-sh*.5,0,1,0,0);
      surface(c,[-ww/2-off*.6,-hh/2+off*.3,ww,hh],mixCol('#1F3C66','#3B6FB0',1-L/6),{level:L===0?'E2':'E1',r:6,gradient:.04});c.restore()}
    T(c,String(q.n),0,hh/2+66,{size:34,weight:'bold',color:P.ink,align:'center'});c.restore()});
  c.restore()}
/** vertical 128-cell bar; cells coloured by a deterministic embedding */
export function Bar128(c,o){const {k,el,x,y,w=34,h=300,seed=0,alpha=1,p=1,lit=0}=o;if(alpha<=0||p<=0)return;c.save();c.globalAlpha*=alpha;const n=32,ch=h/n;
  for(let i=0;i<n;i++){if(i/n>p)break;const v=rnd(seed*97+i*7+3);c.fillStyle=mixCol(heat(.25+v*.6),'#FFF2C8',lit*.5);c.fillRect(x,y+i*ch,w,ch-1)}c.restore()}
