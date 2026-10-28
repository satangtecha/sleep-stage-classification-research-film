// Every number on screen comes from facts.json through fact(). USED records what was drawn (numbers.test reads it).
import fs from 'node:fs';
export const FACTS=JSON.parse(fs.readFileSync(new URL('./facts.json',import.meta.url)));
export const USED=new Map();
const get=p=>p.split('.').reduce((o,k)=>o[k],FACTS);
const rec=(k,s)=>{(USED.get(k)??USED.set(k,new Set()).get(k)).add(s)};
export function fact(path,{pct,signed,comma,tiles,idx,mul}={}){
  let v=get(path);if(idx!=null)v=v[idx];
  let s;
  if(tiles)s=String(Math.round(v*tiles));
  else if(pct!=null)s=(100*v).toFixed(pct)+'%';
  else if(mul!=null)s=(mul*v).toFixed(2);
  else if(comma)s=v.toLocaleString('en-US');
  else s=String(v);
  if(signed&&v>0)s='+'+s;
  s=s.replace('-','−');rec(path,s);return s}
export const factRaw=p=>get(p);
export function derived(name,value,text=String(value)){rec('derived.'+name,text);return text}
// difference paths contain a hyphen: get() splits on '.', which is fine ("differences.fullnight-minus-r1...")
