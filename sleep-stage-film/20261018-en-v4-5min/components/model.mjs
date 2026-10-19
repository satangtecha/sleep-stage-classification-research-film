// Pipeline blocks and model pictures (plan 5.4, 5.5)
import {P,STAGE_COL,clamp,lerp,rgba,shade,mixCol,smooth,cubic,outBack,T,measure,dot,poly,rect,rnd,heat,eeg,wavePts} from '../lib.mjs';
import {surface,bevel,glow} from '../light.mjs';
export function blockIcon(c,kind,cx,cy,sz,col=P.ink){c.save();c.translate(cx,cy);const h=sz/2;
  if(kind==='sst'||kind==='stft'){const n=5,cs=sz/n;for(let i=0;i<n;i++)for(let j=0;j<n;j++){let v;if(kind==='stft')v=.5+.5*Math.sin(i*1.3+j*.9);else v=Math.exp(-((j-2+Math.sin(i*.8)*1.2)**2)*2.2);c.fillStyle=heat(clamp(v));c.fillRect(-h+i*cs+1,-h+j*cs+1,cs-2,cs-2)}}
  else if(kind==='cnn'){for(let i=2;i>=0;i--){c.fillStyle=['#2A4B7A','#3B6FB0',P.blue][2-i];c.strokeStyle='rgba(255,255,255,.25)';c.lineWidth=1.5;c.beginPath();c.roundRect(-h*.6+i*h*.32,-h*.55+i*h*-.18+h*.2,h*1.0,h*.8,4);c.fill();c.stroke()}}
  else if(kind==='contrastive'){for(let i=0;i<3;i++){const y=-h*.55+i*h*.55;dot(c,-h*.62,y,5,P.cyan);dot(c,h*.62,y,5,P.coral);c.strokeStyle=P.muted;c.lineWidth=2;c.beginPath();c.moveTo(-h*.4,y);c.lineTo(-h*.05,y);c.moveTo(h*.4,y);c.lineTo(h*.05,y);c.stroke()}}
  else if(kind==='gru'||kind==='bigru'){c.strokeStyle=col;c.lineWidth=4;c.lineCap='round';const arr=(a0,a1,dir)=>{c.beginPath();c.arc(0,0,h*.62,a0,a1,dir<0);c.stroke();const a=a1,x=Math.cos(a)*h*.62,y=Math.sin(a)*h*.62,t=a+(dir>0?Math.PI/2:-Math.PI/2);c.beginPath();c.moveTo(x,y);c.lineTo(x+Math.cos(t+.5)*-9,y+Math.sin(t+.5)*-9);c.moveTo(x,y);c.lineTo(x+Math.cos(t-.5)*-9,y+Math.sin(t-.5)*-9);c.stroke()};
    if(kind==='gru')arr(-Math.PI*.9,Math.PI*.55,1);else{arr(-Math.PI*.95,-Math.PI*.1,1);arr(Math.PI*.05,Math.PI*.9,1)}}
  c.restore()}
/** PipelineBlock: 176x150 (narrow, B4) or 260x150; drop animates from y-80 */
export function PipelineBlock(c,o){const {k,el,x,y,w=176,h=150,kind,label,alpha=1,drop=1,glowC=null,glowA=0,tint=null}=o;k&&k.rec('PipelineBlock',{el,x,y,w,h,label});if(alpha<=0||drop<=0)return;
  const yy=y-(1-outBack(clamp(drop)))*80;c.save();c.globalAlpha*=alpha*clamp(drop*3);
  if(glowA>0)glow(c,()=>{c.beginPath();c.roundRect(x,yy,w,h,16);c.fill()},glowC,{blur:14,alpha:glowA});
  surface(c,[x,yy,w,h],'#16273F',{level:drop<1?'E4':'E2',r:16,gradient:.05});
  blockIcon(c,kind,x+w/2,yy+50,56);T(c,label,x+w/2,yy+h-22,{size:26,weight:'med',color:P.ink,align:'center'});c.restore()}
export function Slot(c,o){const {x,y,w=176,h=150,alpha=1,text=null,tAlpha=1}=o;if(alpha<=0)return;c.save();c.globalAlpha*=alpha;c.setLineDash([7,6]);c.strokeStyle='rgba(147,163,184,.5)';c.lineWidth=1.5;c.beginPath();c.roundRect(x,y,w,h,16);c.stroke();c.setLineDash([]);
  if(text)T(c,text,x+w/2,y+h/2+8,{size:24,weight:'med',color:P.muted,align:'center',alpha:tAlpha});c.restore()}
export function Connector(c,x0,y,x1,{p=1,col=P.muted,dashed=false,alpha=1}={}){if(p<=0)return;c.save();c.globalAlpha*=alpha;c.strokeStyle=col;c.fillStyle=col;c.lineWidth=2.5;if(dashed)c.setLineDash([8,6]);const xe=lerp(x0,x1,p);c.beginPath();c.moveTo(x0,y);c.lineTo(xe,y);c.stroke();c.setLineDash([]);if(p>.9){c.beginPath();c.moveTo(x1,y);c.lineTo(x1-10,y-6);c.lineTo(x1-10,y+6);c.closePath();c.fill()}c.restore()}
