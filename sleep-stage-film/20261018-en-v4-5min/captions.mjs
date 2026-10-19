import fs from 'node:fs';
import {smooth,wrap} from './lib.mjs';
export const TIMELINE=JSON.parse(fs.readFileSync(new URL('./timeline.json',import.meta.url)));
export const CAPS=TIMELINE.captions;
export const CAP_BY_ID=Object.fromEntries(CAPS.map(c=>[c.id,c]));
export const CPS_MAX=17.3;
const LEAD_IN=0.2,TAIL=0.8;
export const CUES=new Map();
export function cueAbs(id,phrase,nth=0){const c=CAP_BY_ID[id];if(!c)throw Error('cue: unknown caption '+id);
  let i=-1;for(let k=0;k<=nth;k++)i=c.text.indexOf(phrase,i+1);
  if(i<0)throw Error(`cue: "${phrase}" not in ${id}`);
  if(nth===0&&c.text.indexOf(phrase,i+1)>=0)throw Error(`cue: "${phrase}" repeated in ${id}, give nth`);
  const v=c.s+LEAD_IN+(i/c.text.length)*(c.e-c.s-LEAD_IN-TAIL);CUES.set(id+'|'+phrase,{id,phrase,abs:v});return v}
export function capAt(t){const c=CAPS.find(c=>t>=c.s&&t<c.e);if(!c)return null;return {cap:c,alpha:smooth((t-c.s)/0.2)*smooth((c.e-t)/0.2)}}
export function capLines(ctx,text){const one=wrap(ctx,text,1620,33);if(one.length!==2)return one;
  // balance the two lines: choose the word split with the narrowest widest line
  const words=text.split(' ');let best=null;ctx.save();ctx.font='33px Film';
  for(let i=1;i<words.length;i++){const a=words.slice(0,i).join(' '),b=words.slice(i).join(' ');const wa=ctx.measureText(a).width,wb=ctx.measureText(b).width;if(Math.max(wa,wb)>1620)continue;const m=Math.max(wa,wb);if(!best||m<best.m)best={m,a,b}}
  ctx.restore();return best?[best.a,best.b]:one}
export function toSrt(ctx){const p=(n,w)=>String(n).padStart(w,'0');
  const ts=x=>{const ms=Math.round(x*1000);return `${p(Math.floor(ms/3600000),2)}:${p(Math.floor(ms/60000)%60,2)}:${p(Math.floor(ms/1000)%60,2)},${p(ms%1000,3)}`};
  return CAPS.map((c,i)=>`${i+1}\n${ts(c.s)} --> ${ts(c.e)}\n${capLines(ctx,c.text).join('\n')}\n`).join('\n')}
