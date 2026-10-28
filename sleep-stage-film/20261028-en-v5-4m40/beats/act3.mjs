import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,mixCol,T,poly,dot,rect,typed,seg,measure,eeg,wavePts} from '../lib.mjs';
import {HYPNO,matchSet,perm,SEED_POOLED,SEEDS} from '../shared.mjs';
import {NightStrip,tileX,stageColor} from '../components/strip.mjs';
import {Roman,Pill,EegFrame,Bracket} from '../components/misc.mjs';
import {surface,bevel,glowRect,glowCircle} from '../light.mjs';
import {fact,factRaw} from '../facts.mjs';
import {NumberCard,NumText,fmtNum,Stamp,Wall} from '../components/cards.mjs';
import {Person} from '../components/people.mjs';
import {Spectrogram} from '../components/spec.mjs';
import {shakeDy} from '../motion.mjs';
const S={};const E=(...ids)=>ids.map(id=>({id,in:0,out:99}));
const PINK='#FF8FA3',GRN='#7EE0A1',GREY='#3A4A62';
const ROMAN3=(c,us)=>Roman(c,'III',480,513,seg(us,.5,.8,x=>x),{col:P.amber});
S['ActIII']={tag:null,elements:E('roman','name'),draw(c,us,k){k.rec('ActCard',{el:'roman'});ROMAN3(c,us);
  const nm='The nights that failed';T(c,typed(nm,(us-1.2)/(nm.length*.04)),800,534,{size:64,weight:'bold'})}};
// ---- helpers
const NB={SC4021:'comparison.runs.base.selected_nights.SC4021.accuracy',SC4062:'comparison.runs.base.selected_nights.SC4062.accuracy',SC4142:'comparison.runs.base.selected_nights.SC4142.accuracy'};
const NR=Object.fromEntries(Object.entries(NB).map(([k,v])=>[k,v.replace('.base.','.r1.')]));
const LANES=['SC4021','SC4062','SC4142'];
const cntT=(path)=>Math.round(96*factRaw(path));
const baseSet=id=>matchSet(SEEDS[id],96,cntT(NB[id]));
const r1Set=id=>{const b=[...baseSet(id)],o=perm(SEEDS[id]+7,96).filter(i=>!baseSet(id).has(i)),n=cntT(NR[id]);return new Set([...b,...o].slice(0,n))};
function hatch(c,x,y,w,h,r=2){c.save();c.beginPath();c.roundRect(x,y,w,h,r);c.fillStyle=GREY;c.fill();c.clip();c.strokeStyle='rgba(147,163,184,.35)';c.lineWidth=1.2;for(let i=-h;i<w;i+=5){c.beginPath();c.moveTo(x+i,y+h);c.lineTo(x+i+h,y);c.stroke()}c.restore()}
/** expert row / model row, tiles 0..95 over [x,x+w] */
function Rows(c,o){const {x=104,w=1712,y,h=44,gap=96,match,appear=()=>1,tickA=()=>0,tickCol=()=>PINK,alpha=1,labels=true,hide=null,tick=true}=o;const pw=w/96,tw=pw-3;c.save();c.globalAlpha*=alpha;
  for(let i=0;i<96;i++){const a=appear(i);if(a<=0)continue;const px=x+i*pw,col=STAGE_COL[HYPNO[i]],sc=lerp(.6,1,outBack(a));c.save();c.globalAlpha*=clamp(a*2.2);c.translate(px+tw/2,0);c.scale(sc,1);c.translate(-px-tw/2,0);
    bevel(c,px,y,tw,h,col,{r:3});
    if(match.has(i))bevel(c,px,y+gap,tw,h,col,{r:3});else hatch(c,px,y+gap,tw,h,3);
    if(tick){const ta=tickA(i);if(ta>0){c.globalAlpha=clamp(ta);const m=match.has(i);c.fillStyle=tickCol(i,m);c.fillRect(px+tw/2-2,y+h+8,4,gap-h-16)}}
    c.restore()}
  c.restore()}
const lane=(c,o)=>{const {y,id,mset,appear=1,alpha=1,numText=null,numA=0,numCol=P.ink,sub=null,tickA=null,tickCol=null}=o;const x=420,w=1180,pw=w/96,tw=pw-2,h=26;
  c.save();c.globalAlpha*=alpha;T(c,id,104,y+h+22,{size:28,weight:'med',color:P.muted});
  for(let i=0;i<96;i++){const a=typeof appear==='function'?appear(i):appear;if(a<=0)continue;const px=x+i*pw;c.save();c.globalAlpha*=clamp(a*2);bevel(c,px,y,tw,h,STAGE_COL[HYPNO[i]],{r:2});
    if(mset.has(i))bevel(c,px,y+h+14,tw,h,STAGE_COL[HYPNO[i]],{r:2});else hatch(c,px,y+h+14,tw,h,2);
    if(tickA){const ta=tickA(i);if(ta>0){c.globalAlpha=clamp(ta);c.fillStyle=tickCol(i);c.fillRect(px+tw/2-1.5,y+h+2,3,12)}}c.restore()}
  if(numText!=null&&numA>0)NumText(c,numText,1816,y+h+20,{size:48,weight:'bold',color:numCol,align:'right',alpha:numA});
  if(sub&&numA>0)T(c,sub,1816,y+h+58,{size:24,color:P.muted,align:'right',alpha:numA});
  c.restore()};
// ---- B7
const pooled=matchSet(SEED_POOLED,96,cntT('test.base.pooled_accuracy.point'));
S['B7.S1']={tag:'MIX',elements:E('rows','labels'),
 camera:(us,ub)=>{const pinks=[...Array(96).keys()].filter(i=>!pooled.has(i)).slice(0,6).map(i=>.4+i*.029);return {x:0,y:shakeDy(us,pinks,{amp:1.4}),zoom:1+.035*smooth(us/3.5)}},
 draw(c,us,k){const ta=i=>(us-(.4+i*.029+.15))/.15;fact('test.base.pooled_accuracy.point',{tiles:96});
  Rows(c,{y:400,gap:130,match:pooled,appear:i=>(us-i*.004)/.25,tickA:ta});
  const la=smooth((us-.4)/.4);T(c,'Expert',104,370,{size:30,weight:'med',color:P.muted,alpha:la});T(c,'Model',104,612,{size:30,weight:'med',color:P.muted,alpha:la})}};
const bgRows=(c,a)=>{c.save();c.filter='blur(2px)';Rows(c,{y:400,gap:130,match:pooled,tickA:()=>1,tickCol:(i,m)=>m?GRN:PINK,alpha:a});c.restore()};
S['B7.S2']={tag:'MEAS',elements:E('bgstrip','cardL','cardS','bars','persons'),draw(c,us,k){bgRows(c,.2*(1-smooth((us-.8)/.6))+.18*smooth((us-.8)/.6));
  const cp=cubic((us-.6)/.7);const dx=(1-cp)*-300;
  NumberCard(c,{k,el:'cardL',x:200+dx,y:230,size:'L',label:'Macro-F1',text:fact('test.base.subject_mf1.point',{mul:100}),color:P.ink,alpha:smooth(cp*2),sub:null});
  T(c,`95% CI ${fact('test.base.subject_mf1.ci95',{idx:0,mul:100})}–${fact('test.base.subject_mf1.ci95',{idx:1,mul:100})}`,230+dx,610,{size:28,color:P.muted,alpha:smooth((us-2.2)/.5)});
  // five equal bars
  const bp=smooth((us-1.4)/.8);STAGE_COL.forEach((col,i)=>{const h=150*bp;surface(c,[820+i*60,520-h,44,h],col,{level:'E1',r:5,gradient:.05})});T(c,'5 stages, equal weight',940,570,{size:26,weight:'med',color:P.muted,align:'center',alpha:bp});
  for(let i=0;i<20;i++){const q=clamp((us-2.4-i*.06)/1.2);if(q>0&&q<1)Person(c,{x:lerp(280+(i%10)*60,460,cubic(q)),y:lerp(700+(i>>1&1)*40,430,cubic(q)),s:22,state:'neutral',alpha:Math.sin(Math.PI*q)})}
  const ca=k.cue('B7.c1','Accuracy');const sa=cubic((us-ca)/.4);
  NumberCard(c,{k,el:'cardS',x:1300+(1-sa)*200,y:300,size:'S',label:'Accuracy',text:fact('test.base.pooled_accuracy.point',{mul:100}),color:P.ink,alpha:smooth(sa*3)})}};
const showLanes=(c,us,k,{r1=false,alpha=[1,1,1],tick=false,wave=null,numA=null,counts=null})=>{LANES.forEach((id,j)=>{const y=290+j*170;const bs=baseSet(id),rs=r1Set(id);
  const mset=r1&&!wave?rs:bs;
  lane(c,{y,id,mset,alpha:alpha[j],appear:i=>(us-(.2+i*.003+j*.2))/.25,numText:numA&&numA(j)!=null?numA(j).text:null,numA:numA?numA(j).a:0,numCol:numA?numA(j).col:P.ink,sub:numA?numA(j).sub:null,tickA:wave?i=>wave(j,i):null,tickCol:wave?i=>PINK:null})})};
S['B7.S3']={tag:'MIX',elements:E('lanes','pill','nums'),draw(c,us,k){
  const cues=[k.cue('E1.c2','7.22%'),k.cue('E1.c2','18.60%'),k.cue('E1.c2','19.01%')];
  const pa=smooth((us-.6)/.5);T(c,'One night at a time',104,200,{size:30,weight:'med',color:P.muted,alpha:pa});
  const ids=LANES;showLanes(c,us,k,{numA:j=>({text:fact(NB[ids[j]],{mul:100})+'%',a:smooth((us-cues[j])/.3),col:PINK,sub:cntT(NB[ids[j]])+' of 96'})})}};
S['B7.S4']={tag:'MIX',elements:E('lane','q'),draw(c,us,k){const f=smooth(us/.8);
  showLanes(c,us,k,{alpha:[1,1-f,1-f],numA:j=>({text:fact(NB[LANES[j]],{mul:100})+'%',a:1,col:PINK,sub:cntT(NB[LANES[j]])+' of 96'})});
  const qa=smooth((us-.6)/.4);T(c,'?',1500,255,{size:84,weight:'bold',color:P.amber,align:'center',alpha:qa})}};
// ---- B7b
const band=(c,x,y,w,h,col,a=1)=>{rect(c,x,y,w,h,rgba(col,.14*a),{r:6});poly(c,[[x,y],[x+w,y]],{stroke:rgba(col,.6*a),width:1.5,dash:[8,6]});poly(c,[[x,y+h],[x+w,y+h]],{stroke:rgba(col,.6*a),width:1.5,dash:[8,6]})};
function nightWave(c,x,y,w,amp,bandH,seed){const pts=wavePts(x,y,w,amp,a=>eeg(a,seed,'mixed'),360);poly(c,pts,{stroke:P.cyan,width:2.4});
  if(amp>bandH/2){const out=pts.filter(p=>Math.abs(p[1]-y)>bandH/2);c.save();c.beginPath();c.rect(x,y-1000,w,1000-bandH/2);c.rect(x,y+bandH/2,w,1000);c.clip();poly(c,pts,{stroke:P.amber,width:3.2});c.restore()}}
S['B7b.S1']={tag:'MATH',elements:E('frameA','frameB','ruler'),draw(c,us,k){const a=smooth(us/.6);
  [['Night A',300,55,1],['Night B',560,110,2]].forEach(([n,y,amp,sd],j)=>{surface(c,[300,y-100,960,200],'#0C1A2E',{level:'E1',r:14,alpha:a});
    c.save();c.globalAlpha*=a;nightWave(c,320,y,920,amp*.0+amp,9999,sd+10);T(c,n,320,y-70,{size:26,weight:'med',color:P.muted});Pill(c,{k,x:1140,y:y-90,w:100,h:40,text:'N2',color:STAGE_COL[2],size:24});c.restore()});
  c.save();c.globalAlpha*=smooth((us-1)/.5);for(let i=0;i<=6;i++){const yy=250+i*70;poly(c,[[1380,yy],[1420,yy]],{stroke:P.dim,width:2})}poly(c,[[1400,250],[1400,670]],{stroke:P.dim,width:2});c.restore()}};
S['B7b.S2']={tag:'MATH',elements:E('frames','band','labels'),draw(c,us,k){
  [['Night A',300,55,1],['Night B',560,110,2]].forEach(([n,y,amp,sd],j)=>{surface(c,[300,y-100,960,200],'#0C1A2E',{level:'E1',r:14});band(c,320,y-70,920,140,P.violet);
    nightWave(c,320,y,920,amp,140,sd+10);T(c,n,320,y-84,{size:26,weight:'med',color:P.muted});Pill(c,{k,x:1140,y:y-92,w:100,h:40,text:'N2',color:STAGE_COL[2],size:24})});
  T(c,'range seen in training',1400,230,{size:24,color:P.violet,align:'center'});
  const flip=us>1.8&&us<3.8?Math.floor((us-1.8)/.3)%2:us>=3.8?1:0;T(c,'Model: '+(flip?'N3':'N2'),1260+120,590,{size:34,weight:'bold',color:flip?P.amber:P.ink,align:'left'});T(c,'Model: N2',1380,330,{size:34,weight:'bold',align:'left'})}};
S['B7b.S3']={tag:'MATH',elements:E('frames','bands','labels'),draw(c,us,k){const sp=smooth(us/1.2);
  [['Night A',300,55,1,1],['Night B',560,110,2,2]].forEach(([n,y,amp,sd,m],j)=>{surface(c,[300,y-100,960,200],'#0C1A2E',{level:'E1',r:14});band(c,320,y-lerp(70,70*m*.8,sp*(j)),920,lerp(140,140*m*.8,sp*j),P.violet);
    nightWave(c,320,y,920,amp,lerp(140,140*m*.8,sp*j)*1.0,sd+10);T(c,n,320,y-84,{size:26,weight:'med',color:P.muted});Pill(c,{k,x:1140,y:y-92,w:100,h:40,text:'N2',color:STAGE_COL[2],size:24});
    T(c,'×'+m,1330,y+10,{size:40,weight:'bold',color:P.violet,alpha:sp});T(c,'Model: N2',1420,y+10,{size:30,weight:'bold',alpha:sp})})}};
S['B7b.S4']={tag:'MATH',elements:E('hists','means','label'),draw(c,us,k){
  const hist=(x,col,w,label,peak)=>{const bars=[.2,.3,.45,.7,1,.8,.5,.3].map((v,i)=>v);bars.forEach((v,i)=>{const hh=200*v*smooth((us-.2-i*.05)/.4);const bi=peak?i:7-i;const hv=bars[bi];surface(c,[x+i*34,600-hh*hv/v,28,hh*hv/v],col,{level:'E1',r:3,gradient:.04})});T(c,label,x+136,660,{size:28,weight:'bold',align:'center'})};
  hist(380,STAGE_COL[3],0,'Mostly N3',true);hist(1100,STAGE_COL[0],0,'Mostly Wake',false);
  const m=smooth((us-1.2)/.5);poly(c,[[380+3.4*34,380],[380+3.4*34,600]],{stroke:P.amber,width:3,dash:[8,6],alpha:m});poly(c,[[1100+3.2*34-2*34,380],[1100+1.4*34,600]],{stroke:P.amber,width:3,dash:[8,6],alpha:m});
  T(c,'Mean moves with stage mix',960,800,{size:36,weight:'bold',align:'center',alpha:smooth((us-1.6)/.4)})}};
S['B7b.S5']={tag:null,elements:E('pill'),draw(c,us,k){const p=cubic(us/1.6);const x=lerp(960,104,p),y=lerp(513,148,p),w=lerp(160,150,p),h=lerp(500,48,p);
  c.save();c.globalAlpha*=1-.0;poly(c,[[x,y-h/2*(1-p)],[x,y+h/2*(1-p)]],{stroke:rgba(P.violet,.8*(1-p)),width:2});
  Pill(c,{k,x:lerp(880,104,p),y:lerp(480,148,p),w:lerp(160,110,p),h:lerp(48,48,p),text:'R1',color:P.violet,size:26});c.restore()}};
// ---- B8
S['B8.S1']={tag:'ILLU',elements:E('pill','spec'),draw(c,us,k){Pill(c,{k,x:104,y:148,w:110,h:48,text:'R1',color:P.violet,size:26});
  const sp=cubic((us-.2)/3);Spectrogram(c,{k,el:'spec',x:220,y:240,w:1480,h:440,p:sp,cols:96,rows:43,seed:5});
  const la=smooth((us-2.2)/.4);T(c,'time',960,740,{size:26,weight:'med',color:P.muted,align:'center',alpha:la});T(c,'frequency',200,460,{size:26,weight:'med',color:P.muted,align:'right',alpha:la})}};
const rowCurve=(n,raw,seedv)=>Array.from({length:n},(_,i)=>{const u=i/(n-1);return .5+.28*Math.sin(u*9+seedv)+.12*Math.sin(u*31+seedv*2)});
S['B8.S2']={tag:'ILLU',elements:E('pill','spec','plot','formula'),draw(c,us,k){Pill(c,{k,x:104,y:148,w:110,h:48,text:'R1',color:P.violet,size:26});
  const rep=Math.min(2,Math.floor(us/2.2)),ph=(us%2.2)/2.2,rowV=[.12,.30,.55][rep];
  Spectrogram(c,{k,el:'spec',x:220,y:230,w:1480,h:240,p:1,cols:96,rows:43,seed:5});
  const ry=230+240*(1-rowV);rect(c,220,ry-3,1480,6,rgba('#FFFFFF',.35),{r:2});
  T(c,'Per night, per frequency',960,520,{size:30,weight:'med',color:P.muted,align:'center'});
  const cu=rowCurve(96,0,rep+1),X=i=>220+i*1480/95,mean=.5,sp=.2,norm=smooth((ph-.5)/.4);
  const Y=v=>720-(lerp(v,.5+(v-.5)*(.2/.28)*1,norm)-.5)*300*1.2-lerp(70,0,norm)*0;
  poly(c,cu.map((v,i)=>[X(i),Y(v)]),{stroke:P.cyan,width:3});
  const mY=Y(.5)+0,ma=smooth(ph/.3);poly(c,[[220,720],[1700,720]],{stroke:P.amber,width:2.5,dash:[10,6],alpha:ma});
  rect(c,220,720-.2*300*(1)*.6,1480,.2*300*1.2,rgba(P.amber,.12*smooth((ph-.25)/.3)),{r:6});
  T(c,'mean',230,704,{size:22,color:P.amber,alpha:ma});T(c,'spread',1690,650,{size:22,color:P.amber,align:'right',alpha:smooth((ph-.25)/.3)});
  T(c,'z = (x − μ) / σ',1700,860,{size:30,weight:'med',color:P.ink,align:'right',alpha:smooth((us-.6)/.5)})}};
const cc=(a,b,t)=>Math.round(a+(b-a)*outExpo(clamp(t)));
S['B8.S3']={tag:'MEAS',elements:E('cardL','cardR','arrows'),draw(c,us,k){Pill(c,{k,x:104,y:148,w:110,h:48,text:'R1',color:P.violet,size:26});
  const t=(us-.9)/1.6,sl=cubic(us/.7);
  const mf=cc(factRaw('test.base.subject_mf1.point')*100*100,factRaw('test.r1.subject_mf1.point')*100*100,t)/100,ac=cc(factRaw('test.base.pooled_accuracy.point')*100*100,factRaw('test.r1.pooled_accuracy.point')*100*100,t)/100;
  const f1=t>=1?fact('test.r1.subject_mf1.point',{mul:100}):fmtNum(mf),f2=t>=1?fact('test.r1.pooled_accuracy.point',{mul:100}):fmtNum(ac);
  fact('test.base.subject_mf1.point',{mul:100});fact('test.base.pooled_accuracy.point',{mul:100});
  NumberCard(c,{k,el:'cardL',x:250+(1-sl)*-200,y:240,size:'L',label:'Macro-F1',text:f1,color:P.green,sub:`was ${fact('test.base.subject_mf1.point',{mul:100})}%`,alpha:sl});
  NumberCard(c,{k,el:'cardR',x:1030+(1-sl)*200,y:240,size:'L',label:'Accuracy',text:f2,color:P.green,sub:`was ${fact('test.base.pooled_accuracy.point',{mul:100})}%`,alpha:sl});
  c.save();c.globalAlpha*=smooth((us-.9)/.4);c.strokeStyle=GRN;c.fillStyle=GRN;c.lineWidth=5;c.lineCap='round';for(const x of [510,1290]){c.beginPath();c.moveTo(x,640);c.lineTo(x,690);c.stroke();c.beginPath();c.moveTo(x-16,682);c.lineTo(x,704);c.lineTo(x+16,682);c.fill()}c.restore();
  T(c,`95% CI ${fact('test.base.subject_mf1.ci95',{idx:0,mul:100})}–${fact('test.base.subject_mf1.ci95',{idx:1,mul:100})} → ${fact('test.r1.subject_mf1.ci95',{idx:0,mul:100})}–${fact('test.r1.subject_mf1.ci95',{idx:1,mul:100})}`,510,770,{size:26,color:P.muted,align:'center',alpha:smooth((us-3)/.5)});
  T(c,'Same architecture, retrained',1290,770,{size:28,weight:'med',color:P.muted,align:'center',alpha:smooth((us-3.2)/.5)})}};
const laneR=(c,us,k,{breathe=0})=>{const cs=[k.cue('E2.c3','82.54%'),k.cue('E2.c3','88.68%'),k.cue('E2.c3','84.87%')];
  LANES.forEach((id,j)=>{const y=290+j*170,bs=baseSet(id),rs=r1Set(id);const t0=.2+j*.3;
    const flipT=i=>t0+i/96*1.4;
    const mset=new Set([...bs]);
    lane(c,{y,id,mset:new Set([...rs].filter(i=>us>=flipT(i)).concat([...bs])),appear:1,tickA:i=>{if(bs.has(i))return 0;return 1},tickCol:i=>(rs.has(i)&&us>=flipT(i))?GRN:PINK,
      numText:(()=>{const a=factRaw(NB[id])*100,b=factRaw(NR[id])*100,t=(us-t0)/1.6;return t>=1?fact(NR[id],{mul:100})+'%':fmtNum(a+(b-a)*outExpo(clamp(t)))+'%'})(),numA:1,numCol:us>t0+1.6?GRN:PINK,sub:(us>t0+1.6?cntT(NR[id]):cntT(NB[id]))+' of 96'});
    if(breathe>0)glowRect(c,420,y-6,1180,92,GRN,{blur:30,alpha:.12*breathe*(.6+.4*Math.sin(us*1.6))},8)})};
S['B8.S4']={tag:'MIX',elements:E('lanes','nums'),draw(c,us,k){T(c,'One night at a time',250,181,{size:30,weight:'med',color:P.muted});Pill(c,{k,x:104,y:148,w:110,h:48,text:'R1',color:P.violet,size:26});laneR(c,us,k,{})}};
S['B8.S5']={tag:'MIX',elements:E('lanes','nums'),camera:us=>({x:0,y:0,zoom:1-.03*smooth((us-3.9)/1.2)}),draw(c,us,k){T(c,'One night at a time',250,181,{size:30,weight:'med',color:P.muted});Pill(c,{k,x:104,y:148,w:110,h:48,text:'R1',color:P.violet,size:26});laneR(c,us+5,k,{breathe:1})}};
// ---- B9
const SC0=12,SC1=84,EXT=92;
const strip9=(c,k,{scan=1,al=1,mode0=null}={})=>NightStrip(c,{k,el:'strip',y:400,appear:1,alpha:al,mode:i=>i<SC0||i>=EXT?'dark':i>=SC1?'unscored':(i<SC0+(SC1-SC0)*scan?'on':'unscored')});
function Eye(c,x,y,s=1,a=1){c.save();c.globalAlpha*=a;c.translate(x,y);c.scale(s,s);c.strokeStyle=P.muted;c.lineWidth=3;c.beginPath();c.moveTo(-26,0);c.quadraticCurveTo(0,-26,26,0);c.quadraticCurveTo(0,26,-26,0);c.stroke();dot(c,0,0,8,P.muted);c.restore()}
S['B9.S1']={tag:'CODE',elements:E('strip','ruler','eye'),camera:us=>({x:0,y:0,zoom:lerp(1.08,1,smooth(us/1.2))}),draw(c,us,k){strip9(c,k,{});
  const x0=tileX(SC0),x1=tileX(EXT),p=cubic((us-.8)/.9);Bracket(c,{k,el:'ruler',x0,x1:lerp(x0,x1,p),y:372,dir:1,p:1,col:P.cyan,label:p>.9?'Per-night yardstick':null,lsize:28,tip:12,width:4});
  Eye(c,(x0+x1)/2,300,1.3,smooth((us-1.6)/.5))}};
S['B9.S2']={tag:'CODE',elements:E('strip','ruler','line','steps'),draw(c,us,k){const scan=clamp((us-.3)/3.6);strip9(c,k,{scan});
  const x0=tileX(SC0),x1=tileX(EXT),sx=tileX(SC0+(SC1-SC0)*scan);if(scan>0&&scan<1)glowCircle(c,sx,432,8,P.cyan,{blur:16,alpha:.8});
  Bracket(c,{k,el:'ruler',x0,x1,y:372,dir:1,p:1,col:P.cyan,label:null,tip:12,width:4});Eye(c,(x0+x1)/2,300,1.3);
  const la=cubic((us-3.4)/.9);if(la>0){c.save();c.strokeStyle=P.amber;c.lineWidth=4;c.lineCap='round';c.beginPath();c.moveTo(tileX(EXT-4),470);c.bezierCurveTo(tileX(EXT-4),560,(x0+x1)/2+200,560,lerp(tileX(EXT-4),(x0+x1)/2,la)*1,520-la*0);c.stroke();c.restore()}
  T(c,'Reads the scored span, no labels',960,630,{size:30,weight:'med',color:P.amber,align:'center',alpha:smooth((us-4)/.5)});
  const s1=smooth((us-4.8)/.4),s2=smooth((us-5.6)/.4);Pill(c,{k,x:560,y:740,w:330,h:50,text:'1  Baseline fails',color:PINK,size:26,alpha:s1});if(s2>0){poly(c,[[900,765],[1010,765]],{stroke:P.muted,width:2,alpha:s2});Pill(c,{k,x:1020,y:740,w:300,h:50,text:'2  R1 chosen',color:P.green,size:26,alpha:s2})}}};
S['B9.S3']={tag:'CODE',elements:E('strip','stamps'),draw(c,us,k){const dim=smooth(us/.8);strip9(c,k,{scan:1,al:1-.3*dim});rect(c,104,360,1712,130,rgba(P.amber,.06*dim),{r:12});
  const c2=k.cue('B9.c2','offline'),c3=k.cue('B9.c2','post-hoc');
  Stamp(c,{k,el:'stamps',text:'OFFLINE',cx:700,cy:640,p:(us-Math.max(.4,c2))/.5,color:P.amber,rot:-5,seed:1});Stamp(c,{k,el:'stamps',text:'POST-HOC',cx:1260,cy:700,p:(us-Math.max(1.6,c3))/.5,color:P.amber,rot:4,seed:2})}};
S['B9.S4']={tag:'CODE',elements:E('strip','stamps'),draw(c,us,k){strip9(c,k,{scan:1,al:.7});rect(c,104,360,1712,130,rgba(P.amber,.06),{r:12});
  Stamp(c,{k,el:'stamps',text:'OFFLINE',cx:700,cy:640,p:1.5,color:P.amber,rot:-5,seed:1});Stamp(c,{k,el:'stamps',text:'POST-HOC',cx:1260,cy:700,p:1.5,color:P.amber,rot:4,seed:2})}};
// ---- B9b
const cardsL=(c,k,{dx=0,a=1,ps=1})=>{NumberCard(c,{k,el:'cardL',x:380-dx,y:230,size:'L',label:'Ours, R1',text:fact('test.r1.pooled_accuracy.point',{mul:100}),color:P.green,alpha:a});
  NumberCard(c,{k,el:'cardR',x:1020+dx,y:230,size:'L',label:'The paper',text:fact('paper.reported_accuracy_pct'),color:P.ref,alpha:a})};
S['B9b.S1']={tag:'MEAS',elements:E('cardL','cardR','wall'),draw(c,us,k){const p=cubic(us/.9),q=cubic((us-.4)/.9);cardsL(c,k,{dx:(1-p)*-0,a:smooth(us/.6)});Wall(c,{k,el:'wall',p:cubic((us-1.6)/1.2),glowA:0})}};
S['B9b.S2']={tag:'MEAS',elements:E('cardL','cardR','wall','lines'),draw(c,us,k){const pc=k.cue('B9b.c1','protocols');cardsL(c,k,{});const g=Math.sin(Math.PI*clamp((us-pc)/1.2));Wall(c,{k,el:'wall',glowA:.5*g});
  T(c,'Split by person',640,640,{size:32,weight:'med',align:'center',alpha:smooth((us-.4)/.4)});T(c,'R1 reads the test night',640,690,{size:28,color:P.muted,align:'center',alpha:smooth((us-1.2)/.4)});
  T(c,fact('paper.split'),1280,640,{size:32,weight:'med',align:'center',alpha:smooth((us-.8)/.4)});
  T(c,'Different protocols',960,850,{size:28,weight:'med',color:P.ref,align:'center',alpha:smooth((us-pc)/.4)})}};
S['B9b.S3']={tag:'MEAS',elements:E('cardL','cardR','wall'),draw(c,us,k){cardsL(c,k,{});Wall(c,{k,el:'wall',glowA:.5*Math.sin(Math.PI*clamp((us-.5)/1.6))});
  T(c,'Split by person',640,640,{size:32,weight:'med',align:'center'});T(c,'R1 reads the test night',640,690,{size:28,color:P.muted,align:'center'});T(c,fact('paper.split'),1280,640,{size:32,weight:'med',align:'center'});T(c,'Different protocols',960,850,{size:28,weight:'med',color:P.ref,align:'center'})}};
S['B9b.S4']={tag:null,elements:E('cardL','cardR','wall'),draw(c,us,k){const p=smooth(us/1.6);cardsL(c,k,{dx:60*p});Wall(c,{k,el:'wall',alpha:1-.8*p})}};
export const act3=S;
