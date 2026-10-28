// Cards, labels, stamps, wall, padlock (plan 5.4)
import {P,clamp,lerp,rgba,shade,mixCol,smooth,cubic,outBack,outExpo,T,measure,wrap,dot,poly,rect,rnd,font} from '../lib.mjs';
import {surface,elev,ELEV,glow,glowRect,scaleOf,shadowed} from '../light.mjs';
import {tnum,partial} from '../motion.mjs';
import {createCanvas} from '@napi-rs/canvas';

/** number drawn digit by digit at fixed width so counting does not jitter. */
export function NumText(c,s,x,y,{size=64,weight='bold',color=P.ink,align='left',alpha=1}={}){
  if(alpha<=0)return 0;return tnum(c,s,x,y,(ch,cx,yy,w)=>T(c,ch,cx,yy,{size,weight,color,align:'center',alpha}),{size,weight,align})}
export const fmtNum=(v,dec=2)=>(v<0?'−':'')+Math.abs(v).toFixed(dec);
/** NumberCard: size 'L' 520x330 | 'S' 360x200. v counted by caller. */
export function NumberCard(c,o){const {k,el,x,y,size='L',label,text,color=P.ink,sub=null,alpha=1,level='E2',dx=0,fill='#0E1C30',subColor=P.muted,tAlpha=1,suffix='%'}=o;
  const W=size==='L'?520:360,H=size==='L'?330:200;k&&k.rec('NumberCard',{el,x,y,w:W,h:H,size,fontPx:size==='L'?120:64,level,glow:0,color});
  if(alpha<=0)return {w:W,h:H};c.save();c.globalAlpha*=alpha;surface(c,[x+dx,y,W,H],fill,{level,r:16});
  if(label)T(c,label,x+dx+28,y+(size==='L'?56:46),{size:size==='L'?28:24,weight:'med',color:P.muted,alpha:tAlpha});
  const fs=size==='L'?120:64;const by=size==='L'?y+210:y+130;
  const wNum=NumText(c,text,x+dx+28,by,{size:fs,weight:'bold',color,alpha:tAlpha});
  if(suffix)T(c,suffix,x+dx+28+wNum+6,by,{size:size==='L'?64:40,weight:'bold',color,alpha:tAlpha});
  if(sub)T(c,sub,x+dx+28,y+H-30,{size:24,color:subColor,alpha:tAlpha});c.restore();return {w:W,h:H}}

/** vertical-slice perspective warp of an offscreen canvas */
function warp(c,img,x,y,w,h,ry){const sgn=Math.sign(ry)||1,k=Math.abs(ry)/(8*Math.PI/180)*.06,fw=Math.cos(Math.abs(ry));
  const nw=w*fw,step=2;let dx=x+(w-nw)/2;const n=Math.ceil(w/step);
  for(let i=0;i<n;i++){const u0=i/n,u1=(i+1)/n;const far=sgn>0?u0:1-u0; // far side shrinks
    const sh=1-k*far,hh=h*sh;c.drawImage(img,u0*w,0,step,h,dx+u0*nw,y+(h-hh)/2,nw/n+.6,hh)}}
let paperImg=null;
function paperFace(title,venue,authors){const cv=createCanvas(760,500),g=cv.getContext('2d');
  g.fillStyle=P.paper;g.beginPath();g.roundRect(0,0,760,500,10);g.fill();
  g.fillStyle=P.paperInk;g.font=font(22,'med');g.fillText(venue,40,56);
  g.fillStyle='rgba(27,36,51,.25)';g.fillRect(40,74,680,2);
  g.fillStyle=P.paperInk;g.font=font(30,'bold');wrap(g,title,680,30,'bold').forEach((l,i)=>g.fillText(l,40,132+i*42));
  g.font=font(22,'reg');g.fillStyle='rgba(27,36,51,.8)';g.fillText(authors,40,440);
  return cv}
/** PaperCard (B2) with perspective ry (radians) and morph p to RefBadge pill */
export function PaperCard(c,o){const {k,el,x=140,y=184,ry=8*Math.PI/180,alpha=1,morph=0,title,venue,authors,badge}=o;k&&k.rec('PaperCard',{el,x,y,w:760,h:500});
  if(alpha<=0)return;if(!paperImg)paperImg=paperFace(title,venue,authors);
  c.save();c.globalAlpha*=alpha;
  if(morph<=0){
    // shadow quad then warped slices
    elev(c,'E3',()=>{c.beginPath();c.roundRect(x+4,y+4,752,492,10);c.fillStyle=P.paper;c.fill()});
    warp(c,paperImg,x,y,760,500,ry);
    c.fillStyle='rgba(255,255,255,.55)';c.fillRect(x+8,y,740,1.5);
  }else{const m=cubic(morph),bx=lerp(x,104,m),by=lerp(y,148,m),bw=lerp(760,300,m),bh=lerp(500,48,m),r=lerp(10,24,m);
    const col=mixCol(P.paper,'#1A2A40',smooth(m*1.4));
    surface(c,[bx,by,bw,bh],col,{level:m<.7?'E3':'E1',r,gradient:0,rim:false,k:1});
    if(m<.5){c.save();c.globalAlpha*=1-m*2;c.beginPath();c.roundRect(bx,by,bw,bh,r);c.clip();c.drawImage(paperImg,bx,by,bw,bh);c.restore()}
    const ba=smooth((m-.55)/.45);if(ba>0){c.save();c.beginPath();c.roundRect(bx,by,bw,bh,r);c.strokeStyle=rgba(P.ref,.5*ba);c.lineWidth=1.5;c.stroke();c.restore();RefBadgeInner(c,bx,by,ba)}}
  c.restore()}
function RefBadgeInner(c,x,y,a){c.save();c.globalAlpha*=a;c.strokeStyle=P.ref;c.lineWidth=2;c.beginPath();c.roundRect(x+18,y+12,18,24,3);c.stroke();c.beginPath();c.moveTo(x+23,y+20);c.lineTo(x+31,y+20);c.moveTo(x+23,y+26);c.lineTo(x+31,y+26);c.stroke();c.restore();
  T(c,'Reference paper',x+48,y+32,{size:24,weight:'med',color:P.ref,alpha:a})}
export function RefBadge(c,o={}){const {k,el,x=104,y=148,alpha=1}=o;k&&k.rec('RefBadge',{el,x,y,w:300,h:48});if(alpha<=0)return;c.save();c.globalAlpha*=alpha;
  surface(c,[x,y,300,48],'#1A2A40',{level:'E1',r:24,gradient:0,rim:false});c.beginPath();c.roundRect(x,y,300,48,24);c.fillStyle='rgba(169,188,208,.10)';c.fill();c.strokeStyle=rgba(P.ref,.5);c.lineWidth=1.5;c.stroke();RefBadgeInner(c,x,y,1);c.restore()}
/** Ring: 220px diameter */
export function Ring(c,o){const {k,el,cx,cy,r=110,th=18,p=0,text,color=P.ref,alpha=1,size=72}=o;k&&k.rec('Ring',{el,cx,cy});if(alpha<=0)return;c.save();c.globalAlpha*=alpha;
  c.lineCap='butt';c.strokeStyle=P.line;c.lineWidth=th;c.beginPath();c.arc(cx,cy,r-th/2,0,Math.PI*2);c.stroke();
  if(p>0){c.strokeStyle=color;c.beginPath();c.arc(cx,cy,r-th/2,-Math.PI/2,-Math.PI/2+Math.PI*2*p);c.stroke()}
  NumText(c,text,cx,cy+size*.35,{size,weight:'bold',color:P.ink,align:'center'});c.restore()}
/** Chip on a belt: pill 56 high, label 26 Medium. returns width */
export function chipW(c,text){return measure(c,text,26,'med')+44}
export function Chip(c,o){const {k,el,x,y,text,alpha=1,ghost=false,spin=null,drop=1,color=P.ink}=o;const w=chipW(c,text)+(spin!=null?34:0);k&&k.rec('Chip',{el,x,y,w,h:56,text});
  const yy=y-(1-outBack(clamp(drop)))*80;if(alpha<=0||drop<=0)return w;c.save();c.globalAlpha*=alpha*clamp(drop*3);
  if(ghost){c.setLineDash([6,5]);c.strokeStyle='rgba(147,163,184,.5)';c.lineWidth=1.5;c.beginPath();c.roundRect(x,yy,w,56,28);c.stroke();c.setLineDash([])}
  else{surface(c,[x,yy,w,56],'#16273F',{level:'E2',r:28,gradient:.05})}
  let tx=x+22;if(spin!=null){c.strokeStyle=P.ref;c.lineWidth=3.5;c.lineCap='round';c.beginPath();c.arc(x+30,yy+28,10,spin,spin+Math.PI*1.5);c.stroke();tx=x+56}
  T(c,text,tx,yy+36,{size:26,weight:'med',color:ghost?P.muted:color});c.restore();return w}
export function Belt(c,o){const {x0,x1,y,t,alpha=1,dashed=false}=o;if(alpha<=0)return;c.save();c.globalAlpha*=alpha;c.strokeStyle=dashed?'rgba(147,163,184,.35)':P.line;c.lineWidth=2;c.setLineDash([14,12]);c.lineDashOffset=60*t;c.beginPath();c.moveTo(x0,y);c.lineTo(x1,y);c.stroke();c.restore()}
// ---- stamps
export function Stamp(c,o){const {k,el,text,cx,cy,color=P.amber,p=0,scale=1,rot=-6,t=0,seed=1,w=null}=o;k&&k.rec('Stamp',{el,text,cx,cy});if(p<=0)return;
  const fall=outExpo(clamp(p)),sc=lerp(2.2,1,fall)*scale,yo=lerp(-60,0,fall),land=p>=1;
  c.save();c.translate(cx,cy+yo);c.rotate(rot*Math.PI/180);c.scale(sc,sc);c.globalAlpha*=clamp(p*4);
  const fs=64*(scale<1?1:1);c.font=`${fs}px FilmBold`;c.letterSpacing='6px';const tw=c.measureText(text).width;const bw=tw+60,bh=fs+44;
  const level=land?'E1':'E4';
  shadowed(c,ELEV[level],()=>{c.beginPath();c.roundRect(-bw/2,-bh/2,bw,bh,10);c.fillStyle=rgba(P.card,.001);c.fill()},{});
  c.strokeStyle=color;c.lineWidth=6;c.beginPath();c.roundRect(-bw/2,-bh/2,bw,bh,10);c.stroke();c.lineWidth=2;c.beginPath();c.roundRect(-bw/2+10,-bh/2+10,bw-20,bh-20,6);c.stroke();
  c.fillStyle=color;c.textAlign='center';c.textBaseline='alphabetic';c.fillText(text,0,fs*.34);
  // ink wear: seeded specks removed
  c.globalCompositeOperation='destination-out';for(let i=0;i<140;i++){const rx=(rnd(seed*500+i)-.5)*bw,ry=(rnd(seed*500+i+200)-.5)*bh,rr=1+rnd(seed*500+i+400)*2.5;c.fillStyle='rgba(0,0,0,.25)';c.beginPath();c.arc(rx,ry,rr,0,Math.PI*2);c.fill()}
  c.restore();c.letterSpacing='0px'}
export function Wave(c,cx,cy,t,{col=P.ink,max=80}={}){if(t<=0||t>=1)return;c.save();c.strokeStyle=rgba(col,.4*(1-t));c.lineWidth=3;c.beginPath();c.arc(cx,cy,max*t,0,Math.PI*2);c.stroke();c.restore()}
// ---- glass wall (B9b)
export function Wall(c,o){const {k,el,x=953,y=233,w=14,h=560,p=1,alpha=1,glowA=0}=o;k&&k.rec('Wall',{el,x,y,w,h});if(p<=0||alpha<=0)return;const hh=h*p;c.save();c.globalAlpha*=alpha;
  if(glowA>0)glowRect(c,x,y+h-hh,w,hh,P.ref,{blur:40,alpha:glowA},3);
  const g=c.createLinearGradient(x,0,x+w,0);g.addColorStop(0,'rgba(169,188,208,.10)');g.addColorStop(.5,'rgba(169,188,208,.28)');g.addColorStop(1,'rgba(169,188,208,.10)');
  elev(c,'E3',()=>{c.fillStyle=g;c.fillRect(x,y+h-hh,w,hh)});c.fillStyle=g;c.fillRect(x,y+h-hh,w,hh);
  c.fillStyle='rgba(255,255,255,.35)';c.fillRect(x,y+h-hh,1.5,hh);c.fillStyle='rgba(0,0,0,.40)';c.fillRect(x+w-1.5,y+h-hh,1.5,hh);c.restore()}
export function Padlock(c,o){const {k,el,x,y,open=0,alpha=1,glowA=0,s=1}=o;k&&k.rec('Padlock',{el,x,y});if(alpha<=0)return;c.save();c.globalAlpha*=alpha;c.translate(x,y);c.scale(s,s);
  if(glowA>0)glowRect(c,0,16,56,44,P.amber,{blur:28,alpha:glowA},8);
  c.strokeStyle=P.ink;c.lineWidth=8;c.lineCap='round';c.beginPath();c.arc(28,16-12*open,16,Math.PI,0);c.moveTo(12,16-12*open);c.lineTo(12,16);c.moveTo(44,16-12*open);c.lineTo(44,16);c.stroke();
  surface(c,[0,16,56,44],P.ink,{level:'E1',r:8,gradient:.05});c.fillStyle=P.card;c.beginPath();c.arc(28,36,5,0,Math.PI*2);c.fill();c.restore()}
