// People icons, grids, fold montage, icon chips (plan 5.3)
import {P,STAGE_COL,clamp,lerp,rgba,shade,mixCol,smooth,cubic,outBack,T,measure,dot,poly,rect,rnd} from '../lib.mjs';
import {surface,bevel,glowCircle,glow} from '../light.mjs';
import {HYPNO} from '../shared.mjs';
const SC={neutral:'#7C8CA3',train:P.blue,choose:P.amber,test:P.coral,unknown:'#3A4A62',exposed:'#7C8CA3'};
/** Person: (x,y) = centre of the body; s = size px */
export function Person(c,o){const {k,el,x,y,s=44,state='neutral',alpha=1,sc=1,glowA=0,border=null,q=false}=o;k&&k.rec('Person',{el,x,y,s});if(alpha<=0||sc<=0)return;
  c.save();c.globalAlpha*=clamp(alpha);c.translate(x,y);c.scale(sc,sc);const col=SC[state]||SC.neutral;
  const body=()=>{c.beginPath();c.arc(0,-.62*s,.28*s,0,Math.PI*2);c.moveTo(-.55*s,.5*s);c.quadraticCurveTo(-.55*s,-.1*s,0,-.1*s);c.quadraticCurveTo(.55*s,-.1*s,.55*s,.5*s);c.closePath()};
  if(glowA>0)glow(c,()=>{body();c.fill()},col,{blur:14,alpha:glowA});
  if(state==='unknown'){body();c.fillStyle='rgba(58,74,98,.35)';c.fill();c.setLineDash([4,3]);c.strokeStyle='rgba(147,163,184,.6)';c.lineWidth=1.5;c.stroke();c.setLineDash([])}
  else{body();const g=c.createLinearGradient(0,-.9*s,0,.5*s);g.addColorStop(0,shade(col,1.12));g.addColorStop(1,shade(col,.88));c.fillStyle=state==='neutral'?rgba(col,.55):g;c.fill();
    if(state!=='neutral'){c.save();body();c.clip();c.fillStyle='rgba(255,255,255,.18)';c.fillRect(-s,-.9*s,2*s,1.2);c.restore()}}
  if(border){body();c.strokeStyle=border;c.lineWidth=2;c.stroke()}
  if(q){c.strokeStyle=P.ink;c.fillStyle=P.ink;c.lineWidth=2.2;c.lineCap='round';c.beginPath();c.arc(0,.14*s,.1*s,Math.PI*1.1,Math.PI*2.1);c.lineTo(0,.28*s);c.stroke();c.beginPath();c.arc(0,.36*s,1.6,0,Math.PI*2);c.fill()}
  c.restore()}
export function MiniStrip(c,{x,y,w=104,h=14,n=8,seed=0,alpha=1,tint=1}){if(alpha<=0)return;const pw=w/n,tw=pw-2;c.save();c.globalAlpha*=alpha;for(let j=0;j<n;j++){const col=STAGE_COL[HYPNO[(seed*5+j*11+3)%96]];bevel(c,x+j*pw,y,tw,h,col,{r:2,half:true})}c.restore()}
export const gridPos=i=>[184+160*(i%10),i<10?330:590];
export const foldState=(i,f)=>{const t0=2*f,t1=2*f+1;if(i===t0||i===t1)return 'test';if(i===(2*f+2)%20||i===(2*f+3)%20)return 'choose';return 'train'};
/** PeopleGrid 2x10 */
export function PeopleGrid(c,o){const {k,el,state=()=>'neutral',appear=()=>1,glowSet=null,glowA=0,alpha=1,strips=1,skip=null,mini=true}=o;k&&k.rec('PeopleGrid',{el,n:20});
  c.save();c.globalAlpha*=alpha;for(let i=0;i<20;i++){if(skip&&skip.has(i))continue;const p=appear(i);if(p<=0)continue;const [x,y]=gridPos(i);
    Person(c,{x,y,s:44,state:state(i),sc:lerp(.6,1,outBack(clamp(p))),alpha:clamp(p*2),glowA:glowSet&&glowSet.has(i)?glowA:0});
    if(mini)MiniStrip(c,{x:x-52,y:y+40,seed:i,alpha:clamp(p*2)*strips})}
  c.restore()}
// ---- icon chips (Sigma, chart, check, pencil)
export function drawIcon(c,name,cx,cy,sz,col){c.save();c.translate(cx,cy);c.strokeStyle=col;c.fillStyle=col;c.lineWidth=Math.max(3,sz*.075);c.lineCap='round';c.lineJoin='round';const h=sz/2;
  if(name==='sigma'){c.beginPath();c.moveTo(h*.55,-h*.7);c.lineTo(-h*.55,-h*.7);c.lineTo(h*.15,0);c.lineTo(-h*.55,h*.7);c.lineTo(h*.6,h*.7);c.stroke()}
  else if(name==='chart'){c.beginPath();c.moveTo(-h*.7,-h*.6);c.lineTo(-h*.7,h*.6);c.lineTo(h*.75,h*.6);c.stroke();c.beginPath();c.moveTo(-h*.45,h*.25);c.lineTo(-h*.1,-h*.15);c.lineTo(h*.2,h*.1);c.lineTo(h*.65,-h*.45);c.stroke()}
  else if(name==='check'){c.beginPath();c.moveTo(-h*.6,h*.05);c.lineTo(-h*.15,h*.5);c.lineTo(h*.65,-h*.5);c.stroke()}
  else if(name==='pencil'){c.rotate(-Math.PI/4);c.beginPath();c.roundRect(-h*.16,-h*.8,h*.32,h*1.2,3);c.stroke();c.beginPath();c.moveTo(-h*.16,h*.4);c.lineTo(0,h*.8);c.lineTo(h*.16,h*.4);c.closePath();c.fill()}
  c.restore()}
export function IconChip(c,o){const {k,el,cx,y,icon,col=P.ink,lit=0,litCol=P.violet,alpha=1,drop=1,label=null,labelY=null}=o;k&&k.rec('IconChip',{el,cx,y,w:120,h:120});if(alpha<=0||drop<=0)return;
  const yy=y-(1-outBack(clamp(drop)))*40;c.save();c.globalAlpha*=alpha*clamp(drop*3);
  if(lit>0)glow(c,()=>{c.beginPath();c.roundRect(cx-60,yy,120,120,18);c.fill()},litCol,{blur:14,alpha:.45*lit});
  surface(c,[cx-60,yy,120,120],'#16273F',{level:'E2',r:18,gradient:.05});drawIcon(c,icon,cx,yy+60,64,lit>0?mixCol(col,litCol,lit):col);
  if(label)T(c,label,cx,labelY??yy+160,{size:24,weight:'med',color:P.muted,align:'center'});c.restore()}
