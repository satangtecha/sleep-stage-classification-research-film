// v3 film: timeline, frame chrome (reference-style card), scene transitions, chapter cards and rendering.
// Usage: node film.mjs stills | sheet | render <part> <parts> | srt | info
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {fileURLToPath} from 'node:url';
import {createCanvas} from '@napi-rs/canvas';
import {Scene} from '@johnhenry/ecmanim/node';
import {W,H,P,clamp,lerp,smooth,cubic,outExpo,outBack,seg,rgba,T,wrap,measure,poly,rect,dot,pill} from './lib.mjs';
import {scenesA} from './scenes-a.mjs';
import {scenesB} from './scenes-b.mjs';
import {scenesC,FACTS} from './scenes-c.mjs';

export const ROOT=path.dirname(fileURLToPath(import.meta.url));
export const FPS=30,XF=0.9; // crossfade overlap (s)
export const CHAPTERS=[
  {n:0,title:'Opening'},
  {n:1,title:'The signal',sub:['Voltage difference','Sampling and aliasing','Epochs, labels, cohort','Subject-wise folds']},
  {n:2,title:'From waves to frequencies',sub:['Amplitude, frequency, phase','DFT, magnitude, phase','STFT and Hamming window','129 × 29 log-magnitude']},
  {n:3,title:'Putting nights on one scale',sub:['z-scores','Per-frequency statistics','Baseline vs R1','Gain invariance and its cost']},
  {n:4,title:'The network',sub:['Tensors and reshaping','Convolution, ReLU, pooling','BatchNorm and dropout','GRU, BiGRU, softmax']},
  {n:5,title:'How it learns',sub:['Cross-entropy','Class weights','Gradients and backprop','AdamW and early stopping']},
  {n:6,title:'Predicting and scoring',sub:['Overlapping windows','Confusion matrix','Precision, recall, F1','Subject-mean macro-F1']},
  {n:7,title:'What we found',sub:['Failing baseline nights','R1 and full-night results','Paired bootstrap','Folds and per-class recall']},
  {n:8,title:'The evidence boundary',sub:['Rejected pilots','Provenance audit','Limitations','The whole system']},
];
export const TAGS={MEAS:['Archived result. Measured.',P.green],CODE:['From the project code.',P.blue],ILLU:['Illustrative signal. Not recorded data.',P.amber],CONC:['Concept picture. Not model internals.',P.amber],MATH:['Worked example. Hypothetical numbers.',P.violet]};

const content=[...scenesA,...scenesB,...scenesC];
// insert chapter cards
export const SCENES=[];{let last=-1;for(const s of content){if(s.ch!==last&&s.ch>0)SCENES.push({id:'chapter-'+s.ch,ch:s.ch,card:true,dur:3.6,cap:[]});last=s.ch;SCENES.push(s)}}
export const CPS=17;for(const s of SCENES){let k=1;s.cap.forEach(([t0,x],i)=>{const end=i+1<s.cap.length?s.cap[i+1][0]:s.dur-XF/2;k=Math.max(k,x.length/CPS/(end-t0-(i===0?XF/2:0)))});s.k=k;if(k>1){s.dur*=k;s.cap=s.cap.map(([t0,x])=>[t0*k,x])}}
let t=0;SCENES.forEach((s,i)=>{s.start=t;s.end=t+s.dur;t+=s.dur-(i<SCENES.length-1?XF:0)});
export const DURATION=Math.round(t*FPS)/FPS;
export const FRAMES=Math.round(DURATION*FPS);

// ---------------- chrome ----------------
const CARD=[56,44,1808,992];
let bgCache=null;
function background(){if(bgCache)return bgCache;const c=createCanvas(W,H),x=c.getContext('2d');const g=x.createLinearGradient(0,0,W,H);g.addColorStop(0,'#141236');g.addColorStop(.5,'#0B0B22');g.addColorStop(1,'#16123A');x.fillStyle=g;x.fillRect(0,0,W,H);
  // reference-style purple arcs
  for(const [cx,cy,r,a] of [[420,-520,700,.55],[1180,-560,720,.45],[2050,260,700,.5],[-260,980,520,.35]]){const gr=x.createRadialGradient(cx,cy,r*.85,cx,cy,r*1.05);gr.addColorStop(0,'rgba(120,110,220,0)');gr.addColorStop(.9,`rgba(140,130,240,${a*.35})`);gr.addColorStop(1,'rgba(140,130,240,0)');x.fillStyle=gr;x.beginPath();x.arc(cx,cy,r*1.05,0,Math.PI*2);x.fill();x.strokeStyle=`rgba(170,160,255,${a})`;x.lineWidth=2.5;x.beginPath();x.arc(cx,cy,r,0,Math.PI*2);x.stroke()}
  x.save();x.shadowColor='rgba(0,0,0,0.6)';x.shadowBlur=40;x.fillStyle=P.card;x.beginPath();x.roundRect(...CARD,22);x.fill();x.restore();
  x.strokeStyle='rgba(255,255,255,0.06)';x.lineWidth=1.5;x.beginPath();x.roundRect(...CARD,22);x.stroke();
  bgCache=c;return c}

function chapterLabel(s){const ch=CHAPTERS[s.ch];return ch.n?`${ch.n}. ${ch.title}`:'Sleep stage research'}
function capAt(s,u){let k=-1;for(let i=0;i<s.cap.length;i++)if(u>=s.cap[i][0])k=i;return k}
function drawCaption(c,s,u){if(!s.cap.length)return;const k=capAt(s,u);const draw=(txt,a,rise)=>{const lines=wrap(c,txt,1620,33);const y0=lines.length>1?950:968;lines.slice(0,2).forEach((l,i)=>T(c,l,960,y0+i*44+rise,{size:33,align:'center',alpha:a}))};
  const a=k===0?1:seg(u,s.cap[k][0],.6,clamp);if(a<.5)draw(s.cap[k-1][1],smooth(1-2*a),-6*a*2);else draw(s.cap[k][1],smooth(2*a-1),8*(2-2*a))}
function header(c,s,u){T(c,chapterLabel(s),104,108,{size:27,color:P.ink,weight:'med'});if(s.tag){const [txt,col]=TAGS[s.tag];T(c,txt,1816,108,{size:24,color:col,align:'right',weight:'med'})}
  poly(c,[[104,906],[1816,906]],{stroke:P.line,width:1.5})}

function chapterCard(c,s,u){const ch=CHAPTERS[s.ch];const a=seg(u,0,.8,cubic);
  // sweeping arc
  c.save();c.globalAlpha=.9;c.strokeStyle=P.cyan;c.lineWidth=4;c.shadowColor=P.cyan;c.shadowBlur=18;c.beginPath();c.arc(560,500,230,-Math.PI/2,-Math.PI/2+Math.PI*1.9999*seg(u,.1,1.4,cubic));c.stroke();c.restore();
  c.save();c.strokeStyle=rgba(P.violet,.4);c.lineWidth=2;c.beginPath();c.arc(560,500,262,Math.PI/2,Math.PI/2+Math.PI*1.4*seg(u,.3,1.6,cubic));c.stroke();c.restore();
  const sc=lerp(.6,1,outBack(seg(u,.1,.9,(x)=>x)));c.save();c.translate(560,500);c.scale(sc,sc);T(c,String(ch.n).padStart(2,'0'),0,62,{size:190,weight:'bold',align:'center',color:P.ink,alpha:a});c.restore();
  T(c,`Chapter ${ch.n}`,900,400,{size:28,color:P.cyan,weight:'med',alpha:seg(u,.4,.6)});
  T(c,ch.title,900,478,{size:64,weight:'bold',alpha:seg(u,.5,.7),rise:20});
  ch.sub.forEach((l,i)=>{const b=seg(u,.9+i*.18,.5);dot(c,912,560+i*48-9,5,P.cyan,b);T(c,l,936,560+i*48,{size:28,color:P.muted,alpha:b,rise:10})});}

function drawScene(c,s,u){if(s.card){chapterCard(c,s,u);return}header(c,s,u);c.save();c.beginPath();c.rect(CARD[0],128,CARD[2],770);c.clip();s.draw(c,u/(s.k||1),s);c.restore();drawCaption(c,s,u)}

const layerA=createCanvas(W,H),layerB=createCanvas(W,H);
function renderLayer(layer,s,u){const c=layer.getContext('2d');c.clearRect(0,0,W,H);c.save();c.beginPath();c.roundRect(...CARD,22);c.clip();drawScene(c,s,u);c.restore();return layer}

function progress(c,time){const x0=104,x1=1816,y=1012;poly(c,[[x0,y],[x1,y]],{stroke:'#1A2940',width:3});
  for(const s of SCENES)if(s.card){const x=x0+(x1-x0)*s.start/DURATION;dot(c,x,y,4,P.line)}
  const x=x0+(x1-x0)*time/DURATION;poly(c,[[x0,y],[x,y]],{stroke:P.cyan,width:3});dot(c,x,y,5,P.cyan,1,10)}

export function frameAt(canvas,time){const c=canvas.getContext('2d');c.drawImage(background(),0,0);
  const act=SCENES.filter(s=>time>=s.start&&time<s.end);const s1=act[0],s2=act[1];
  if(!s2){c.save();c.beginPath();c.roundRect(...CARD,22);c.clip();drawScene(c,s1,time-s1.start);c.restore()}
  else{const p=cubic((time-s2.start)/XF);const A=renderLayer(layerA,s1,time-s1.start),B=renderLayer(layerB,s2,time-s2.start);const kind=s1.card||s2.card?'iris':(SCENES.indexOf(s2)%2?'zoom':'push');
    if(kind==='zoom'){c.save();c.globalAlpha=1-p;c.translate(960,520);c.scale(1+.06*p,1+.06*p);c.translate(-960,-520);c.drawImage(A,0,0);c.restore();c.save();c.globalAlpha=p;c.translate(960,520);const k=.94+.06*p;c.scale(k,k);c.translate(-960,-520);c.drawImage(B,0,0);c.restore()}
    else if(kind==='push'){c.save();c.globalAlpha=1-p;c.drawImage(A,-240*p,0);c.restore();c.save();c.globalAlpha=p;c.drawImage(B,240*(1-p),0);c.restore()}
    else{c.drawImage(A,0,0);c.save();const r=1150*p;c.beginPath();c.arc(960,520,r,0,Math.PI*2);c.clip();c.drawImage(background(),0,0);c.drawImage(B,0,0);c.restore();c.save();c.strokeStyle=rgba(P.cyan,(1-p)*.9);c.lineWidth=5;c.shadowColor=P.cyan;c.shadowBlur=24;c.beginPath();c.arc(960,520,r,0,Math.PI*2);c.stroke();c.restore()}}
  progress(c,time)}

// ---------------- outputs ----------------
const OUT=path.join(ROOT,'outputs');
export function storyJSON(){return {language:'en',audio:false,fps:FPS,duration_seconds:DURATION,crossfade_seconds:XF,chapters:CHAPTERS.map(c=>({n:c.n,title:c.title})),scenes:SCENES.map(s=>({id:s.id,chapter:s.ch,tag:s.tag?TAGS[s.tag][0]:null,start:+s.start.toFixed(3),end:+s.end.toFixed(3),captions:s.cap.map(([t,x])=>({at:+(s.start+t).toFixed(3),text:x}))}))}}
function srt(){const ts=x=>{const ms=Math.round(x*1000);const h=Math.floor(ms/3.6e6),m=Math.floor(ms/6e4)%60,s=Math.floor(ms/1000)%60;return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},${String(ms%1000).padStart(3,'0')}`};
  const items=[];for(const s of SCENES)s.cap.forEach(([t0,txt],i)=>{const a=s.start+t0+(i===0&&s.start>0?XF*.5:0),b=i+1<s.cap.length?s.start+s.cap[i+1][0]:s.end-(s===SCENES.at(-1)?0:XF*.5);items.push([a,b,txt])});
  return items.map(([a,b,x],i)=>`${i+1}\n${ts(a)} --> ${ts(b)}\n${x}\n`).join('\n')}

async function render(part,parts){fs.mkdirSync(path.join(OUT,'parts'),{recursive:true});const f0=Math.floor(FRAMES*part/parts),f1=Math.floor(FRAMES*(part+1)/parts);const file=path.join(OUT,'parts',`part-${part}.mp4`);
  const canvas=createCanvas(W,H);const ff=spawn('ffmpeg',['-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',`${W}x${H}`,'-r',String(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-threads','1',file],{stdio:['pipe','inherit','inherit']});const done=once(ff,'exit');
  const t0=Date.now();let n=0;
  // ecmanim Scene drives the frame clock (fps-locked timeline); we offset into this part's range.
  const scene=new Scene({fps:FPS,frameHandler:async(_,i)=>{const fi=f0+n;if(fi>=f1)return;frameAt(canvas,fi/FPS);if(!ff.stdin.write(canvas.data()))await once(ff.stdin,'drain');n++;if(n%300===0)console.log(`part ${part}: ${n}/${f1-f0} frames, ${((Date.now()-t0)/n).toFixed(1)} ms/frame`)}});
  await scene.wait((f1-f0)/FPS);while(n<f1-f0){frameAt(canvas,(f0+n)/FPS);if(!ff.stdin.write(canvas.data()))await once(ff.stdin,'drain');n++}
  ff.stdin.end();const [code]=await done;if(code)throw Error('ffmpeg failed');console.log(JSON.stringify({part,frames:n,f0,f1,file,seconds:(Date.now()-t0)/1000}))}

function stills(times){fs.mkdirSync(path.join(OUT,'stills'),{recursive:true});const canvas=createCanvas(W,H);const files=[];
  for(const s of SCENES){if(s.card&&times!=='all')continue;for(const fr of (times==='all'?[.5]:[.72])){const tt=s.start+XF+(s.dur-2*XF)*fr;frameAt(canvas,tt);const f=path.join(OUT,'stills',`${String(SCENES.indexOf(s)).padStart(2,'0')}-${s.id}.jpg`);fs.writeFileSync(f,canvas.toBuffer('image/jpeg',85));files.push(f)}}return files}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){const cmd=process.argv[2];
  if(cmd==='info')console.log(JSON.stringify({scenes:SCENES.length,content:content.length,duration:DURATION,frames:FRAMES},null,1));
  else if(cmd==='stills'){const f=stills();console.log(f.length+' stills')}
  else if(cmd==='frame'){const canvas=createCanvas(W,H);const tt=+process.argv[3];frameAt(canvas,tt);fs.writeFileSync(process.argv[4],canvas.toBuffer('image/jpeg',88))}
  else if(cmd==='scene'){const s=SCENES.find(x=>x.id===process.argv[3]);const canvas=createCanvas(W,H);for(const u of process.argv.slice(4).map(Number)){frameAt(canvas,s.start+u);fs.writeFileSync(path.join(OUT,`dbg-${s.id}-${u}.jpg`),canvas.toBuffer('image/jpeg',85))}}
  else if(cmd==='render')await render(+process.argv[3],+process.argv[4]);
  else if(cmd==='srt'){fs.mkdirSync(OUT,{recursive:true});fs.writeFileSync(path.join(OUT,'captions-en.srt'),srt());fs.writeFileSync(path.join(ROOT,'story.json'),JSON.stringify(storyJSON(),null,1)+'\n');console.log('srt + story written')}
  else throw Error('Usage: node film.mjs info|stills|frame t out|scene id u..|render part parts|srt')}
