// v4 film: frame compositor (layers, transitions, carry), CLI.
// node film.mjs info | frame <t> <out.jpg> | shot <id> <us...> | stills | sheet | preview <scene> | render <k> <parts> | srt
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {fileURLToPath} from 'node:url';
import {createCanvas} from '@napi-rs/canvas';
import {W,H,P,clamp,lerp,smooth,cubic,rgba,T,rnd,poly,wrap} from './lib.mjs';
import {paintBackground,clipCard,CARD,glowCircle} from './light.mjs';
import {TIMELINE,cueAbs,capLines,toSrt} from './captions.mjs';
import {fact} from './facts.mjs';
import {ACT_OF,ACTS,toneAt,header,drawCaption,progress,TAGS} from './chrome.mjs';
import {SHOTS} from './beats/index.mjs';

export const ROOT=path.dirname(fileURLToPath(import.meta.url));
export const FPS=TIMELINE.fps,FRAMES=TIMELINE.frames,DURATION=TIMELINE.duration;
export const SCENES=TIMELINE.scenes;
export const CUE_LOG=[];           // {shot, id, phrase, rel}
export const hooks={rec:null};     // tests install hooks.rec to collect component props
const PAR={2:.90,3:1,4:1.04,5:1.08};
const smoothP=(a,b,t)=>smooth((t-a)/(b-a));

export function sceneAt(t){for(let i=SCENES.length-1;i>=0;i--)if(t>=SCENES[i].t0)return SCENES[i];return SCENES[0]}
export function shotAt(scene,t){return scene.shots.find(s=>t>=s.t0&&t<s.t1)||scene.shots.at(-1)}
function defaultCam(scene,t){const p=clamp((t-scene.t0)/(scene.t1-scene.t0));const a=ACT_OF[scene.id];
  if(a===0||a===1)return {x:0,y:0,zoom:1+.03*smooth(p)};
  if(a===2)return {x:lerp(-20,20,smooth(p)),y:0,zoom:1};
  if(a===4)return {x:0,y:0,zoom:1+.006*p};
  return {x:0,y:0,zoom:1}}

function makeK(c,scene,shot,t,pass){
  const us=t-shot.t0,ub=t-scene.t0,def=SHOTS[shot.id]||{};
  const k={t,us,ub,pass,scene,shot,rnd,fact,cue:null,cam:null,L:null,label:null,rec:null,shotLen:shot.t1-shot.t0};
  k.cam=def.camera?def.camera(us,ub,k):defaultCam(scene,t);
  k.cue=(id,phrase,nth=0)=>{const rel=cueAbs(id,phrase,nth)-shot.t0;CUE_LOG.push({shot:shot.id,id,phrase,rel});return rel};
  k.L=(f,fn)=>{const par=PAR[f]??f,cam=k.cam,s=1+(cam.zoom-1)*par;c.save();c.translate(960,513);c.scale(s,s);c.translate(-960-cam.x*par,-513-cam.y*par);fn();c.restore()};
  // label at world position, screen-space size (plan 6.5 labelAt)
  k.label=(text,wx,wy,o={})=>{const cam=k.cam,s=1+(cam.zoom-1);const sx=960+(wx-960-cam.x)*s,sy=513+(wy-513-cam.y)*s;return T(c,text,sx,sy,o)};
  k.rec=(name,props={})=>{if(hooks.rec)hooks.rec({name,shot:shot.id,us,...props})};
  return k}

/** draw one scene (opaque, own background) at story time t. pass: 'all' | 'rest' | 'carry' */
export function drawLayer(c,scene,t,pass='all',{content=true}={}){
  const tone=toneAt(t),shot=shotAt(scene,t);shot.def=SHOTS[shot.id];
  if(pass!=='carry'){paintBackground(c,tone.vig,tone.wash);header(c,scene,shot,t)}
  if(content){c.save();if(scene.kind==='beat'){c.beginPath();c.rect(56,128,1808,770);c.clip()}else clipCard(c);
    const k=makeK(c,scene,shot,t,pass);
    if(shot.def&&(pass!=='carry'||shot.def.carry))shot.def.draw(c,t-shot.t0,k);
    else if(!shot.def){c.fillStyle='#fff';c.font='36px FilmMed';c.fillText('TODO '+shot.id,120,200)}
    c.restore()}}

const layerA=createCanvas(W,H),layerB=createCanvas(W,H);const frozen=new Map();
const IRIS_COL={1:P.cyan,2:P.violet,3:P.amber,4:P.muted};
const KIND={ActI:'iris',B1:'iris',B2:'push',ActII:'iris',B3:'iris',B4:'zoom',B5:'match',B6:'push',ActIII:'iris',B7:'iris',B7b:'zoom',B8:'push',B9:'pullback',B9b:'push',ActIV:'iris',B10:'iris',B11:'zoom',B12:'push',B13:'zoom',End:'slow'};
export const transitionKind=id=>KIND[id];
export function transitionAt(t){const i=SCENES.findIndex(s=>t>=s.t0&&t<s.t1);if(i<=0)return null;const s=SCENES[i];if(t>=s.t0+s.xf)return null;return {from:SCENES[i-1],to:s,p:cubic((t-s.t0)/s.xf),kind:KIND[s.id]}}

export function frameAt(canvas,t){
  const c=canvas.getContext('2d');const tr=transitionAt(t);
  if(!tr){drawLayer(c,sceneAt(t),t,'all')}
  else{
    const {from,to,p,kind}=tr;
    const A=layerA.getContext('2d');if(frozen.get('id')!==from.id){drawLayer(A,from,from.t1-1/FPS,'rest');frozen.set('id',from.id)}
    const B=layerB.getContext('2d');drawLayer(B,to,t,'rest');
    c.drawImage(layerA,0,0);
    c.save();clipCard(c);
    if(kind==='iris'){const r=1150*p;c.save();c.beginPath();c.arc(960,520,Math.max(.01,r),0,Math.PI*2);c.clip();c.drawImage(layerB,0,0);c.restore();
      const a=ACT_OF[to.id];const col=IRIS_COL[a]||P.cyan;c.save();c.strokeStyle=rgba(col,(1-p)*(a===4?.6:.9));c.lineWidth=5;if(a!==4){c.shadowColor=col;c.shadowBlur=24}c.beginPath();c.arc(960,520,Math.max(.01,r),0,Math.PI*2);c.stroke();c.restore()}
    else if(kind==='push'){c.save();c.translate(-240*p,0);c.drawImage(layerA,0,0);c.restore();c.save();c.globalAlpha=p;c.translate(240*(1-p),0);c.drawImage(layerB,0,0);c.restore()}
    else if(kind==='zoom'){c.save();c.translate(960,520);c.scale(1+.06*p,1+.06*p);c.translate(-960,-520);c.drawImage(layerA,0,0);c.restore();c.save();c.globalAlpha=p;c.translate(960,520);const s=.94+.06*p;c.scale(s,s);c.translate(-960,-520);c.drawImage(layerB,0,0);c.restore()}
    else{c.save();c.globalAlpha=p;c.drawImage(layerB,0,0);c.restore()}
    c.restore();
    drawLayer(c,to,t,'carry')}
  drawCaption(c,t);progress(c,t);
  const sc=sceneAt(t);if(sc.id==='End'){const f=smoothP(297.6,298.4,t);if(f>0){c.fillStyle=`rgba(0,0,0,${f})`;c.fillRect(0,0,W,H)}}
  return canvas}

// ---------------- outputs ----------------
const OUT=path.join(ROOT,'outputs');
const jpg=(canvas,file)=>{fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,canvas.toBuffer('image/jpeg',90));return file};
export function storyJSON(){return {language:'en',audio:false,fps:FPS,duration_seconds:DURATION,scenes:SCENES.map(s=>({id:s.id,kind:s.kind,start:s.t0,end:s.t1,shots:s.shots.map(h=>({id:h.id,start:h.t0,end:h.t1,tag:(SHOTS[h.id]||{}).tag||null}))})),captions:TIMELINE.captions}}
const X264=['-an','-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p','-c:v','libx264','-preset','slow','-crf','18','-tune','animation','-g','90','-x264-params','aq-mode=3','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv','-threads','1'];
export async function renderPart(part,parts,{crf=18,g=90}={}){
  fs.mkdirSync(path.join(OUT,'parts'),{recursive:true});
  const f0=Math.floor(FRAMES*part/parts),f1=Math.floor(FRAMES*(part+1)/parts),tmp=path.join(OUT,'parts',`part-${part}.tmp.mp4`);
  const args=['-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',`${W}x${H}`,'-r',String(FPS),'-i','pipe:0',...X264.map((a,i,arr)=>arr[i-1]==='-crf'?String(crf):arr[i-1]==='-g'?String(g):a),tmp];
  const ff=spawn('ffmpeg',args,{stdio:['pipe','inherit','inherit']});const done=once(ff,'exit');const canvas=createCanvas(W,H);const t0=Date.now();
  for(let n=0;n<f1-f0;n++){frameAt(canvas,(f0+n)/FPS);if(!ff.stdin.write(canvas.data()))await once(ff.stdin,'drain');if((n+1)%100===0)console.log(`part ${part}: ${n+1}/${f1-f0} ${((Date.now()-t0)/(n+1)).toFixed(0)} ms/frame`)}
  ff.stdin.end();const [code]=await done;if(code)throw Error('ffmpeg failed');
  const file=path.join(OUT,'parts',`part-${part}.mp4`);fs.renameSync(tmp,file);
  const info={k:part,parts,f0,f1,frames:f1-f0,crf,g,ms_per_frame:(Date.now()-t0)/(f1-f0),wall_s:(Date.now()-t0)/1000};fs.writeFileSync(path.join(OUT,'parts',`part-${part}.json`),JSON.stringify(info));console.log(JSON.stringify(info))}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const cmd=process.argv[2],canvas=createCanvas(W,H);
  if(cmd==='info')console.log(JSON.stringify({scenes:SCENES.length,shots:SCENES.reduce((a,s)=>a+s.shots.length,0),duration:DURATION,frames:FRAMES,defined:Object.keys(SHOTS).length}));
  else if(cmd==='frame'){frameAt(canvas,+process.argv[3]);jpg(canvas,process.argv[4])}
  else if(cmd==='shot'){const id=process.argv[3];const sh=SCENES.flatMap(s=>s.shots).find(s=>s.id===id);if(!sh)throw Error('no shot '+id);
    for(const u of process.argv.slice(4).map(Number)){frameAt(canvas,sh.t0+u);console.log(jpg(canvas,path.join(OUT,'stills',`${id}-${u}.jpg`)))}}
  else if(cmd==='stills'){const ids=process.argv.slice(3);for(const s of SCENES)for(const sh of s.shots){if(ids.length&&!ids.some(i=>sh.id===i||sh.id.startsWith(i+'.')||s.id===i))continue;const d=sh.t1-sh.t0;
    [[.3,'a'],[d/2,'b'],[d-.3,'c']].forEach(([u,n])=>{frameAt(canvas,sh.t0+Math.min(u,d-.034));jpg(canvas,path.join(OUT,'stills',`${sh.id}-${n}.jpg`))})}console.log('stills done')}
  else if(cmd==='render')await renderPart(+process.argv[3],+process.argv[4]);
  else if(cmd==='srt'){fs.mkdirSync(OUT,{recursive:true});fs.writeFileSync(path.join(OUT,'captions-en.srt'),toSrt(canvas.getContext('2d')));fs.writeFileSync(path.join(OUT,'story.json'),JSON.stringify(storyJSON(),null,1)+'\n');console.log('srt + story.json written')}
  else throw Error('usage: info|frame t out|shot id us..|stills [ids]|render k parts|srt')}
