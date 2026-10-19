// Frame chrome: act tone (vignette/wash), header, evidence tag, captions, progress bar. Plan sections 3, 4, 7.
import {W,H,P,clamp,lerp,smooth,rgba,T,poly,dot,wrap,mixCol} from './lib.mjs';
import {TIMELINE,capAt,capLines} from './captions.mjs';
import {glowCircle} from './light.mjs';

export const ACT_OF={T1:0,ActI:1,B1:1,B2:1,ActII:2,B3:2,B4:2,B5:2,B6:2,ActIII:3,B7:3,B7b:3,B8:3,B9:3,B9b:3,ActIV:4,B10:4,B11:4,B12:4,B13:4,End:5};
export const ACTS=[null,
 {n:'I',name:'A night in 30-second pieces',col:P.cyan},
 {n:'II',name:'A different question',col:P.violet},
 {n:'III',name:'The nights that failed',col:P.amber},
 {n:'IV',name:'What we can honestly say',col:P.muted}];
export const TAGS={
 MEAS:['Archived result. Measured.',P.green],CODE:['From the project code.',P.blue],ILLU:['Illustrative. Not recorded data.',P.amber],
 CONCEPT:['Concept picture.',P.amber],MATH:['Worked example. Hypothetical numbers.',P.violet],REF:['Reported by the paper. Not our result.',P.ref],MIX:['Measured rate. Tile positions simulated.',P.green]};
export const TAG_FULL={...TAGS};

const q=(v,s)=>Math.round(v/s)*s;
/** per-time tone: {vig, wash} (plan section 4 table) */
export function toneAt(t){
  const sc=TIMELINE.scenes.find(s=>t>=s.t0&&t<s.t1)||TIMELINE.scenes.at(-1),ub=t-sc.t0;let vig=.18,wash=null;
  switch(sc.id){
    case 'T1':vig=.25;break;
    case 'ActI':case 'B1':case 'B2':vig=.18;break;
    case 'ActII':case 'B3':case 'B4':case 'B5':case 'B6':vig=.12;wash={rgb:[91,224,240],a:.03,screen:true};break;
    case 'ActIII':vig=lerp(.45,.30,smooth(ub/2.5));wash={rgb:[255,160,150],a:.06};break;
    case 'B7':case 'B7b':case 'B8':case 'B9':case 'B9b':{vig=.30;
      const g=sc.id==='B8'?smooth((t-182.9)/2):sc.id==='B9'||sc.id==='B9b'?1:0;
      const a=lerp(.04,.03,g),rgb=[Math.round(lerp(255,126,g)),Math.round(lerp(196,224,g)),Math.round(lerp(107,161,g))];wash={rgb,a:q(a,.002),bottom:g<1};
      if(g>=1)wash.bottom=false;break}
    case 'ActIV':case 'B10':case 'B11':case 'B12':case 'B13':vig=.08;wash={rgb:[143,161,184],a:.04};break;
    case 'End':vig=lerp(.35,.60,smooth(ub/6));break}
  return {vig:q(vig,.01),wash}}

export function header(c,scene,shot,t){
  const a=ACT_OF[scene.id];if(scene.kind!=='beat')return;const act=ACTS[a];
  T(c,`${act.n} · ${act.name}`,104,108,{size:27,color:act.col,weight:'med'});
  const tag=shot&&shot.def&&shot.def.tag;if(tag){const one=typeof tag==='string'?tag:tag.main;const e=TAGS[one];if(e){
    if(one==='MIX')mixTag(c);else T(c,e[0],1816,108,{size:24,color:e[1],align:'right',weight:'med'})}}
  poly(c,[[104,906],[1816,906]],{stroke:P.line,width:1.5})}
function mixTag(c){const a='Measured rate.',b=' Tile positions simulated.';c.save();c.font='24px FilmMed';const wb=c.measureText(b).width;c.restore();T(c,b,1816,108,{size:24,color:P.amber,align:'right',weight:'med'});T(c,a,1816-wb,108,{size:24,color:P.green,align:'right',weight:'med'})}
export function drawCaption(c,t){const r=capAt(t);if(!r)return;const lines=capLines(c,r.cap.text).slice(0,2);const y0=lines.length>1?950:968;
  lines.forEach((l,i)=>T(c,l,960,y0+i*44,{size:33,align:'center',alpha:r.alpha}))}
const ACT_STARTS=['ActI','ActII','ActIII','ActIV'].map(id=>TIMELINE.scenes.find(s=>s.id===id).t0);
export function progress(c,t){const x0=104,x1=1816,y=1012,D=TIMELINE.duration;poly(c,[[x0,y],[x1,y]],{stroke:'#1A2940',width:3});
  for(const s of ACT_STARTS)dot(c,x0+(x1-x0)*s/D,y,4,P.line);
  const x=x0+(x1-x0)*t/D;poly(c,[[x0,y],[x,y]],{stroke:P.cyan,width:3});dot(c,x,y,5,P.cyan,1,10)}
