// Sections 1-2 (new shots): P1 pipeline, B2.S4 split protocols, B3 new question, Q2 scope and hypothesis
import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,mixCol,T,poly,dot,rect,arrow,pill,typed,seg,measure,eeg,wavePts} from '../lib.mjs';
import {HYPNO} from '../shared.mjs';
import {NightStrip,Legend} from '../components/strip.mjs';
import {HeadTop,EegFrame,Pill} from '../components/misc.mjs';
import {blockIcon} from '../components/model.mjs';
import {PaperCard,RefBadge,Stamp,Padlock} from '../components/cards.mjs';
import {Person,MiniStrip,IconChip} from '../components/people.mjs';
import {surface,bevel,glowRect,glowCircle} from '../light.mjs';
import {fact} from '../facts.mjs';
import {partial} from '../motion.mjs';
const S={};const E=(...ids)=>ids.map(id=>({id,in:0,out:99}));
const PINK='#FF8FA3',GRN='#7EE0A1',AMB='#FFC46B';

// ---------------------------------------------------------------- P1: Input -> Process -> Output
const IN={x:104,w:360},PR={x:540,w:690},OUT={x:1306,w:510},PY=316,PH=440;
const BLK=[['epoch','30 s epochs','one 30 s slice'],['stft','STFT picture','129 × 29'],['cnn','CNN','128 numbers'],['bigru','BiGRU','20 epochs']];
function pipeDraw(c,us,k,{a1=0,a2=0,a3=0,pa=1,titles=1,cu}){
  // titles
  [['INPUT',IN,P.cyan],['PROCESS',PR,P.violet],['OUTPUT',OUT,P.green]].forEach(([t,r,col],i)=>{const a=smooth((us-.1-i*.12)/.4)*titles;
    T(c,t,r.x+r.w/2,PY-24,{size:34,weight:'bold',color:col,align:'center',alpha:a,rise:8})});
  [[IN,0],[PR,1],[OUT,2]].forEach(([r,i])=>{const a=smooth((us-.1-i*.12)/.4);
    surface(c,[r.x,PY,r.w,PH],'#0E1C30',{level:'E2',r:18,alpha:a});
    if(a>0){c.save();c.globalAlpha*=a;c.setLineDash([8,7]);c.strokeStyle='rgba(147,163,184,.28)';c.lineWidth=1.5;c.beginPath();c.roundRect(r.x+10,PY+10,r.w-20,PH-20,12);c.stroke();c.restore()}});
  // arrows between panels
  arrow(c,IN.x+IN.w+10,PY+PH/2,PR.x-12,PY+PH/2,{col:P.muted,width:4,head:16,p:clamp(a2*2.5),alpha:smooth(a2*2)});
  arrow(c,PR.x+PR.w+10,PY+PH/2,OUT.x-12,PY+PH/2,{col:P.muted,width:4,head:16,p:clamp(a3*2.5),alpha:smooth(a3*2)});
  // INPUT
  const hp=smooth(a1*1.6),wv=clamp((a1-.35)*2);
  HeadTop(c,{k,el:'head',cx:IN.x+IN.w/2,cy:PY+130,r:100,alpha:hp,fpz:smooth(a1*3-.3),cz:smooth(a1*3-.6)});
  if(wv>0){const x0=IN.x+30,w=IN.w-60,y0=PY+310;c.save();c.globalAlpha*=smooth(wv*2);surface(c,[x0,y0-55,w,110],'#0C1A2E',{level:'E1',r:12,gradient:.03});
    const pts=wavePts(x0+10,y0,w-20,32,a=>eeg(a,4,'mixed'),260);poly(c,partial(pts,cubic(wv)),{stroke:P.cyan,width:2.4});c.restore()}
  T(c,'Fpz-Cz · '+fact('pipeline.hz')+' Hz',IN.x+IN.w/2,PY+PH-58,{size:28,weight:'med',color:P.muted,align:'center',alpha:smooth((a1-.6)*3)});
  T(c,'all night, one channel',IN.x+IN.w/2,PY+PH-26,{size:22,color:P.dim,align:'center',alpha:smooth((a1-.75)*4)});
  // PROCESS
  const bw=140,gap=32,bx0=PR.x+(PR.w-(4*bw+3*gap))/2,by=PY+100;
  BLK.forEach(([kind,label,sub],i)=>{const p=clamp(a2*4-i*.9),x=bx0+i*(bw+gap);if(p<=0)return;
    const yy=by-(1-outBack(p))*40;c.save();c.globalAlpha*=smooth(p*3);
    surface(c,[x,yy,bw,bw],'#16273F',{level:'E2',r:16,gradient:.05});
    if(kind==='epoch'){const pts=wavePts(x+14,yy+bw/2,bw-28,26,a=>eeg(a,3,'mixed'),90);poly(c,pts,{stroke:STAGE_COL[2],width:2.2});
      poly(c,[[x+14,yy+bw-22],[x+bw-14,yy+bw-22]],{stroke:P.muted,width:2});T(c,'30 s',x+bw/2,yy+bw-30,{size:20,weight:'med',color:P.muted,align:'center'})}
    else blockIcon(c,kind,x+bw/2,yy+bw/2,72);
    T(c,label,x+bw/2,yy+bw+40,{size:25,weight:'med',align:'center'});T(c,sub,x+bw/2,yy+bw+72,{size:21,color:P.muted,align:'center'});c.restore();
    if(i>0)arrow(c,x-gap+4,by+bw/2,x-4,by+bw/2,{col:P.muted,width:3,head:11,alpha:smooth(p*3)})});
  // OUTPUT
  const ox=OUT.x+30,ow=OUT.w-60,tile=20;
  NightStrip(c,{k,el:'out',x:ox,w:ow,y:PY+130,h:72,range:[18,18+tile],gap:3,appear:i=>(a3*1.6-(i-18)*.03)*1.2,tray:true,alpha:1});
  if(a3>0.35)Legend(c,{k,el:'legend',cx:OUT.x+OUT.w/2,y:PY+290,t:(a3-.35)*3,alpha:1});
  T(c,'5 stages · one per 30 s',OUT.x+OUT.w/2,PY+PH-58,{size:28,weight:'med',color:P.muted,align:'center',alpha:smooth((a3-.6)*3)});
  T(c,'hypnogram',OUT.x+OUT.w/2,PY+PH-26,{size:22,color:P.dim,align:'center',alpha:smooth((a3-.75)*4)});}
S['P1.S1']={tag:'ILLU',elements:E('head','out','legend','blocks'),draw(c,us,k){pipeDraw(c,us,k,{a1:0,a2:0,a3:0})}};
S['P1.S2']={tag:'ILLU',elements:E('head','out','legend','blocks'),draw(c,us,k){const t0=k.cue('P1.c1','Input'),t1=k.cue('P1.c1','100 samples');
  pipeDraw(c,us+9,k,{a1:clamp((us-t0)/(t1-t0+1.2)),a2:0,a3:0,titles:1})}};
S['P1.S3']={tag:'ILLU',elements:E('head','out','legend','blocks'),draw(c,us,k){const t0=k.cue('P1.c2','Process'),t1=k.cue('P1.c2','BiGRU');
  pipeDraw(c,us+9,k,{a1:1,a2:clamp((us-t0)/(t1-t0+1.3)),a3:0})}};
S['P1.S4']={tag:'ILLU',elements:E('head','out','legend','blocks'),draw(c,us,k){const t0=k.cue('P1.c3','Output');
  pipeDraw(c,us+9,k,{a1:1,a2:1,a3:clamp((us-t0)/2.2)})}};

// ---------------------------------------------------------------- B2.S4: paper card shrinks to badge, then split protocols
const faintStrip=(c,k,a)=>{if(a<=0)return;k.L(2,()=>{c.save();c.filter='blur(2px)';NightStrip(c,{k,el:'bgstrip',y:481,appear:1,alpha:a*.2,tray:false});c.restore()})};
const paper=()=>({title:fact('paper.title'),venue:`${fact('paper.venue')} · ${fact('paper.year')}`,authors:fact('paper.authors_short')});
const rnd=(i)=>{const x=Math.sin(i*127.1+311.7)*43758.5453;return x-Math.floor(x)};
S['B2.S4']={tag:'REF',elements:E('paper','left','right','lock','mark'),draw(c,us,k){
  const mp=clamp((us-.1)/.9);faintStrip(c,k,1-smooth(us/.8));
  if(mp<1)k.L(5,()=>PaperCard(c,{k,el:'paper',morph:mp,...paper()}));else RefBadge(c,{k,el:'paper'});
  const a=smooth((us-.9)/.5);
  const LX=104,RX=996,PW=820,Y=262,PHt=470;
  // left: random epoch split
  surface(c,[LX,Y,PW,PHt],'#0E1C30',{level:'E2',r:18,alpha:a});
  T(c,'The paper: random epoch split',LX+PW/2,Y+50,{size:32,weight:'bold',color:P.ref,align:'center',alpha:a});
  T(c,fact('paper.split'),LX+PW/2,Y+88,{size:24,color:P.muted,align:'center',alpha:a});
  const tA=k.cue('B2.c3','at random');
  Person(c,{k,el:'left',x:LX+PW/2,y:Y+190,s:96,state:'neutral',alpha:a});
  const n=44,pw=(PW-80)/n,x0=LX+40,y0=Y+270,rv=smooth((us-tA)/1.2);
  for(let i=0;i<n;i++){const r=rnd(i*3+5),col=r<.8?P.blue:r<.9?AMB:PINK,col0=STAGE_COL[HYPNO[(i*2)%96]];
    const t=clamp(rv*1.6-i/n*.6);bevel(c,x0+i*pw,y0,pw-3,80,mixCol(col0,col,t),{r:3,alpha:a})}
  const lg=smooth((us-tA-.8)/.5);[['train',P.blue],['validate',AMB],['test',PINK]].forEach(([s,col],i)=>{dot(c,LX+150+i*190,Y+385,8,col,lg);T(c,s,LX+168+i*190,Y+393,{size:24,weight:'med',alpha:lg})});
  const bs=k.cue('B2.c3','both sides'),xm=smooth((us-bs)/.4);
  if(xm>0){c.save();c.globalAlpha*=xm;c.strokeStyle=PINK;c.lineWidth=9;c.lineCap='round';const cx=LX+PW/2,cy=Y+190;c.beginPath();c.moveTo(cx+70,cy-30);c.lineTo(cx+120,cy+20);c.moveTo(cx+120,cy-30);c.lineTo(cx+70,cy+20);c.stroke();c.restore();
    T(c,'same person in train and test',LX+PW/2,Y+440,{size:30,weight:'bold',color:'#FF8F9B',align:'center',alpha:xm})}
  // right: split by person
  surface(c,[RX,Y,PW,PHt],'#0E1C30',{level:'E2',r:18,alpha:a});
  T(c,'Ours: split by person',RX+PW/2,Y+50,{size:32,weight:'bold',color:P.cyan,align:'center',alpha:a});
  T(c,'no person on both sides',RX+PW/2,Y+88,{size:24,color:P.muted,align:'center',alpha:a});
  const sp=k.cue('B2.c3','We split by person'),rp=smooth((us-sp)/.8);
  const states=['train','train','train','train','train','choose','test','test'];
  for(let i=0;i<8;i++){const x=RX+75+i*95,test=states[i]==='test',gx=test?24:0;const p=clamp(rp*1.5-i*.05);
    Person(c,{k,el:'right',x:x+gx*smooth(rp),y:Y+185,s:60,state:states[i],alpha:a,sc:lerp(.7,1,smooth(p))});
    MiniStrip(c,{x:x+gx*smooth(rp)-40,y:Y+230,w:80,h:14,n:8,seed:i+4,alpha:a});}
  if(rp>0){const lx=RX+75+5.5*95+12;poly(c,[[lx+6,Y+130],[lx+6,Y+280]],{stroke:P.ink,width:3,dash:[8,6],alpha:rp})}
  const lk=smooth((us-sp-.8)/.5);Padlock(c,{k,el:'lock',x:RX+PW/2-28,y:Y+310,open:1-lk,alpha:lk});
  T(c,'one person → one set',RX+PW/2,Y+410,{size:30,weight:'bold',align:'center',alpha:lk})}};

// ---------------------------------------------------------------- B3: the new question (badge stays)
const badge=(c,k,a=1)=>RefBadge(c,{k,el:'badge',alpha:a});
S['B3.S1']={tag:'CONCEPT',elements:E('badge','bar','arrow'),draw(c,us,k){badge(c,k,.85);
  const g=cubic((us-.1)/1.0),h=320*g;if(g>0){surface(c,[880,760-h,160,h],P.violet,{level:'E1',r:6,gradient:.06});
    const ay=760-h-24-120;c.save();c.globalAlpha*=smooth((us-.1)/.3);c.strokeStyle=P.ink;c.fillStyle=P.ink;c.lineWidth=6;c.lineCap='round';
    c.beginPath();c.moveTo(960,ay+120);c.lineTo(960,ay+8);c.stroke();c.beginPath();c.moveTo(960,ay-6);c.lineTo(944,ay+20);c.lineTo(976,ay+20);c.closePath();c.fill();c.restore()}
  poly(c,[[760,760],[1160,760]],{stroke:P.line,width:3});
  T(c,'one number, as high as possible',960,830,{size:30,weight:'med',color:P.muted,align:'center',alpha:smooth((us-.9)/.4)})}};
const Q_L1='Does it still work on a person',Q_L2='the model has never seen?';
const questionDraw=(c,us,k,{hold=false}={})=>{badge(c,k,.85);
  const c0=hold?0:k.cue('B3.c1','does it still'),c1=hold?0:k.cue('B3.c1','never seen'),c2=hold?0:k.cue('B3.c1','explain every step');
  const ca=hold?1:smooth((us-.1)/.45);
  surface(c,[300,240,1320,220],'#10213A',{level:'E3',r:18,alpha:ca});
  const pr=hold?1:clamp((us-c0+.2)/(Math.max(.8,c1-c0+.9)));const l1=typed(Q_L1,clamp(pr*2)),l2=typed(Q_L2,clamp(pr*2-1));
  T(c,l1,960,340,{size:54,weight:'bold',align:'center'});T(c,l2,960,410,{size:54,weight:'bold',align:'center'});
  const pp=hold?1:outBack((us-c1+.3)/.5);Person(c,{k,el:'person',x:1500,y:350,s:84,state:'test',sc:clamp(pp),alpha:clamp(pp*2),glowA:.4});
  const ta=hold?1:smooth((us-c2+.2)/.3);
  T(c,hold?'…and can we explain every step?':typed('…and can we explain every step?',(us-c2+.2)/.9),960,560,{size:48,weight:'bold',color:P.ink,align:'center',alpha:hold?1:ta});
  ['sigma','chart','check'].forEach((n,i)=>IconChip(c,{k,el:'icons',cx:640+i*320,y:630,icon:n,lit:hold?.7:smooth((us-c2-.6-i*.4)/.3)*.9,litCol:[P.violet,P.cyan,P.green][i],drop:hold?1:(us-c2-.4-i*.3)/.4,label:['derive','plot','check'][i],labelY:790}))};
S['B3.S2']={tag:'CONCEPT',elements:E('badge','card','person','icons'),draw(c,us,k){questionDraw(c,us,k)}};
S['B3.S3']={tag:'CONCEPT',elements:E('badge','card','person','icons'),draw(c,us,k){questionDraw(c,us,k,{hold:true})}};

// ---------------------------------------------------------------- Q2: scope and hypothesis
const SC=[{t:'Not a replication',s:'and not clinical validation',ph:'not a replication',ic:'no'},
          {t:'20 people',s:'one public dataset',ph:'Twenty people',ic:'people'},
          {t:'Unseen people only',s:'answers hold within this data',ph:'unseen people only',ic:'q'}];
const scopeIcon=(c,ic,cx,cy,a)=>{c.save();c.globalAlpha*=a;
  if(ic==='no'){c.strokeStyle=P.amber;c.lineWidth=7;c.lineCap='round';c.beginPath();c.arc(cx,cy,44,0,Math.PI*2);c.stroke();c.beginPath();c.moveTo(cx-31,cy+31);c.lineTo(cx+31,cy-31);c.stroke()}
  else if(ic==='people'){for(let i=0;i<10;i++){Person(c,{x:cx-120+(i%5)*60,y:cy-28+(i>=5?56:0),s:30,state:'neutral'})}}
  else{Person(c,{x:cx,y:cy+6,s:84,state:'test',q:true,glowA:.3})}
  c.restore()};
const scopeCards=(c,k,{p=[1,1,1],y=300,h=330,mini=0})=>{SC.forEach((s,i)=>{const x=120+i*580,a=smooth(p[i]);
  if(mini>0){if(i===0)c._mx=470;const w=pill(c,s.t,c._mx,172,{size:22,color:P.muted,align:'left',pad:18,alpha:mini});c._mx+=w+22;return}
  c.save();c.globalAlpha*=1;surface(c,[x,y,520,h],'#10213A',{level:'E2',r:18,alpha:a});
  if(a<1){c.save();c.globalAlpha*=1-a;c.setLineDash([8,7]);c.strokeStyle='rgba(147,163,184,.35)';c.lineWidth=2;c.beginPath();c.roundRect(x,y,520,h,18);c.stroke();c.restore()}
  c.restore();scopeIcon(c,s.ic,x+260,y+110,a);T(c,s.t,x+260,y+230,{size:38,weight:'bold',align:'center',alpha:a,rise:10});T(c,s.s,x+260,y+275,{size:26,color:P.muted,align:'center',alpha:a})})};
S['Q2.S1']={tag:'CONCEPT',elements:E('badge','cards'),draw(c,us,k){badge(c,k,.85);
  T(c,'Scope',960,250,{size:44,weight:'bold',align:'center',alpha:smooth(us/.5)});scopeCards(c,k,{p:[0,0,0]})}};
S['Q2.S2']={tag:'CONCEPT',elements:E('badge','cards'),draw(c,us,k){badge(c,k,.85);
  T(c,'Scope',960,250,{size:44,weight:'bold',align:'center'});
  scopeCards(c,k,{p:SC.map(s=>(us-k.cue('Q2.c1',s.ph)+.15)/.5)})}};
const hyp=(c,k,us,{h1,h2,stamp,hold=false})=>{badge(c,k,.85);
  scopeCards(c,k,{mini:1});
  const H=[{n:'1',t:'Nights differ in signal strength',s:'a model trained on some nights misreads others',col:P.amber},
          {n:'2',t:'Scale each night by its own statistics',s:'then the problem should shrink',col:P.violet}];
  H.forEach((h,i)=>{const p=clamp([h1,h2][i]),y=290+i*210,x=240;if(p<=0)return;const e=outBack(clamp(p*1.4));
    c.save();c.globalAlpha*=smooth(p*3);c.translate(lerp(60,0,e),0);surface(c,[x,y,1440,170],'#10213A',{level:'E2',r:18});
    c.fillStyle=h.col;c.beginPath();c.roundRect(x,y,10,170,5);c.fill();
    T(c,h.n,x+64,y+108,{size:84,weight:'bold',color:h.col,align:'center'});
    T(c,h.t,x+130,y+80,{size:42,weight:'bold'});T(c,h.s,x+130,y+126,{size:28,color:P.muted});c.restore()});
  if(stamp>0)Stamp(c,{k,el:'stamp',text:'POST-HOC',cx:1560,cy:600,p:stamp,color:P.amber,rot:5,seed:7,scale:.8})};
S['Q2.S3']={tag:'CONCEPT',elements:E('badge','cards','h1','h2','stamp'),draw(c,us,k){
  const a=k.cue('Q2.c2','Hypothesis'),b=k.cue('Q2.c2','per-night scaling'),s=k.cue('Q2.c2','formed after');
  hyp(c,k,us,{h1:(us-a)/.5,h2:(us-b+.8)/.5,stamp:(us-s-.2)/.5})}};
S['Q2.S4']={tag:'CONCEPT',elements:E('badge','cards','h1','h2','stamp'),draw(c,us,k){hyp(c,k,us,{h1:1,h2:1,stamp:1.5})}};
export const s1=S;
