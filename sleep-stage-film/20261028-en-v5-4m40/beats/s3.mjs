// Sections 5-6 (new and merged shots): E1-E4 evidence, L1-L3 limits and summary
import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,mixCol,T,poly,dot,rect,arrow,typed,seg,measure,eeg,wavePts,EQ} from '../lib.mjs';
import {HYPNO,n1Sim,vennDistance} from '../shared.mjs';
import {NightStrip,tileX,stageColor} from '../components/strip.mjs';
import {Bracket,Pill} from '../components/misc.mjs';
import {NumberCard,NumText,Stamp,Padlock,fmtNum} from '../components/cards.mjs';
import {Person} from '../components/people.mjs';
import {blockIcon} from '../components/model.mjs';
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
// ---- E2.S1 / E2.R : the ruler, in 3D and in maths
const R3=9,C3=90,U3=44,DX3=8,DY3=10,X03=210,YB3=640,W3=600;
const mk=(seed,i)=>Math.sin(i*127.1+seed*311.7)*43758.5453-Math.floor(Math.sin(i*127.1+seed*311.7)*43758.5453);
function night(seed){const rows=[];for(let r=0;r<R3;r++){const f=[],ph=[],am=[];for(let j=0;j<4;j++){f.push(1+mk(seed+r,j)*1.6+j*1.5);ph.push(mk(seed*3+r,j+9)*6.28);am.push([1,.8,.5,.3][j]*(.7+mk(seed*5+r,j+3)*.5))}
  const raw=[];for(let t=0;t<C3;t++){const u=t/(C3-1);let v=0;for(let j=0;j<4;j++)v+=am[j]*Math.sin(u*Math.PI*2*f[j]+ph[j]);raw.push(v)}
  const m=raw.reduce((a,b)=>a+b,0)/C3,sd=Math.sqrt(raw.reduce((a,b)=>a+(b-m)**2,0)/C3);rows.push(raw.map(v=>(v-m)/sd))}return rows}
const TA=night(11),TB=night(29);
// baseline z = offset + spread * (night-standardised shape); R1 z = the shape itself (mean 0, sd 1 by construction)
const offA=r=>-1.05+.25*Math.sin(r*.7),sprA=r=>.55+.08*Math.sin(r*.5+1),offB=r=>.85+.2*Math.sin(r*.6+2),sprB=r=>1.3+.12*Math.sin(r*.4);
const pdf=(x,m,sd)=>Math.exp(-((x-m)**2)/(2*sd*sd))/(sd*Math.sqrt(2*Math.PI));
function ruler3d(c,k,us,{m=0,rev=1,eqP=1,eqMode='base',slabA=1,persons=0,pdfA=1,noLab=0,label=1}){
  const LX=104,LY=290,LW=936,LH=590,RX=1080,RW=736;
  surface(c,[LX,LY,LW,LH],'#0E1C30',{level:'E2',r:18});surface(c,[RX,LY,RW,LH],'#0E1C30',{level:'E2',r:18});
  T(c,'z-scored spectrograms of two nights',LX+LW/2,LY+48,{size:30,weight:'bold',color:P.ink,align:'center'});
  dot(c,LX+200,LY+82,7,P.cyan);T(c,'Night A · weak signal',LX+216,LY+90,{size:23,color:P.muted});dot(c,LX+520,LY+82,7,P.violet);T(c,'Night B · strong signal',LX+536,LY+90,{size:23,color:P.muted});
  const ux=(z)=>z*U3,X=(r,t)=>X03+r*DX3+t/(C3-1)*W3,Yp=(r,z)=>YB3-r*DY3-ux(z);
  // translucent slab: the ruler, mean ± 1 sd, drawn at the front, the right side and the back
  const sc=m>.5?P.cyan:AMB,sa=slabA;
  if(sa>0){const x1=X03+W3,xb=X03+(R3-1)*DX3,x1b=x1+(R3-1)*DX3,yt=Yp(0,1),yo=Yp(0,-1),ytb=Yp(R3-1,1),yob=Yp(R3-1,-1);
    c.save();c.globalAlpha*=sa;c.fillStyle=rgba(sc,.07);c.beginPath();c.moveTo(X03,yt);c.lineTo(x1,yt);c.lineTo(x1,yo);c.lineTo(X03,yo);c.closePath();c.fill();
    c.fillStyle=rgba(sc,.05);c.beginPath();c.moveTo(x1,yt);c.lineTo(x1b,ytb);c.lineTo(x1b,yob);c.lineTo(x1,yo);c.closePath();c.fill();
    c.strokeStyle=rgba(sc,.75);c.lineWidth=2;c.setLineDash([9,7]);[[X03,yt,x1,yt,x1b,ytb,xb,ytb],[X03,yo,x1,yo,x1b,yob,xb,yob]].forEach(q=>{c.beginPath();c.moveTo(q[0],q[1]);c.lineTo(q[2],q[3]);c.lineTo(q[4],q[5]);c.lineTo(q[6],q[7]);c.closePath();c.stroke()});c.setLineDash([]);
    c.strokeStyle=rgba(sc,.95);c.lineWidth=2.6;c.beginPath();c.moveTo(X03,Yp(0,0));c.lineTo(x1,Yp(0,0));c.lineTo(x1b,Yp(R3-1,0));c.stroke();c.restore();
    [['+1σ',1],['0',0],['−1σ',-1]].forEach(([l,z])=>T(c,l,X03-16,Yp(0,z)+8,{size:23,weight:'med',color:sc,align:'right',alpha:sa}));
    T(c,m>.5?'each night: mean 0, spread 1':'one shared ruler: μ ± 1σ from training',LX+LW/2,LY+LH-62,{size:25,weight:'med',color:sc,align:'center',alpha:sa})}
  // ridges: back to front, 12 of the 129 frequency bins
  const e=cubic(rev);
  for(let r=R3-1;r>=0;r--){const pr=clamp(e*1.6-(R3-1-r)/R3*.6);if(pr<=0)continue;
    [[TA,offA,sprA,P.cyan],[TB,offB,sprB,P.violet]].forEach(([T_,of,sp,col])=>{const pts=[];const n=Math.max(2,Math.round(C3*pr));
      for(let t=0;t<n;t++){const s0=T_[r][t],zb=of(r)+sp(r)*s0,z=lerp(zb,s0,cubic(m));pts.push([X(r,t),Yp(r,z)])}
      poly(c,pts,{stroke:col,width:2.4-r*.05,alpha:.95-r*.045})})}
  T(c,'time →',LX+LW/2,LY+LH-24,{size:22,color:P.muted,align:'center',alpha:label});
  const fx=X03+W3+(R3-1)*DX3+26;poly(c,[[X03+W3+14,YB3+8],[fx,Yp(R3-1,0)+8]],{stroke:P.muted,width:2,alpha:label});T(c,'frequency f',fx+8,Yp(R3-1,0)-4,{size:23,color:P.muted,alpha:label});
  // right: one frequency bin, after z-scoring
  T(c,'one frequency bin, after z-scoring',RX+RW/2,LY+48,{size:30,weight:'bold',color:P.ink,align:'center'});
  const px=RX+50,pw=RW-100,py=LY+370,ys=300,Z=z=>px+(z+4)/8*pw,cm=cubic(m);
  poly(c,[[px,py],[px+pw,py]],{stroke:P.line,width:2});[-2,0,2].forEach(z=>{poly(c,[[Z(z),py],[Z(z),py+10]],{stroke:P.line,width:2});T(c,String(z).replace('-','−'),Z(z),py+40,{size:22,color:P.muted,align:'center'})});T(c,'z',px+pw+6,py+8,{size:22,color:P.muted});
  const cur=(mu,sd,col,fa,dash)=>{const pts=[];for(let i=0;i<=120;i++){const z=-4+8*i/120;pts.push([Z(z),py-pdf(z,mu,sd)*ys])}
    if(fa>0){c.save();c.globalAlpha*=pdfA;c.beginPath();pts.forEach((q,i)=>i?c.lineTo(q[0],q[1]):c.moveTo(q[0],q[1]));c.lineTo(px+pw,py);c.lineTo(px,py);c.closePath();c.fillStyle=rgba(col,fa);c.fill();c.restore()}
    poly(c,pts,{stroke:col,width:dash?2.2:3,dash:dash?[8,7]:undefined,alpha:pdfA})};
  cur(0,1,P.slate,0,true);
  const mA=lerp(-1.0,0,cm),sA=lerp(.55,1,cm),mB=lerp(.85,0,cm),sB=lerp(1.45,1,cm);
  cur(mA,sA,P.cyan,.2,false);cur(mB,sB,P.violet,.2,false);
  poly(c,[[Z(0),py-.4*ys-30],[Z(0),py]],{stroke:rgba(P.slate,.5),width:1.5,dash:[4,6],alpha:pdfA});
  T(c,'training people: mean 0, spread 1',RX+RW/2,LY+98,{size:23,color:P.slate,align:'center',alpha:pdfA});
  const tl=1-smooth(cm*3);T(c,'Night A: shifted and squeezed',RX+RW/2,py+86,{size:26,weight:'med',color:P.cyan,align:'center',alpha:pdfA*tl});T(c,'Night B: shifted and stretched',RX+RW/2,py+122,{size:26,weight:'med',color:P.violet,align:'center',alpha:pdfA*tl});
  T(c,'both nights land on the same ruler',RX+RW/2,py+104,{size:28,weight:'bold',color:P.cyan,align:'center',alpha:pdfA*smooth((cm-.55)*3)});
  if(persons>0)for(let i=0;i<16;i++)Person(c,{k,el:'persons',x:RX+60+i*40.5,y:py+160,s:17,state:'train',alpha:persons*smooth((persons*1.8-i*.05)),sc:.8+.2*persons});
  if(persons>0)T(c,'16 training people → one μ, σ per frequency',RX+RW/2,py+212,{size:23,color:P.blue,align:'center',alpha:persons});
  if(noLab>0)Pill(c,{k,el:'nolabel',x:RX+RW/2-190,y:py+130,w:380,h:50,text:'no labels used · offline',color:GRN,size:24,alpha:noLab});
  // equation
  const ey=184,ea=eqMode==='base'?1:0,eb=eqMode==='base'?0:1;
  if(eqMode==='base')EQ(c,'z_{f,t}\\,=\\,\\frac{x_{f,t}-\\mu_f^{\\mathrm{train}}}{\\sigma_f^{\\mathrm{train}}}',960,ey,{size:40,p:eqP});
  else EQ(c,'z_{f,t}\\,=\\,\\frac{x_{f,t}-\\mu_f^{\\mathrm{night}}}{\\sigma_f^{\\mathrm{night}}}\\qquad\\mu_f^{\\mathrm{night}}=\\frac{1}{T}\\sum_{t=1}^{T}x_{f,t}',960,ey,{size:36,p:eqP,color:P.cyan});
  T(c,'x = log-STFT value at frequency bin f, frame t · z is what the CNN sees',960,270,{size:22,color:P.muted,align:'center'})}

// ---- E2.Z: what z-scoring does, one frequency bin of one night
const gauss=(x,m,sd)=>Math.exp(-((x-m)**2)/(2*sd*sd))/(sd*Math.sqrt(2*Math.PI));
S['E2.Z']={tag:'MATH',elements:E('eq','axis','curve','arrows','labels'),draw(c,us,k){
  const cS=k.cue('E2.c1','subtract'),cD=k.cue('E2.c1','divide'),cE=k.cue('E2.c1','standard deviations');
  const a=smooth(us/.5);surface(c,[104,290,1712,590],'#0E1C30',{level:'E2',r:18,alpha:a});
  EQ(c,'z\\,=\\,\\frac{x-\\mu}{\\sigma}',960,190,{size:46,p:us/.9,color:P.ink});
  const X0=160,XW=1600,x2p=v=>X0+(v+6)/18*XW,py=780,ys=720,m1=smooth((us-cS)/1.3),m2=smooth((us-cD)/1.3);
  poly(c,[[X0,py],[X0+XW,py]],{stroke:P.line,width:2,alpha:a});
  const mu=lerp(5,0,cubic(m1)),sd=lerp(2,1,cubic(m2)),col=P.cyan;
  const fill=[];const pts=[];for(let i=0;i<=160;i++){const v=-6+18*i/160,y=py-gauss(v,mu,sd)*ys*sd*.9;pts.push([x2p(v),y])}
  c.save();c.globalAlpha*=a;c.beginPath();pts.forEach((q,i)=>i?c.lineTo(q[0],q[1]):c.moveTo(q[0],q[1]));c.lineTo(x2p(12),py);c.lineTo(x2p(-6),py);c.closePath();c.fillStyle=rgba(col,.18);c.fill();c.restore();
  poly(c,pts,{stroke:col,width:4,alpha:a});
  // zero line and the mean marker
  poly(c,[[x2p(0),py+4],[x2p(0),py-330]],{stroke:rgba(P.ink,.35),width:2,dash:[6,8],alpha:a});T(c,'0',x2p(0),py+34,{size:26,color:P.muted,align:'center',alpha:a});
  poly(c,[[x2p(mu),py],[x2p(mu),py-gauss(mu,mu,sd)*ys*sd*.9-14]],{stroke:AMB,width:3,alpha:a});T(c,'mean μ',x2p(mu),py-gauss(mu,mu,sd)*ys*sd*.9-26,{size:26,weight:'med',color:AMB,align:'center',alpha:a});
  // the spread: ±1σ bracket
  const by=py-150;poly(c,[[x2p(mu-sd),by],[x2p(mu+sd),by]],{stroke:GRN,width:4,alpha:a});[mu-sd,mu+sd].forEach(v=>poly(c,[[x2p(v),by-10],[x2p(v),by+10]],{stroke:GRN,width:4,alpha:a}));
  T(c,m2>.5?'spread σ = 1':'spread σ',x2p(mu),by+40,{size:26,weight:'med',color:GRN,align:'center',alpha:a});
  // step arrows and labels
  if(us>cS-.3){const sa=smooth((us-cS+.3)/.4)*(1-smooth((us-cS-1.1)/.4));arrow(c,x2p(5.2),py-390,x2p(0.4),py-390,{col:AMB,width:5,head:16,p:cubic((us-cS+.3)/1.0),alpha:sa});T(c,'step 1: subtract the mean',x2p(3.4),py-420,{size:28,weight:'bold',color:AMB,align:'center',alpha:sa})}
  if(us>cD-.3){const sa=smooth((us-cD+.3)/.4)*(1-smooth((us-cD-1.8)/.4)),pp=cubic((us-cD+.3)/1.0);arrow(c,x2p(-4.2),py-390,x2p(-1.2),py-390,{col:GRN,width:5,head:16,p:pp,alpha:sa});arrow(c,x2p(4.2),py-390,x2p(1.2),py-390,{col:GRN,width:5,head:16,p:pp,alpha:sa});T(c,'step 2: divide by the spread',x2p(0),py-420,{size:28,weight:'bold',color:GRN,align:'center',alpha:sa})}
  const ea=smooth((us-cE+.2)/.5);T(c,'mean 0 · spread 1 · values are counted in standard deviations',960,852,{size:30,weight:'bold',color:P.cyan,align:'center',alpha:ea});
  T(c,'one frequency bin of one night · x = log power',960,316,{size:24,color:P.muted,align:'center',alpha:a})}};
// ---- E2.Y: why, every frequency has its own mean and spread
const BANDS=[['0.5–4 Hz',9,1.8],['4–8 Hz',7.4,1.4],['8–13 Hz',6,1.0],['13–20 Hz',4.6,.8],['20–30 Hz',3.4,.6]];
S['E2.Y']={tag:'CONCEPT',elements:E('lanes','bars','axis','labels'),draw(c,us,k){
  const cW=k.cue('E2.c2','Raw sizes'),cC=k.cue('E2.c2','common scale');
  const a=smooth(us/.5),mp=cubic((us-cC+.2)/1.5);surface(c,[104,290,1712,590],'#0E1C30',{level:'E2',r:18,alpha:a});
  EQ(c,'z\\,=\\,\\frac{x-\\mu_f}{\\sigma_f}',960,190,{size:46,p:1});
  T(c,mp>.5?'z-scored: every frequency on the same scale':'raw log power: every frequency has its own mean and spread',960,350,{size:30,weight:'bold',color:mp>.5?P.cyan:P.ink,align:'center',alpha:a});
  const AX0=420,AXW=1180,X=v=>AX0+(v/12)*AXW,ZX=v=>AX0+((v+4)/8)*AXW;
  BANDS.forEach(([lab,mu,sd],i)=>{const y=430+i*84,al=smooth((us-cW+.3-i*.12)/.4);if(al<=0)return;
    T(c,lab,360,y+10,{size:28,weight:'med',color:P.muted,align:'right',alpha:al});
    const cx=lerp(X(mu),ZX(0),mp),hw=lerp(sd/12*AXW,1/8*AXW,mp);
    c.save();c.globalAlpha*=al;surface(c,[cx-hw,y-20,hw*2,40],rgba(P.cyan,.28),{level:'E1',r:8,gradient:0});c.strokeStyle=P.cyan;c.lineWidth=2.5;c.beginPath();c.roundRect(cx-hw,y-20,hw*2,40,8);c.stroke();dot(c,cx,y,6,AMB);c.restore()});
  poly(c,[[ZX(0),410],[ZX(0),850]],{stroke:rgba(P.ink,.4),width:2,dash:[6,8],alpha:mp});
  T(c,'bar = mean ± 1 spread',960,868,{size:24,color:P.muted,align:'center',alpha:a*(1-mp)});T(c,'0',ZX(0),868,{size:26,color:P.muted,align:'center',alpha:mp})}};
// ---- E2.P: what R1 changes in the pipeline
S['E2.P']={tag:'CONCEPT',elements:E('blocks','chips','note','arrows'),draw(c,us,k){
  const cE=k.cue('E2.c5','Everything else'),cR=k.cue('E2.c5','retrained');
  const a=smooth(us/.5),BW=270,GP=62,X0=(1920-(5*BW+4*GP))/2,Y=380,H=190;
  const B=[['Night','eeg','one night, no labels'],['STFT','stft','same'],['z-score','z','changed'],['CNN','cnn','same'],['BiGRU','bigru','same']];
  B.forEach(([t,kind,note],i)=>{const x=X0+i*(BW+GP),ch=kind==='z',pa=smooth((us-i*.1)/.4);
    if(i>0)arrow(c,x-GP+6,Y+H/2,x-6,Y+H/2,{col:P.muted,width:4,head:12,p:pa,alpha:pa});
    c.save();c.globalAlpha*=pa;if(ch)glowRect(c,x,Y,BW,H,AMB,{blur:22,alpha:.45},16);surface(c,[x,Y,BW,H],ch?'#2A2314':'#16273F',{level:'E2',r:16});
    if(ch){c.strokeStyle=rgba(AMB,.9);c.lineWidth=2.6;c.beginPath();c.roundRect(x,Y,BW,H,16);c.stroke();T(c,'z',x+BW/2,Y+95,{size:92,weight:'bold',color:AMB,align:'center'})}
    else if(kind==='eeg'){poly(c,wavePts(x+30,Y+85,BW-60,34,u=>eeg(u,5,'mixed'),160),{stroke:P.cyan,width:2.4})}
    else blockIcon(c,kind,x+BW/2,Y+82,76);
    T(c,t,x+BW/2,Y+H-26,{size:30,weight:'bold',color:ch?AMB:P.ink,align:'center'});c.restore();
    const ca=i===0?pa:ch?smooth((us-.6)/.4):smooth((us-cE+.2-i*.12)/.4);
    if(i>0||true)Pill(c,{k,el:'chips',x:x+25,y:Y+H+24,w:BW-50,h:46,text:note,color:ch?AMB:i===0?P.muted:GRN,size:22,alpha:ca})});
  const zx=X0+2*(BW+GP),ra=smooth((us-.9)/.5);
  T(c,'baseline: the 16 training people’s ruler',zx+BW/2,Y-70,{size:26,color:P.muted,align:'center',alpha:ra*(1-smooth((us-1.8)/.4))});
  T(c,'R1: this night’s own ruler',zx+BW/2,Y-70,{size:30,weight:'bold',color:P.cyan,align:'center',alpha:smooth((us-1.8)/.4)});
  const na=smooth((us-cR+.2)/.5);T(c,'retrained on the per-night z-scores',960,780,{size:36,weight:'bold',color:P.cyan,align:'center',alpha:na});
  T(c,'no labels read · offline',960,826,{size:26,color:P.muted,align:'center',alpha:na})}};

S['E2.S1']={tag:'CONCEPT',elements:E('wall','ridges','plot','eq','persons'),draw(c,us,k){
  const cZ=k.cue('E2.c3','already did this'),cOne=k.cue('E2.c3','one ruler'),c16=k.cue('E2.c3','16 training people');
  ruler3d(c,k,us,{m:0,rev:(us-cZ+.3)/1.6,eqP:(us-cZ)/.9,slabA:smooth((us-cOne+.5)/.6),persons:smooth((us-c16+.1)/.6),pdfA:smooth((us-cOne+.2)/.6),eqMode:'base'})}};
S['E2.R']={tag:'CONCEPT',elements:E('wall','ridges','plot','eq','nolabel'),draw(c,us,k){
  const cR=k.cue('E2.c4','R1 gives'),cO=k.cue('E2.c4','its own ruler'),cN=k.cue('E2.c4','no labels');
  const sw=smooth((us-cR+.1)/.5);
  ruler3d(c,k,us,{m:(us-cO-.2)/2.2,rev:1,eqP:us<cR-.1?1:(us-cR)/1.1,slabA:1,persons:1-smooth((us-cR)/.4),pdfA:1,eqMode:us<cR-.1?'base':'night',noLab:smooth((us-cN+.2)/.4)})}};
S['E2.S2']={tag:'MEAS',elements:E('cardL','cardR','arrows','gain'),draw(c,us,k){act3['B8.S3'].draw(c,us,k);
  const ga=k.cue('E2.c6','Gain'),a=smooth((us-ga+.3)/.4);
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
