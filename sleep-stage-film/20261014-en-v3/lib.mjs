// Rendering primitives for the v3 film: fonts, easing, text, MathJax equations, 2D charts and a small 3D world
// projected with ecmanim's ThreeDCamera. Everything is drawn natively on @napi-rs/canvas.
import fs from 'node:fs';
import {GlobalFonts,Image} from '@napi-rs/canvas';
import {ThreeDCamera} from '@johnhenry/ecmanim/node';
import {mathjax} from 'mathjax-full/js/mathjax.js';
import {TeX} from 'mathjax-full/js/input/tex.js';
import {SVG} from 'mathjax-full/js/output/svg.js';
import {liteAdaptor} from 'mathjax-full/js/adaptors/liteAdaptor.js';
import {RegisterHTMLHandler} from 'mathjax-full/js/handlers/html.js';
import {AllPackages} from 'mathjax-full/js/input/tex/AllPackages.js';

export const W=1920,H=1080;
// Palette tuned to the reference: deep navy card, cyan primary, amber highlight, violet secondary.
export const P={bg:'#07101C',card:'#0A1422',ink:'#EEF3FA',muted:'#93A3B8',dim:'#56657A',line:'#22344C',grid:'#16263A',
  cyan:'#5BE0F0',amber:'#FFC46B',violet:'#B6A8FF',coral:'#FF8FA3',green:'#7EE0A1',blue:'#6FA8FF',white:'#FFFFFF'};
export const STAGE_COL=['#5BE0F0','#FFC46B','#B6A8FF','#6FA8FF','#FF8FA3'];
export const STAGES=['W','N1','N2','N3','REM'];

const FONT_CANDIDATES=[
  ['Film','/usr/share/fonts/opentype/inter/Inter-Regular.otf','C:/Windows/Fonts/segoeui.ttf'],
  ['FilmMed','/usr/share/fonts/opentype/inter/Inter-Medium.otf','C:/Windows/Fonts/seguisb.ttf'],
  ['FilmBold','/usr/share/fonts/opentype/inter/Inter-SemiBold.otf','C:/Windows/Fonts/seguisb.ttf'],
  ['FilmMono','/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf','C:/Windows/Fonts/consola.ttf'],
];
for(const [name,...files] of FONT_CANDIDATES){const f=files.find(x=>fs.existsSync(x));if(!f||!GlobalFonts.registerFromPath(f,name))throw Error('Missing font for '+name)}

// ---------- easing / timing ----------
export const clamp=(x,a=0,b=1)=>Math.min(b,Math.max(a,x));
export const lerp=(a,b,t)=>a+(b-a)*t;
export const smooth=x=>{x=clamp(x);return x*x*(3-2*x)};
export const cubic=x=>{x=clamp(x);return x<.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2};
export const outExpo=x=>{x=clamp(x);return x===1?1:1-Math.pow(2,-10*x)};
export const outBack=x=>{x=clamp(x);const c1=1.70158,c3=c1+1;return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2)};
/** eased progress of t through [a, a+d] */
export const seg=(t,a,d=1,f=cubic)=>f((t-a)/d);

// ---------- colour ----------
export function rgba(hex,a=1){const n=parseInt(hex.slice(1),16);return `rgba(${n>>16},${n>>8&255},${n&255},${a})`}
export function shade(hex,k){const n=parseInt(hex.slice(1),16);return '#'+[n>>16,n>>8&255,n&255].map(v=>Math.round(clamp(v*k,0,255)).toString(16).padStart(2,'0')).join('')}
export function mixCol(a,b,t){const A=parseInt(a.slice(1),16),B=parseInt(b.slice(1),16);return '#'+[16,8,0].map(s=>Math.round(lerp(A>>s&255,B>>s&255,clamp(t))).toString(16).padStart(2,'0')).join('')}
export function heat(v){v=clamp(v);const stops=['#0E1B33','#2B2F7A','#7A3F9E','#E06A7E','#FFC46B','#FFF2C8'];const x=v*(stops.length-1),i=Math.min(stops.length-2,Math.floor(x));return mixCol(stops[i],stops[i+1],x-i)}

// ---------- text ----------
export function font(size,weight='reg'){return `${size}px ${{reg:'Film',med:'FilmMed',bold:'FilmBold',mono:'FilmMono'}[weight]}`}
/** text with optional fade/rise; returns measured width */
export function T(c,s,x,y,{size=30,color=P.ink,align='left',weight='reg',alpha=1,rise=0,base='alphabetic',glow=0}={}){
  if(alpha<=0.002)return 0;c.save();c.globalAlpha*=clamp(alpha);c.font=font(size,weight);c.fillStyle=color;c.textAlign=align;c.textBaseline=base;
  if(glow){c.shadowColor=color;c.shadowBlur=glow}c.fillText(s,x,y+rise*(1-clamp(alpha)));const w=c.measureText(s).width;c.restore();return w}
export function measure(c,s,size,weight='reg'){c.save();c.font=font(size,weight);const w=c.measureText(s).width;c.restore();return w}
export function wrap(c,s,maxW,size,weight='reg'){c.save();c.font=font(size,weight);const out=[];let cur='';for(const w of s.split(' ')){const n=cur?cur+' '+w:w;if(cur&&c.measureText(n).width>maxW){out.push(cur);cur=w}else cur=n}if(cur)out.push(cur);c.restore();return out}
/** typewriter reveal */
export function typed(s,p){const n=Math.round(s.length*clamp(p));return s.slice(0,n)}
export function fmt(n,d=0){return n.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d})}

// ---------- MathJax equations ----------
const adaptor=liteAdaptor();RegisterHTMLHandler(adaptor);
const mjDoc=mathjax.document('',{InputJax:new TeX({packages:AllPackages}),OutputJax:new SVG({fontCache:'none'})});
const mathCache=new Map();
export function M(tex,color=P.ink,size=40){
  const key=tex+'|'+color+'|'+size;let img=mathCache.get(key);if(img)return img;
  let svg=adaptor.innerHTML(mjDoc.convert(tex,{display:true})).replace(/currentColor/g,color);
  const exPx=size*0.442;
  svg=svg.replace(/width="([\d.]+)ex" height="([\d.]+)ex"/,(_,w,h)=>`width="${(w*exPx).toFixed(1)}" height="${(h*exPx).toFixed(1)}"`);
  img=new Image();img.src=Buffer.from(svg);if(!img.width)throw Error('MathJax render failed: '+tex);mathCache.set(key,img);return img}
/** draw equation; align: 'left'|'center'|'right'; y is the vertical centre. p = left-to-right wipe progress */
export function EQ(c,tex,x,y,{color=P.ink,size=40,align='center',p=1,alpha=1,glow=0}={}){
  if(p<=0||alpha<=0)return {w:0,h:0};const img=M(tex,color,size),w=img.width,h=img.height;
  const x0=align==='center'?x-w/2:align==='right'?x-w:x,y0=y-h/2;
  c.save();c.globalAlpha*=clamp(alpha);c.beginPath();c.rect(x0-4,y0-20,(w+8)*clamp(p),h+40);c.clip();if(glow){c.shadowColor=color;c.shadowBlur=glow}
  c.drawImage(img,x0,y0);c.restore();
  if(p<1&&p>0){c.save();c.globalAlpha*=alpha*(1-p);const gx=x0+w*p;const g=c.createLinearGradient(gx-30,0,gx+6,0);g.addColorStop(0,rgba(color,0));g.addColorStop(1,rgba(color,.8));c.fillStyle=g;c.fillRect(gx-30,y0-6,36,h+12);c.restore()}
  return {w,h,x0,y0}}

// ---------- 2D drawing ----------
export function poly(c,pts,{stroke=P.cyan,width=3,alpha=1,fill=null,close=false,dash=null,glow=0,cap='round'}={}){
  if(pts.length<2||alpha<=0)return;c.save();c.globalAlpha*=clamp(alpha);c.lineJoin='round';c.lineCap=cap;c.beginPath();pts.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));if(close)c.closePath();
  if(fill){c.fillStyle=fill;c.fill()}if(stroke){if(dash)c.setLineDash(dash);if(glow){c.shadowColor=stroke;c.shadowBlur=glow}c.strokeStyle=stroke;c.lineWidth=width;c.stroke()}c.restore()}
/** draw-on polyline (partial by p) with glowing head */
export function drawOn(c,pts,p,opt={}){if(p<=0)return;const n=Math.max(2,Math.floor(pts.length*clamp(p)));poly(c,pts.slice(0,n),opt);if(p<1&&opt.head!==false){const q=pts[n-1];dot(c,q[0],q[1],(opt.width||3)*1.8,opt.stroke||P.cyan,opt.alpha??1,14)}}
export function dot(c,x,y,r,col,alpha=1,glow=0){if(alpha<=0||r<=0)return;c.save();c.globalAlpha*=clamp(alpha);if(glow){c.shadowColor=col;c.shadowBlur=glow}c.fillStyle=col;c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill();c.restore()}
export function rect(c,x,y,w,h,col,{alpha=1,r=0,stroke=null,sw=2}={}){if(alpha<=0)return;c.save();c.globalAlpha*=clamp(alpha);c.beginPath();if(r)c.roundRect(x,y,w,h,r);else c.rect(x,y,w,h);if(col){c.fillStyle=col;c.fill()}if(stroke){c.strokeStyle=stroke;c.lineWidth=sw;c.stroke()}c.restore()}
export function arrow(c,x1,y1,x2,y2,{col=P.ink,width=3,alpha=1,head=14,p=1}={}){if(p<=0)return;const x=lerp(x1,x2,p),y=lerp(y1,y2,p);poly(c,[[x1,y1],[x,y]],{stroke:col,width,alpha});const a=Math.atan2(y-y1,x-x1);poly(c,[[x-head*Math.cos(a-.45),y-head*Math.sin(a-.45)],[x,y],[x-head*Math.cos(a+.45),y-head*Math.sin(a+.45)]],{stroke:col,width,alpha})}
/** rounded pill label */
export function pill(c,s,x,y,{size=24,color=P.cyan,alpha=1,fill=null,pad=14,align='center',weight='med'}={}){if(alpha<=0)return;const w=measure(c,s,size,weight)+pad*2,h=size*1.6;const x0=align==='center'?x-w/2:align==='right'?x-w:x;rect(c,x0,y-h/2,w,h,fill||rgba(color,.12),{alpha,r:h/2,stroke:rgba(color,.55),sw:1.5});T(c,s,x0+w/2,y+size*.35,{size,color,align:'center',alpha,weight});return w}
/** framed box with title (like "Points card" in the reference) */
export function panel(c,x,y,w,h,{title=null,col=P.cyan,alpha=1}={}){if(alpha<=0)return;rect(c,x,y,w,h,rgba('#0E1C30',.85),{alpha,r:12,stroke:rgba(col,.6),sw:2});if(title)T(c,title,x+w/2,y+40,{size:26,color:col,align:'center',alpha,weight:'med'})}

export function wavePts(x0,y0,w,amp,fn,n=400){const pts=[];for(let i=0;i<=n;i++){const a=i/n;pts.push([x0+a*w,y0-amp*fn(a)])}return pts}
/** pseudo-random deterministic */
export function rnd(i){const x=Math.sin(i*127.1+311.7)*43758.5453;return x-Math.floor(x)}
/** illustrative EEG-like signal (sum of rhythms, deterministic) */
export function eeg(a,seed=0,mode='mixed'){const s=seed*7.3;let v=0;
  if(mode==='slow')v=.75*Math.sin(a*2*Math.PI*8+s)+.25*Math.sin(a*2*Math.PI*21+s*2);
  else if(mode==='fast')v=.35*Math.sin(a*2*Math.PI*60+s)+.25*Math.sin(a*2*Math.PI*97+s);
  else v=.45*Math.sin(a*2*Math.PI*6+s)+.22*Math.sin(a*2*Math.PI*37+s*1.7)+.12*Math.sin(a*2*Math.PI*91+s*.3)+.5*Math.exp(-(((a-.63)/.025)**2))*Math.sin(a*2*Math.PI*140);
  return v+.08*Math.sin(a*733+s)}

// chart axes: returns mapping fns
export function axes(c,{x,y,w,h,xmin=0,xmax=1,ymin=0,ymax=1,xt=[],yt=[],xl=null,yl=null,alpha=1,fmtY=v=>String(v),fmtX=v=>String(v),size=22}){
  const X=v=>x+(v-xmin)/(xmax-xmin)*w,Y=v=>y+h-(v-ymin)/(ymax-ymin)*h;
  for(const v of yt){poly(c,[[x,Y(v)],[x+w,Y(v)]],{stroke:P.grid,width:1.5,alpha});T(c,fmtY(v),x-14,Y(v)+7,{size,color:P.muted,align:'right',alpha})}
  poly(c,[[x,y+h],[x+w,y+h]],{stroke:P.line,width:2,alpha});
  for(const v of xt){T(c,fmtX(v),X(v),y+h+34,{size,color:P.muted,align:'center',alpha})}
  if(xl)T(c,xl,x+w,y+h+70,{size,color:P.muted,align:'right',alpha});if(yl)T(c,yl,x,y-22,{size,color:P.muted,align:'left',alpha});
  return {X,Y}}

// ---------- 3D ----------
const FACE_LIGHT=[.42,.62,.86,.55,.7,1.12];
export class World{
  /** box: pixel rect in frame coords where the 3D view is drawn */
  constructor({box=[84,130,1752,760],center=[0,0,1],phi=1.05,theta=-1.3,zoom=1,frameHeight=7.4}={}){
    this.box=box;const [bx,by,bw,bh]=box;
    this.cam=new ThreeDCamera({pixelWidth:bw,pixelHeight:bh,frameHeight,frameWidth:frameHeight*bw/bh,frameCenter:center,phi,theta,zoom,focalDistance:24});
    this.faces=[];this.lines=[];this.back=[];this.labels=[];}
  px(p){const q=this.cam.toPixel(p);return [q[0]+this.box[0],q[1]+this.box[1]]}
  depth(p){return this.cam.projectionDepth(p)}
  box3(pos,size,col,{alpha=1,edge=null}={}){if(alpha<=0)return this;const [x,y,z]=pos,[w,d,h]=size;const v=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].map(a=>[x+a[0]*w/2,y+a[1]*d/2,z+a[2]*h/2]);
    [[0,1,2,3],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]].forEach((f,i)=>this.faces.push({p:f.map(j=>v[j]),col:shade(col,FACE_LIGHT[i]),alpha,edge}));return this}
  /** box standing on the floor (z=base) that grows with g in [0,1] */
  grow(pos,size,col,g,opt={}){g=clamp(g);if(g<=0)return this;return this.box3([pos[0],pos[1],(pos[2]||0)+size[2]*g/2],[size[0],size[1],Math.max(.001,size[2]*g)],col,opt)}
  sphere(p,r,col,{alpha=1,seg=8}={}){if(r<=0||alpha<=0)return this;const at=(a,b)=>[p[0]+r*Math.sin(a)*Math.cos(b),p[1]+r*Math.sin(a)*Math.sin(b),p[2]+r*Math.cos(a)];
    for(let i=0;i<seg/2+1;i++)for(let j=0;j<seg;j++){const a0=i*Math.PI/(seg/2+1),a1=(i+1)*Math.PI/(seg/2+1),b0=j*2*Math.PI/seg,b1=(j+1)*2*Math.PI/seg;this.faces.push({p:[at(a0,b0),at(a1,b0),at(a1,b1),at(a0,b1)],col:shade(col,.5+.55*Math.cos(a0)*.5+.3+.12*Math.sin(b0+1)),alpha})}return this}
  quad(pts,col,{alpha=1,edge=null}={}){this.faces.push({p:pts,col,alpha,edge});return this}
  line(pts,col=P.cyan,width=2,{alpha=1,back=false,glow=0}={}){(back?this.back:this.lines).push({p:pts,col,width,alpha,glow});return this}
  floor({size=6,step=1,alpha=.7,col='#1A2B44'}={}){for(let i=-size;i<=size;i+=step){this.line([[i,-size*.6,0],[i,size*.6,0]],col,1.2,{back:true,alpha});}for(let j=-size*.6;j<=size*.6+1e-9;j+=step)this.line([[-size,j,0],[size,j,0]],col,1.2,{back:true,alpha});return this}
  label(p,s,opt){this.labels.push({p,s,opt});return this}
  draw(c){
    for(const l of this.back)poly(c,l.p.map(p=>this.px(p)),{stroke:l.col,width:l.width,alpha:l.alpha});
    const d=f=>{let s=0;for(const p of f.p)s+=this.depth(p);return s/f.p.length};
    for(const f of this.faces)f.d=d(f);this.faces.sort((a,b)=>a.d-b.d);
    for(const f of this.faces){const pts=f.p.map(p=>this.px(p));c.save();c.globalAlpha*=f.alpha;c.beginPath();pts.forEach((p,i)=>i?c.lineTo(p[0],p[1]):c.moveTo(p[0],p[1]));c.closePath();c.fillStyle=f.col;c.fill();c.strokeStyle=f.edge||'rgba(255,255,255,0.07)';c.lineWidth=f.edge?1.6:.8;c.stroke();c.restore()}
    for(const l of this.lines)poly(c,l.p.map(p=>this.px(p)),{stroke:l.col,width:l.width,alpha:l.alpha,glow:l.glow});
    for(const l of this.labels){const [x,y]=this.px(l.p);T(c,l.s,x,y,{align:'center',...l.opt})}
  }
}
/** simple person figure */
export function person(w,x,y,col,s=.7,{alpha=1,g=1}={}){if(g<=0)return;const z=(1-outBack(g))*1.5;w.box3([x,y,.45*s+z],[.38*s,.28*s,.62*s],col,{alpha}).sphere([x,y,1.0*s+z],.2*s,col,{alpha,seg:8});w.box3([x-.1*s,y,.1*s+z],[.12*s,.2*s,.26*s],shade(col,.8),{alpha}).box3([x+.1*s,y,.1*s+z],[.12*s,.2*s,.26*s],shade(col,.8),{alpha})}
