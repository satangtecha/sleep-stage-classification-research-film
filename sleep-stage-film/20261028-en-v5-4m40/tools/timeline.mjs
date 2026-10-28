// Builds timeline.json (v5): scene/shot times derived from docs/script-data.mjs. Run: node tools/timeline.mjs
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const ROOT=path.join(path.dirname(fileURLToPath(import.meta.url)),'..');
const {SECTIONS}=await import(path.join(ROOT,'docs/script-data.mjs'));
const TEXT=Object.fromEntries(SECTIONS.flatMap(a=>a.beats).map(b=>[b.id,b.caps]));
const GAP=0.7,r1=x=>Math.round(x*10)/10;
const dur=t=>Math.max(r1(t.length/17),Math.ceil(t.length/17.3*10)/10);
// beats: [lead, hold, shots[[suffix, token]]]; tokens: L = first caption start, cN = end of caption N, H = scene end
const beats={
 B1:[1.6,0.5,[['S1','L'],['S2','c1'],['S3','H']]],
 P1:[1.0,0.9,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B2:[1.2,0.5,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B3:[1.0,0.9,[['S1','L'],['S2','c1'],['S3','H']]],
 Q2:[0.8,0.7,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B3b:[1.0,0.5,[['S1','L'],['S2','c1'],['S3','c2'],['S4','c3'],['S5','H']]],
 D2:[0.5,0.7,[['S1','c1'],['S2','H']]],
 M1:[0.5,0.5,[['S1','c1'],['S2','H']]],
 M2:[0.5,0.7,[['S1','H']]],
 M3:[0.5,0.5,[['S1','c1'],['S2','H']]],
 M4:[0.5,0.5,[['S1','c1'],['S2','H']]],
 M5:[0.5,0.5,[['S1','c1'],['S2','H']]],
 E1:[0.5,0.5,[['S1','c1'],['S2','H']]],
 E2:[0.5,0.5,[['S1','c1'],['S2','c2'],['S3','H']]],
 E3:[0.5,0.5,[['S1','c1'],['S2','H']]],
 E4:[0.5,0.7,[['S1','c1'],['S2','H']]],
 L1:[0.5,0.5,[['S1','c1'],['S2','H']]],
 L2:[0.6,0.5,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 L3:[0.5,1.4,[['S1','H']]],
};
const order=['T1','B1','P1','B2','B3','Q2','B3b','D2','M1','M2','M3','M4','M5','E1','E2','E3','E4','L1','L2','L3','End'];
const fixed={T1:['cover',4.0,[['T1']]],End:['end',0,[['E1',1.0],['E2',4.0]]]};
let t=0;const scenes=[],caps=[];
for(const id of order){
  const sc={id,kind:'',xf:id==='End'?1.0:(scenes.length?0.9:0),t0:r1(t),shots:[]};
  if(fixed[id]){const [kind,d,shots]=fixed[id];sc.kind=kind;
    if(id==='End'){let e=t;for(const [sid,dd] of shots){e+=dd;sc.shots.push({id:sid,t0:r1(sc.shots.length?sc.shots.at(-1).t1:t),t1:r1(e)})}t=e}
    else{t+=d;sc.shots.push({id,t0:sc.t0,t1:r1(t)})}}
  else{sc.kind='beat';const [lead,hold,shots]=beats[id];const tx=TEXT[id];let s=t+lead;const cs=[];
    tx.forEach((text,i)=>{const d=dur(text);const c={id:`${id}.c${i+1}`,beat:id,c:i+1,s:r1(s),e:r1(s+d),text};cs.push(c);caps.push(c);s+=d+GAP});
    const end=r1(cs.at(-1).e+hold);let prev=t;
    for(const [sid,tok] of shots){let e;
      if(tok==='L')e=cs[0].s;else if(tok==='H')e=end;else e=cs[+tok[1]-1].e;
      sc.shots.push({id:`${id}.${sid}`,t0:r1(prev),t1:r1(e)});prev=e}
    t=end}
  sc.t1=r1(t);scenes.push(sc)}
for(const c of caps){if(c.text.length/(c.e-c.s)>17.3+1e-9)throw Error('CPS '+c.id)}
for(const s of scenes)for(const h of s.shots)if(h.t1-h.t0<0.5)console.warn('short shot',h.id,(h.t1-h.t0).toFixed(2));
const FPS=30,duration=scenes.at(-1).t1;
fs.writeFileSync(path.join(ROOT,'timeline.json'),JSON.stringify({fps:FPS,duration,frames:Math.round(duration*FPS),scenes,captions:caps},null,1)+'\n');
const sec=(a,b)=>r1(scenes.find(s=>s.id===b).t0-scenes.find(s=>s.id===a).t0);
console.log('timeline.json',duration,'s',Math.round(duration*FPS),'frames',caps.length,'captions',scenes.length,'scenes',scenes.reduce((n,s)=>n+s.shots.length,0),'shots');
console.log('sections: 1',sec('T1','B2'),' 2',sec('B2','B3b'),' 3',sec('B3b','M1'),' 4',sec('M1','E1'),' 5',sec('E1','L1'),' 6',sec('L1','End'));
