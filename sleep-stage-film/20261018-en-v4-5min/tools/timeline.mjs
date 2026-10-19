// Builds timeline.json (golden table, plan section 9.1) + captions (section 9.3). Run: node tools/timeline.mjs
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const ROOT=path.join(path.dirname(fileURLToPath(import.meta.url)),'..');
const S=(id,kind,shots,xf=0.9)=>({id,kind,xf,shots});
// [shot id suffix, end time]; scene start = previous end. Times are story seconds (storyboard-approved).
const plan=[
 ['T1','cover',[['T1',6.0]]],
 ['ActI','act',[['ActI',8.5]]],
 ['B1','beat',[['S1',12.0],['S2',18.0],['S3',25.4]]],
 ['B2','beat',[['S1',28.9],['S2',37.3],['S3',42.1],['S4',45.8]]],
 ['ActII','act',[['ActII',48.3]]],
 ['B3','beat',[['S1',51.8],['S2',59.1],['S3',62.9],['S4',65.1]]],
 ['B4','beat',[['S1',68.6],['S2',75.4],['S3',80.1],['S4',84.3]]],
 ['B5','beat',[['S1',87.8],['S2',94.1],['S3',100.5],['S4',102.7]]],
 ['B6','beat',[['S1',106.2],['S2',113.0],['S3',119.5],['S4',121.7]]],
 ['ActIII','act',[['ActIII',124.2]]],
 ['B7','beat',[['S1',127.7],['S2',134.4],['S3',141.8],['S4',145.5]]],
 ['B7b','beat',[['S1',149.0],['S2',155.4],['S3',160.5],['S4',163.9],['S5',166.1]]],
 ['B8','beat',[['S1',169.6],['S2',176.4],['S3',182.9],['S4',187.4],['S5',192.1]]],
 ['B9','beat',[['S1',195.6],['S2',202.3],['S3',207.4],['S4',209.6]]],
 ['B9b','beat',[['S1',213.1],['S2',220.0],['S3',223.0],['S4',225.2]]],
 ['ActIV','act',[['ActIV',227.7]]],
 ['B10','beat',[['S1',231.2],['S2',236.0],['S3',243.9],['S4',246.1]]],
 ['B11','beat',[['S1',249.6],['S2',256.1],['S3',259.7],['S4',261.9]]],
 ['B12','beat',[['S1',265.4],['S2',271.4],['S3',276.6]]],
 ['B13','beat',[['S1',280.1],['S2',286.6],['S3',290.2],['S4',292.4]]],
 ['End','end',[['E1',293.6],['E2',298.4]]],
];
let t=0;const scenes=[];
for(const [id,kind,shots] of plan){const sc={id,kind,xf:id==='End'?1.2:(scenes.length?0.9:0),t0:+t.toFixed(1),shots:[]};
  for(const [sid,end] of shots){const sh={id:kind==='beat'?`${id}.${sid}`:sid,t0:+t.toFixed(1),t1:end};sc.shots.push(sh);t=end}
  sc.t1=t;scenes.push(sc)}
// captions from the plan's table (single source of approved text)
const md=fs.readFileSync(path.join(ROOT,'docs/production-plan.md'),'utf8');
const caps=[...md.matchAll(/^\| (B\d+b?\.c\d) \| ([\d.]+)[–-]([\d.]+) \|.*?\| \d+ \| [\d.]+ \| \d \| (.+?) \|$/gm)].map(m=>({id:m[1],beat:m[1].split('.')[0],c:+m[1].slice(-1),s:+m[2],e:+m[3],text:m[4]}));
if(caps.length!==30)throw Error('expected 30 captions, got '+caps.length);
const FPS=30,duration=scenes.at(-1).t1;
fs.writeFileSync(path.join(ROOT,'timeline.json'),JSON.stringify({fps:FPS,duration,frames:Math.round(duration*FPS),scenes,captions:caps},null,1)+'\n');
console.log('timeline.json',duration,'s',Math.round(duration*FPS),'frames',caps.length,'captions');
