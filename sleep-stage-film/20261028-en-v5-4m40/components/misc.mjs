// Shared small components: EEG frame, bracket, pen, head, pills, padlock, person.
import {P,clamp,lerp,rgba,shade,mixCol,smooth,cubic,outBack,outExpo,T,measure,dot,poly,rect,eeg,rnd,typed} from '../lib.mjs';
import {surface,bevel,glowCircle,glowRect,elev,ELEV} from '../light.mjs';
import {partial} from '../motion.mjs';

/** EEG frame: rounded box with a wave. mode: 'slow'|'fast'|'mixed' */
export function EegFrame(c,o){const {k,el,x,y,w=420,h=220,mode='mixed',amp=1,seed=1,alpha=1,label=null,r=14,level='E1',ampPx=null,lw=2.5,color=P.cyan}=o;k&&k.rec('EegFrame',{el,x,y,w,h});
  if(alpha<=0)return;c.save();c.globalAlpha*=alpha;surface(c,[x,y,w,h],'#0C1A2E',{level,r,gradient:.03});
  c.save();c.beginPath();c.roundRect(x,y,w,h,r);c.clip();const A=(ampPx??h*.32)*amp;
  const pts=[];for(let i=0;i<=240;i++){const a=i/240;pts.push([x+10+a*(w-20),y+h/2-A*eeg(a,seed,mode)])}
  poly(c,pts,{stroke:color,width:lw});c.restore();
  if(label)T(c,label,x+14,y+30,{size:24,weight:'med',color:P.muted});c.restore()}
/** Bracket spanning x0..x1 at y, ends pointing toward dir (+1 down tips, -1 up tips), grows from center with p */
export function Bracket(c,o){const {k,el,x0,x1,y,dir=-1,p=1,col=P.cyan,label=null,lsize=28,lalpha=1,tip=18,width=4,labelAbove=true,alpha=1}=o;k&&k.rec('Bracket',{el,x0,x1,y});
  if(p<=0||alpha<=0)return;const cx=(x0+x1)/2,a=cx-(cx-x0)*p,b=cx+(x1-cx)*p;
  poly(c,[[a,y+dir*tip],[a,y],[b,y],[b,y+dir*tip]],{stroke:col,width,alpha});
  if(label)T(c,label,cx,labelAbove?y-12+(dir>0?-tip:0)-(dir>0?0:tip)+tip*(dir>0?1:0):y+tip+lsize+12,{size:lsize,weight:'med',color:col,align:'center',alpha:alpha*lalpha})}
export function Pill(c,o){const {k,el,x,y,w,h=48,text,color=P.cyan,alpha=1,size=24,fill=null,weight='med',textAlpha=1}=o;k&&k.rec('Pill',{el,x,y,w,h,text});if(alpha<=0)return;
  c.save();c.globalAlpha*=alpha;surface(c,[x,y,w,h],fill||rgba(color,.10),{level:'E1',r:h/2,gradient:0,rim:false});c.beginPath();c.roundRect(x,y,w,h,h/2);c.strokeStyle=rgba(color,.55);c.lineWidth=1.5;c.stroke();
  T(c,text,x+w/2,y+h/2+size*.35,{size,color,weight,align:'center',alpha:textAlpha});c.restore()}
export function Pen(c,x,y,{alpha=1,size=36}={}){if(alpha<=0)return;c.save();c.globalAlpha*=alpha;c.translate(x,y);c.rotate(-Math.PI/4);c.fillStyle=P.ink;c.beginPath();c.roundRect(-4,-size,8,size*.8,2);c.fill();c.fillStyle=P.amber;c.beginPath();c.moveTo(-4,-size*.2);c.lineTo(4,-size*.2);c.lineTo(0,2);c.closePath();c.fill();c.restore()}
export function HeadTop(c,o){const {k,el,cx,cy,r=120,alpha=1,fpz=0,cz=0}=o;k&&k.rec('HeadTop',{el,cx,cy,r});if(alpha<=0)return;c.save();c.globalAlpha*=alpha;
  surface(c,[cx-r*.86,cy-r,r*1.72,r*2],'#12233A',{level:'E1',r:r*.86,gradient:.05,rim:true});
  c.beginPath();c.moveTo(cx-14,cy-r+4);c.lineTo(cx,cy-r-18);c.lineTo(cx+14,cy-r+4);c.strokeStyle=rgba(P.ink,.6);c.lineWidth=3;c.stroke();
  const f=[cx,cy-r*.66],z=[cx,cy];dot(c,f[0],f[1],8,P.cyan,fpz);dot(c,z[0],z[1],8,P.cyan,cz);
  if(fpz>0)glowCircle(c,f[0],f[1],8,P.cyan,{blur:12,alpha:.4*fpz});if(cz>0)glowCircle(c,z[0],z[1],8,P.cyan,{blur:12,alpha:.4*cz});
  T(c,'Fpz',f[0]+22,f[1]+8,{size:24,color:P.muted,weight:'med',alpha:fpz});T(c,'Cz',z[0]+22,z[1]+8,{size:24,color:P.muted,weight:'med',alpha:cz});c.restore();return {f,z}}
/** roman numeral strokes (plan 5.1) */
export const ROMAN={I:[[[0,0],[0,190]]],II:[[[0,0],[0,190]],[[56,0],[56,190]]],III:[[[0,0],[0,190]],[[56,0],[56,190]],[[112,0],[112,190]]],IV:[[[0,0],[0,190]],[[56,0],[104,190],[152,0]]]};
export const romanW=n=>({I:0,II:56,III:112,IV:152}[n]);
export function Roman(c,n,cx,cy,p,{col=P.cyan,width=14,scale=1,alpha=1,glow=false}={}){const strokes=ROMAN[n],W=romanW(n);if(p<=0)return;
  const per=1/strokes.length;strokes.forEach((s,i)=>{const sp=clamp((p-i*per*.5)/(1-(strokes.length-1)*per*.5));const pts=s.map(([x,y])=>[cx+(x-W/2)*scale,cy+(y-95)*scale]);const part=partial(pts,cubic(sp));if(part.length>1)poly(c,part,{stroke:col,width:width*scale,alpha,glow:glow?14:0,cap:'round'})})}
