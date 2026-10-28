// Frame chrome: act tone (vignette/wash), header, evidence tag, captions, progress bar. Plan sections 3, 4, 7.
import {W,H,P,clamp,lerp,smooth,rgba,T,poly,dot,wrap,mixCol} from './lib.mjs';
import {TIMELINE,capAt,capLines} from './captions.mjs';
import {glowCircle} from './light.mjs';

export const ACT_OF={T1:0,B1:1,P1:1,B2:2,B3:2,Q2:2,B3b:3,D2:3,M1:4,M2:4,M3:4,M4:4,M5:4,E1:5,E2:5,E3:5,E4:5,L1:6,L2:6,L3:6,End:7};
// six sections, one per presentation criterion (v6 script)
export const ACTS=[null,
 {n:'1',name:'Problem and pipeline',col:P.cyan},
 {n:'2',name:'Research question',col:P.violet},
 {n:'3',name:'Data',col:P.blue},
 {n:'4',name:'Technique',col:P.green},
 {n:'5',name:'Evidence',col:P.amber},
 {n:'6',name:'Limits and summary',col:P.muted}];
export const TAGS={
 MEAS:['Archived result. Measured.',P.green],CODE:['From the project code.',P.blue],ILLU:['Illustrative. Not recorded data.',P.amber],
 CONCEPT:['Concept picture.',P.amber],MATH:['Worked example. Hypothetical numbers.',P.violet],REF:['Reported by the paper. Not our result.',P.ref],DATA:['Dataset description (PhysioNet). Illustration.',P.violet],MIX:['Measured rate. Tile positions simulated.',P.green],PIPE:['Project pipeline. Illustrative pictures.',P.amber]};
export const TAG_FULL={...TAGS};

const q=(v,s)=>Math.round(v/s)*s;
/** per-time tone: {vig, wash} (plan section 4 table) */
export function toneAt(t){
  const sc=TIMELINE.scenes.find(s=>t>=s.t0&&t<s.t1)||TIMELINE.scenes.at(-1),ub=t-sc.t0;let vig=.18,wash=null;
  switch(sc.id){
    case 'T1':vig=.25;break;
    case 'B1':case 'P1':vig=.18;break;
    case 'B2':case 'B3':case 'Q2':vig=.15;wash={rgb:[182,168,255],a:.025,screen:true};break;
    case 'B3b':case 'D2':vig=.12;wash={rgb:[111,168,255],a:.03,screen:true};break;
    case 'M1':case 'M2':case 'M3':case 'M4':case 'M5':vig=.12;wash={rgb:[126,224,161],a:.025,screen:true};break;
    case 'E1':vig=.30;wash={rgb:[255,160,150],a:.05,bottom:true};break;
    case 'E2':{vig=.30;const g=smooth((t-R1_T)/2),a=lerp(.05,.03,g);wash={rgb:[Math.round(lerp(255,126,g)),Math.round(lerp(160,224,g)),Math.round(lerp(150,161,g))],a:q(a,.002),bottom:g<1};break}
    case 'E3':vig=.30;wash={rgb:[126,224,161],a:.03};break;
    case 'E4':case 'L1':case 'L2':case 'L3':vig=.08;wash={rgb:[143,161,184],a:.04};break;
    case 'End':vig=lerp(.35,.60,smooth(ub/6));break}
  return {vig:q(vig,.01),wash}}
const R1_T=(TIMELINE.scenes.find(s=>s.id==='E2').shots.find(h=>h.id==='E2.S2')||{t0:0}).t0;

export function header(c,scene,shot,t){
  const a=ACT_OF[scene.id];if(scene.kind!=='beat')return;const act=ACTS[a];
  T(c,`${act.n} · ${act.name}`,104,108,{size:27,color:act.col,weight:'med'});
  const tag=shot&&shot.def&&shot.def.tag;if(tag){const one=typeof tag==='string'?tag:tag.main;const e=TAGS[one];if(e){
    if(one==='MIX')mixTag(c);else T(c,e[0],1816,108,{size:24,color:e[1],align:'right',weight:'med'})}}
  poly(c,[[104,906],[1816,906]],{stroke:P.line,width:1.5})}
function mixTag(c){const a='Measured rate.',b=' Tile positions simulated.';c.save();c.font='24px FilmMed';const wb=c.measureText(b).width;c.restore();T(c,b,1816,108,{size:24,color:P.amber,align:'right',weight:'med'});T(c,a,1816-wb,108,{size:24,color:P.green,align:'right',weight:'med'})}
export function drawCaption(c,t){const r=capAt(t);if(!r)return;const lines=capLines(c,r.cap.text).slice(0,2);const y0=lines.length>1?950:968;
  lines.forEach((l,i)=>T(c,l,960,y0+i*44,{size:33,align:'center',alpha:r.alpha}))}
const ACT_STARTS=['B1','B2','B3b','M1','E1','L2'].map(id=>TIMELINE.scenes.find(s=>s.id===id).t0);
export function progress(c,t){const x0=104,x1=1816,y=1012,D=TIMELINE.duration;poly(c,[[x0,y],[x1,y]],{stroke:'#1A2940',width:3});
  for(const s of ACT_STARTS)dot(c,x0+(x1-x0)*s/D,y,4,P.line);
  const x=x0+(x1-x0)*t/D;poly(c,[[x0,y],[x,y]],{stroke:P.cyan,width:3});dot(c,x,y,5,P.cyan,1,10)}
