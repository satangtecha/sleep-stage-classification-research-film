import fs from 'node:fs';
import path from 'node:path';
import {spawn,execFileSync} from 'node:child_process';
import {once} from 'node:events';
import {fileURLToPath} from 'node:url';
import {createCanvas,GlobalFonts} from '@napi-rs/canvas';
import {Scene,ThreeDCamera} from '@johnhenry/ecmanim/node';

const ROOT=path.dirname(fileURLToPath(import.meta.url));
const OUTPUT=path.join(ROOT,'outputs','final');
const STORY=JSON.parse(fs.readFileSync(path.join(ROOT,'story.json')));
const FACTS=JSON.parse(fs.readFileSync(path.join(ROOT,'facts.json')));
GlobalFonts.registerFromPath('C:/Windows/Fonts/tahoma.ttf','FilmThai');
if(!GlobalFonts.registerFromPath('C:/Windows/Fonts/tahomabd.ttf','FilmThaiBold'))throw Error('Thai bold font unavailable');
GlobalFonts.registerFromPath('C:/Windows/Fonts/segoeui.ttf','FilmLatin');
GlobalFonts.registerFromPath('C:/Windows/Fonts/seguisb.ttf','FilmBold');
const P={bg:'#081321',cyan:'#51D9E8',amber:'#FFCC73',coral:'#FF8099',violet:'#B2ABFF',white:'#EFF6FF',muted:'#A5B5CA',line:'#294157'};
const W=1920,H=1080,FPS=24;
export const ease=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x)};
const pct=x=>(100*x).toFixed(2);
const lerp=(a,b,t)=>a+(b-a)*t;
export function sceneAt(minute,t){return STORY.chapters[minute-1].scenes[Math.min(2,Math.floor(Math.min(59.999,t)/20))]}
export function textFamily(text,bold=false){return bold?(/[\u0E00-\u0E7F]/.test(text)?'FilmThaiBold':'FilmBold'):'FilmThai'}
function txt(c,s,x,y,size=32,color=P.white,align='left',weight=false){c.save();c.fillStyle=color;c.textAlign=align;c.font=`${size}px ${textFamily(s,weight)}`;c.fillText(s,x,y);c.restore()}
function wrap(c,s,width,size=32){c.font=`${size}px FilmThai`;let lines=[],line='';for(const p of new Intl.Segmenter('th',{granularity:'word'}).segment(s)){if(line&&c.measureText(line+p.segment).width>width){lines.push(line.trim());line=p.segment}else line+=p.segment}if(line)lines.push(line.trim());return lines}
function line(c,pts,color,width=2,alpha=1){c.save();c.strokeStyle=color;c.lineWidth=width;c.globalAlpha*=alpha;c.beginPath();pts.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.stroke();c.restore()}
function poly(c,pts,color,alpha=1,stroke='#FFFFFF20'){c.save();c.globalAlpha*=alpha;c.fillStyle=color;c.strokeStyle=stroke;c.lineWidth=1.2;c.beginPath();pts.forEach((p,i)=>i?c.lineTo(...p):c.moveTo(...p));c.closePath();c.fill();if(stroke)c.stroke();c.restore()}
function shade(hex,k){const n=parseInt(hex.slice(1),16);return '#'+[n>>16,(n>>8)&255,n&255].map(v=>Math.round(Math.min(255,v*k)).toString(16).padStart(2,'0')).join('')}
function cube(pos,size,color){const [x,y,z]=pos,[w,d,h]=size;let v=[[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]].map(p=>[x+p[0]*w/2,y+p[1]*d/2,z+p[2]*h/2]);return [[0,1,2,3],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7],[4,5,6,7]].map((f,i)=>({p:f.map(j=>v[j]),color:shade(color,[.48,.67,.77,.62,.85,1.1][i])}))}
function sphere(pos,r,color,lon=8,lat=5){let faces=[];const p=(a,b)=>[pos[0]+r*Math.sin(a)*Math.cos(b),pos[1]+r*Math.sin(a)*Math.sin(b),pos[2]+r*Math.cos(a)];for(let a=0;a<lat;a++)for(let b=0;b<lon;b++)faces.push({p:[p(a*Math.PI/lat,b*2*Math.PI/lon),p((a+1)*Math.PI/lat,b*2*Math.PI/lon),p((a+1)*Math.PI/lat,(b+1)*2*Math.PI/lon),p(a*Math.PI/lat,(b+1)*2*Math.PI/lon)],color:shade(color,.65+.3*a/lat+.25*b/lon)});return faces}
class World {
  constructor(c,t){this.c=c;this.faces=[];this.paths=[];this.labels=[];this.camera=new ThreeDCamera({pixelWidth:W,pixelHeight:H,frameHeight:8.8,frameWidth:15.644,frameCenter:[0,0,.65],phi:1.04,theta:-1.32+.11*Math.sin(t/7),zoom:1,focalDistance:24})}
  cub(p,s,col){this.faces.push(...cube(p,s,col));return this}
  ball(p,r,col,detail=6){this.faces.push(...sphere(p,r,col,detail,4));return this}
  wire(p,col=P.cyan,width=2,alpha=1){this.paths.push({p,col,width,alpha});return this}
  label(s,p,size=29,col=P.white){this.labels.push({s,p,size,col});return this}
  floor(){for(let i=-6;i<=6;i++)this.wire([[i,-3,0],[i,3,0]],P.line,1,.6);for(let j=-3;j<=3;j++)this.wire([[-6,j,0],[6,j,0]],P.line,1,.6);for(const p of this.paths)p.behind=true}
  draw(){for(const p of this.paths.filter(p=>p.behind))line(this.c,p.p.map(p=>this.camera.toPixel(p)),p.col,p.width,p.alpha);this.faces.sort((a,b)=>{const avg=p=>p.reduce((v,x)=>v+this.camera.projectionDepth(x),0)/p.length;return avg(a.p)-avg(b.p)});for(const f of this.faces)poly(this.c,f.p.map(p=>this.camera.toPixel(p)),f.color,f.alpha??1);for(const p of this.paths.filter(p=>!p.behind))line(this.c,p.p.map(p=>this.camera.toPixel(p)),p.col,p.width,p.alpha);for(const l of this.labels){const [x,y]=this.camera.toPixel(l.p);txt(this.c,l.s,x,y,l.size,l.col,'center')}}
}
function person(world,x,y,col,scale=1){world.cub([x,y,.52*scale],[.35*scale,.24*scale,.75*scale],col);world.ball([x,y,1.13*scale],.18*scale,col,6);world.cub([x-.1*scale,y,.1*scale],[.10*scale,.22*scale,.3*scale],col);world.cub([x+.1*scale,y,.1*scale],[.10*scale,.22*scale,.3*scale],col)}
function waveform(world,pos,w=7,h=.4,t=0,col=P.cyan){const p=[];for(let i=0;i<=180;i++){let a=i/180,pulse=Math.sin(a*48+t)*.38+Math.sin(a*121+t*.4)*.2+Math.sin(a*12)*.15;p.push([pos[0]+a*w,pos[1],pos[2]+h*pulse])}world.wire(p,col,3)}
function bars(world,values,names,colors,t,zscale=3.0){values.forEach((v,i)=>{const x=(i-(values.length-1)/2)*2.5,hh=Math.max(.03,v*zscale*ease(t/2));world.cub([x,0,hh/2],[1.1,1,hh],colors[i]);world.label(names[i],[x,-.8,-.15],30);world.label(pct(v)+'%',[x,0,hh+.35],39,colors[i])})}
function sceneVisual(c,s,u){const w=new World(c,u);w.floor();const intro=ease(u/1.7);c.save();c.globalAlpha=intro;
  switch(s.visual){
    case 'sleep':{
      w.cub([-.8,0,.32],[4.8,2.1,.45],'#344B76').cub([-.8,0,.6],[4.55,1.9,.16],'#8C9FD2');w.cub([-.1,0,.85],[2.8,1.1,.36],P.violet).ball([-2.35,0,.92],.39,'#DCBDB4',9);w.cub([3.4,.5,1.8],[1.9,.14,1.65],'#365578');w.cub([3.4,.40,1.82],[1.65,.06,1.38],'#081B29');waveform(w,[2.65,.32,1.83],1.5,.6,u*.8);w.wire([[-2.45,0,1.25],[-2.7,1,1.75],[2.4,1,1.9]],P.cyan,2);w.label('EEG Fpz-Cz',[-1,1.1,1.8],34,P.cyan);break}
    case 'scope':{
      w.cub([-3,0,1.1],[2,.4,1.6],P.cyan).label('log-spectrogram',[-3,-.8,.1],30);w.cub([0,0,1.1],[2,.7,1.6],P.violet).label('CNN + BiGRU',[0,-.8,.1],30);w.cub([3,0,1.1],[2,.4,1.6],P.amber).label('5 sleep stages',[3,-.8,.1],30);w.wire([[-2,0,1.1],[-1,0,1.1]],P.white,4).wire([[1,0,1.1],[2,0,1.1]],P.white,4);txt(c,'เส้นทางเดิม: SST / contrastive / GRU',W/2,782,31,P.muted,'center');break}
    case 'cohort':{
      for(let i=0;i<20;i++)person(w,(i%10-4.5)*1.05,Math.floor(i/10)*1.75-.9,i%2?P.cyan:P.violet,.7);txt(c,'20 คน',415,337,76,P.cyan,'center',true);txt(c,'39 คืน',960,337,76,P.violet,'center',true);txt(c,'42,307 epochs',1510,337,67,P.amber,'center',true);break}
    case 'spectrogram':{
      waveform(w,[-5,-.7,2.2],3.9,.8,u*.4);w.label('30-second EEG',[-3,-1.2,1.5],30);const cols=24,rows=16;for(let x=0;x<cols;x++)for(let y=0;y<rows;y++){let v=Math.sin(x*.4+y*.3)*.2+Math.exp(-y*.35)*(.5+.5*Math.sin(x*.8+u*.06));const color=v>.45?P.amber:v>.15?P.coral:v>0?P.violet:'#263D66';w.cub([.4+x*.18,.18,y*.145+.25],[.17,.075,.136],color)}w.label('STFT / log power',[2.5,-.9,.1],33,P.cyan);w.wire([[-.8,-.4,1.1],[.1,-.4,1.1]],P.white,3);break}
    case 'network':{
      for(let i=0;i<4;i++)w.cub([-4+i*.23,0,1.2],[.12,1.6,1.7],i%2?P.cyan:P.violet);w.label('CNN features',[-3.7,-1.2,-.05],31);for(let i=0;i<6;i++){const x=-1.8+i*.64;w.cub([x,0,1.1],[.44,.52,.6],P.violet);if(i<5)w.wire([[x+.22,0,1.1],[x+.43,0,1.1]],P.cyan,4);w.ball([x,0,1.6+.09*Math.sin(u+i)],.07,P.amber)}w.label('BiGRU sequence',[0,-1.2,-.05],31);for(let i=0;i<5;i++){const z=.5+i*.37;w.ball([4,0,z],.14,[P.cyan,P.amber,P.violet,P.coral,P.white][i]);w.wire([[1.7,0,1.1],[4,0,z]],P.line,1.5)}w.label('W / N1 / N2 / N3 / REM',[3.7,-1.2,-.05],27);break}
    case 'split':{
      for(let i=0;i<20;i++){let x,y,col;if(i<16){x=(i%8-3.5)*.68-1.6;y=Math.floor(i/8)*1.2;col=P.cyan}else{x=(i%2)*.65+2.2+(i>=18?1.8:0);y=.4;col=i<18?P.amber:P.coral}person(w,x,y,col,.62)}w.label('train',[-2, -1.1,.1],37,P.cyan).label('validation',[2.5,-1.1,.1],30,P.amber).label('test',[4.35,-1.1,.1],37,P.coral);txt(c,'2 test subjects / fold',960,340,60,P.coral,'center',true);break}
    case 'baseline':bars(w,[FACTS.test.base.subject_mf1.point,FACTS.test.base.pooled_accuracy.point],['subject-mean MF1','pooled accuracy'],[P.cyan,P.amber],u,4.1);break;
    case 'normalization':{
      const blend=ease((u-5)/7);for(let row=0;row<3;row++){const z=.65+row*.68;const mean=[.3,-.15,.55][row],scale=[.4,.8,.25][row];let pts=[];for(let i=0;i<=120;i++){const a=i/120,shape=Math.sin(a*17)*.4+Math.cos(a*33)*.12;pts.push([-4.3+8.6*a,0,z+lerp(mean+shape*scale,shape*.45,blend)])}w.wire(pts,[P.cyan,P.amber,P.violet][row],3);w.label('night '+(row+1),[-5,0,z],27)}txt(c,'x′ = (x − μnight,f) / max(σnight,f, ε)',960,770,42,P.white,'center');break}
    case 'results':bars(w,['base','r1','fullnight'].map(k=>FACTS.test[k].subject_mf1.point),['Base','R1','Full-night'],[P.violet,P.cyan,P.amber],u,4.1);txt(c,'Accuracy: 65.00%      80.99%      79.10%',960,790,37,P.muted,'center');break;
    case 'fullnight':{
      for(let i=0;i<28;i++){w.cub([-5.6+i*.4,0,.25],[.33,.8,.45],P.cyan);if(i>5&&i<23)w.cub([-5.6+i*.4,0,.68],[.3,.7,.22],P.amber)}w.label('ALL complete PSG epochs',[0,.2,1.7],39,P.cyan);w.label('retained train / evaluation epochs',[0,-1.2,.05],33,P.amber);waveform(w,[-5.5,.9,1.1],11,.55,u*.2,P.violet);txt(c,'Stats ทั้งคืน ไม่ใช้ hypnogram เลือกช่วง',960,778,40,P.white,'center');break}
    case 'uncertainty':{
      w.draw();c.restore();const x=v=>660+(v+8)/12*890,y=565;line(c,[[x(-8),y],[x(4),y]],P.line,3);for(let n=-8;n<=4;n+=2){line(c,[[x(n),y-9],[x(n),y+9]],P.muted,2);txt(c,String(n),x(n),y+50,28,P.muted,'center')}line(c,[[x(0),370],[x(0),720]],P.violet,3,.7);line(c,[[x(-7.124246),y],[x(1.215923),y]],P.amber,11);line(c,[[x(-7.124246),y-23],[x(-7.124246),y+23]],P.amber,5);line(c,[[x(1.215923),y-23],[x(1.215923),y+23]],P.amber,5);c.fillStyle=P.cyan;c.beginPath();c.arc(x(-3.021697),y,13,0,Math.PI*2);c.fill();txt(c,'95% CI',500,578,39,P.amber,'center');txt(c,'−7.12 ถึง +1.22 pp',1120,430,59,P.white,'center',true);txt(c,'ช่วงคร่อมศูนย์ ไม่ใช่หลักฐานว่าผลเท่ากัน',1120,733,34,P.muted,'center');return}
    case 'pilots':{
      const vals=[.137064,-.5180,-.04224];for(let i=0;i<3;i++){const x=(i-1)*3.2;w.cub([x,0,.08],[1.2,1,.16],P.line);w.cub([x,0,.35+Math.abs(vals[i])*.6],[1.2,.8,.4+Math.abs(vals[i])*.6],i===0?P.cyan:P.coral);w.label(['logit τ=0.25','head-only','decoder λ=0.10'][i],[x,-.85,-.1],31);w.label((vals[i]>=0?'+':'')+vals[i].toFixed(2)+' pp',[x,0,1.9],49,i===0?P.cyan:P.coral)}txt(c,'เกณฑ์ MF1 gain ≥ +1.00 pp: ไม่มีวิธีผ่าน',960,782,39,P.amber,'center');break}
    case 'audit':{
      for(let i=0;i<78;i++)w.cub([(i%13-6)*.58,(Math.floor(i/13)-2.5)*.54,.22],[.36,.38,.44],i<30?P.cyan:P.amber);txt(c,'30 เคยใช้พัฒนา',540,330,60,P.cyan,'center',true);txt(c,'48 ประวัติยังไม่ชัด',1370,330,60,P.amber,'center',true);txt(c,'ไม่ได้แปลว่า 48 คน “ไม่เคยใช้”',960,780,35,P.white,'center');break}
    case 'gate':{
      w.cub([-3,0,1.05],[2.2,1.1,1.9],P.cyan).label('LOCKED MODEL',[-3,-1.0,-.05],31);w.cub([0,0,1.05],[.3,2.7,2.7],P.amber).label('PROTOCOL GATE',[0,-1.1,-.05],31);w.cub([3.3,0,1.05],[2.2,1.1,1.9],P.violet).label('NEW COHORT',[3.3,-1.0,-.05],31);break}
    case 'close':{
      bars(w,[FACTS.test.base.subject_mf1.point,FACTS.test.r1.subject_mf1.point,FACTS.test.fullnight.subject_mf1.point],['Base','R1','Full-night'],[P.violet,P.cyan,P.amber],u,3.4);txt(c,'Next: independent confirmation',960,790,44,P.white,'center');break}
  }
  w.draw();if(s.visual==='gate')txt(c,'0 certified independent',960,308,58,P.amber,'center',true);c.restore();
}
export function drawFrame(canvas,minute,t){const c=canvas.getContext('2d'),s=sceneAt(minute,t),u=t%20;const g=c.createLinearGradient(0,0,W,H);g.addColorStop(0,'#0D1A2D');g.addColorStop(.65,P.bg);g.addColorStop(1,'#161C3C');c.fillStyle=g;c.fillRect(0,0,W,H);c.fillStyle='#49CFE514';c.beginPath();c.ellipse(1350,540,650,380,-.3,0,Math.PI*2);c.fill();line(c,[[68,245],[1852,245]],P.line,1.5);txt(c,String(minute).padStart(2,'0')+'  '+STORY.chapters[minute-1].title,68,65,26,P.cyan);txt(c,`${Math.floor(((minute-1)*60+t)/60)}:${String(Math.floor(t)%60).padStart(2,'0')} / 5:00`,1852,65,26,P.muted,'right');txt(c,s.heading,68,137,51,P.white,'left',true);txt(c,s.subheading,70,197,32,P.muted);sceneVisual(c,s,u);txt(c,s.disclosure,960,868,23,P.muted,'center');
  const lines=wrap(c,s.narration,1650,30);const pages=[];for(let i=0;i<lines.length;i+=2)pages.push(lines.slice(i,i+2));
  const totalChars=pages.reduce((n,p)=>n+p.join('').length,0),progress=Math.max(0,Math.min(1,(u-.35)/19.1));let seen=0,caption=pages.at(-1);for(const p of pages){seen+=p.join('').length;if(seen>=progress*totalChars){caption=p;break}}
  c.fillStyle='#06101DEC';c.fillRect(68,904,1784,122);caption.forEach((v,i)=>txt(c,v,960,950+i*43,30,P.white,'center'));line(c,[[68,1043],[1852,1043]],P.line,4);line(c,[[68,1043],[68+1784*((minute-1)*60+t)/300,1043]],P.cyan,4);
  const footer=s.visual==='close'?'Sleep-EDF Expanded 1.0.0 / Kemp et al. 2000 / Goldberger et al. 2000 / ODC-By 1.0':'Sleep Stage Research  /  Recorded results, not a new experiment';txt(c,footer,68,1070,17,P.muted);
}
function probe(file){return JSON.parse(execFileSync('ffprobe',['-v','error','-show_entries','format=duration','-of','json',file],{encoding:'utf8'})).format.duration*1}
function exec(args){execFileSync('ffmpeg',['-hide_banner','-loglevel','error',...args],{stdio:'inherit'})}
export async function audioFor(minute){
  const out=path.join(ROOT,'outputs'),tmp=path.join(out,'audio');fs.mkdirSync(tmp,{recursive:true});
  const paths=[],measurements=[];
  for(const s of STORY.chapters[minute-1].scenes){
    const stem=s.audio_stem||s.id,raw=path.join(ROOT,'audio',stem+'.wav'),target=path.join(tmp,stem+'-20s.wav');
    const dur=probe(raw),speed=Math.max(.76,dur/19.1);
    if(speed>1.65)throw Error('Narration too long: '+s.id+' '+dur+'s');
    if(!fs.existsSync(target))exec(['-i',raw,'-af',`atempo=${speed},adelay=250,apad,atrim=duration=20`,'-ar','48000','-ac','1',target]);
    measurements.push({scene:s.id,raw_seconds:dur,speech_speed:speed,slot_seconds:20});paths.push(target);
  }
  const suffix=STORY.chapters[minute-1].scenes.some(s=>s.audio_stem)?'-reviewed':'';
  const dest=path.join(out,`minute-${String(minute).padStart(2,'0')}${suffix}.wav`);
  if(!fs.existsSync(dest)){const input=paths.flatMap(p=>['-i',p]);exec([...input,'-filter_complex','[0:a][1:a][2:a]concat=n=3:v=0:a=1[a]','-map','[a]',dest])}
  fs.writeFileSync(path.join(tmp,`minute-${minute}-timings.json`),JSON.stringify(measurements,null,2));return dest;
}
export async function renderMinute(minute,{seconds=60,variant=''}={}){
  if(!Number.isInteger(minute)||minute<1||minute>5)throw Error('minute must be 1..5');
  if(variant&&variant!=='credited')throw Error('Unknown output variant');
  const out=variant?path.join(OUTPUT,variant):OUTPUT;fs.mkdirSync(path.join(out,'frames'),{recursive:true});
  const target=path.join(out,`minute-${String(minute).padStart(2,'0')}.mp4`);
  if(fs.existsSync(target))throw Error('Refusing overwrite '+target);
  const audio=await audioFor(minute),canvas=createCanvas(W,H);
  const enc=spawn('ffmpeg',['-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgba','-s',`${W}x${H}`,'-r',String(FPS),'-i','pipe:0','-i',audio,'-map','0:v','-map','1:a','-c:v','libx264','-preset','veryfast','-crf','21','-threads','4','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',String(seconds),'-movflags','+faststart',target],{stdio:['pipe','inherit','inherit']});
  const stopped=once(enc,'exit');let frames=0,maxRSS=0;const started=Date.now();
  const scene=new Scene({fps:FPS,frameHandler:async(_m,n,t)=>{
    drawFrame(canvas,minute,Math.max(0,t-1/FPS));
    if(n===1||n===10*FPS||n===30*FPS||n===50*FPS){const file=path.join(out,'frames',`minute-${minute}-${Math.round(t)}s.png`);if(!fs.existsSync(file))fs.writeFileSync(file,canvas.toBuffer('image/png'))}
    if(!enc.stdin.write(canvas.data()))await once(enc.stdin,'drain');
    frames++;maxRSS=Math.max(maxRSS,process.memoryUsage().rss);
    if(n%(FPS*10)===0)console.log(`minute ${minute}: ${Math.round(t)} / ${seconds}s (${frames} frames)`);
  }});
  await scene.wait(seconds);enc.stdin.end();const [code]=await stopped;if(code!==0)throw Error('FFmpeg failed '+code);
  const evidence={minute,frames,fps:FPS,width:W,height:H,duration_seconds:probe(target),render_seconds:(Date.now()-started)/1000,peak_process_rss_mib:maxRSS/2**20,renderer:'ecmanim Scene timeline + ThreeDCamera, custom original low-poly scientific meshes, napi canvas, FFmpeg',training:false,new_inference:false};
  fs.writeFileSync(path.join(out,`minute-${minute}-render.json`),JSON.stringify(evidence,null,2));console.log(JSON.stringify(evidence));return target;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const command=process.argv[2],minute=Number(process.argv[3]||1);
  if(command==='render')await renderMinute(minute,{seconds:Number(process.argv[4]||60),variant:process.argv[5]||''});
  else if(command==='still'){fs.mkdirSync(path.join(OUTPUT,'frames'),{recursive:true});const canvas=createCanvas(W,H);drawFrame(canvas,minute,Number(process.argv[4]||10));const target=path.join(OUTPUT,'frames',`preview-minute-${minute}.png`);fs.writeFileSync(target,canvas.toBuffer('image/png'));console.log(target)}
  else throw Error('Usage: node film.mjs render|still <minute> [seconds|time]');
}
