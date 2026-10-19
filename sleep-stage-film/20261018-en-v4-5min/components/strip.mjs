// Night strip, tiles, legend (plan 5.2)
import {P,STAGE_COL,STAGES,clamp,lerp,mixCol,rgba,outBack,smooth,T,measure,dot,rect} from '../lib.mjs';
import {tray,bevel,glowRect} from '../light.mjs';
import {HYPNO} from '../shared.mjs';
export const TRAY='#060D17';
export const stageColor=(s,act=1)=>act===4?mixCol(STAGE_COL[s],P.slate,.55):STAGE_COL[s];
const val=(v,i)=>typeof v==='function'?v(i):v;
/** NightStrip: modes on|dim|dark|unscored|ghost|hidden ; appear = raw progress 0..1 per tile */
export function NightStrip(c,o){
  const {k,el,x=104,y,w=1712,h=64,range=[0,96],gap=3,stage=i=>HYPNO[i],appear=1,mode='on',lit=0,tray:tr=true,act=1,alpha=1,r=3,maxGlow=3,fade=1}=o;
  k&&k.rec('NightStrip',{el,x,y,w,h,range,n:range[1]-range[0]});
  const n=range[1]-range[0],pitch=w/n,tw=pitch-gap;
  c.save();c.globalAlpha*=alpha;
  if(tr)tray(c,x-8,y-8,w+16,h+16,{alpha:fade});
  let glows=0;
  for(let i=range[0];i<range[1];i++){const p=val(appear,i),m=val(mode,i);if(p<=0||m==='hidden')continue;
    const px=x+(i-range[0])*pitch,sc=lerp(.6,1,outBack(p)),a=clamp(p*2.2)*fade,cx=px+tw/2,cy=y+h/2;
    c.save();c.globalAlpha*=a;c.translate(cx,cy);c.scale(sc,sc);c.translate(-cx,-cy);
    const col=stageColor(stage(i),act);
    if(m==='on')bevel(c,px,y,tw,h,col,{r});
    else if(m==='dim')bevel(c,px,y,tw,h,mixCol(col,TRAY,.7),{r,half:true});
    else if(m==='dark')bevel(c,px,y,tw,h,mixCol(col,TRAY,.86),{r,half:true});
    else if(m==='unscored'){c.setLineDash([4,4]);c.strokeStyle='rgba(147,163,184,.5)';c.lineWidth=1.5;c.beginPath();c.roundRect(px+.75,y+.75,tw-1.5,h-1.5,r);c.stroke()}
    else if(m==='ghost'){c.strokeStyle='rgba(147,163,184,.30)';c.lineWidth=1.2;c.beginPath();c.roundRect(px+.6,y+.6,tw-1.2,h-1.2,r);c.stroke()}
    c.restore();
    const L=val(lit,i);if(L>0&&glows<maxGlow&&(m==='on'||m==='dim')){glows++;glowRect(c,px,y,tw,h,col,{blur:14,alpha:.45*L},r)}}
  c.restore()}
export const tileX=(i,{x=104,w=1712,range=[0,96]}={})=>x+(i-range[0])*(w/(range[1]-range[0]));
/** Legend chips (W N1 N2 N3 REM): dot + label */
export function Legend(c,o){const {k,el,y=598,cx=960,t=1,alpha=1,act=1}=o;k&&k.rec('Legend',{el});
  const gap=44,items=STAGES.map((s,i)=>({s,w:14+10+measure(c,s,24,'med')}));const total=items.reduce((a,b)=>a+b.w,0)+gap*(items.length-1);let x=cx-total/2;
  items.forEach((it,i)=>{const a=alpha*smooth((t-i*.15)/.3);dot(c,x+7,y-8,7,stageColor(i,act),a);T(c,it.s,x+24,y,{size:24,weight:'med',color:P.ink,alpha:a});x+=it.w+gap})}
