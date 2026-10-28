// Sections 3-4 (new shots): D2 variables and limits, M1-M5 technique
import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,mixCol,T,poly,dot,rect,arrow,typed,seg,measure,eeg,wavePts,heat} from '../lib.mjs';
import {HYPNO} from '../shared.mjs';
import {NightStrip,Legend,tileX} from '../components/strip.mjs';
import {EegFrame,Pill,Bracket} from '../components/misc.mjs';
import {blockIcon,Connector} from '../components/model.mjs';
import {Spectrogram,Plates,Bar128} from '../components/spec.mjs';
import {PipelineBlock,Slot} from '../components/model.mjs';
import {Stamp,Padlock,RefBadge,NumText} from '../components/cards.mjs';
import {Person,MiniStrip,PeopleGrid,IconChip,foldState,gridPos} from '../components/people.mjs';
import {surface,bevel,glowRect,glowCircle} from '../light.mjs';
import {fact} from '../facts.mjs';
const S={};const E=(...ids)=>ids.map(id=>({id,in:0,out:99}));
const PINK='#FF8FA3',GRN='#7EE0A1',AMB='#FFC46B';

// ================================================================ D2: variables and limits
const VARS=[{t:'EEG signal',s:fact('pipeline.channel'),ph:'EEG signal',col:P.cyan},
            {t:'Stage label',s:'W · N1 · N2 · N3 · REM per 30 s',ph:'stage label',col:P.amber},
            {t:'Person ID',s:'only used to split the data',ph:'person ID',col:P.muted}];
S['D2.S1']={tag:'DATA',elements:E('cards','model','arrows','lock'),draw(c,us,k){
  const cus=VARS.map(v=>k.cue('D2.c1',v.ph)),never=k.cue('D2.c1','never feeds');
  VARS.forEach((v,i)=>{const x=120+i*580,y=250,p=smooth((us-cus[i]+.2)/.45);if(p<=0)return;
    c.save();c.globalAlpha*=p;surface(c,[x,y,520,330],'#10213A',{level:'E2',r:18});
    if(i===0){const pts=wavePts(x+40,y+120,440,36,a=>eeg(a,5,'mixed'),260);poly(c,pts,{stroke:P.cyan,width:2.4})}
    if(i===1){for(let j=0;j<16;j++)bevel(c,x+40+j*27,y+95,24,56,STAGE_COL[HYPNO[(j*5+8)%96]],{r:3})}
    if(i===2){Person(c,{k,el:'cards',x:x+260,y:y+125,s:92,state:'neutral'})}
    T(c,v.t,x+260,y+230,{size:38,weight:'bold',align:'center'});T(c,v.s,x+260,y+276,{size:24,color:P.muted,align:'center'});c.restore()});
  // model bar and arrows
  const ma=smooth((us-cus[1])/.6);
  surface(c,[120,700,1700,90],'#16273F',{level:'E2',r:18,alpha:ma});T(c,'Model',970,758,{size:40,weight:'bold',align:'center',alpha:ma});
  [0,1].forEach(i=>arrow(c,380+i*580,590,380+i*580,690,{col:VARS[i].col,width:5,head:16,p:smooth((us-cus[i]-.5)/.5),alpha:ma}));
  const sp=smooth((us-cus[2]-.4)/.5),nv=smooth((us-never+.2)/.4);
  if(sp>0){arrow(c,1540,590,1540,640,{col:P.muted,width:5,head:0,p:sp,alpha:.9});
    c.save();c.globalAlpha*=nv;c.strokeStyle=PINK;c.lineWidth=9;c.lineCap='round';c.beginPath();c.moveTo(1510,640);c.lineTo(1570,680);c.moveTo(1570,640);c.lineTo(1510,680);c.stroke();c.restore();
    Padlock(c,{k,el:'lock',x:1332,y:598,open:1-nv,alpha:nv,s:.9});
    T(c,'splits folds · never a model input',1540,845,{size:28,weight:'bold',color:'#FF8F9B',align:'center',alpha:nv})}}};
const LIM=[{t:'Healthy adults only',s:'no patients, no disorders',ph:'healthy adults only',ic:'person'},
           {t:'Just 20 people',s:'one public dataset',ph:'just 20 people',ic:'people'},
           {t:'Human-scored labels',s:'not perfect ground truth',ph:'human-scored labels',ic:'pencil'},
           {t:'One channel',s:'other channels unused',ph:'one channel',ic:'wave'}];
S['D2.S2']={tag:'DATA',elements:E('cards','banner'),draw(c,us,k){
  LIM.forEach((l,i)=>{const x=104+i*434,y=250,w=410,h=300,p=smooth((us-k.cue('D2.c2',l.ph)+.15)/.45);if(p<=0)return;
    c.save();c.globalAlpha*=p;surface(c,[x,y,w,h],'#10213A',{level:'E2',r:18});c.translate(0,lerp(14,0,p));
    const cx=x+w/2;
    if(l.ic==='person')Person(c,{k,el:'cards',x:cx,y:y+120,s:84,state:'neutral'});
    if(l.ic==='people')for(let j=0;j<10;j++)Person(c,{x:cx-100+(j%5)*50,y:y+88+(j>>2)*0+(j>=5?50:0),s:28,state:'neutral'});
    if(l.ic==='pencil'){c.save();c.translate(cx,y+110);c.rotate(-Math.PI/4);c.fillStyle=P.ink;c.beginPath();c.roundRect(-9,-52,18,84,3);c.fill();c.fillStyle=AMB;c.beginPath();c.moveTo(-9,32);c.lineTo(9,32);c.lineTo(0,58);c.closePath();c.fill();c.restore()}
    if(l.ic==='wave'){const pts=wavePts(cx-130,y+110,260,30,a=>eeg(a,6,'mixed'),200);poly(c,pts,{stroke:P.cyan,width:2.4})}
    T(c,l.t,cx,y+222,{size:32,weight:'bold',align:'center'});T(c,l.s,cx,y+264,{size:23,color:P.muted,align:'center'});c.restore()});
  const b=smooth((us-k.cue('D2.c2','cannot speak')+.3)/.5);
  if(b>0){c.save();c.globalAlpha*=b;surface(c,[104,650,1712,130],rgba(AMB,.08),{level:'E1',r:18,gradient:0});c.strokeStyle=rgba(AMB,.8);c.lineWidth=3;c.beginPath();c.roundRect(104,650,1712,130,18);c.stroke();c.restore();
    T(c,'This data cannot speak for patients,',960,712,{size:42,weight:'bold',color:AMB,align:'center',alpha:b,rise:8});T(c,'sleep disorders or other recording setups',960,760,{size:30,color:P.ink,align:'center',alpha:smooth((us-k.cue('D2.c2','cannot speak')-.5)/.4)})}}};

// ================================================================ technique: shared pipe bar
const COL=[104,334,564,794],BW=190;
/** two aligned chains: ours (top) and the paper's (below). n = how many of our blocks are visible (0..3, fractional), act = active block, ref = fade of the paper chain */
function pipeBar(c,k,{n=1,act=-1,ref=0,slot=0,hot=-1}){
  const O=[['stft','STFT',0],['cnn','CNN',1],['bigru','BiGRU',3]],Y=146,H=56;
  T(c,'Our chain',1030,Y+36,{size:28,weight:'bold',color:P.cyan,alpha:1});
  O.forEach(([kind,label,col],i)=>{const p=clamp(n-i);if(p<=0)return;const x=COL[col],isA=i===act;
    c.save();c.globalAlpha*=smooth(p*2.5);
    if(isA)glowRect(c,x,Y,BW,H,P.cyan,{blur:18,alpha:.5},14);
    surface(c,[x,Y,BW,H],isA?'#1C3556':'#16273F',{level:'E2',r:14,gradient:.05});
    if(isA){c.strokeStyle=rgba(P.cyan,.9);c.lineWidth=2.2;c.beginPath();c.roundRect(x,Y,BW,H,14);c.stroke()}
    blockIcon(c,kind,x+36,Y+H/2,34);T(c,label,x+70,Y+H/2+9,{size:27,weight:'bold',color:isA?P.ink:P.muted});c.restore();
    if(i>0){const x0=i===1?COL[0]+BW+4:i===2?COL[1]+BW+4:COL[2]+BW+4;const x1=col===3?COL[3]-4:COL[col]-4;
      if(i===2){Connector(c,COL[1]+BW+4,Y+H/2,COL[3]-4,{p:smooth(p*2),col:P.muted,dashed:true,alpha:.8})}
      else Connector(c,x0,Y+H/2,x1,{p:smooth(p*2),col:P.muted})}});
  if(slot>0)Slot(c,{x:COL[2],y:Y,w:BW,h:H,alpha:slot,text:null});
  if(slot>0)T(c,'not used',COL[2]+BW/2,Y+H/2+8,{size:23,weight:'med',color:P.muted,align:'center',alpha:slot});
  // reference chain
  if(ref>0){const R=['SST','CNN','Contrastive','GRU'],Y2=216,H2=42;
    T(c,'Reference paper',1030,Y2+29,{size:24,weight:'med',color:P.ref,alpha:ref});
    R.forEach((r,i)=>{const x=COL[i],h=hot===i;c.save();c.globalAlpha*=ref;
      if(h)glowRect(c,x,Y2,BW,H2,AMB,{blur:16,alpha:.6},12);
      surface(c,[x,Y2,BW,H2],h?'#2A2314':'#111E31',{level:'E1',r:12,gradient:.03});c.strokeStyle=rgba(h?AMB:P.ref,h?.9:.4);c.lineWidth=h?2.2:1.4;c.beginPath();c.roundRect(x,Y2,BW,H2,12);c.stroke();
      T(c,r,x+BW/2,Y2+H2/2+8,{size:22,weight:'med',color:h?AMB:P.ref,align:'center'});c.restore()})}}

// ---------------------------------------------------------------- M1: STFT
const EX=200,EW=1520;
S['M1.S1']={tag:'ILLU',elements:E('bar','signal','win','spec','labels'),draw(c,us,k){
  const cS=k.cue('M1.c1','slides'),cE=k.cue('M1.c1','over time'),cN=k.cue('M1.c1','129 × 29');
  pipeBar(c,k,{n:smooth(us/.5),act:0});
  const e=smooth(us/.6);const fy=312,fh=140;surface(c,[EX,fy,EW,fh],'#0C1A2E',{level:'E1',r:12,alpha:e});
  const pts=wavePts(EX+12,fy+fh/2,EW-24,36,a=>eeg(a,3,'mixed'),400);poly(c,pts,{stroke:STAGE_COL[2],width:2.4,alpha:e});
  T(c,'one 30 s epoch',EX+EW/2,fy+fh+34,{size:26,weight:'med',color:P.muted,align:'center',alpha:e});
  const sp=cubic((us-cS)/Math.max(1.2,cE-cS));
  const wu=(EW-24)/30,idx=Math.min(28,Math.floor(sp*29)),wx=EX+12+wu*idx,ww=wu*2;
  if(us>cS-.4)rect(c,wx,fy+6,ww,fh-12,rgba(P.cyan,.20),{stroke:P.cyan,sw:2.4,r:4,alpha:smooth((us-cS+.4)/.3)});
  T(c,'2 s Hamming window · 1 s hop',EX+EW/2,fy-14,{size:26,weight:'med',color:P.cyan,align:'center',alpha:smooth((us-.9)/.4)});
  const sx=360,sy=560,sw=1200,sh=260;Spectrogram(c,{k,el:'spec',x:sx,y:sy,w:sw,h:sh,p:sp,alpha:smooth((us-cS+.4)/.3)});
  if(sp>0&&sp<1){const colx=sx+(idx+.5)*sw/29;poly(c,[[wx+ww/2,fy+fh-6],[colx,sy-4]],{stroke:rgba(P.cyan,.55),width:2,dash:[6,6]})}
  const la=smooth((us-cN+.3)/.4);
  T(c,'frequency · '+fact('pipeline.shape',{idx:0})+' bins',sx-22,sy+sh/2+9,{size:26,weight:'med',color:P.muted,align:'right',alpha:la});
  T(c,'time · '+fact('pipeline.shape',{idx:1})+' frames',sx+sw/2,sy+sh+48,{size:26,weight:'med',color:P.muted,align:'center',alpha:la})}};
// SST look-alike: thin bright ridge
const ridge=(c,x,y,w,h)=>{const cols=44,rows=44,cw=w/cols,rh=h/rows;for(let i=0;i<cols;i++){const u=i/(cols-1),r=.30+.08*Math.sin(u*7)+.12*Math.exp(-((u-.62)**2)/.01),r2=.62+.05*Math.sin(u*5+1);
  for(let j=0;j<rows;j++){const v=j/(rows-1);const val=Math.min(1,.06+.95*Math.exp(-((v-r)**2)/.0009)+.35*Math.exp(-((v-r2)**2)/.0007)+.10*Math.exp(-v*6));
    c.fillStyle=heat(val);c.fillRect(x+i*cw,y+h-(j+1)*rh,cw+.6,rh+.6)}}};
S['M1.S2']={tag:'CONCEPT',elements:E('bar','left','right','chips','note'),draw(c,us,k){
  const cSST=k.cue('M1.c2','synchrosqueezed'),cWe=k.cue('M1.c2','We chose STFT'),cDr=k.cue('M1.c2','draw, compute'),cNv=k.cue('M1.c2','never compared');
  const refA=smooth((us-cSST+.5)/.5);pipeBar(c,k,{n:1,act:0,ref:refA});
  const ra=smooth((us-cSST+.2)/.5),la=smooth((us-cWe+.4)/.5);
  // right: SST (paper)
  c.save();c.globalAlpha*=.55+.0*ra;surface(c,[1040,300,740,430],'#0E1C30',{level:'E2',r:18,alpha:ra});c.restore();
  if(ra>0){c.save();c.globalAlpha*=ra;T(c,'SST · the paper',1410,350,{size:30,weight:'bold',color:P.ref,align:'center'});c.beginPath();c.roundRect(1130,384,560,280,10);c.clip();ridge(c,1130,384,560,280);c.restore();
    T(c,'synchrosqueezed transform',1410,704,{size:23,color:P.muted,align:'center',alpha:ra})}
  // left: STFT (ours)
  surface(c,[140,300,740,430],'#0E1C30',{level:'E2',r:18,alpha:smooth(us/.4)});
  if(la>0)glowRect(c,140,300,740,430,P.green,{blur:26,alpha:.28*la},18);
  T(c,'STFT · ours',510,350,{size:30,weight:'bold',color:P.green,align:'center',alpha:smooth(us/.4)});
  Spectrogram(c,{k,el:'left',x:230,y:384,w:560,h:280,p:1,alpha:smooth(us/.4)});
  T(c,'plain window, plain Fourier transform',510,704,{size:23,color:P.muted,align:'center',alpha:smooth(us/.4)});
  ['drawn','computed','checked'].forEach((s,i)=>Pill(c,{k,el:'chips',x:190+i*230,y:760,w:200,h:46,text:s+' by hand',color:P.green,size:22,alpha:smooth((us-cDr-i*.35+.1)/.35)}));
  const nv=smooth((us-cNv+.4)/.4);
  if(nv>0){c.save();c.globalAlpha*=nv;surface(c,[760,790,400,64],rgba(AMB,.1),{level:'E1',r:32,gradient:0});c.strokeStyle=rgba(AMB,.9);c.lineWidth=2.5;c.beginPath();c.roundRect(760,790,400,64,32);c.stroke();T(c,'never compared',960,833,{size:32,weight:'bold',color:AMB,align:'center'});c.restore()}}};

// ---------------------------------------------------------------- M2: CNN
S['M2.S1']={tag:'ILLU',elements:E('bar','spec','plates','vec','notes'),draw(c,us,k){
  const c3=k.cue('M2.c1','three blocks'),c32=k.cue('M2.c1','32'),c64=k.cue('M2.c1','64'),cSq=k.cue('M2.c1','squeeze'),cN=k.cue('M2.c1','128 numbers'),cL=k.cue('M2.c1','sees one epoch');
  pipeBar(c,k,{n:1+smooth((us-.1)/.5),act:1,ref:1});
  Spectrogram(c,{k,el:'spec',x:150,y:470,w:250,h:190,p:1,alpha:smooth((us-.1)/.4)});
  T(c,'one epoch',275,712,{size:24,weight:'med',color:P.muted,align:'center',alpha:smooth((us-.3)/.4)});
  const pa=smooth((us-.5)/.5);if(pa>0)arrow(c,420,565,520,565,{col:P.muted,width:3,head:12,alpha:pa});
  Plates(c,{k,el:'plates',cx:880,cy:560,t:us,p:[(us-c32+.2)/.5,(us-c64+.2)/.5,(us-c64-.5)/.5],squeeze:smooth((us-cSq)/1.4)});
  T(c,'Conv 3×3 · BatchNorm · ReLU · MaxPool',880,792,{size:25,weight:'med',color:P.muted,align:'center',alpha:smooth((us-c3+.2)/.4)});
  const bp=smooth((us-cSq-.4)/1.0);Bar128(c,{k,el:'vec',x:1500,y:380,w:44,h:360,seed:1,p:bp});
  if(bp>0)arrow(c,1250,560,1470,560,{col:P.muted,width:3,head:12,alpha:bp});
  T(c,fact('pipeline.embedding_size')+' numbers',1522,780,{size:34,weight:'bold',color:P.cyan,align:'center',alpha:smooth((us-cN+.3)/.4)});
  const lm=smooth((us-cL+.3)/.4);if(lm>0){c.save();c.globalAlpha*=lm;surface(c,[580,826,760,56],rgba(AMB,.1),{level:'E1',r:28,gradient:0});c.strokeStyle=rgba(AMB,.8);c.lineWidth=2;c.beginPath();c.roundRect(580,826,760,56,28);c.stroke();T(c,'Limit: it sees one epoch at a time',960,864,{size:28,weight:'bold',color:AMB,align:'center'});c.restore()}}};

// ---------------------------------------------------------------- M3: BiGRU
const BX=200,BWd=1520,BPW=BWd/20;
S['M3.S1']={tag:'ILLU',elements:E('bar','bars','bracket','arrows','out'),draw(c,us,k){
  const cB=k.cue('M3.c1','20 neighbouring'),cL=k.cue('M3.c1','two layers'),cF=k.cue('M3.c1','forwards'),cBk=k.cue('M3.c1','backwards'),cS=k.cue('M3.c1','sequence');
  pipeBar(c,k,{n:2+smooth((us-.1)/.5),act:2,ref:1,slot:smooth((us-.3)/.5)});
  for(let i=0;i<20;i++)Bar128(c,{x:BX+i*BPW+4,y:360,w:BPW-8,h:190,seed:i+3,p:clamp((us-cB+.3-i*.05)/.4),lit:i===10?smooth((us-cS)/.4):0});
  Bracket(c,{k,el:'bracket',x0:BX,x1:BX+BWd,y:322,dir:1,p:cubic((us-cB+.2)/.6),col:P.ink,label:fact('pipeline.window_epochs')+' epochs',lsize:28,labelAbove:true,tip:12,width:3});
  const lp=smooth((us-cL+.2)/.4);if(lp>0)Pill(c,{k,x:1440,y:272,w:280,h:44,text:'2 layers · hidden '+fact('pipeline.gru_hidden_size'),color:P.cyan,size:21,alpha:lp});
  arrow(c,BX+40,598,BX+BWd-40,598,{col:P.cyan,width:5,head:16,p:cubic((us-cF+.2)/1.1)});
  arrow(c,BX+BWd-40,646,BX+40,646,{col:P.cyan,width:5,head:16,p:cubic((us-cBk+.2)/1.1)});
  T(c,'forward',BX+40,578,{size:23,weight:'med',color:P.cyan,alpha:smooth((us-cF)/.3)});T(c,'backward',BX+BWd-40,682,{size:23,weight:'med',color:P.cyan,align:'right',alpha:smooth((us-cBk)/.3)});
  NightStrip(c,{k,el:'out',x:BX,w:BWd,y:706,h:44,range:[38,58],appear:1,mode:'dim',stage:i=>HYPNO[i]});
  const pr=smooth((us-cS+.2)/1.2);for(let i=0;i<20;i++){const q=smooth((us-cS+.2-Math.abs(i-10)*.07)/.3);if(q>0)rect(c,BX+i*BPW+4,770,BPW-8,34,STAGE_COL[HYPNO[38+i]],{r:3,alpha:q})}
  T(c,'a stage for every epoch',960,846,{size:26,weight:'med',color:P.muted,align:'center',alpha:pr})}};
S['M3.S2']={tag:'CONCEPT',elements:E('bar','strip','now','arrows','stamp'),draw(c,us,k){
  const cF=k.cue('M3.c2','future epochs'),cO=k.cue('M3.c2','offline only'),cR=k.cue('M3.c2','never in real time');
  pipeBar(c,k,{n:3,act:2,ref:1,slot:1});
  const n=40,x0=160,w=1600,pw=w/n,y=500,now=18;
  NightStrip(c,{k,el:'strip',x:x0,w,y,h:70,range:[20,20+n],appear:1,mode:i=>i-20<=now?'on':'dim',stage:i=>HYPNO[i]});
  const nx=x0+(now+.5)*pw;glowRect(c,x0+now*pw,y,pw-3,70,P.ink,{blur:16,alpha:.7},3);
  T(c,'this epoch',nx,y-24,{size:26,weight:'med',align:'center'});poly(c,[[nx,y-14],[nx,y-2]],{stroke:P.ink,width:3});
  T(c,'past',x0+now*pw/2,y+108,{size:26,weight:'med',color:P.muted,align:'center'});
  const fa=smooth((us-cF+.3)/.4);
  if(fa>0){rect(c,x0+(now+1)*pw,y-6,(n-now-1)*pw,82,rgba(P.cyan,.10*fa),{r:6,stroke:rgba(P.cyan,.7*fa),sw:2});T(c,'future',x0+(now+1)*pw+(n-now-1)*pw/2,y+108,{size:26,weight:'bold',color:P.cyan,align:'center',alpha:fa});
    c.save();c.globalAlpha*=fa;c.strokeStyle=P.cyan;c.lineWidth=4;c.lineCap='round';c.beginPath();c.moveTo(nx+16,y+142);c.bezierCurveTo(nx+300,y+215,x0+w-300,y+215,x0+w-30,y+142);c.stroke();c.restore();
    T(c,'looks ahead',nx+(x0+w-nx)/2,y+236,{size:25,color:P.cyan,align:'center',alpha:fa})}
  Stamp(c,{k,el:'stamp',text:'OFFLINE ONLY',cx:620,cy:800,p:(us-cO+.2)/.5,color:AMB,rot:-3,seed:11,scale:.85});
  const ra=smooth((us-cR+.2)/.4);if(ra>0){c.save();c.globalAlpha*=ra;const cx=1280,cy=790;c.strokeStyle=P.muted;c.lineWidth=5;c.beginPath();c.arc(cx,cy,42,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(cx,cy);c.lineTo(cx,cy-26);c.moveTo(cx,cy);c.lineTo(cx+18,cy+8);c.stroke();
    c.strokeStyle=PINK;c.lineWidth=7;c.beginPath();c.moveTo(cx-52,cy+52);c.lineTo(cx+52,cy-52);c.stroke();c.restore();T(c,'no real-time use',cx,cy+88,{size:24,weight:'med',color:'#FF8F9B',align:'center',alpha:ra})}}};

// ---------------------------------------------------------------- M4: why no contrastive stage (large side by side)
const CX=[104,320,536,752],RXs=[992,1208,1424,1640],BY=300;
const L4=[['sst','SST'],['cnn','CNN'],['contrastive','Contrastive'],['gru','GRU']];
function b4(c,k,{left=[1,1,1,1],right=[1,1,1],slot=1,leftA=1,glowC=0,slotText=0,heads=1,icons=null}){
  RefBadge(c,{k,el:'badge',alpha:1});poly(c,[[960,150],[960,880]],{stroke:P.line,width:2});
  T(c,'Our study',RXs[0],178,{size:30,weight:'med',color:P.cyan,alpha:smooth(heads)});
  c.save();c.globalAlpha*=leftA;L4.forEach((b,i)=>{if(i<3)Connector(c,CX[i]+176+4,BY+75,CX[i+1]-4,{p:clamp(left[i+1]*2),alpha:left[i+1]>0?1:0});
    PipelineBlock(c,{k,el:'left',x:CX[i],y:BY,kind:b[0],label:b[1],drop:left[i],glowC:i===2?P.amber:null,glowA:i===2?glowC*.6:0})});c.restore();
  const R=[['stft','STFT'],['cnn','CNN'],null,['bigru','BiGRU']];
  R.forEach((b,i)=>{if(!b){Slot(c,{x:RXs[i],y:BY,alpha:slot,text:slotText>0?'no contrastive\nstage':null,tAlpha:slotText});return}
    const j=i===3?2:i,dr=right[j];if(dr<=0)Slot(c,{x:RXs[i],y:BY,alpha:slot});else PipelineBlock(c,{k,el:'right',x:RXs[i],y:BY,kind:b[0],label:b[1],drop:dr});
    if(i>0&&dr>0)Connector(c,RXs[i-1]+180,BY+75,RXs[i]-4,{p:clamp(dr*2),col:P.cyan})});
  if(icons)['pencil','sigma','check'].forEach((n,i)=>IconChip(c,{k,el:'icons',cx:RXs[0]+88+i*216,y:520,icon:n,lit:icons[i],litCol:P.cyan,drop:clamp(icons[i]*3),label:['drawn','derived','checked'][i],labelY:700}))}
S['M4.S1']={tag:'CODE',elements:E('badge','left','right','icons','note'),draw(c,us,k){
  const g0=k.cue('M4.c1','contrastive'),r0=k.cue('M4.c1','reproducing it failed'),a=k.cue('M4.c1','chain'),b=k.cue('M4.c1','check'),d=k.cue('M4.c1','step by step');
  b4(c,k,{left:[0,1,2,3].map(i=>(us-.05-i*.18)/.4),right:[0,1,2].map(i=>(us-.45-i*.2)/.4),slot:smooth((us-.5)/.4),glowC:Math.sin(Math.PI*clamp((us-g0)/1.8)),slotText:smooth((us-g0)/.4),heads:(us-.3)/.3,
    icons:[smooth((us-a)/.3),smooth((us-b)/.3),smooth((us-d)/.3)]});
  const ra=smooth((us-r0)/.4);T(c,'Not reproduced: time and compute limits',CX[0],612,{size:28,weight:'med',color:AMB,alpha:ra});rect(c,CX[2],BY+160,176,8,rgba(AMB,.6*ra),{r:3})}};
S['M4.S2']={tag:'CODE',elements:E('badge','left','right','icons','note'),draw(c,us,k){
  const h0=k.cue('M4.c2','do not claim');b4(c,k,{leftA:.55,slotText:1,icons:[1,1,1]});
  T(c,'Helps? Hurts?  Never compared.',960,810,{size:44,weight:'bold',color:AMB,align:'center',alpha:smooth((us-h0+.5)/.4)})}};

// ---------------------------------------------------------------- M5: leave-persons-out test
S['M5.S1']={tag:'CODE',elements:E('grid','legend','counter'),draw(c,us,k){
  const c16=k.cue('M5.c1','16 people'),cN=k.cue('M5.c1','Nobody appears twice');
  T(c,'Leave-persons-out · 10 folds',960,200,{size:36,weight:'bold',align:'center',alpha:smooth(us/.4)});
  const f=us<c16+.6?0:Math.min(9,Math.floor((us-c16-.6)/.42)),st=i=>foldState(i,f);const testSet=new Set([2*f,2*f+1]);
  PeopleGrid(c,{k,el:'grid',state:us<c16-.2?()=>'neutral':st,glowSet:us<c16?null:testSet,glowA:.55,strips:1,appear:i=>(us-.1-i*.04)/.35});
  const la=smooth((us-c16+.2)/.4);const items=[['16 train',P.blue],['2 choose checkpoint',P.amber],['2 test',P.coral]];let x=420;
  items.forEach(([s,col],i)=>{dot(c,x,790,9,col,la);T(c,s,x+20,798,{size:28,weight:'med',alpha:la});x+=measure(c,s,28,'med')+90});
  const tested=us<c16+.6?0:Math.min(20,2*(f+1)),ca=smooth((us-cN+.6)/.4);
  T(c,`tested once: ${tested} / ${fact('study.participants')}`,1600,798,{size:28,weight:'med',color:P.muted,align:'right',alpha:ca})}};
S['M5.S2']={tag:'CODE',elements:E('persons','gauge','note'),draw(c,us,k){
  const cT=k.cue('M5.c2','two test people'),cS=k.cue('M5.c2','swing');
  T(c,'Leave-persons-out · 10 folds',960,200,{size:36,weight:'bold',align:'center'});
  const a=smooth((us-cT+.3)/.5);
  Person(c,{k,el:'persons',x:760,y:470,s:150,state:'test',glowA:.5*a,alpha:smooth(us/.3),sc:lerp(.9,1,a)});Person(c,{k,el:'persons',x:1010,y:470,s:150,state:'test',glowA:.5*a,alpha:smooth(us/.3),sc:lerp(.9,1,a)});
  T(c,'2 test people per fold',885,640,{size:38,weight:'bold',color:P.coral,align:'center',alpha:a});
  const gp=smooth((us-cS+.3)/.5);if(gp>0){c.save();c.globalAlpha*=gp;const gx=1420,gy=520,r=150;c.strokeStyle=P.line;c.lineWidth=16;c.lineCap='round';c.beginPath();c.arc(gx,gy,r,Math.PI*1.1,Math.PI*1.9);c.stroke();
    const ang=Math.PI*1.5+Math.sin((us-cS)*3.2)*.62*Math.min(1,(us-cS+.3));c.strokeStyle=AMB;c.lineWidth=7;c.beginPath();c.moveTo(gx,gy);c.lineTo(gx+Math.cos(ang)*(r-16),gy+Math.sin(ang)*(r-16));c.stroke();dot(c,gx,gy,12,AMB);
    T(c,'scores swing between folds',gx,gy+90,{size:28,weight:'bold',color:AMB,align:'center'});c.restore()}}};
export const s2=S;
