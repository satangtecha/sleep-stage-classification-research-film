// Light and shadow layer (plan section 4): one key light from the upper left, five elevations, glow, bevel, baked vignette.
import {createCanvas} from '@napi-rs/canvas';
import {W,H,P,clamp,lerp,rgba,shade,mixCol,smooth,rnd} from './lib.mjs';

export const CARD=[56,44,1808,992];
export const ELEV={E1:{o:[2,6],b:14,a:.35},E2:{o:[5,12],b:28,a:.50},E3:{o:[10,22],b:44,a:.60},E4:{o:[16,34],b:60,a:.62}};
export const scaleOf=c=>{const m=c.getTransform();return Math.hypot(m.a,m.b)||1};
const lv=l=>typeof l==='string'?ELEV[l]:l;

/** shadowed(c, spec, fn): draws fn with a canvas shadow whose offset and blur follow the current scale (canvas shadows ignore transforms) */
export function shadowed(c,spec,fn,{k=1,alpha=1}={}){
  if(!spec||k<=0){fn();return}
  const s=scaleOf(c);c.save();c.shadowColor=`rgba(0,0,0,${(spec.a*k*alpha).toFixed(3)})`;c.shadowBlur=spec.b*s*k;c.shadowOffsetX=spec.o[0]*s*k;c.shadowOffsetY=spec.o[1]*s*k;fn();c.restore()}
/** elev(c, 'E2', drawFn, {k}) : k in 0..1 animates the level (0 = flat) */
export function elev(c,level,fn,opt={}){shadowed(c,lv(level),fn,opt)}

/** Surface: rounded card with gradient, rim light and elevation shadow. rect=[x,y,w,h] */
export function surface(c,rect,color,{level='E2',gradient=.06,rim=true,r=16,alpha=1,k=1,contactShadow=false}={}){
  const [x,y,w,h]=rect;if(alpha<=0)return;c.save();c.globalAlpha*=clamp(alpha);
  const path=()=>{c.beginPath();c.roundRect(x,y,w,h,r)};
  elev(c,level,()=>{path();c.fillStyle=color;c.fill()},{k});
  const g=c.createLinearGradient(0,y,0,y+h);g.addColorStop(0,shade(color,1+gradient));g.addColorStop(1,shade(color,1-gradient));path();c.fillStyle=g;c.fill();
  if(rim){c.save();path();c.clip();c.fillStyle='rgba(255,255,255,.10)';c.fillRect(x,y,w,1.5);c.restore()}
  if(contactShadow)contact(c,rect);
  c.restore()}
/** contact shadow at the foot of an object */
export function contact(c,[x,y,w,h]){const s=scaleOf(c);c.save();c.shadowColor='rgba(0,0,0,.5)';c.shadowBlur=6*s;c.shadowOffsetY=3*s;c.fillStyle='rgba(0,0,0,.001)';c.beginPath();c.roundRect(x+6,y+h-4,w-12,4,2);c.fill();c.restore()}
/** Tray (night strip bed): darker than the card, inset shadow on top, faint light on the bottom edge */
export function tray(c,x,y,w,h,{alpha=1,r=10}={}){
  c.save();c.globalAlpha*=clamp(alpha);c.beginPath();c.roundRect(x,y,w,h,r);c.fillStyle='#060D17';c.fill();
  c.save();c.clip();const g=c.createLinearGradient(0,y,0,y+10);g.addColorStop(0,'rgba(0,0,0,.45)');g.addColorStop(1,'rgba(0,0,0,0)');c.fillStyle=g;c.fillRect(x,y,w,10);c.restore();
  c.strokeStyle='rgba(255,255,255,.05)';c.lineWidth=1;c.beginPath();c.moveTo(x+r,y+h+.5);c.lineTo(x+w-r,y+h+.5);c.stroke();c.restore()}
/** bevel tile: vertical gradient + top highlight + bottom shade */
export function bevel(c,x,y,w,h,color,{r=3,half=false,alpha=1}={}){
  if(alpha<=0)return;c.save();c.globalAlpha*=clamp(alpha);
  const g=c.createLinearGradient(0,y,0,y+h);g.addColorStop(0,shade(color,1.12));g.addColorStop(1,shade(color,.90));
  c.beginPath();c.roundRect(x,y,w,h,r);c.fillStyle=g;c.fill();
  const k=half?.5:1;c.fillStyle=`rgba(255,255,255,${.22*k})`;c.fillRect(x+r*.6,y,w-r*1.2,1);c.fillStyle=`rgba(0,0,0,${.28*k})`;c.fillRect(x+r*.6,y+h-1.5,w-r*1.2,1.5);c.restore()}
/** glow: draws only the halo of a shape (shape itself is off-canvas). shapeFn must draw the filled shape in user space. */
export function glow(c,shapeFn,color,{blur=14,alpha=.45,breathe=0,t=0,passes=1}={}){
  const a=alpha*(breathe?(0.85+0.15*Math.sin(2*Math.PI*breathe*t)):1);if(a<=0.003)return;
  const s=scaleOf(c);c.save();c.globalCompositeOperation='lighter';c.translate(-6000/s,0);c.shadowColor=rgba(color,clamp(a));c.shadowBlur=blur*s;c.shadowOffsetX=6000;c.fillStyle='#000';
  for(let i=0;i<passes;i++)shapeFn();c.restore()}
export const glowRect=(c,x,y,w,h,color,o={},r=3)=>glow(c,()=>{c.beginPath();c.roundRect(x,y,w,h,r);c.fill()},color,o);
export const glowCircle=(c,x,y,rad,color,o={})=>glow(c,()=>{c.beginPath();c.arc(x,y,rad,0,Math.PI*2);c.fill()},color,o);
export const glowLine=(c,pts,color,width,o={})=>glow(c,()=>{c.beginPath();pts.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.lineWidth=width;c.lineCap='round';c.strokeStyle='#000';c.stroke()},color,o);

// ---------- baked background: card + vignette + wash + static TPDF dither, rounded in float (plan 10.4) ----------
const N=W*H;
let base=null; // {outer: Uint8ClampedArray rgba of the purple surround+card shadow, mask: Uint8Array, vigT: Float32Array, noise: Float32Array, wy: Float32Array}
function setup(){
  if(base)return base;const cv=createCanvas(W,H),x=cv.getContext('2d');
  const g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#141236');g.addColorStop(.5,'#0B0B22');g.addColorStop(1,'#16123A');x.fillStyle=g;x.fillRect(0,0,W,H);
  for(const [cx,cy,r,a] of [[420,-520,700,.55],[1180,-560,720,.45],[2050,260,700,.5],[-260,980,520,.35]]){const gr=x.createRadialGradient(cx,cy,r*.85,cx,cy,r*1.05);gr.addColorStop(0,'rgba(120,110,220,0)');gr.addColorStop(.9,`rgba(140,130,240,${a*.35})`);gr.addColorStop(1,'rgba(140,130,240,0)');x.fillStyle=gr;x.beginPath();x.arc(cx,cy,r*1.05,0,Math.PI*2);x.fill();x.strokeStyle=`rgba(170,160,255,${a})`;x.lineWidth=2.5;x.beginPath();x.arc(cx,cy,r,0,Math.PI*2);x.stroke()}
  x.save();x.shadowColor='rgba(0,0,0,0.6)';x.shadowBlur=40;x.shadowOffsetX=10;x.shadowOffsetY=22;x.fillStyle=P.card;x.beginPath();x.roundRect(...CARD,22);x.fill();x.restore();
  const outer=new Uint8ClampedArray(x.getImageData(0,0,W,H).data);
  const m=createCanvas(W,H).getContext('2d');m.fillStyle='#fff';m.beginPath();m.roundRect(...CARD,22);m.fill();const md=m.getImageData(0,0,W,H).data;
  const mask=new Uint8Array(N);for(let i=0;i<N;i++)mask[i]=md[i*4+3];
  const vigT=new Float32Array(N),wy=new Float32Array(N),noise=new Float32Array(N);
  const cx=CARD[0]+CARD[2]/2,cy=CARD[1]+CARD[3]/2,dmax=Math.hypot(CARD[2]/2,CARD[3]/2);
  for(let y=0;y<H;y++)for(let xx=0;xx<W;xx++){const i=y*W+xx;const rr=Math.hypot(xx-cx,y-cy)/dmax;const u=clamp((rr-.55)/.45);vigT[i]=u*u*(3-2*u);const v=clamp((y-cy)/(CARD[3]/2));wy[i]=v>0?v*v:0;noise[i]=rnd(i)+rnd(i+N)-1}
  base={outer,mask,vigT,wy,noise,ctx:createCanvas(W,H).getContext('2d')};base.img=base.ctx.createImageData(W,H);return base}
const cache=new Map();
/** bgField(s, wash): opaque ImageData of the whole frame; wash={rgb:[r,g,b],a,bottom?,screen?} ; cached (LRU 16) */
export function bgField(s,wash=null){
  const key=Math.round(s*100)+'|'+(wash?`${wash.rgb}|${wash.a.toFixed(3)}|${wash.bottom?1:0}|${wash.screen?1:0}`:'-');
  if(cache.has(key)){const v=cache.get(key);cache.delete(key);cache.set(key,v);return v}
  const B=setup(),img=B.ctx.createImageData(W,H),d=img.data,card=[10,20,34];
  const sa=Math.round(s*100)/100,wa=wash?wash.a:0,wr=wash?wash.rgb:[0,0,0],bot=wash&&wash.bottom,scr=wash&&wash.screen;
  const o=B.outer,mk=B.mask,vg=B.vigT,wy=B.wy,nz=B.noise;
  for(let i=0,p=0;i<N;i++,p+=4){const m=mk[i];
    if(m===255){const v=1-sa*vg[i],a=bot?wa*wy[i]:wa,n=nz[i];
      for(let c=0;c<3;c++){let b=card[c];if(a>0){b=scr?255-(255-b)*(1-wr[c]/255*a):b*(1-a)+wr[c]*a}d[p+c]=b*v+n}d[p+3]=255}
    else if(m===0){d[p]=o[p];d[p+1]=o[p+1];d[p+2]=o[p+2];d[p+3]=255}
    else{const t=m/255,v=1-sa*vg[i];for(let c=0;c<3;c++)d[p+c]=o[p+c]*(1-t)+(card[c]*v+nz[i])*t;d[p+3]=255}}
  cache.set(key,img);if(cache.size>16)cache.delete(cache.keys().next().value);return img}
export function paintBackground(c,s,wash){c.putImageData(bgField(s,wash),0,0);
  c.strokeStyle='rgba(255,255,255,0.06)';c.lineWidth=1.5;c.beginPath();c.roundRect(...CARD,22);c.stroke()}
export const clipCard=c=>{c.beginPath();c.roundRect(...CARD,22);c.clip()};
