// Scenes for chapters 6-8: prediction and scoring, archived results, evidence boundary.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {P,STAGE_COL,STAGES,clamp,lerp,smooth,cubic,outExpo,outBack,seg,rgba,shade,heat,mixCol,T,wrap,fmt,EQ,poly,drawOn,dot,rect,arrow,pill,panel,rnd,axes,World,person,measure} from './lib.mjs';
const ROOT=path.dirname(fileURLToPath(import.meta.url));
export const FACTS=JSON.parse(fs.readFileSync(path.join(ROOT,'facts.json')));
const fin=(u,a,d=.6)=>seg(u,a,d,smooth);
const pct=(x,d=2)=>(100*x).toFixed(d);
const RUNS=['base','r1','fullnight'],RLAB=['Baseline','R1','Full-night'],RCOL=[P.violet,P.cyan,P.amber];
const CM=FACTS.comparison.runs.r1.pooled_confusion;

function matrix(c,u,{x,y,cw,ch,t0=0,size=28,hiRow=-1,hiCol=-1}){
  STAGES.forEach((k,i)=>{T(c,k,x+i*cw+cw/2,y-18,{size:24,color:STAGE_COL[i],align:'center',weight:'bold',alpha:fin(u,t0)});T(c,k,x-18,y+i*ch+ch/2+9,{size:24,color:STAGE_COL[i],align:'right',weight:'bold',alpha:fin(u,t0)})});
  CM.forEach((row,i)=>{const tot=row.reduce((a,b)=>a+b,0);row.forEach((v,j)=>{const a=fin(u,t0+.2+(i+j)*.08,.5),cnt=Math.round(v*seg(u,t0+.3+(i+j)*.08,1.4,outExpo));const dim=(hiRow>=0||hiCol>=0)&&!(i===hiRow||j===hiCol);
    rect(c,x+j*cw+3,y+i*ch+3,cw-6,ch-6,mixCol('#0E1C30',i===j?P.cyan:P.violet,.12+.8*v/tot),{r:8,alpha:a*(dim?.3:1)});
    T(c,fmt(cnt),x+j*cw+cw/2,y+i*ch+ch/2+size*.36,{size,align:'center',weight:i===j?'bold':'reg',alpha:a*(dim?.35:1)})})});
  if(hiRow>=0)rect(c,x,y+hiRow*ch,5*cw,ch,null,{stroke:P.cyan,sw:3.5,r:10,alpha:fin(u,t0+1.5)});
  if(hiCol>=0)rect(c,x+hiCol*cw,y,cw,5*ch,null,{stroke:P.amber,sw:3.5,r:10,alpha:fin(u,t0+3.5)});
}

export const scenesC=[
// ---------------------------------------------------------------- CH6 PREDICT AND SCORE
{id:'windows',ch:6,tag:'CODE',dur:13,cap:[[0,'At inference, 20-epoch windows slide forward 5 epochs at a time, so most epochs are predicted by several windows.'],[6.5,'We average the logits, not labels or probabilities. Softmax of an average is not the average of softmaxes.']],
draw(c,u){
  const x0=150,cw=30,n=40,y0=640,target=22;
  for(let i=0;i<n;i++){const a=fin(u,.1+i*.015);rect(c,x0+i*cw,y0,cw-5,46,i===target&&u>3?P.amber:'#1B2D47',{r:5,alpha:a})}
  T(c,'epochs of one night',x0,y0+86,{size:22,color:P.muted,alpha:fin(u,.2)});
  const cov=[];for(let k=0;k<5;k++){const s=k*5,y=560-k*62,a=seg(u,.8+k*.4,.6,cubic);rect(c,x0+s*cw,y,lerp(cw,20*cw,a)-5,30,rgba(RCOL[k%3],.25),{r:8,stroke:RCOL[k%3],sw:2,alpha:clamp(a*2)});T(c,`window ${k+1}`,x0+s*cw+10,y-10,{size:20,color:RCOL[k%3],alpha:clamp(a)});if(target>=s&&target<s+20)cov.push([k,y])}
  if(u>3)for(const [k,y] of cov)poly(c,[[x0+target*cw+16,y+30],[x0+target*cw+16,y0]],{stroke:P.amber,width:2,dash:[6,5],alpha:fin(u,3)});
  // logit vectors averaging
  const lx=1520;cov.forEach(([k,y],j)=>{const a=fin(u,4+j*.3);for(let c5=0;c5<5;c5++){const v=.4+.5*rnd(k*7+c5)+(c5===2?.6:0);rect(c,lx+c5*34,250+j*70-v*40,26,v*40,STAGE_COL[c5],{alpha:a,r:3})}T(c,`w${k+1}`,lx-20,250+j*70,{size:20,color:P.muted,align:'right',alpha:a})});
  const avA=fin(u,5.6);poly(c,[[lx-10,250+cov.length*70-25],[lx+175,250+cov.length*70-25]],{stroke:P.ink,width:2,alpha:avA});
  for(let c5=0;c5<5;c5++){const v=cov.reduce((s,[k])=>s+.4+.5*rnd(k*7+c5)+(c5===2?.6:0),0)/cov.length;rect(c,lx+c5*34,250+cov.length*70+30-v*40,26,v*40,STAGE_COL[c5],{alpha:avA,r:3})}
  T(c,'mean logits',lx-20,250+cov.length*70+30,{size:20,color:P.ink,align:'right',alpha:avA});
  EQ(c,'\\overline{\\mathbf a}_t=\\frac{1}{|\\mathcal W(t)|}\\sum_{w\\in\\mathcal W(t)}\\mathbf a_t^{(w)}',700,200,{size:34,p:seg(u,4.4,1.2)});
  EQ(c,'\\operatorname{softmax}\\!\\left(\\tfrac{a^{(1)}+a^{(2)}}{2}\\right)\\neq\\tfrac{\\operatorname{softmax}(a^{(1)})+\\operatorname{softmax}(a^{(2)})}{2}',960,800,{size:32,color:P.coral,p:seg(u,7,1.4)});
}},
{id:'confusion',ch:6,tag:'MEAS',dur:12,cap:[[0,'Each scored epoch is counted by true stage (row) and predicted stage (column). These are R1 test counts.'],[6,'The diagonal is correct: 34,266 of 42,307 epochs, a pooled accuracy of 80.99%.']],
draw(c,u){
  matrix(c,u,{x:330,y:240,cw:160,ch:104,t0:.2,size:30});
  T(c,'true',250,500,{size:24,color:P.muted,align:'right',alpha:fin(u,.2)});T(c,'predicted',730,182,{size:24,color:P.muted,align:'center',alpha:fin(u,.2)});
  if(u>5.6)for(let i=0;i<5;i++)rect(c,330+i*160+3,240+i*104+3,154,98,null,{stroke:P.green,sw:3,r:8,alpha:fin(u,5.6+i*.1)});
  EQ(c,'\\text{Accuracy}=\\frac{\\sum_c C_{c,c}}{\\sum_{i}\\sum_{j} C_{i,j}}',1450,330,{size:40,p:seg(u,4,1.2)});
  EQ(c,'=\\frac{34{,}266}{42{,}307}=0.8099',1450,470,{size:40,color:P.green,p:seg(u,6.2,1.2)});
  T(c,'every epoch counts equally',1450,600,{size:24,color:P.muted,align:'center',alpha:fin(u,7)});
}},
{id:'n1',ch:6,tag:'MEAS',dur:15,cap:[[0,'Recall asks: of all true N1 epochs, how many did we catch? 1,253 of 2,804, or 44.7%.'],[5,'Precision asks: of everything predicted N1, how much was right? 1,253 of 3,220, or 38.9%.'],[9.5,'Their harmonic mean: pooled N1 F1 = 0.416. An accuracy near 81% hides this weak class.']],
draw(c,u){
  matrix(c,u,{x:250,y:250,cw:124,ch:96,t0:0,size:24,hiRow:u>.6?1:-1,hiCol:u>3?1:-1});
  EQ(c,'R_{N1}=\\frac{C_{N1,N1}}{\\sum_j C_{N1,j}}=\\frac{1253}{2804}\\approx 0.4469',1350,270,{size:36,color:P.cyan,p:seg(u,1.4,1.4)});
  EQ(c,'P_{N1}=\\frac{C_{N1,N1}}{\\sum_i C_{i,N1}}=\\frac{1253}{3220}\\approx 0.3891',1350,420,{size:36,color:P.amber,p:seg(u,5.2,1.4)});
  EQ(c,'F1_{N1}=\\frac{2PR}{P+R}=\\frac{2(1253)}{2804+3220}\\approx 0.4160',1350,580,{size:36,color:P.green,p:seg(u,9.6,1.4)});
  T(c,'row sum = 2,804',900,250+96*1+58,{size:22,color:P.cyan,alpha:fin(u,2)});T(c,'column sum = 3,220',250+124*1+62,250+96*5+40,{size:22,color:P.amber,align:'center',alpha:fin(u,4)});
}},
{id:'macro',ch:6,tag:'CONC',dur:12,cap:[[0,'Macro-F1 averages the five class F1 scores, so rare N1 counts as much as common N2.'],[6,'Our headline goes one step further: compute macro-F1 for each person, then average the 20 people equally.']],
draw(c,u){
  const f1=[.86,.42,.85,.8,.82];const base=470,x0=200;
  f1.forEach((v,k)=>{const h=v*260*seg(u,.2+k*.12,.8,outBack);rect(c,x0+k*110,base-h,80,h,STAGE_COL[k],{r:6});T(c,STAGES[k],x0+k*110+40,base+34,{size:24,weight:'bold',align:'center',color:STAGE_COL[k],alpha:fin(u,.2)})});
  const m=f1.reduce((a,b)=>a+b)/5,ma=fin(u,2);poly(c,[[x0-10,base-m*260],[x0+550,base-m*260]],{stroke:P.ink,width:3,dash:[10,6],alpha:ma});T(c,'macro-F1',x0+560,base-m*260+8,{size:24,alpha:ma});
  EQ(c,'\\operatorname{MacroF1}=\\frac15\\sum_{c=0}^{4}F1_c',1350,280,{size:40,p:seg(u,1,1.2)});
  // people
  const py=770;for(let s=0;s<20;s++){const v=.55+.35*rnd(s*13),a=fin(u,6.2+s*.05);const x=200+s*72;rect(c,x,py-v*170,48,v*170,s%2?P.cyan:P.violet,{r:5,alpha:a});dot(c,x+24,py+26,11,s%2?P.cyan:P.violet,a)}
  T(c,'one macro-F1 per participant (bars hypothetical)',200,py-200,{size:22,color:P.muted,alpha:fin(u,6.2)});
  EQ(c,'\\operatorname{MeanSubjectMF1}=\\frac{1}{20}\\sum_{s=1}^{20}\\Big[\\frac15\\sum_{c}F1_{s,c}\\Big]',1350,470,{size:34,color:P.amber,p:seg(u,7,1.4)});
  pill(c,'≠ macro-F1 of the pooled matrix',1350,600,{size:24,color:P.coral,alpha:fin(u,9)});
}},
// ---------------------------------------------------------------- CH7 FINDINGS
{id:'nights',ch:7,tag:'MEAS',dur:12,cap:[[0,'The baseline collapsed on particular test nights. One night was predicted entirely as a single class.'],[6,'Four diagnostic rounds found no confirmed pairing, timing, channel or label-alignment defect.']],
draw(c,u){
  const sel=FACTS.comparison.runs.base.selected_nights,ids=['SC4021','SC4062','SC4142','SC4051','SC4101'];
  const w=new World({box:[96,170,1728,600],center:[0,0,1.6],phi:1.1,theta:-1.5+.15*Math.sin(u/5),frameHeight:6.4});w.floor({size:6,alpha:.35});
  ids.forEach((id,i)=>{const v=sel[id].accuracy,col=v<.5?P.coral:P.cyan;w.grow([(i-2)*2.2,0,0],[1.2,1.0,v*4.2],col,seg(u,.3+i*.25,1.2,outBack))});w.draw(c);
  ids.forEach((id,i)=>{const v=sel[id].accuracy,p=w.px([(i-2)*2.2,0,v*4.2*seg(u,.3+i*.25,1.2,cubic)]),b=w.px([(i-2)*2.2,0,0]);T(c,pct(v*seg(u,.3+i*.25,1.6,outExpo))+'%',p[0],p[1]-24,{size:38,weight:'bold',align:'center',color:v<.5?P.coral:P.cyan,alpha:fin(u,.6+i*.25)});T(c,id,b[0],b[1]+60,{size:26,align:'center',alpha:fin(u,.6+i*.25)})});
  T(c,'baseline accuracy on selected test nights',960,820,{size:24,color:P.muted,align:'center',alpha:fin(u,1)});
}},
{id:'results',ch:7,tag:'MEAS',dur:14,cap:[[0,'Subject-mean macro-F1: baseline 56.42%, R1 74.86%, full-night sensitivity 71.84%. Pooled accuracy rose from 65.00% to 80.99%.'],[7,'R1 changed normalization and retrained the weights together, and it was chosen after seeing the baseline failures. It is post-hoc.']],
draw(c,u){
  const w=new World({box:[96,150,1150,650],center:[0,0,1.7],phi:1.12,theta:lerp(-1.75,-1.3,seg(u,0,14,smooth)),frameHeight:6.2});w.floor({size:5,alpha:.35});
  RUNS.forEach((k,i)=>w.grow([(i-1)*2.4,0,0],[1.4,1.2,FACTS.test[k].subject_mf1.point*4.6],RCOL[i],seg(u,.3+i*.5,1.4,outBack)));w.draw(c);
  RUNS.forEach((k,i)=>{const v=FACTS.test[k].subject_mf1.point,g=seg(u,.3+i*.5,1.4,cubic),p=w.px([(i-1)*2.4,0,v*4.6*g]),b=w.px([(i-1)*2.4,0,0]);
    T(c,pct(v*seg(u,.3+i*.5,2,outExpo))+'%',p[0],p[1]-26,{size:44,weight:'bold',align:'center',color:RCOL[i],alpha:fin(u,.6+i*.5)});T(c,RLAB[i],b[0],b[1]+56,{size:28,align:'center',weight:'med',alpha:fin(u,.6+i*.5)});
    T(c,'accuracy '+pct(FACTS.test[k].pooled_accuracy.point)+'%',b[0],b[1]+90,{size:22,align:'center',color:P.muted,alpha:fin(u,2+i*.3)})});
  T(c,'subject-mean macro-F1 (test, 20 participants)',600,215,{size:24,color:P.muted,align:'center',alpha:fin(u,.2)});
  const d=FACTS.differences['r1-minus-base'].per_subject_mean_macro_f1;
  panel(c,1290,260,500,190,{title:'R1 − baseline',col:P.cyan,alpha:fin(u,4)});T(c,'+'+pct(d.point)+' points',1540,370,{size:44,weight:'bold',color:P.cyan,align:'center',alpha:fin(u,4.2)});T(c,`95% CI ${pct(d.ci95[0])} to ${pct(d.ci95[1])}`,1540,415,{size:22,color:P.muted,align:'center',alpha:fin(u,4.4)});
  [['post-hoc choice',P.coral],['normalization + retraining together',P.amber],['offline · transductive',P.violet]].forEach(([s,col],i)=>pill(c,s,1540,530+i*80,{size:24,color:col,alpha:fin(u,7.4+i*.5)}));
}},
{id:'fullnight',ch:7,tag:'CODE',dur:12,cap:[[0,'The full-night sensitivity run takes statistics from the complete recording, without hypnogram-based trimming.'],[6,'Training and scored epochs stay exactly the same. Only the range used for the statistics changes. It is still transductive.']],
draw(c,u){
  const x0=200,cw=37,n=40,keep=[6,33];const rows=[['retained epochs (scored)',P.violet,i=>i>=keep[0]&&i<keep[1],.3],['R1 statistics range',P.cyan,i=>i>=keep[0]&&i<keep[1],2],['full-night statistics range',P.amber,()=>true,4.2]];
  rows.forEach(([l,col,on,t],r)=>{const y=290+r*170;T(c,l,x0,y-22,{size:26,color:col,alpha:fin(u,t),weight:'med'});for(let i=0;i<n;i++){const a=fin(u,t+i*.02,.4);rect(c,x0+i*cw,y,cw-5,56,on(i)?col:'#152238',{r:5,alpha:a})}});
  const b=fin(u,1.2);poly(c,[[x0+keep[0]*cw,268+520],[x0+keep[0]*cw,252+60]],{stroke:P.dim,width:1.5,dash:[6,6],alpha:b});poly(c,[[x0+keep[1]*cw-5,268+520],[x0+keep[1]*cw-5,252+60]],{stroke:P.dim,width:1.5,dash:[6,6],alpha:b});
  T(c,'start of PSG',x0,810,{size:22,color:P.muted,alpha:fin(u,4.2)});T(c,'end of PSG',x0+n*cw,810,{size:22,color:P.muted,align:'right',alpha:fin(u,4.2)});
  pill(c,'MF1 71.84%   ·   accuracy 79.10%',1500,200,{size:26,color:P.amber,alpha:fin(u,7)});
}},
{id:'bootstrap',ch:7,tag:'MEAS',dur:15,cap:[[0,'A paired bootstrap redraws the 20 participants with replacement, 1,000 times, using the same draw for both runs.'],[7,'Full-night minus R1: −3.02 points, 95% interval −7.12 to +1.22. It crosses zero: not enough evidence of a difference, and not proof they are equal.']],
draw(c,u){
  const round=Math.floor(Math.max(0,u-1)/.9);
  for(let s=0;s<20;s++){const a=fin(u,.1+s*.03);dot(c,200+s*34,240,12,s%2?P.cyan:P.violet,a);}
  T(c,'participants',200,200,{size:22,color:P.muted,alpha:fin(u,.1)});
  if(u>1){const counts={};for(let j=0;j<20;j++){const pick=Math.floor(rnd(round*31+j*7)*20);counts[pick]=(counts[pick]||0)+1;const d=seg(u,1+round*.9+j*.02,.35,cubic);dot(c,lerp(200+pick*34,200+j*34,d),lerp(240,330,d),12,pick%2?P.cyan:P.violet,1);if(counts[pick]>1)dot(c,200+j*34,330,17,P.amber,.35*d)}
    T(c,`resample ${Math.min(1000,round+1)}`,200,390,{size:22,color:P.amber,alpha:fin(u,1)});}
  // histogram (illustrative shape, interval from archive)
  const d=FACTS.differences['fullnight-minus-r1'].per_subject_mean_macro_f1;const lo=d.ci95[0]*100,hi=d.ci95[1]*100,pt=d.point*100;
  const ax={X:v=>1000+(v+10)/14*760};const by=700,bins=28,shown=Math.floor(bins*seg(u,2,5,smooth));const sd=(hi-lo)/3.92;
  for(let b=0;b<shown;b++){const v=-10+(b+.5)*14/bins,h=260*Math.exp(-(((v-pt)/sd)**2)/2);rect(c,ax.X(v-.25),by-h,760/bins-3,h,(v<lo||v>hi)?'#2A3A55':rgba(P.cyan,.75),{r:2})}
  poly(c,[[ax.X(-10),by],[ax.X(4),by]],{stroke:P.line,width:2,alpha:fin(u,2)});for(let v=-10;v<=4;v+=2)T(c,String(v),ax.X(v),by+34,{size:20,color:P.muted,align:'center',alpha:fin(u,2)});
  T(c,'Δ subject-mean MF1 (points)',1380,by+74,{size:22,color:P.muted,align:'center',alpha:fin(u,2)});
  const z=fin(u,6.4);poly(c,[[ax.X(0),by-360],[ax.X(0),by+8]],{stroke:P.violet,width:3,alpha:z});T(c,'zero',ax.X(0),by-372,{size:22,color:P.violet,align:'center',alpha:z});
  const ci=fin(u,7.4);poly(c,[[ax.X(lo),by-300],[ax.X(hi),by-300]],{stroke:P.amber,width:6,alpha:ci});for(const v of [lo,hi])poly(c,[[ax.X(v),by-318],[ax.X(v),by-282]],{stroke:P.amber,width:4,alpha:ci});dot(c,ax.X(pt),by-300,11,P.white,ci,12);
  T(c,lo.toFixed(2),ax.X(lo),by-330,{size:26,weight:'bold',color:P.amber,align:'center',alpha:ci});T(c,'+'+hi.toFixed(2),ax.X(hi)+20,by-330,{size:26,weight:'bold',color:P.amber,align:'center',alpha:ci});T(c,pt.toFixed(2),ax.X(pt),by-262,{size:26,weight:'bold',align:'center',alpha:ci});
  T(c,'histogram shape illustrative · interval and point from the archive',1380,230,{size:20,color:P.dim,align:'center',alpha:fin(u,2.4)});
  EQ(c,'\\Delta^{(b)}=M^{(b)}_{\\text{full}}-M^{(b)}_{R1}',540,560,{size:34,p:seg(u,3,1.2)});
  EQ(c,'\\big[Q_{0.025}(\\Delta^{(b)}),\\ Q_{0.975}(\\Delta^{(b)})\\big]',540,670,{size:32,color:P.amber,p:seg(u,7.6,1.2)});
  pill(c,'seed 20261011',540,780,{size:22,color:P.muted,alpha:fin(u,4),weight:'mono'});
}},
{id:'folds',ch:7,tag:'MEAS',dur:11,cap:[[0,'Ten held-out folds tell a less tidy story. R1 improved pooled macro-F1 in all ten folds, but folds 0 and 9 stay comparatively weak.'],[6,'Each fold pools only two test participants, and training sets overlap, so folds are not independent samples.']],
draw(c,u){
  const ax=axes(c,{x:220,y:220,w:1100,h:520,xmin:-.4,xmax:9.4,ymin:.3,ymax:.9,xt:[0,1,2,3,4,5,6,7,8,9],yt:[.3,.5,.7,.9],fmtY:v=>Math.round(v*100)+'%',xl:'fold',alpha:fin(u,0)});
  RUNS.forEach((k,j)=>{const pts=FACTS.comparison.runs[k].folds.map(f=>[ax.X(f.fold),ax.Y(f.macro_f1)]);const p=seg(u,.6+j*.9,2.2);drawOn(c,pts.flatMap((q,i)=>i?[[lerp(pts[i-1][0],q[0],.5),lerp(pts[i-1][1],q[1],.5)],q]:[q]),p,{stroke:RCOL[j],width:3.4,head:false});pts.forEach((q,i)=>dot(c,q[0],q[1],7,RCOL[j],fin(u,.6+j*.9+i*.2)))});
  for(const f of [0,9]){const v=FACTS.comparison.runs.r1.folds[f].macro_f1;rect(c,ax.X(f)-30,ax.Y(v)-30,60,60,null,{stroke:P.coral,sw:2.5,r:30,alpha:fin(u,4.8)})}
  RLAB.forEach((l,i)=>{const a=fin(u,.6+i*.9);poly(c,[[1420,330+i*70],[1470,330+i*70]],{stroke:RCOL[i],width:5,alpha:a});T(c,l,1490,339+i*70,{size:26,alpha:a})});
  T(c,'pooled macro-F1 per test fold',1420,260,{size:22,color:P.muted,alpha:fin(u,.3)});
}},
{id:'recall',ch:7,tag:'MEAS',dur:11,cap:[[0,'Per-class recall shows which stages are recovered. N1 is still the hardest: 44.7% with R1, 39.5% with full-night.'],[6,'Better overall numbers do not solve every class.']],
draw(c,u){
  const ax=axes(c,{x:220,y:220,w:1200,h:500,xmin:0,xmax:5,ymin:0,ymax:1,yt:[0,.25,.5,.75,1],fmtY:v=>Math.round(v*100)+'%',alpha:fin(u,0)});
  STAGES.forEach((k,i)=>{const bx=ax.X(i)+40;RUNS.forEach((r,j)=>{const v=FACTS.test[r].recall[i],h=(ax.Y(0)-ax.Y(v))*seg(u,.4+i*.2+j*.1,1,outBack);rect(c,bx+j*52,ax.Y(0)-h,44,h,RCOL[j],{r:4,alpha:i===1||u<5.6?1:.5});if(i===1||u<5.6)T(c,pct(v,1),bx+j*52+22,ax.Y(0)-h-10,{size:19,align:'center',alpha:fin(u,1+i*.2)})});
    T(c,k,bx+76,ax.Y(0)+38,{size:28,align:'center',weight:'bold',color:STAGE_COL[i],alpha:fin(u,.3)})});
  if(u>5.6)rect(c,ax.X(1)+24,ax.Y(.6),190,ax.Y(0)-ax.Y(.6)+60,null,{stroke:P.coral,sw:3,r:12,alpha:fin(u,5.6)});
  RLAB.forEach((l,i)=>{const a=fin(u,.4);poly(c,[[1500,330+i*70],[1550,330+i*70]],{stroke:RCOL[i],width:8,alpha:a});T(c,l,1570,339+i*70,{size:26,alpha:a})});
}},
// ---------------------------------------------------------------- CH8 EVIDENCE BOUNDARY
{id:'pilots',ch:8,tag:'MEAS',dur:12,cap:[[0,'Three small validation-only pilots tried to fix N1: logit adjustment, head-only retraining and a sequence decoder.'],[6,'None reached the locked +1.00 point macro-F1 gate. All were rejected and the original settings were kept.']],
draw(c,u){
  const sets=[['Logit adjustment',.25,'logit'],['Head-only retraining','candidate','head_cached_FP32'],['Sequence decoder',.1,'decoder']];const zero=900,sc=300;
  poly(c,[[zero,220],[zero,700]],{stroke:P.violet,width:2,alpha:fin(u,0)});T(c,'0',zero,740,{size:22,color:P.muted,align:'center',alpha:fin(u,0)});
  const g=fin(u,.8);poly(c,[[zero+sc,220],[zero+sc,700]],{stroke:P.green,width:3,dash:[10,8],alpha:g});T(c,'+1.00 gate',zero+sc,205,{size:26,color:P.green,align:'center',weight:'bold',alpha:g});
  sets.forEach(([l,s,id],i)=>{const b=FACTS.pilots.find(p=>p.pilot===id&&(p.setting===0||p.setting==='baseline')),cd=FACTS.pilots.find(p=>p.pilot===id&&p.setting===s);const d=(cd.mf1-b.mf1)*100,y=300+i*150,p=seg(u,1.4+i*.6,1,outBack);
    T(c,l,560,y+10,{size:30,align:'right',alpha:fin(u,1.2+i*.6)});rect(c,Math.min(zero,zero+d*sc*p),y-22,Math.abs(d*sc*p),44,d>=0?P.cyan:P.coral,{r:6});
    T(c,(d>=0?'+':'')+d.toFixed(2),zero+d*sc+(d>=0?18:-18),y+12,{size:30,weight:'bold',color:d>=0?P.cyan:P.coral,align:d>=0?'left':'right',alpha:fin(u,2+i*.6)});
    const st=seg(u,6.4+i*.4,.5,outBack);if(st>0){c.save();c.translate(1560,y);c.rotate(-.12);c.scale(clamp(st,0,1.3),clamp(st,0,1.3));rect(c,-110,-30,220,60,null,{stroke:P.coral,sw:4,r:8});T(c,'REJECTED',0,12,{size:30,weight:'bold',color:P.coral,align:'center'});c.restore()}});
  T(c,'validation-only change in macro-F1 (points)',zero,800,{size:24,color:P.muted,align:'center',alpha:fin(u,.5)});
}},
{id:'audit',ch:8,tag:'MEAS',dur:12,cap:[[0,'A provenance audit checked 78 participants: 30 had documented development exposure and 48 have unresolved history.'],[6.5,'Zero are certified independent. Unresolved does not mean unused, so there is no clean external test yet.']],
draw(c,u){
  const w=new World({box:[96,200,1728,560],center:[0,0,.3],phi:1.0,theta:-1.45+.2*Math.sin(u/5),frameHeight:6.6});w.floor({size:7,alpha:.3});
  for(let i=0;i<78;i++){const g=seg(u,.2+i*.025,.5,outBack);w.grow([(i%13-6)*.68,(Math.floor(i/13)-2.5)*.7,0],[.48,.5,.42],i<30?P.cyan:P.amber,g)}w.draw(c);
  T(c,String(Math.round(30*seg(u,1,2,outExpo))),520,250,{size:76,weight:'bold',color:P.cyan,align:'center',alpha:fin(u,1)});T(c,'documented exposure',520,290,{size:24,color:P.muted,align:'center',alpha:fin(u,1)});
  T(c,String(Math.round(48*seg(u,1.6,2,outExpo))),1400,250,{size:76,weight:'bold',color:P.amber,align:'center',alpha:fin(u,1.6)});T(c,'unresolved history',1400,290,{size:24,color:P.muted,align:'center',alpha:fin(u,1.6)});
  T(c,'0',960,260,{size:96,weight:'bold',color:P.coral,align:'center',alpha:fin(u,6.6),glow:20});T(c,'certified independent',960,300,{size:26,color:P.coral,align:'center',alpha:fin(u,6.8)});
}},
{id:'limits',ch:8,tag:'CONC',dur:14,cap:[[0,'Read every number within these limits: post-hoc selection, one model seed, and normalization that sees each test night.'],[7,'The protocol differs from the original SST paper. This is neither a replication nor clinical validation, nor an online system.']],
draw(c,u){
  const cards=[['Post-hoc selection','R1 chosen after baseline test failures',P.coral],['One model seed','training randomness not sampled',P.violet],['Offline · transductive','normalization uses each evaluated night',P.amber],['Different protocol','subject-wise folds ≠ the paper\'s split',P.blue],['Conditional intervals','bootstrap omits selection & seed uncertainty',P.cyan],['Not clinical','no diagnosis, no online prediction',P.green]];
  cards.forEach(([t,s,col],i)=>{const x=200+(i%3)*520,y=230+Math.floor(i/3)*280,f=seg(u,.3+i*.35+(i>2?3.4:0),.7,cubic);const sx=Math.abs(Math.cos((1-f)*Math.PI/2));if(f<=0)return;
    c.save();c.translate(x+230,y+110);c.scale(Math.max(.02,f),1);c.translate(-(x+230),-(y+110));panel(c,x,y,460,220,{col});rect(c,x,y,8,220,col,{r:4});T(c,t,x+40,y+90,{size:34,weight:'bold',color:col});wrap(c,s,380,24).forEach((l,k)=>T(c,l,x+40,y+140+k*34,{size:24,color:P.muted}));c.restore()});
}},
{id:'close',ch:8,tag:'CONC',dur:20,cap:[[0,'Sampling, STFT, log, normalization, CNN, BiGRU, loss, AdamW, averaging, metrics, bootstrap: one connected system.'],[7,'R1 scored higher in this cohort, and we know exactly which data, transforms and averaging produced it.'],[13,'Next gate: a locked protocol on genuinely independent participants, after human approval.']],
draw(c,u){
  const nodes=['Sampling','STFT','log |X|','Normalize','CNN','BiGRU','Logits','Loss','AdamW','Averaging','Metrics','Bootstrap'];
  const cx=960,cy=440,R=300;
  const pos=nodes.map((_,i)=>{const a=-Math.PI/2+i/nodes.length*Math.PI*2;return [cx+Math.cos(a)*R*1.75,cy+Math.sin(a)*R*.9]});
  for(let i=0;i<nodes.length;i++){const j=(i+1)%nodes.length;if(j===0)continue;const a=seg(u,.3+i*.25,.6);poly(c,[pos[i],[lerp(pos[i][0],pos[j][0],a),lerp(pos[i][1],pos[j][1],a)]],{stroke:P.line,width:2.5})}
  const k=(u*1.6)%(nodes.length-1),i0=Math.floor(k),fr=k-i0;if(u>3.4)dot(c,lerp(pos[i0][0],pos[i0+1][0],fr),lerp(pos[i0][1],pos[i0+1][1],fr),9,P.amber,1,18);
  nodes.forEach((n,i)=>{const a=seg(u,.2+i*.25,.6,outBack);if(a<=0)return;const col=[P.cyan,P.cyan,P.cyan,P.amber,P.violet,P.violet,P.violet,P.coral,P.coral,P.green,P.green,P.green][i];c.save();c.translate(pos[i][0],pos[i][1]);c.scale(clamp(a,0,1.2),clamp(a,0,1.2));pill(c,n,0,0,{size:24,color:col});c.restore()});
  const fa=fin(u,7);T(c,'R1 scored higher in this evaluated cohort',cx,cy-20,{size:40,weight:'bold',align:'center',alpha:fa});
  T(c,'Baseline 56.42%  ·  R1 74.86%  ·  Full-night 71.84%',cx,cy+30,{size:28,align:'center',color:P.cyan,alpha:fin(u,7.6)});
  T(c,'with a clear evidence boundary',cx,cy+76,{size:26,align:'center',color:P.muted,alpha:fin(u,8.2)});
  T(c,'Data: Sleep-EDF Expanded 1.0.0 · Kemp et al. (2000) · Goldberger et al. (2000) · PhysioNet · ODC-By 1.0',cx,850,{size:20,color:P.dim,align:'center',alpha:fin(u,9)});
}},
];
