// Builds timeline.json (v4.1): scene/shot times derived from docs/script-data.mjs. Run: node tools/timeline.mjs
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const ROOT=path.join(path.dirname(fileURLToPath(import.meta.url)),'..');
const {ACTS}=await import(path.join(ROOT,'docs/script-data.mjs'));
const TEXT=Object.fromEntries(ACTS.flatMap(a=>a.beats).map(b=>[b.id,b.caps]));
const GAP=0.7,r1=x=>Math.round(x*10)/10;
const dur=t=>Math.max(r1(t.length/17),Math.ceil(t.length/17.3*10)/10);
// beats: [id, lead, hold, shots[[suffix, token]]]; tokens: L=c1 start, cN=caption N end, cm=c2 start+56% of c2, H=scene end
const std=['L','c1','c2','H'].map((t,i)=>['S'+(i+1),t]);
const beats={
 B1:[3.5,2.2,[['S1','L'],['S2','c1'],['S3','H']]],
 B2:[3.5,3.7,std.map(x=>x).concat([]).slice(0,0).concat([['S1','L'],['S2','c1'],['S3','c2'],['S4','H']])],
 B3:[3.5,2.2,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B3b:[2.0,2.2,[['S1','L'],['S2','c1'],['S3','c2'],['S4','c3'],['S5','H']]],
 B4:[3.5,2.2,[['S1','L'],['S2','c1'],['S3','c2'],['S4','c3'],['S5','H']]],
 B5:[3.5,2.2,[['S1','L'],['S2','c1'],['S3','c2'],['S4','c3'],['S5','H']]],
 B6:[3.5,2.2,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B7:[2.0,2.2,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B7b:[2.0,1.7,[['S1','L'],['S2','c1'],['S3','cm'],['S4','c2'],['S5','H']]],
 B8:[2.0,2.7,[['S1','L'],['S2','c1'],['S3','c2'],['S4','c3'],['S5','H']]],
 B9:[2.0,1.7,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B9b:[2.0,1.7,[['S1','L'],['S2','c1'],['S4','H']]],
 B10:[2.0,1.7,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B11:[2.0,1.7,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
 B13:[2.0,1.7,[['S1','L'],['S2','c1'],['S3','c2'],['S4','H']]],
};
const order=['T1','ActI','B1','B2','ActII','B3','B3b','B4','B5','B6','ActIII','B7','B7b','B8','B9','B9b','ActIV','B10','B11','B13','End'];
const fixed={T1:['cover',6.0,[['T1']]],ActI:['act',2.5,[['ActI']]],ActII:['act',2.5,[['ActII']]],ActIII:['act',2.5,[['ActIII']]],ActIV:['act',2.5,[['ActIV']]],End:['end',0,[['E1',1.2],['E2',4.8]]]};
let t=0;const scenes=[],caps=[];
for(const id of order){
  const sc={id,kind:'',xf:id==='End'?1.2:(scenes.length?0.9:0),t0:r1(t),shots:[]};
  if(fixed[id]){const [kind,d,shots]=fixed[id];sc.kind=kind;
    if(id==='End'){let e=t;for(const [sid,dd] of shots){e+=dd;sc.shots.push({id:sid,t0:r1(sc.shots.length?sc.shots.at(-1).t1:t),t1:r1(e)})}t=e}
    else{t+=d;sc.shots.push({id,t0:sc.t0,t1:r1(t)})}}
  else{sc.kind='beat';const [lead,hold,shots]=beats[id];const tx=TEXT[id];let s=t+lead;const cs=[];
    tx.forEach((text,i)=>{const d=dur(text);const c={id:`${id}.c${i+1}`,beat:id,c:i+1,s:r1(s),e:r1(s+d),text};cs.push(c);caps.push(c);s+=d+GAP});
    const end=r1(cs.at(-1).e+hold);let prev=t;
    for(const [sid,tok] of shots){let e;
      if(tok==='L')e=cs[0].s;else if(tok==='H')e=end;else if(tok==='cm')e=r1(cs[1].s+0.56*(cs[1].e-cs[1].s));else e=cs[+tok[1]-1].e;
      sc.shots.push({id:`${id}.${sid}`,t0:r1(prev),t1:r1(e)});prev=e}
    t=end}
  sc.t1=r1(t);scenes.push(sc)}
for(const c of caps){if(c.text.length/(c.e-c.s)>17.3+1e-9)throw Error('CPS '+c.id)}
const FPS=30,duration=scenes.at(-1).t1;
fs.writeFileSync(path.join(ROOT,'timeline.json'),JSON.stringify({fps:FPS,duration,frames:Math.round(duration*FPS),scenes,captions:caps},null,1)+'\n');
console.log('timeline.json',duration,'s',Math.round(duration*FPS),'frames',caps.length,'captions',scenes.length,'scenes',scenes.reduce((n,s)=>n+s.shots.length,0),'shots');
