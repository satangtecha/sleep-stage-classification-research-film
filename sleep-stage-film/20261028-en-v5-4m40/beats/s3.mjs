// Sections 5-6 (new and merged shots): E1-E4 evidence, L1-L3 limits and summary
import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,mixCol,T,poly,dot,rect,arrow,typed,seg,measure,eeg,wavePts,EQ} from '../lib.mjs';
import {HYPNO,n1Sim,vennDistance} from '../shared.mjs';
import {NightStrip,tileX,stageColor} from '../components/strip.mjs';
import {Bracket,Pill} from '../components/misc.mjs';
import {NumberCard,NumText,Stamp,Padlock,fmtNum} from '../components/cards.mjs';
import {Person} from '../components/people.mjs';
import {surface,bevel,glowRect,glowCircle} from '../light.mjs';
import {fact,factRaw,derived} from '../facts.mjs';
import {act3} from './act3.mjs';
import {act4} from './act4.mjs';
const S={};const E=(...ids)=>ids.map(id=>({id,in:0,out:99}));
const PINK='#FF8FA3',GRN='#7EE0A1',AMB='#FFC46B',SL=P.slate;
const fm=(p,o={})=>fact(p,o);

// ================================================================ E1: the baseline
const BASE='test.base',FOLDS=()=>factRaw('comparison.runs.base.folds');
S['E1.S1']={tag:'MEAS',elements:E('cardL','cardS','bars','labels'),draw(c,us,k){
  const cA=k.cue('E1.c1','Accuracy'),cF=k.cue('E1.c1','Folds swing');
  const cp=cubic((us-.1)/.7);
  NumberCard(c,{k,el:'cardL',x:120+(1-cp)*-160,y:230,size:'L',label:'Macro-F1 · baseline',text:fm(BASE+'.subject_mf1.point',{mul:100}),color:P.ink,alpha:smooth(cp*2)});
  T(c,`95% interval ${fm(BASE+'.subject_mf1.ci95',{idx:0,mul:100})} to ${fm(BASE+'.subject_mf1.ci95',{idx:1,mul:100})}`,148,610,{size:26,color:P.muted,alpha:smooth((us-1.4)/.5)});
  const sa=cubic((us-cA+.2)/.5);
  NumberCard(c,{k,el:'cardS',x:120,y:650,size:'S',label:'Accuracy',text:fm(BASE+'.pooled_accuracy.point',{mul:100}),color:P.ink,alpha:smooth(sa*3),dx:(1-sa)*-60});
  // fold bars
  const F=FOLDS(),x0=790,w=1010,y0=760,H=470,bw=64,gap=(w-10*bw)/9;
  T(c,'Macro-F1 by fold · 2 test people each',x0+w/2,262,{size:28,weight:'med',color:P.muted,align:'center',alpha:smooth((us-cF+1.2)/.5)});
  [0,.25,.5,.75,1].forEach(v=>{const y=y0-v*H;poly(c,[[x0-10,y],[x0+w+10,y]],{stroke:P.grid,width:1.5,alpha:smooth((us-cF+1.2)/.5)});T(c,(v*100)+'%',x0-22,y+8,{size:20,color:P.dim,align:'right',alpha:smooth((us-cF+1.2)/.5)})});
  const mn=F.reduce((a,b)=>b.macro_f1<a.macro_f1?b:a),mx=F.reduce((a,b)=>b.macro_f1>a.macro_f1?b:a);
  F.forEach((f,i)=>{const t=cubic((us-cF+1-i*.07)/.6),h=f.macro_f1*H*t,x=x0+i*(bw+gap),col=f===mn?PINK:f===mx?GRN:P.blue;
    if(h>0)surface(c,[x,y0-h,bw,h],col,{level:'E1',r:6,gradient:.06});T(c,'F'+f.fold,x+bw/2,y0+30,{size:20,color:P.dim,align:'center',alpha:smooth(t*2)})});
  const la=smooth((us-cF-.9)/.5);
  [[mn,PINK],[mx,GRN]].forEach(([f,col])=>{const i=F.indexOf(f),x=x0+i*(bw+gap)+bw/2,y=y0-f.macro_f1*H;
    T(c,derived('fold.'+(f===mn?'min':'max'),f.macro_f1,(100*f.macro_f1).toFixed(2)+'%'),x,y-16,{size:28,weight:'bold',color:col,align:'center',alpha:la})})}};
// E1.S2: three failing nights (shared lane drawing from the v4.1 shot, cues re-pointed to E1.c2)
S['E1.S2']={tag:'MIX',elements:E('lanes','nums','note'),draw(c,us,k){act3['B7.S3'].draw(c,us,k);
  const a=smooth((us-k.cue('E1.c2','The average hid them')+.3)/.4);
  if(a>0){surface(c,[560,812,800,60],rgba(PINK,.08),{level:'E1',r:30,gradient:0,alpha:a});c.save();c.globalAlpha*=a;c.strokeStyle=rgba(PINK,.7);c.lineWidth=2;c.beginPath();c.roundRect(560,812,800,60,30);c.stroke();c.restore();
    T(c,'The average hid them',960,853,{size:32,weight:'bold',color:'#FF8F9B',align:'center',alpha:a})}}};

// ================================================================ E2: R1 = a ruler per night
const curve=(n,mu,amp,seed)=>Array.from({length:n},(_,i)=>{const u=i/(n-1);return mu+amp*(.55*Math.sin(u*11+seed)+.30*Math.sin(u*27+seed*2.1)+.15*Math.sin(u*53+seed*.7))});
const NA={mu:.28,amp:.07,col:P.cyan,seed:1},NB_={mu:.72,amp:.12,col:P.violet,seed:2.6};
const PW2=840,PY2=250,PH2=570,PLH=300;
function rulerPanel(c,k,us,{x,title,col,sub,mode,reveal,bandA,persons,norm,curvesA}){
  surface(c,[x,PY2,PW2,PH2],'#0E1C30',{level:'E2',r:18});
  T(c,title,x+PW2/2,PY2+52,{size:32,weight:'bold',color:col,align:'center'});
  const px=x+50,pw=PW2-100,py=PY2+110,ph=PLH,N=140;
  poly(c,[[px,py+ph],[px+pw,py+ph]],{stroke:P.line,width:2});
  const Y=v=>py+ph-v*ph,X=i=>px+i/(N-1)*pw;
  // bands
  if(mode==='shared'&&bandA>0){const b=[.5,.14];rect(c,px,Y(b[0]+b[1]),pw,ph*b[1]*2,rgba(P.cyan,.12*bandA),{r:6});[b[0]+b[1],b[0]-b[1]].forEach(v=>poly(c,[[px,Y(v)],[px+pw,Y(v)]],{stroke:rgba(P.cyan,.7*bandA),width:2,dash:[9,7]}));
    poly(c,[[px,Y(.5)],[px+pw,Y(.5)]],{stroke:rgba(P.cyan,.8*bandA),width:2.5});T(c,'the one ruler',px+pw-10,Y(b[0])+8,{size:22,weight:'med',color:P.cyan,align:'right',alpha:bandA})}
  if(mode==='own'&&bandA>0){[[NA,.09],[NB_,.14]].forEach(([n,hw])=>{const m=lerp(n.mu,.5,norm),h=lerp(hw,.14,norm);rect(c,px,Y(m+h),pw,ph*h*2,rgba(n.col,.13*bandA),{r:6});[m+h,m-h].forEach(v=>poly(c,[[px,Y(v)],[px+pw,Y(v)]],{stroke:rgba(n.col,.75*bandA),width:2,dash:[9,7]}));
    poly(c,[[px,Y(m)],[px+pw,Y(m)]],{stroke:rgba(n.col,.85*bandA),width:2.5})})}
  if(reveal>0)[[NA,.09],[NB_,.14]].forEach(([n,hw])=>{const cv=curve(N,n.mu,n.amp,n.seed);
    const pts=cv.map((v,i)=>{const vv=mode==='own'?lerp(v,.5+(v-n.mu)*(.14/hw)*1.0*0+ (v-n.mu)*(.55/ (n.amp*1.0))*0,0):v;
      const z=mode==='own'?lerp(v,.5+(v-n.mu)*(.12/n.amp),norm):v;return [X(i),Y(z)]});
    c.save();c.globalAlpha*=reveal;poly(c,pts,{stroke:n.col,width:2.8});c.restore()});
  T(c,sub,x+PW2/2,PY2+PH2-40,{size:25,weight:'med',color:P.muted,align:'center'});
  // night labels
  if(reveal>0){dot(c,x+60,PY2+88,6,NA.col,reveal);T(c,'Night A · weak signal',x+76,PY2+95,{size:21,color:P.muted,alpha:reveal});dot(c,x+PW2-250,PY2+88,6,NB_.col,reveal);T(c,'Night B · strong signal',x+PW2-234,PY2+95,{size:21,color:P.muted,alpha:reveal})}
  if(persons>0)for(let i=0;i<16;i++)Person(c,{k,el:'persons',x:x+60+i*45.5,y:PY2+PH2-118,s:19,state:'train',alpha:persons*smooth((persons*1.8-i*.05)),sc:.8+.2*persons})}
S['E2.S1']={tag:'CONCEPT',elements:E('panelL','panelR','persons','formula'),draw(c,us,k){
  const cZ=k.cue('E2.c1','already z-scored'),cOne=k.cue('E2.c1','one ruler'),c16=k.cue('E2.c1','16 training people'),cR=k.cue('E2.c1','R1 gives'),cOwn=k.cue('E2.c1','its own ruler');
  T(c,'per frequency:   z = (x − μ) / σ',960,205,{size:32,weight:'med',color:P.ink,align:'center',alpha:smooth((us-cZ+.2)/.4)});
  const lp=smooth((us-.3)/.5);c.save();c.globalAlpha*=lp;
  rulerPanel(c,k,us,{x:104,title:'Baseline: one shared ruler',col:P.muted,sub:'every night is measured by the same μ and σ',mode:'shared',reveal:smooth((us-cZ+.1)/.5),bandA:smooth((us-cOne+.1)/.5),persons:smooth((us-c16+.1)/.6)});c.restore();
  c.save();c.globalAlpha*=lp;
  rulerPanel(c,k,us,{x:976,title:'R1: a ruler per night',col:P.cyan,sub:'each night uses its own μ and σ',mode:'own',reveal:smooth((us-cR+.1)/.5),bandA:smooth((us-cOwn+.4)/.5),persons:0,norm:cubic((us-cOwn-.5)/1.8)});c.restore();
  const ta=smooth((us-c16-.8)/.5);T(c,'μ, σ from the 16 training people',104+PW2/2,PY2+PH2-68,{size:22,color:P.blue,align:'center',alpha:ta*smooth((us-c16)/.4)})}};
S['E2.S2']={tag:'MEAS',elements:E('cardL','cardR','arrows','gain'),draw(c,us,k){act3['B8.S3'].draw(c,us,k);
  const ga=k.cue('E2.c2','Gain'),a=smooth((us-ga+.3)/.4);
  if(a>0){const D='differences.r1-minus-base.per_subject_mean_macro_f1';c.save();c.globalAlpha*=a;surface(c,[300,812,1320,66],rgba(GRN,.08),{level:'E1',r:33,gradient:0});c.strokeStyle=rgba(GRN,.7);c.lineWidth=2;c.beginPath();c.roundRect(300,812,1320,66,33);c.stroke();
    T(c,`Gain over baseline ${fm(D+'.point',{mul:100,signed:true})} points · 95% interval ${fm(D+'.ci95',{idx:0,mul:100})} to ${fm(D+'.ci95',{idx:1,mul:100})} · excludes zero`,960,855,{size:29,weight:'bold',color:GRN,align:'center'});c.restore()}}};
S['E2.S3']={tag:'MIX',elements:E('lanes','nums'),draw(c,us,k){act3['B8.S4'].draw(c,us,k)}};

// ================================================================ E3: the catch, then the sensitivity check
const SC0=12,SC1=84,EXT=92;
function eye(c,x,y,s=1,a=1){c.save();c.globalAlpha*=a;c.translate(x,y);c.scale(s,s);c.strokeStyle=P.muted;c.lineWidth=3;c.beginPath();c.moveTo(-26,0);c.quadraticCurveTo(0,-26,26,0);c.quadraticCurveTo(0,26,-26,0);c.stroke();dot(c,0,0,8,P.muted);c.restore()}
S['E3.S1']={tag:'CODE',elements:E('strip','ruler','pills','stamps'),draw(c,us,k){
  const cR=k.cue('E3.c1','reads'),cU=k.cue('E3.c1','unlabeled'),cC=k.cue('E3.c1','chosen after'),cO=k.cue('E3.c1','offline'),cP=k.cue('E3.c1','post-hoc');
  const scan=clamp((us-cR+.1)/2.4);
  NightStrip(c,{k,el:'strip',y:400,appear:i=>(us-i*.004)/.25,mode:i=>i<SC0||i>=EXT?'dark':i>=SC1?'unscored':(i<SC0+(SC1-SC0)*scan||us<cR-.1?'on':'unscored')});
  const x0=tileX(SC0),x1=tileX(EXT),p=cubic((us-cR+.2)/.9);
  Bracket(c,{k,el:'ruler',x0,x1:lerp(x0,x1,p),y:372,dir:1,p:1,col:P.cyan,label:p>.9?"This night's own ruler":null,lsize:28,tip:12,width:4});
  eye(c,(x0+x1)/2,300,1.3,smooth((us-cR)/.5));
  const sx=tileX(SC0+(SC1-SC0)*scan);if(scan>0&&scan<1)glowCircle(c,sx,432,8,P.cyan,{blur:16,alpha:.8});
  T(c,'Reads the scored span of the test night · no labels',960,540,{size:30,weight:'med',color:AMB,align:'center',alpha:smooth((us-cU+.2)/.5)});
  const s1=smooth((us-cC+.2)/.4),s2=smooth((us-cC-.6)/.4);Pill(c,{k,el:'pills',x:560,y:600,w:330,h:50,text:'1  Baseline fails',color:PINK,size:26,alpha:s1});
  if(s2>0){poly(c,[[900,625],[1010,625]],{stroke:P.muted,width:2,alpha:s2});Pill(c,{k,el:'pills',x:1020,y:600,w:300,h:50,text:'2  R1 chosen',color:GRN,size:26,alpha:s2})}
  Stamp(c,{k,el:'stamps',text:'OFFLINE',cx:700,cy:780,p:(us-cO+.1)/.5,color:AMB,rot:-5,seed:1,scale:.85});Stamp(c,{k,el:'stamps',text:'POST-HOC',cx:1260,cy:790,p:(us-cP+.1)/.5,color:AMB,rot:4,seed:2,scale:.85})}};
S['E3.S2']={tag:'MEAS',elements:E('strip','brackets','card','axis','point'),draw(c,us,k){
  const sw=k.cue('E3.c2','−3.02')-.5,f=smooth((us-sw)/.6);
  if(f<1){c.save();c.globalAlpha*=1-f;act4['B10.S2'].draw(c,us,k);c.restore()}
  if(f>0){c.save();c.globalAlpha*=f;act4['B10.S3'].draw(c,Math.max(0,us-sw-.2),k);c.restore()}}};

// ================================================================ E4: N1, then three rejected fixes
const PIL=['Logit adjustment','Head-only retraining','Sequence decoder'];
const rej=(c,k,us,{t0=[.8,1.6,2.4],shrink=0})=>{PIL.forEach((n,i)=>{const x=150+i*560,y=lerp(400,700,shrink),h=lerp(160,70,shrink);surface(c,[x,y,500,h],'#10213A',{level:'E2',r:14});T(c,n,x+250,y+h/2+(h>100?-4:10),{size:lerp(34,28,shrink),weight:'bold',align:'center'});
  Stamp(c,{k,el:'stamps',text:'REJECTED',cx:x+250,cy:y+h/2+(h>100?44:0),p:(us-t0[i])/.5,color:PINK,scale:.55,rot:i%2?4:-4,seed:i+3})})};
S['E4.S1']={tag:'MEAS',elements:E('venn','nums','cards','stamps','label'),draw(c,us,k){
  const tS=k.cue('E4.c1','Three fixes')-.5,sh=smooth((us-tS)/.7);
  if(us<tS+.7){c.save();c.globalAlpha*=1-sh;act4['B11.S2'].draw(c,us,k);c.restore()}
  if(sh>0){c.save();c.translate(lerp(0,-300,sh),lerp(0,-190,sh));c.scale(lerp(1,.3,sh),lerp(1,.3,sh));
    const {row,col,both}=(()=>{const cm=factRaw('comparison.runs.r1.pooled_confusion');return {row:cm[1].reduce((a,b)=>a+b,0),col:cm.reduce((a,r)=>a+r[1],0),both:cm[1][1]}})(),rB=175,rA=rB*Math.sqrt(row/col),d=vennDistance(rA,rB,Math.PI*rA*rA*both/row);
    c.globalAlpha*=sh;c.fillStyle=rgba(P.cyan,.22);c.strokeStyle=P.cyan;c.lineWidth=3;c.beginPath();c.arc(520,480,rA,0,Math.PI*2);c.fill();c.stroke();c.fillStyle=rgba(AMB,.22);c.strokeStyle=AMB;c.beginPath();c.arc(520+d,480,rB,0,Math.PI*2);c.fill();c.stroke();c.restore();
    const k2=k.cue('E4.c1','rejected');rej(c,k,us,{t0:[Math.max(tS+.9,k2-1.5),Math.max(tS+1.6,k2-.8),Math.max(tS+2.3,k2-.1)]});T(c,'Validation only',960,700,{size:30,weight:'med',color:P.muted,align:'center',alpha:smooth((us-tS-2.6)/.4)})}}};
S['E4.S2']={tag:'MEAS',elements:E('cards','stamps'),draw(c,us,k){rej(c,k,us,{t0:[-9,-9,-9],shrink:smooth((us-.1)/1.0)});T(c,'Validation only',960,820,{size:30,weight:'med',color:P.muted,align:'center'})}};

// ================================================================ L1: what we can say
const NBp=id=>`comparison.runs.base.selected_nights.${id}.accuracy`,IDS=['SC4021','SC4062','SC4142'];
const tick=(c,cx,cy,r,col,a)=>{c.save();c.globalAlpha*=a;c.strokeStyle=col;c.lineWidth=5;c.lineCap='round';c.lineJoin='round';c.beginPath();c.arc(cx,cy,r,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(cx-r*.42,cy);c.lineTo(cx-r*.1,cy+r*.34);c.lineTo(cx+r*.45,cy-r*.3);c.stroke();c.restore()};
const canCards=(c,k,{a1,a2,a3})=>{
  T(c,'WHAT WE CAN SAY',960,205,{size:40,weight:'bold',color:GRN,align:'center',alpha:1});
  [[a1,140,'An average can hide failing nights',IDS.map(i=>fm(NBp(i),{mul:100})+'%').join('  ·  '),'right on only this share of epochs, on three nights'],
   [a2,1000,'Per-night scaling helped in this test',`${fm('test.base.subject_mf1.point',{mul:100})}%  →  ${fm('test.r1.subject_mf1.point',{mul:100})}%`,'macro-F1, same architecture, retrained']].forEach(([a,x,t,ev,sub],i)=>{if(a<=0)return;const e=outBack(clamp(a));
    c.save();c.globalAlpha*=smooth(a*3);c.translate(0,lerp(24,0,e));surface(c,[x,270,780,380],'#10213A',{level:'E2',r:20});
    c.strokeStyle=rgba(GRN,.55);c.lineWidth=2.5;c.beginPath();c.roundRect(x,270,780,380,20);c.stroke();tick(c,x+62,340,26,GRN,1);
    T(c,t,x+110,352,{size:36,weight:'bold'});T(c,ev,x+390,500,{size:i?58:50,weight:'bold',color:i?GRN:'#FF8F9B',align:'center'});T(c,sub,x+390,560,{size:25,color:P.muted,align:'center'});c.restore()});
  if(a3>0)Pill(c,{k,x:660,y:710,w:600,h:56,text:'in these 20 people · in this test',color:P.violet,size:28,alpha:a3})};
S['L1.S1']={tag:'MEAS',elements:E('cards','pill'),draw(c,us,k){canCards(c,k,{a1:(us-k.cue('L1.c1','an average')+.2)/.5,a2:(us-k.cue('L1.c1','per-night scaling')+.2)/.5,a3:(us-k.cue('L1.c1','in these 20')+.1)/.4})}};
S['L1.S2']={tag:'MEAS',elements:E('cards','pill'),draw(c,us,k){canCards(c,k,{a1:1,a2:1,a3:1})}};

// ================================================================ L2: what we cannot say
const NO=[{t:'That it works on new people',s:'R1 is offline and was chosen post hoc',ph:'new people'},
          {t:()=>`That ${fm('test.r1.pooled_accuracy.point',{mul:100})}% beats or matches ${fm('paper.reported_accuracy_pct')}%`,s:'protocols differ, and R1 reads the test night',ph:'beats or matches'},
          {t:'That it is clinically ready',s:'healthy adults, 20 people, one dataset',ph:'clinically ready'},
          {t:'That N1 is solved',s:()=>`recall ${fm('test.r1.recall',{idx:1,pct:2})}, three fixes rejected`,ph:'N1 is solved'}];
const noCard=(c,i,a,dim=1)=>{const x=140+(i%2)*860,y=272+(i>>1)*250,w=780,h=216,n=NO[i];
  c.save();c.globalAlpha*=dim;
  if(a<1){c.save();c.globalAlpha*=1-smooth(a);c.setLineDash([9,8]);c.strokeStyle=rgba(AMB,.3);c.lineWidth=2;c.beginPath();c.roundRect(x,y,w,h,20);c.stroke();c.restore()}
  if(a>0){const e=outBack(clamp(a));c.save();c.globalAlpha*=smooth(a*3);c.translate(0,lerp(22,0,e));surface(c,[x,y,w,h],'#10213A',{level:'E2',r:20});c.strokeStyle=rgba(AMB,.7);c.lineWidth=2.5;c.beginPath();c.roundRect(x,y,w,h,20);c.stroke();
    c.strokeStyle=AMB;c.lineWidth=5;c.lineCap='round';c.beginPath();c.arc(x+58,y+70,26,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(x+46,y+58);c.lineTo(x+70,y+82);c.moveTo(x+70,y+58);c.lineTo(x+46,y+82);c.stroke();
    T(c,typeof n.t==='function'?n.t():n.t,x+108,y+84,{size:35,weight:'bold'});T(c,typeof n.s==='function'?n.s():n.s,x+108,y+138,{size:26,color:P.muted});c.restore()}
  c.restore()};
const gx=i=>400+(i%13)*90,gy=i=>290+Math.floor(i/13)*76;
const audit=(c,k,us,t0)=>{const a=smooth((us-t0)/.5);if(a<=0)return;
  T(c,'78 audited participants',960,230,{size:40,weight:'bold',align:'center',alpha:a});
  for(let i=0;i<78;i++){const p=smooth((us-t0-i*.01)/.3);if(p<=0)continue;Person(c,{k,el:'grid78',x:gx(i)+40,y:gy(i)+30,s:34,state:'unknown',alpha:p,q:true,border:i<30?rgba(AMB,smooth((us-t0-1)/.8)):null})}
  const ca=smooth((us-t0-.8)/.4);
  T(c,'Certified independent:',760,810,{size:40,weight:'med',align:'right',alpha:ca});NumText(c,`${fm('audit.independent_confirmed')} / ${fm('audit.available')}`,790,810,{size:56,weight:'bold',color:AMB,alpha:ca});
  const la=smooth((us-t0-1.4)/.5);dot(c,520,876,9,AMB,la);T(c,`${fm('audit.counts.documented_development_exposure')} documented exposure`,540,884,{size:24,color:P.muted,alpha:la});dot(c,1000,876,9,P.muted,la);T(c,`${fm('audit.counts.completed_metadata_association_usage_not_fully_resolved')} usage unresolved`,1020,884,{size:24,color:P.muted,alpha:la})};
S['L2.S1']={tag:null,elements:E('head','cards'),draw(c,us,k){T(c,typed('WHAT WE CANNOT SAY YET',us/.8),960,205,{size:40,weight:'bold',color:AMB,align:'center'});NO.forEach((n,i)=>noCard(c,i,0))}};
S['L2.S2']={tag:null,elements:E('head','cards'),draw(c,us,k){T(c,'WHAT WE CANNOT SAY YET',960,205,{size:40,weight:'bold',color:AMB,align:'center'});
  NO.forEach((n,i)=>noCard(c,i,i===0?(us-k.cue('L2.c1',NO[0].ph)+.3)/.5:0))}};
S['L2.S3']={tag:null,elements:E('head','cards'),draw(c,us,k){T(c,'WHAT WE CANNOT SAY YET',960,205,{size:40,weight:'bold',color:AMB,align:'center'});
  NO.forEach((n,i)=>noCard(c,i,i===0?1:(us-k.cue('L2.c2',n.ph)+.3)/.5))}};
S['L2.S4']={tag:'MEAS',elements:E('cards','grid78','counter'),draw(c,us,k){const t0=k.cue('L2.c3','audited')-.3,f=smooth((us-t0+.4)/.6);
  T(c,'WHAT WE CANNOT SAY YET',960,205,{size:40,weight:'bold',color:AMB,align:'center',alpha:1-f});NO.forEach((n,i)=>noCard(c,i,1,1-f));
  audit(c,k,us,Math.max(0,t0))}};

// ================================================================ L3: summary card
S['L3.S1']={tag:'CONCEPT',elements:E('bars','text','next'),draw(c,us,k){
  const cN=k.cue('L3.c1','Nights differ'),cH=k.cue('L3.c1','hide the one'),cX=k.cue('L3.c1','Next'),cL=k.cue('L3.c1','lock the protocol'),cI=k.cue('L3.c1','independent data');
  const H=[.86,.9,.2,.88,.84],x0=150,bw=82,gap=36,y0=650,Hh=290;
  const e=smooth((us-.2)/.5);surface(c,[104,250,720,470],'#0E1C30',{level:'E2',r:20,alpha:e});
  T(c,'five nights',464,296,{size:26,weight:'med',color:P.muted,align:'center',alpha:e});
  H.forEach((h,i)=>{const p=cubic((us-cN-i*.12)/.5),bad=i===2,hl=smooth((us-cH)/.5),col=bad?mixCol(P.blue,PINK,hl):P.blue,x=x0+i*(bw+gap)+30;
    if(p>0)surface(c,[x,y0-h*Hh*p,bw,h*Hh*p],col,{level:'E1',r:6,gradient:.06})});
  const avg=.74,ay=y0-avg*Hh,aa=smooth((us-cH+.2)/.5);poly(c,[[130,ay],[800,ay]],{stroke:rgba(AMB,.9*aa),width:3,dash:[10,8]});T(c,'dashed line = their average',464,330,{size:23,weight:'med',color:AMB,align:'center',alpha:aa});
  T(c,'one night fails',x0+2*(bw+gap)+30+bw/2,y0+36,{size:24,weight:'bold',color:'#FF8F9B',align:'center',alpha:smooth((us-cH-.3)/.4)});
  const ta=smooth((us-cN+.2)/.5);T(c,'Nights differ.',1320,370,{size:64,weight:'bold',align:'center',alpha:ta,rise:10});
  T(c,'An average can hide',1320,450,{size:42,weight:'med',align:'center',alpha:smooth((us-cN-.5)/.5)});T(c,'the one that fails.',1320,505,{size:42,weight:'med',align:'center',alpha:smooth((us-cH+.3)/.5)});
  const na=smooth((us-cX+.2)/.5);
  if(na>0){c.save();c.globalAlpha*=na;surface(c,[880,590,920,180],'#10213A',{level:'E2',r:20});T(c,'NEXT',940,650,{size:26,weight:'bold',color:P.cyan});
    const lk=smooth((us-cL)/.5);Padlock(c,{k,el:'next',x:944,y:672,open:1-lk,alpha:1,s:.8});T(c,'Lock the protocol',1020,715,{size:32,weight:'bold'});
    arrow(c,1330,700,1440,700,{col:P.muted,width:4,head:14,alpha:smooth((us-cL-.3)/.4)});
    const bf=smooth((us-cI+.2)/.5);c.setLineDash(bf<1?[9,7]:[]);c.strokeStyle=bf<1?P.muted:P.ink;c.lineWidth=3;c.beginPath();c.roundRect(1460,650,300,100,16);c.stroke();c.setLineDash([]);
    T(c,'truly independent data',1610,709,{size:25,weight:'bold',align:'center',alpha:bf});c.restore()}}};
export const s3=S;
