// Scenes for chapters 0-2: opening, the signal, waves to frequencies.
import {P,STAGE_COL,STAGES,clamp,lerp,smooth,cubic,outExpo,outBack,seg,rgba,shade,heat,T,wrap,typed,fmt,EQ,poly,drawOn,dot,rect,arrow,pill,panel,wavePts,rnd,eeg,axes,World,person,measure} from './lib.mjs';

const fin=(u,a,d=.6)=>seg(u,a,d,smooth);
const TAU=Math.PI*2;
// precomputed illustrative spectrogram values (129 x 29) used by several scenes
export const SPEC=Array.from({length:29},(_,t)=>Array.from({length:129},(_,f)=>{const fr=f/128;const slow=Math.exp(-fr*7)*(.75+.25*Math.sin(t*.55));const spindle=.42*Math.exp(-(((fr-.27)/.035)**2))*(t>9&&t<17?1:.25);const alpha=.25*Math.exp(-(((fr-.2)/.05)**2))*(.5+.5*Math.cos(t*.4));return clamp(.12+slow*.8+spindle+alpha+.05*rnd(t*131+f))}));

export const scenesA=[
// ---------------------------------------------------------------- OPENING
{id:'open',ch:0,tag:'ILLU',dur:11,cap:[[0,'One night of sleep. One EEG channel. One stage label for every 30 seconds.'],[5.5,'This film walks through the math behind every step, then what the evidence does and does not show.']],
draw(c,u){
  const x0=150,x1=1770,y=470,n=900;const pts=wavePts(x0,y,x1-x0,70,a=>eeg(a*18,2)*.9,n);
  const tp=seg(u,.2,2.6,cubic);const drop=seg(u,3.6,2.2,cubic);
  const hyp=[0,0,1,2,2,3,3,2,4,4,2,3,2,2,4,1,2,2,4,4,2,1,0,0];const segs=hyp.length,sw=(x1-x0)/segs;
  // trace fades as it becomes the hypnogram
  drawOn(c,pts,tp,{stroke:P.cyan,width:2.6,alpha:1-drop*.75,glow:10});
  for(let i=1;i<segs;i++){const a=fin(u,2.8+i*.03,.3)*(1-drop);poly(c,[[x0+i*sw,y-120],[x0+i*sw,y+120]],{stroke:P.line,width:1.5,alpha:a})}
  if(drop>0){for(let i=0;i<segs;i++){const st=hyp[i],d=seg(u,3.6+i*.05,1.2,cubic);const ty=600+st*42;const yy=lerp(y-20,ty,d);rect(c,x0+i*sw+2,yy-14,sw-4,28,STAGE_COL[st],{alpha:d,r:5})}
    for(let k=0;k<5;k++)T(c,STAGES[k],x0-24,600+k*42+9,{size:22,color:STAGE_COL[k],align:'right',alpha:seg(u,4.8,.6),weight:'med'})}
  const ta=fin(u,5.2,.9);T(c,'Reading Sleep from One EEG Channel',960,250,{size:70,weight:'bold',align:'center',alpha:ta,rise:18});
  T(c,'The math, the model and the evidence, one step at a time',960,312,{size:32,color:P.muted,align:'center',alpha:fin(u,6,.9),rise:12});
  T(c,'30-second epochs',x0+sw*1.5,820,{size:22,color:P.muted,align:'center',alpha:fin(u,6.5)});
}},
// ---------------------------------------------------------------- CH1 THE SIGNAL
{id:'electrodes',ch:1,tag:'ILLU',dur:12,cap:[[0,'EEG measures a voltage difference between two electrodes on the scalp. It does not read thoughts.'],[6,'Our channel is Fpz minus Cz, recorded in microvolts. One point on the trace is one voltage reading.']],
draw(c,u){
  const w=new World({box:[96,140,900,740],center:[0,0,1.7],phi:1.12,theta:-1.25+.25*Math.sin(u/5),frameHeight:4.6});
  const g=fin(u,0,1.2);w.floor({size:4,alpha:.5});
  w.sphere([0,0,1.7],1.25*outBack(g),'#33507A',{seg:16});w.sphere([-1.22,0,1.6],.22*g,'#2C4870',{seg:8}).sphere([1.22,0,1.6],.22*g,'#2C4870',{seg:8});w.box3([0,-1.3,1.45],[.22,.25,.4],'#3A5C8A',{alpha:g});w.box3([0,0,.35],[.6,.5,.7],'#26405F',{alpha:g});
  const fp=[0,-1.18,2.0],cz=[0,-.05,2.97];const e=fin(u,1.2,.6);
  w.sphere(fp,.13*e,P.cyan,{seg:8}).sphere(cz,.13*e,P.violet,{seg:8});
  w.label([fp[0]+.55,fp[1]-.3,fp[2]+.15],'Fpz',{size:26,color:P.cyan,weight:'bold',alpha:e});w.label([cz[0]+.1,cz[1],cz[2]+.45],'Cz',{size:26,color:P.violet,weight:'bold',alpha:e});
  w.draw(c);
  // three traces on the right
  const X0=1040,X1=1770,traces=[[ 'V_Fpz(t)',P.cyan,1],['V_Cz(t)',P.violet,2],['x(t)',P.amber,3]];
  const sc=u*.02;
  traces.forEach(([lab,col,k],i)=>{const y=240+i*150,p=seg(u,1.6+i*.9,2.4);const f=k===3?a=>eeg(a*3+sc,1)-.7*eeg(a*3+sc,4,'slow'):k===1?a=>eeg(a*3+sc,1):a=>.7*eeg(a*3+sc,4,'slow');
    poly(c,[[X0,y],[X1,y]],{stroke:P.grid,width:1.5,alpha:p});drawOn(c,wavePts(X0,y,X1-X0,40,f,300),p,{stroke:col,width:2.6});EQ(c,lab,X0,y-62,{size:28,color:col,align:'left',p:fin(u,1.6+i*.9,.5)});
    if(i===2)T(c,'= difference',X0+115,y-52,{size:24,color:P.muted,alpha:p})});
  EQ(c,'x(t)=V_{\\mathrm{Fpz}}(t)-V_{\\mathrm{Cz}}(t)',1405,720,{size:42,p:seg(u,4.6,1.2)});
  EQ(c,'1\\,\\mu V = 10^{-6}\\,V',1405,815,{size:34,color:P.muted,p:seg(u,6.4,1)});
}},
{id:'sampling',ch:1,tag:'CODE',dur:12,cap:[[0,'A computer cannot store a continuous curve. It keeps samples at regular moments.'],[6,'Our recording uses 100 samples per second, so one value every 0.01 seconds.']],
draw(c,u){
  const x0=200,x1=1720,y=430,amp=150,f=a=>.8*Math.sin(TAU*a*2.2)+.3*Math.sin(TAU*a*7.1+1)+.12*Math.sin(TAU*a*13);
  const A=axes(c,{x:x0,y:y-200,w:x1-x0,h:400,xmin:0,xmax:.5,ymin:-1.3,ymax:1.3,xt:[0,.1,.2,.3,.4,.5],yt:[],fmtX:v=>v.toFixed(1)+' s',alpha:fin(u,0)});
  const curve=wavePts(x0,y,x1-x0,amp,a=>f(a*.5),500);const fade=1-.65*fin(u,5.5,1);
  drawOn(c,curve,seg(u,.3,2),{stroke:P.cyan,width:3,alpha:fade,glow:8});
  const N=50,sp=(x1-x0)/N;
  for(let n=0;n<=N;n++){const a=seg(u,2.4+n*.055,.4,outExpo);if(a<=0)continue;const x=x0+n*sp,v=y-amp*f(n/N*.5);poly(c,[[x,y],[x,lerp(y,v,a)]],{stroke:P.amber,width:2.2,alpha:a});dot(c,x,lerp(y,v,a),5.5,P.amber,a)}
  // delta t bracket
  const b=fin(u,6.5);poly(c,[[x0+10*sp,y-185],[x0+10*sp,y-172],[x0+11*sp,y-172],[x0+11*sp,y-185]],{stroke:P.ink,width:2,alpha:b});EQ(c,'\\Delta t',x0+10.5*sp,y-210,{size:28,p:b});
  pill(c,'f_s = 100 Hz',1640,180,{size:26,color:P.amber,alpha:fin(u,2.3)});
  EQ(c,'x[n]=x\\!\\left(\\tfrac{n}{f_s}\\right)',560,790,{size:40,p:seg(u,6,1)});
  EQ(c,'\\Delta t=\\frac{1}{f_s}=\\frac{1}{100}=0.01\\ \\text{s}',1300,790,{size:40,p:seg(u,7.2,1.2)});
}},
{id:'aliasing',ch:1,tag:'ILLU',dur:12,cap:[[0,'Sampling sets a ceiling: the Nyquist frequency is half the sampling rate, here 50 Hz.'],[6,'A 70 Hz wave sampled at 100 Hz lands on the same points as a 30 Hz wave. That is aliasing.']],
draw(c,u){
  const x0=180,x1=1740,y=470,amp=150,span=.2;
  const A=axes(c,{x:x0,y:y-190,w:x1-x0,h:380,xmin:0,xmax:span,ymin:-1.2,ymax:1.2,xt:[0,.05,.1,.15,.2],fmtX:v=>v.toFixed(2)+' s',alpha:fin(u,0)});
  EQ(c,'f_{\\mathrm{Nyquist}}=\\frac{f_s}{2}=50\\ \\text{Hz}',960,200,{size:42,p:seg(u,.3,1.2)});
  drawOn(c,wavePts(x0,y,x1-x0,amp,a=>Math.sin(TAU*70*a*span),1400),seg(u,1.3,2),{stroke:P.cyan,width:2.2,alpha:1-.55*fin(u,6,1)});
  for(let n=0;n<=20;n++){const a=seg(u,3.4+n*.07,.35,outBack);const x=x0+n*(x1-x0)/20,v=y-amp*Math.sin(TAU*70*n*.01);dot(c,x,v,8*a,P.amber,clamp(a),10)}
  drawOn(c,wavePts(x0,y,x1-x0,amp,a=>-Math.sin(TAU*30*a*span),700),seg(u,6,2.2),{stroke:P.amber,width:3.4,glow:10});
  pill(c,'true wave: 70 Hz',520,800,{size:26,color:P.cyan,alpha:fin(u,1.6)});
  pill(c,'what the samples show: 30 Hz',1320,800,{size:26,color:P.amber,alpha:fin(u,7)});
}},
{id:'epoch',ch:1,tag:'CODE',dur:12,cap:[[0,'We cut the night into 30-second epochs. At 100 Hz, each epoch holds 3,000 numbers.'],[6,'So one epoch is a vector of 3,000 real numbers, paired with one reference stage label y.']],
draw(c,u){
  const x0=160,x1=1760,y=280;const p=seg(u,.2,1.8);
  drawOn(c,wavePts(x0,y,x1-x0,55,a=>eeg(a*6,3),900),p,{stroke:P.cyan,width:2.2,alpha:1-.4*fin(u,3.5)});
  const b=fin(u,1.8);poly(c,[[x0,y+80],[x0,y+92],[x1,y+92],[x1,y+80]],{stroke:P.muted,width:2,alpha:b});T(c,'30 s',960,y+130,{size:26,color:P.muted,align:'center',alpha:b});
  EQ(c,'N=f_sT=100\\times 30=3000',960,y+215,{size:44,p:seg(u,2.4,1.4)});
  // vector cells
  const vals=['12.4','9.8','4.1','-3.6','-8.2','-5.0','…','7.7','11.3'],labs=['x[0]','x[1]','x[2]','x[3]','x[4]','x[5]','','x[2998]','x[2999]'];
  const cw=150,cx0=960-cw*vals.length/2,cy=650;
  vals.forEach((v,i)=>{const a=seg(u,4+i*.12,.5,outBack);if(a<=0)return;
    // particles flying from trace
    const src=[x0+(i/(vals.length-1))*(x1-x0),y];const d=seg(u,3.6+i*.12,.7,cubic);if(d<1)dot(c,lerp(src[0],cx0+i*cw+cw/2,d),lerp(src[1],cy,d),6,P.cyan,1-d,10);
    if(v==='…'){T(c,'…',cx0+i*cw+cw/2,cy+12,{size:44,color:P.muted,align:'center',alpha:clamp(a)});return}
    rect(c,cx0+i*cw+6,cy-36,cw-12,72,rgba(P.cyan,.08),{alpha:clamp(a),r:10,stroke:rgba(P.cyan,.6),sw:1.5});T(c,v,cx0+i*cw+cw/2,cy+10,{size:28,align:'center',alpha:clamp(a),weight:'med'});
    EQ(c,labs[i],cx0+i*cw+cw/2,cy-62,{size:22,color:P.muted,alpha:clamp(a)})});
  T(c,'μV values are illustrative',cx0,cy+70,{size:20,color:P.dim,alpha:fin(u,5.4)});
  EQ(c,'\\mathbf{x}=[x[0],x[1],\\ldots,x[2999]]\\in\\mathbb{R}^{3000}',720,800,{size:38,p:seg(u,6,1.4)});
  EQ(c,'(\\mathbf{x}_i,\\,y_i)',1470,800,{size:40,color:P.amber,p:seg(u,7.6,1)});
}},
{id:'labels',ch:1,tag:'CODE',dur:12,cap:[[0,'Each epoch gets one of five labels, coded 0 to 4. The codes are names, not depth: REM = 4 is not deeper than N3 = 3.'],[6.5,'Old sleep stages 3 and 4 are merged into N3. Movement and unknown epochs are left out of the five classes.']],
draw(c,u){
  const w=new World({box:[96,150,1728,560],center:[0,0,1],phi:1.15,theta:-1.45+.12*Math.sin(u/4),frameHeight:6});
  w.floor({size:6,alpha:.4});
  const names=['W','N1','N2','N3','REM'],desc=['Wake','Light sleep','Stable sleep','Deep sleep','Rapid eye movement'];
  for(let i=0;i<5;i++){const x=(i-2)*2.2;w.grow([x,0,0],[1.4,1.2,1.4],STAGE_COL[i],seg(u,.2+i*.18,.9,outBack));w.label([x,0,2.15],String(i),{size:46,weight:'bold',color:STAGE_COL[i],alpha:fin(u,.6+i*.18)})}
  // stage 3 + 4 merge into N3
  const m=seg(u,6.6,1.6,cubic),ma=fin(u,6.4)*(1-fin(u,8.4,.5));
  if(ma>0){w.box3([2.2-0.9*(1-m),-.2,2.9-.6*m],[.6,.6,.5],'#6FA8FF',{alpha:ma});w.box3([2.2+.9*(1-m),-.2,2.9-.6*m],[.6,.6,.5],'#3F7AD0',{alpha:ma});
    w.label([2.2-1.1*(1-m)-.3,-.2,3.45],'stage 3',{size:22,color:P.muted,alpha:ma*(1-m)});w.label([2.2+1.1*(1-m)+.3,-.2,3.45],'stage 4',{size:22,color:P.muted,alpha:ma*(1-m)})}
  w.draw(c);
  for(let i=0;i<5;i++){const x=960+(i-2)*300;T(c,names[i],x,700,{size:40,color:STAGE_COL[i],align:'center',weight:'bold',alpha:fin(u,.8+i*.18)});T(c,desc[i],x,740,{size:22,color:P.muted,align:'center',alpha:fin(u,1+i*.18)})}
  // "not depth" callout
  const k=fin(u,3.2);EQ(c,'y\\in\\{0,1,2,3,4\\}',420,830,{size:38,p:seg(u,2.8,1)});
  T(c,'REM = 4  is not  "deeper than"  N3 = 3',1250,842,{size:30,color:P.coral,align:'center',alpha:k,weight:'med'});
  const ex=fin(u,8.6);pill(c,'movement / unknown: excluded',1580,200,{size:24,color:P.dim,alpha:ex});
}},
{id:'cohort',ch:1,tag:'MEAS',dur:11,cap:[[0,'The evaluated cohort: 20 participants, 39 recorded nights and 42,307 retained epochs from Sleep-EDF Expanded.'],[6,'Epochs from the same person are strongly related, so the data must be split by person, not by epoch.']],
draw(c,u){
  const w=new World({box:[96,250,1728,560],center:[0,.4,.6],phi:1.12,theta:-1.5+.18*Math.sin(u/4),frameHeight:5.6});w.floor({size:7,alpha:.35});
  for(let i=0;i<20;i++)person(w,(i%10-4.5)*1.15,Math.floor(i/10)*1.5-.3,i%2?P.cyan:P.violet,.85,{g:seg(u,.3+i*.08,.7)});w.draw(c);
  const nums=[[20,'participants',P.cyan],[39,'nights',P.violet],[42307,'30-second epochs',P.amber]];
  nums.forEach(([n,l,col],i)=>{const x=480+i*480,p=seg(u,.6+i*.5,2.2,outExpo);T(c,fmt(Math.round(n*p)),x,250,{size:84,weight:'bold',color:col,align:'center',alpha:fin(u,.5+i*.5)});T(c,l,x,295,{size:28,color:P.muted,align:'center',alpha:fin(u,.8+i*.5)})});
}},
{id:'split',ch:1,tag:'CODE',dur:13,cap:[[0,'In each fold, 16 people train the model, 2 people choose the checkpoint and 2 people are kept for testing.'],[6.5,'Ten folds rotate the held-out people, so every participant is tested exactly once and never sits in two sets.']],
draw(c,u){
  const fold=u<5.5?0:Math.min(9,Math.floor((u-5.5)/.62));const sep=seg(u,1,1.6,cubic);
  const w=new World({box:[96,180,1728,560],center:[0,.3,.6],phi:1.15,theta:-1.5,frameHeight:5.8});w.floor({size:7,alpha:.35});
  const role=i=>{const t=[2*fold,2*fold+1],v=[(2*fold+2)%20,(2*fold+3)%20];return t.includes(i)?2:v.includes(i)?1:0};
  for(let i=0;i<20;i++){const r=role(i);const col=[P.cyan,P.amber,P.coral][r];const lift=r?-1.25*sep:0;person(w,(i%10-4.5)*1.15,Math.floor(i/10)*1.5-.3+lift,col,.85)}
  w.draw(c);
  [['TRAIN','16',P.cyan,560],['VALIDATION','2',P.amber,960],['TEST','2',P.coral,1360]].forEach(([n,k,col,x],i)=>{const a=fin(u,1.8+i*.3);T(c,k,x,240,{size:70,weight:'bold',color:col,align:'center',alpha:a});T(c,n,x,280,{size:24,color:col,align:'center',alpha:a,weight:'med'})});
  pill(c,`Fold ${fold+1} of 10`,1640,200,{size:26,color:P.ink,alpha:fin(u,5.4)});
  EQ(c,'S_{\\text{train}}\\cap S_{\\text{val}}=\\varnothing\\qquad S_{\\text{train}}\\cap S_{\\text{test}}=\\varnothing\\qquad S_{\\text{val}}\\cap S_{\\text{test}}=\\varnothing',960,815,{size:34,p:seg(u,3,1.6)});
}},
// ---------------------------------------------------------------- CH2 WAVES TO FREQUENCIES
{id:'sine',ch:2,tag:'ILLU',dur:12,cap:[[0,'A sine wave has three knobs. Amplitude A sets its size.'],[4,'Frequency f sets how many cycles happen each second.'],[8,'Phase φ sets where in its cycle the wave starts.']],
draw(c,u){
  const A=1+.55*Math.sin(clamp(u-1,0,3)*Math.PI/1.5)*(u<4.2?1:0),f=2+(u>4&&u<8?1.6*Math.sin((u-4)*Math.PI/2):0),ph=u>8?(u-8)*1.4:0;
  const hi=u<4?0:u<8?1:2;const x0=180,x1=1300,y=500;
  axes(c,{x:x0,y:y-220,w:x1-x0,h:440,xmin:0,xmax:1,ymin:-1.6,ymax:1.6,xt:[0,.5,1],fmtX:v=>v+' s',alpha:fin(u,0)});
  drawOn(c,wavePts(x0,y,x1-x0,130,a=>A*Math.sin(TAU*f*a+ph),500),seg(u,.2,1.4),{stroke:P.cyan,width:3.6,glow:12});
  const cols=[P.ink,P.ink,P.ink];cols[hi]=P.amber;
  EQ(c,`x(t)=\\color{${cols[0]}}{A}\\,\\sin(2\\pi \\color{${cols[1]}}{f}\\,t+\\color{${cols[2]}}{\\phi})`,740,200,{size:48,p:seg(u,.2,1.4)});
  const knobs=[['A','amplitude',A.toFixed(2)],['f','frequency',f.toFixed(2)+' Hz'],['\\phi','phase',(ph%TAU).toFixed(2)+' rad']];
  knobs.forEach(([s,l,v],i)=>{const y0=290+i*170,act=i===hi,a=fin(u,.6+i*.2);panel(c,1420,y0,380,140,{col:act?P.amber:P.line,alpha:a});EQ(c,s,1480,y0+70,{size:48,color:act?P.amber:P.muted,alpha:a});T(c,l,1540,y0+58,{size:24,color:P.muted,alpha:a});T(c,v,1540,y0+100,{size:32,weight:'bold',color:act?P.amber:P.ink,alpha:a})});
}},
{id:'sum',ch:2,tag:'MATH',dur:12,cap:[[0,'Real signals are sums of waves. Here: a 2 Hz wave of size 20 plus a 12 Hz wave of size 5.'],[6.5,'The recorded trace only shows the sum. The individual parts are hidden inside it.']],
draw(c,u){
  const x0=220,x1=1700,s=3.6,m=seg(u,5,1.8,cubic);
  const y1=lerp(250,560,m),y2=lerp(420,560,m);
  const f1=a=>20*Math.sin(TAU*2*a),f2=a=>5*Math.sin(TAU*12*a);
  poly(c,[[x0,560],[x1,560]],{stroke:P.grid,width:1.5,alpha:fin(u,0)});
  drawOn(c,wavePts(x0,y1,x1-x0,s,f1,600),seg(u,.3,1.6),{stroke:P.cyan,width:3,alpha:1-m});
  drawOn(c,wavePts(x0,y2,x1-x0,s*3,f2,600),seg(u,1.4,1.6),{stroke:P.violet,width:3,alpha:1-m});
  T(c,'2 Hz, size 20',x0,y1-95,{size:26,color:P.cyan,alpha:fin(u,.6)*(1-m)});T(c,'12 Hz, size 5',x0,y2-48,{size:26,color:P.violet,alpha:fin(u,1.6)*(1-m)});
  drawOn(c,wavePts(x0,560,x1-x0,s,a=>f1(a)+f2(a),800),seg(u,6,1.6),{stroke:P.amber,width:3.4,glow:10});
  T(c,'sum: what the electrode records',x0,440,{size:26,color:P.amber,alpha:fin(u,6.6)});
  EQ(c,'x[n]=20\\sin\\!\\left(2\\pi\\tfrac{2n}{100}\\right)+5\\sin\\!\\left(2\\pi\\tfrac{12n}{100}\\right)',960,800,{size:40,p:seg(u,2.6,1.6)});
}},
{id:'power',ch:2,tag:'MATH',dur:11,cap:[[0,'For a sine wave over full cycles, the average of x² equals A²/2.'],[5.5,'Double the amplitude and the power grows four times. Magnitude and power are different quantities.']],
draw(c,u){
  EQ(c,'\\operatorname{mean}(x^2)=\\frac{A^2}{2}',1450,220,{size:48,p:seg(u,.3,1.2)});
  [[1,P.cyan,330],[2,P.amber,620]].forEach(([A,col,y],i)=>{const x0=160,x1=1100,a=seg(u,.5+i*2.2,1.4);
    T(c,`A = ${A}`,x0,y-130,{size:28,weight:'bold',color:col,alpha:fin(u,.5+i*2.2)});
    poly(c,[[x0,y],[x1,y]],{stroke:P.grid,width:1.5,alpha:a});
    const sq=wavePts(x0,y,x1-x0,40,t=>(A*Math.sin(TAU*3*t))**2,400);const fa=seg(u,1.4+i*2.2,1);
    if(fa>0)poly(c,[[x0,y],...sq,[x1,y]],{stroke:null,fill:rgba(col,.18*fa),close:true});
    drawOn(c,wavePts(x0,y,x1-x0,40,t=>A*Math.sin(TAU*3*t),400),a,{stroke:col,width:3});
    const my=y-40*A*A/2;poly(c,[[x0,my],[x1,my]],{stroke:col,width:2,dash:[10,8],alpha:fa});T(c,`mean of x² = ${(A*A/2).toFixed(1)}`,x1+20,my+8,{size:24,color:col,alpha:fa})});
  // bars
  const b1=seg(u,5.5,1.2,outBack),b2=seg(u,6.1,1.2,outBack),base=760;
  rect(c,1360,base-60*b1,120,60*b1,P.cyan,{r:6});rect(c,1560,base-240*b2,120,240*b2,P.amber,{r:6});
  T(c,'0.5',1420,base-60*b1-16,{size:30,align:'center',weight:'bold',color:P.cyan,alpha:fin(u,6)});T(c,'2.0',1620,base-240*b2-16,{size:30,align:'center',weight:'bold',color:P.amber,alpha:fin(u,6.6)});
  T(c,'× 4',1730,base-140,{size:44,weight:'bold',color:P.ink,alpha:fin(u,7.4)});poly(c,[[1360,base],[1700,base]],{stroke:P.line,width:2,alpha:fin(u,5.4)});
  T(c,'A = 1',1420,base+36,{size:22,color:P.muted,align:'center',alpha:fin(u,5.5)});T(c,'A = 2',1620,base+36,{size:22,color:P.muted,align:'center',alpha:fin(u,5.5)});
}},
{id:'dft',ch:2,tag:'ILLU',dur:14,cap:[[0,'The DFT compares the signal with a cosine and a sine at each test frequency.'],[5,'Wrap the signal around a circle at that frequency. When the frequency matches, the wrapped curve leans to one side.'],[10,'Measure that lean for every frequency and peaks appear at 2 Hz and 12 Hz.']],
draw(c,u){
  EQ(c,'X[k]=\\sum_{n=0}^{N-1}x[n]\\,e^{-j2\\pi kn/N}',560,200,{size:40,p:seg(u,.2,1.4)});
  EQ(c,'e^{-j\\theta}=\\cos\\theta-j\\sin\\theta',1380,200,{size:34,color:P.muted,p:seg(u,1.4,1)});
  const sig=t=>20*Math.sin(TAU*2*t)+5*Math.sin(TAU*12*t);
  const ft=u<2.5?.6:Math.min(16,.6+(u-2.5)*1.5);
  const cx=560,cy=540,sc=8.4,a=fin(u,1.6);
  poly(c,[[cx-250,cy],[cx+250,cy]],{stroke:P.grid,width:1.5,alpha:a});poly(c,[[cx,cy-250],[cx,cy+250]],{stroke:P.grid,width:1.5,alpha:a});
  const pts=[];let sx=0,sy=0;const N=700;for(let i=0;i<N;i++){const t=i/N,v=sig(t),x=v*Math.cos(TAU*ft*t),y=-v*Math.sin(TAU*ft*t);sx+=x;sy+=y;pts.push([cx+x*sc,cy-y*sc])}
  drawOn(c,pts,seg(u,2,1.2),{stroke:P.cyan,width:1.6,alpha:.85,head:false});
  const mx=cx+sx/N*sc*2,my=cy-sy/N*sc*2;dot(c,mx,my,10,P.amber,a,16);poly(c,[[cx,cy],[mx,my]],{stroke:P.amber,width:3,alpha:a});
  T(c,`test frequency ${ft.toFixed(1)} Hz`,cx,cy+300,{size:26,color:P.ink,align:'center',alpha:fin(u,2.2)});
  // spectrum
  const X0=1050,Y0=760,Wd=700,Hh=420;const ax=axes(c,{x:X0,y:Y0-Hh,w:Wd,h:Hh,xmin:0,xmax:16,ymin:0,ymax:11,xt:[0,2,4,8,12,16],fmtX:v=>v+' Hz',yt:[],alpha:fin(u,2.4)});
  T(c,'|X(f)|',X0,Y0-Hh-20,{size:24,color:P.muted,alpha:fin(u,2.4)});
  const spec=[];for(let f=0;f<=ft;f+=.05){let re=0,im=0;const M=400;for(let i=0;i<M;i++){const t=i/M,v=sig(t);re+=v*Math.cos(TAU*f*t);im-=v*Math.sin(TAU*f*t)}spec.push([ax.X(f),ax.Y(Math.hypot(re,im)/M)])}
  poly(c,spec,{stroke:P.amber,width:3,glow:8});
  if(u>11){T(c,'2 Hz',ax.X(2),ax.Y(10)-16,{size:24,color:P.amber,align:'center',alpha:fin(u,11)});T(c,'12 Hz',ax.X(12),ax.Y(2.5)-16,{size:24,color:P.amber,align:'center',alpha:fin(u,11.3)})}
}},
{id:'complex',ch:2,tag:'MATH',dur:12,cap:[[0,'Each DFT output is a complex number with a real part a and an imaginary part b.'],[6,'We keep the magnitude |X| and drop the phase. The FFT is simply a fast way to compute the same DFT.']],
draw(c,u){
  const cx=600,cy=560,s=110,ax=fin(u,0);
  poly(c,[[cx-320,cy],[cx+460,cy]],{stroke:P.line,width:2,alpha:ax});poly(c,[[cx,cy+260],[cx,cy-330]],{stroke:P.line,width:2,alpha:ax});
  T(c,'real',cx+470,cy+8,{size:24,color:P.muted,alpha:ax});T(c,'imaginary',cx+12,cy-340,{size:24,color:P.muted,alpha:ax});
  const a=3.2,b=2.3,px=cx+a*s,py=cy-b*s,v=seg(u,.6,1.2,cubic);
  arrow(c,cx,cy,px,py,{col:P.cyan,width:4,p:v,head:18});
  const d=fin(u,1.8);poly(c,[[px,py],[px,cy]],{stroke:P.amber,width:2,dash:[8,8],alpha:d});poly(c,[[px,py],[cx,py]],{stroke:P.violet,width:2,dash:[8,8],alpha:d});
  EQ(c,'a',(cx+px)/2,cy+36,{size:36,color:P.amber,alpha:d});EQ(c,'b',cx-34,(cy+py)/2,{size:36,color:P.violet,alpha:d});
  const arcA=fin(u,3)*(1-.75*fin(u,7));c.save();c.globalAlpha=arcA;c.strokeStyle=P.coral;c.lineWidth=3;c.beginPath();c.arc(cx,cy,90,-Math.atan2(b,a),0);c.stroke();c.restore();
  EQ(c,'\\arg',cx+130,cy-38,{size:30,color:P.coral,alpha:arcA});
  T(c,'|X|',(cx+px)/2-50,(cy+py)/2-24,{size:34,weight:'bold',color:P.cyan,alpha:fin(u,2.4)});
  EQ(c,'X[k]=a_k+jb_k',1420,250,{size:44,p:seg(u,.8,1)});
  EQ(c,'|X[k]|=\\sqrt{a_k^2+b_k^2}',1420,370,{size:44,color:P.cyan,p:seg(u,2.2,1)});
  EQ(c,'\\arg X[k]=\\operatorname{atan2}(b_k,a_k)',1420,490,{size:40,color:P.coral,p:seg(u,3.2,1),alpha:1-.6*fin(u,7)});
  if(u>7){const k=fin(u,7);poly(c,[[1180,490],[1660,490]],{stroke:P.coral,width:3,alpha:k});pill(c,'phase dropped',1420,560,{size:24,color:P.coral,alpha:k})}
  pill(c,'keep |X|',1250,680,{size:30,color:P.cyan,alpha:fin(u,7.5)});pill(c,'FFT = fast DFT',1560,680,{size:30,color:P.ink,alpha:fin(u,8.5)});
}},
{id:'stft',ch:2,tag:'CODE',dur:14,cap:[[0,'One FFT over all 30 seconds tells which frequencies exist, but not when they happen.'],[5,'The STFT slides a 2-second Hamming window forward 1 second at a time and runs an FFT at each stop.'],[10,'Stacking the 29 windows gives a time-frequency picture of one epoch.']],
draw(c,u){
  const x0=160,x1=1760,y=250;const trace=wavePts(x0,y,x1-x0,50,a=>eeg(a*5,7),900);drawOn(c,trace,seg(u,.2,1.5),{stroke:P.cyan,width:2});
  const k=u<4?-1:Math.min(28,Math.floor((u-4)/.22));const step=(x1-x0)/30;
  if(k>=0){const wx=x0+k*step,ww=2*step;const hump=[];for(let i=0;i<=40;i++){const n=i/40;hump.push([wx+n*ww,y+70-110*(.54-.46*Math.cos(TAU*n))])}
    rect(c,wx,y-75,ww,150,rgba(P.amber,.1),{r:6,stroke:rgba(P.amber,.8),sw:2});poly(c,hump,{stroke:P.amber,width:2.5,glow:6})}
  T(c,'2 s window',x0+Math.max(0,k)*step+step,y-90,{size:22,color:P.amber,align:'center',alpha:k>=0?1:0});
  // spectrogram grid
  const gx=600,gy=380,cw=24,rh=2.8;
  for(let t=0;t<=Math.min(k,28);t++){const fresh=k===t?.6:0;for(let f=0;f<129;f++){c.fillStyle=heat(SPEC[t][f]+fresh*.2);c.fillRect(gx+t*cw,gy+(128-f)*rh,cw-1,rh+.4)}}
  rect(c,gx-2,gy-2,29*cw+3,129*rh+4,null,{stroke:P.line,sw:2,alpha:fin(u,3.8)});
  T(c,'0 Hz',gx-12,gy+129*rh,{size:20,color:P.muted,align:'right',alpha:fin(u,3.8)});T(c,'50 Hz',gx-12,gy+14,{size:20,color:P.muted,align:'right',alpha:fin(u,3.8)});
  T(c,'time →',gx+29*cw,gy+129*rh+30,{size:20,color:P.muted,align:'right',alpha:fin(u,3.8)});
  const chips=[["window='hamming'",P.amber],['nperseg=200',P.ink],['noverlap=100',P.ink],['nfft=256',P.ink]];
  chips.forEach(([s,col],i)=>{const a=fin(u,5.4+i*.3);rect(c,1380,400+i*70,330,52,rgba(col,.08),{r:10,stroke:rgba(col,.4),sw:1.5,alpha:a});T(c,s,1400,435+i*70,{size:24,color:col,weight:'mono',alpha:a})});
  T(c,'scipy.signal.stft(fs=100)',1380,375,{size:22,color:P.muted,alpha:fin(u,5.2),weight:'mono'});
}},
{id:'hamming',ch:2,tag:'ILLU',dur:12,cap:[[0,'Cutting a short piece of signal creates hard edges, and hard edges smear energy into nearby frequencies.'],[6,'The Hamming window weights the middle and fades the edges. Leakage drops, at the cost of a slightly wider peak.']],
draw(c,u){
  EQ(c,'w[n]=0.54-0.46\\cos\\!\\left(\\frac{2\\pi n}{L}\\right)',520,210,{size:40,p:seg(u,.3,1.4)});
  const x0=140,x1=880,y0=640,hh=300;const A=fin(u,0);poly(c,[[x0,y0],[x1,y0]],{stroke:P.line,width:2,alpha:A});
  drawOn(c,[[x0,y0],[x0,y0-hh],[x1,y0-hh],[x1,y0]],seg(u,.6,1),{stroke:P.violet,width:3});
  drawOn(c,wavePts(x0,y0,x1-x0,hh,a=>.54-.46*Math.cos(TAU*a),200),seg(u,1.6,1.4),{stroke:P.amber,width:3.5,glow:8});
  T(c,'rectangular cut',x0,y0-hh-24,{size:24,color:P.violet,alpha:fin(u,.8)});T(c,'Hamming',(x0+x1)/2,y0-hh+70,{size:24,color:P.amber,align:'center',alpha:fin(u,2)});
  T(c,'n = 0',x0,y0+34,{size:20,color:P.muted,alpha:A});T(c,'n = L',x1,y0+34,{size:20,color:P.muted,align:'right',alpha:A});
  // leakage spectra (dB)
  const X0=1050,Y0=740,Wd=720,Hh=460;const ax=axes(c,{x:X0,y:Y0-Hh,w:Wd,h:Hh,xmin:0,xmax:25,ymin:-90,ymax:0,xt:[0,5,10,15,20,25],yt:[0,-30,-60,-90],fmtX:v=>v+' Hz',fmtY:v=>v+' dB',alpha:fin(u,3)});
  T(c,'spectrum of one 10.3 Hz tone',X0+Wd/2,Y0-Hh-24,{size:24,color:P.muted,align:'center',alpha:fin(u,3)});
  for(const [arr,col,t0] of [[LEAK.rect,P.violet,3.6],[LEAK.ham,P.amber,6]])drawOn(c,arr.map(([f,d])=>[ax.X(f),ax.Y(Math.max(-90,d))]),seg(u,t0,1.6),{stroke:col,width:2.6});
}},
{id:'grid',ch:2,tag:'CODE',dur:13,cap:[[0,'Count the windows: 29 time steps. Count the one-sided FFT bins: 129 frequencies. One epoch becomes a 129 × 29 grid.'],[7,'Bins are 0.39 Hz apart, but zero-padding from 200 to 256 points adds bins, not new information.']],
draw(c,u){
  const gx=210,gy=200,cw=15,rh=4.4;const cols=Math.floor(29*seg(u,.3,2.5,cubic)),rows=Math.floor(129*seg(u,2.8,2.5,cubic));
  for(let t=0;t<cols;t++)for(let f=0;f<129;f++){c.fillStyle=f<rows?heat(SPEC[t][f]):'#13233A';c.fillRect(gx+t*cw,gy+(128-f)*rh,cw-1,rh)}
  for(let t=0;t<cols;t++)rect(c,gx+t*cw,gy+129*rh+10,cw-1,10,P.cyan,{alpha:.8});
  for(let f=0;f<rows;f+=4)rect(c,gx-22,gy+(128-f)*rh,10,rh*3,P.amber,{alpha:.8});
  T(c,String(cols),gx+29*cw/2,gy+129*rh+60,{size:40,weight:'bold',color:P.cyan,align:'center',alpha:fin(u,.3)});T(c,'time steps',gx+29*cw/2,gy+129*rh+92,{size:22,color:P.muted,align:'center',alpha:fin(u,.3)});
  T(c,String(rows),gx-40,gy+129*rh/2,{size:40,weight:'bold',color:P.amber,align:'right',alpha:fin(u,2.8)});T(c,'freq bins',gx-40,gy+129*rh/2+32,{size:22,color:P.muted,align:'right',alpha:fin(u,2.8)});
  EQ(c,'N_{\\text{time}}=1+\\left\\lfloor\\frac{3000-200}{100}\\right\\rfloor=29',1180,230,{size:40,color:P.cyan,p:seg(u,.6,1.4)});
  EQ(c,'N_{\\text{freq}}=\\frac{256}{2}+1=129',1180,370,{size:40,color:P.amber,p:seg(u,3,1.2)});
  EQ(c,'X\\in\\mathbb{C}^{129\\times 29}',1180,480,{size:42,p:seg(u,5,1)});
  EQ(c,'\\Delta f=\\frac{f_s}{M}=\\frac{100}{256}=0.390625\\ \\text{Hz}',1180,600,{size:38,p:seg(u,6.6,1.2)});
  pill(c,'bin spacing ≠ true resolution',1180,730,{size:26,color:P.coral,alpha:fin(u,8.4)});
}},
{id:'log',ch:2,tag:'CODE',dur:12,cap:[[0,'Spectral magnitudes span huge ranges, so we take the natural logarithm. A 100× gap becomes about 4.6 units.'],[6.5,'This is log-magnitude, not log-power. The tiny ε = 10⁻⁶ prevents ln(0) = −∞.']],
draw(c,u){
  const base=760,x0=260,m=seg(u,2.6,2,cubic);const vals=[1,10,100],logs=vals.map(Math.log);
  poly(c,[[x0-60,base],[x0+700,base]],{stroke:P.line,width:2,alpha:fin(u,0)});
  vals.forEach((v,i)=>{const g=seg(u,.3+i*.3,1,outBack);const h=lerp(v*5,logs[i]*100,m)*g,x=x0+i*230;rect(c,x,base-h,150,Math.max(2,h),[P.cyan,P.violet,P.amber][i],{r:6});
    T(c,m<.5?String(v):logs[i].toFixed(2),x+75,base-h-18,{size:34,weight:'bold',align:'center',color:P.ink,alpha:fin(u,.6+i*.3)});
    T(c,m<.5?`|X| = ${v}`:`ln(${v})`,x+75,base+40,{size:24,align:'center',color:P.muted,alpha:fin(u,.6+i*.3)})});
  EQ(c,'F[k,m]=\\ln\\!\\left(|X[k,m]|+\\epsilon_{\\log}\\right)',1360,250,{size:42,p:seg(u,1.2,1.4)});
  EQ(c,'\\epsilon_{\\log}=10^{-6}',1360,350,{size:36,color:P.muted,p:seg(u,2.6,1)});
  EQ(c,'\\ln(0)=-\\infty',1360,450,{size:36,color:P.coral,p:seg(u,6.8,1)});
  panel(c,1060,540,600,210,{alpha:fin(u,7.6),col:P.amber});
  EQ(c,'\\ln(|X|+\\epsilon)',1220,610,{size:36,color:P.cyan,alpha:fin(u,7.8)});T(c,'ours: log-magnitude',1220,690,{size:22,color:P.cyan,align:'center',alpha:fin(u,7.8)});
  EQ(c,'\\ln(|X|^2+\\epsilon)',1500,610,{size:36,color:P.dim,alpha:fin(u,8.2)});T(c,'not used: log-power',1500,690,{size:22,color:P.dim,align:'center',alpha:fin(u,8.2)});
}},
{id:'numbers',ch:2,tag:'CONC',dur:10,cap:[[0,'Colors are only for people. The network never sees colors.'],[4.5,'It receives a 129 × 29 matrix of real numbers for every epoch.']],
draw(c,u){
  const cols=12,rows=7,cw=128,ch=74,gx=960-cols*cw/2,gy=200;
  for(let r=0;r<rows;r++)for(let k=0;k<cols;k++){const v=SPEC[k*2][120-r*14];const val=(Math.log(v*40+.5)-1.6).toFixed(2);
    const flip=seg(u,1.6+(k+r)*.11,.5,cubic);const sx=Math.abs(Math.cos(flip*Math.PI));const x=gx+k*cw,y=gy+r*ch;
    c.save();c.translate(x+cw/2,y+ch/2);c.scale(Math.max(.02,sx),1);
    if(flip<.5){c.fillStyle=heat(v);c.fillRect(-cw/2+2,-ch/2+2,cw-4,ch-4)}else{c.fillStyle='#0E1C30';c.fillRect(-cw/2+2,-ch/2+2,cw-4,ch-4);c.strokeStyle=rgba(P.cyan,.35);c.lineWidth=1;c.strokeRect(-cw/2+2,-ch/2+2,cw-4,ch-4);c.font='26px FilmMono';c.fillStyle=P.ink;c.textAlign='center';c.fillText(val,0,9)}
    c.restore()}
  T(c,'a corner of one log-magnitude feature matrix (illustrative values)',960,gy+rows*ch+40,{size:22,color:P.muted,align:'center',alpha:fin(u,4)});
  EQ(c,'F\\in\\mathbb{R}^{129\\times 29}',960,830,{size:50,p:seg(u,5,1.2)});
}},
];

// leakage spectra precomputed for the Hamming scene
const LEAK=(()=>{const L=200,fs=100,f0=10.3;const out={rect:[],ham:[]};let maxR=0,maxH=0;const raw=[];for(let f=0;f<=25;f+=.05){let rr=0,ri=0,hr=0,hi=0;for(let n=0;n<L;n++){const x=Math.sin(TAU*f0*n/fs),w=.54-.46*Math.cos(TAU*n/L),ph=TAU*f*n/fs;rr+=x*Math.cos(ph);ri-=x*Math.sin(ph);hr+=x*w*Math.cos(ph);hi-=x*w*Math.sin(ph)}const R=Math.hypot(rr,ri),Hm=Math.hypot(hr,hi);maxR=Math.max(maxR,R);maxH=Math.max(maxH,Hm);raw.push([f,R,Hm])}
  for(const [f,R,Hm] of raw){out.rect.push([f,20*Math.log10(R/maxR+1e-9)]);out.ham.push([f,20*Math.log10(Hm/maxH+1e-9)])}return out})();
