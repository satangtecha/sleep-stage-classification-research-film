import {P,STAGE_COL,STAGES,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,T,poly,dot,rect,wavePts,eeg,typed,seg,measure} from '../lib.mjs';
import {HYPNO,DEMO_TILES} from '../shared.mjs';
import {NightStrip,Legend,stageColor,tileX} from '../components/strip.mjs';
import {EegFrame,Bracket,Pen,HeadTop,Roman,Pill} from '../components/misc.mjs';
import {glowCircle,glowRect,tray} from '../light.mjs';
import {partial} from '../motion.mjs';
import {fact,factRaw} from '../facts.mjs';
import {PaperCard,RefBadge,Ring,Chip,Belt,chipW} from '../components/cards.mjs';
import {surface} from '../light.mjs';

const S={};
const wave=(amp)=>wavePts(210,600,1500,amp,a=>eeg(a,1,'mixed'),480);
S['T1']={tag:null,elements:[{id:'line',in:0,out:6},{id:'title',in:2,out:6},{id:'sub',in:3.5,out:6},{id:'row',in:5.6,out:6}],
 draw(c,us,k){
  const draw=cubic(us/2.8),amp=60*(1-smooth((us-5)/.6));
  k.rec('Cover',{el:'line'});
  const pts=wave(amp),part=partial(pts,draw),lineA=1-smooth((us-5.6)/.4);
  if(part.length>1){poly(c,part,{stroke:P.cyan,width:3,alpha:lineA});
    if(us<5.2){const h=part.at(-1);glowCircle(c,h[0],h[1],6,P.cyan,{blur:18,alpha:.9*(1-smooth((us-5)/.4))});glowCircle(c,h[0],h[1],26,P.cyan,{blur:26,alpha:.25*(1-smooth((us-5)/.4))});dot(c,h[0],h[1],5,P.cyan,1-smooth((us-5)/.4))}}
  T(c,'Reading Sleep from One EEG Channel',960,410,{size:70,weight:'bold',align:'center',alpha:smooth((us-2)/.3),rise:10});
  T(c,'What we tried, what broke, and what we can honestly say',960,470,{size:32,color:P.muted,align:'center',alpha:smooth((us-3.5)/.3),rise:10});
  NightStrip(c,{k,el:'row',y:568,appear:i=>(us-5.6-i*.004)/.25,tray:false,act:1,alpha:1})}};
S['ActI']={tag:null,elements:[{id:'roman',in:.5,out:2.5},{id:'name',in:1.2,out:2.5}],
 draw(c,us,k){k.rec('ActCard',{el:'roman'});Roman(c,'I',560,513,seg(us,.5,.8,x=>x),{col:P.cyan});
  const nm='A night in 30-second pieces';T(c,typed(nm,(us-1.2)/(nm.length*.04)),800,534,{size:64,weight:'bold'})}};
// ---- B1

S['B1.S1']={tag:'ILLU',elements:[{id:'strip',in:0,out:3.5},{id:'legend',in:1.6,out:3.5}],
 draw(c,us,k){k.L(3,()=>NightStrip(c,{k,el:'strip',y:481,appear:i=>(us-i*.0345)/.25}));
  k.L(6,()=>Legend(c,{k,el:'legend',y:598,t:us-1.6}))}};
const frameX=[205,419,598],frameY=250;
S['B1.S2']={tag:'ILLU',elements:[{id:'strip',in:0,out:6},{id:'frames',in:1.2,out:6},{id:'bracket',in:2,out:6},{id:'pen',in:4.2,out:6},{id:'labels',in:4.2,out:6}],
 camera:us=>({x:-452*smooth(us/1.2),y:0,zoom:lerp(1,2,smooth(us/1.2))}),
 draw(c,us,k){
  const cueP=k.cue('B1.c1','Experts score'),litOut=1-smooth((us-5.6)/.4);
  k.L(3,()=>NightStrip(c,{k,el:'strip',y:481,appear:1,lit:i=>DEMO_TILES.includes(i)?smooth((us-(1.2+DEMO_TILES.indexOf(i)*.25))/.2)*litOut:0}));
  if(us<.4)Legend(c,{k,y:598,t:1,alpha:1-smooth(us/.4)});
  const kinds=['fast','mixed','slow'],labs=['W','N2','N3'],cols=[STAGE_COL[0],STAGE_COL[2],STAGE_COL[3]],amps=[.45,1,1.25];
  DEMO_TILES.forEach((tile,j)=>{const t0=1.2+j*.25,p=outBack(clamp((us-t0)/.5));if(p<=0)return;
    const tx=[187.6,401.6,580][j]+0,x=lerp(tx,frameX[j],p),w=lerp(14,150,clamp(p)),y=lerp(481-0,frameY,clamp(p)),h=lerp(64,110,clamp(p));
    EegFrame(c,{k,el:'frames',x:frameX[j],y:frameY,w:150,h:110,mode:kinds[j],amp:amps[j]*.8,seed:j+2,alpha:smooth((us-t0)/.25),label:null,r:10,ampPx:36,lw:2.2,color:cols[j]})});
  const bp=cubic((us-2)/.5);if(bp>0)Bracket(c,{k,el:'bracket',x0:frameX[0],x1:frameX[0]+150,y:380,dir:-1,p:bp,col:P.ink,label:fact('study.epoch_seconds')+' s',lsize:26,labelAbove:false,tip:12,width:3});
  labs.forEach((l,j)=>{const t0=cueP+j*.5;if(us<t0)return;T(c,typed(l,(us-t0-.35)/(l.length*.04)),frameX[j]+75,236,{size:28,weight:'med',color:cols[j],align:'center'});
    if(us>t0&&us<t0+.35){}});
  // pen travels W -> N2 -> N3
  const pj=clamp((us-cueP)/.5,0,2.999),pi=Math.floor(pj),pf=cubic((pj-pi)*.5/.35);const px=lerp(frameX[Math.min(2,pi)]+90,frameX[Math.min(2,pi+(pf>0&&pi<2?1:0))]+90,pf);
  if(us>cueP-.1)Pen(c,frameX[pi]+112+(pi<2?(frameX[pi+1]-frameX[pi])*pf:0),240,{alpha:smooth((us-cueP+.1)/.2)})}};
S['B1.S3']={tag:'ILLU',elements:[{id:'strip',in:0,out:7.4},{id:'head',in:1,out:7.4},{id:'bracket',in:2,out:7.4},{id:'q',in:.9,out:7.4}],
 camera:us=>({x:-452*(1-smooth(us/1.2)),y:0,zoom:lerp(2,1,smooth(us/1.2))}),
 draw(c,us,k){
  k.L(3,()=>NightStrip(c,{k,el:'strip',y:481,appear:1}));
  // frames shrink back
  const sh=1-smooth(us/.6);if(sh>0)DEMO_TILES.forEach((t,j)=>EegFrame(c,{k,x:frameX[j],y:frameY,w:150,h:110,mode:['fast','mixed','slow'][j],seed:j+2,alpha:sh,r:10,ampPx:36}));
  const hp=outBack(clamp((us-1)/.8)),hx=lerp(1900,1580,hp);
  const pts=HeadTop(c,{k,el:'head',cx:hx,cy:300,r:120,alpha:smooth((us-1)/.4),fpz:smooth((us-2)/.25),cz:smooth((us-2.25)/.25)});
  const bp=cubic((us-2.6)/.6);if(bp>0){const xb=1580-120*.86-26;poly(c,partial([[xb+10,pts.f[1]],[xb,pts.f[1]],[xb,pts.z[1]],[xb+10,pts.z[1]]],bp),{stroke:P.ink,width:3});
    T(c,'one voltage difference',xb-18,(pts.f[1]+pts.z[1])/2+9,{size:26,weight:'med',color:P.ink,align:'right',alpha:smooth((us-3)/.4)})}
  const cue=k.cue('B1.c2','Can a computer'),qs=smooth((us-cue)/.3),pulse=us<5.2?1+.08*Math.sin(2*Math.PI*1.2*(us-cue)):1;
  if(qs>0){c.save();c.translate(960,420);c.scale(pulse,pulse);T(c,'?',0,26,{size:72,weight:'bold',color:P.amber,align:'center',alpha:qs});c.restore()}}};


// ---- B2 The reference
const faintStrip=(c,k,a)=>{if(a<=0)return;k.L(2,()=>{c.save();c.filter='blur(2px)';NightStrip(c,{k,el:'bgstrip',y:481,appear:1,alpha:a*.2,tray:false});c.restore()})};
const paper=()=>({title:fact('paper.title'),venue:`${fact('paper.venue')} \u00b7 ${fact('paper.year')}`,authors:fact('paper.authors_short')});
const CHIPS=['Synchrosqueezed transform','CNN','Contrastive learning','GRU'];
const chipXs=c=>{let x=140;return CHIPS.map(t=>{const w=chipW(c,t);const r=x;x+=w+24;return r})};
S['B2.S1']={tag:'REF',elements:[{id:'paper',in:0,out:3.5},{id:'bgstrip',in:0,out:3.5}],
 draw(c,us,k){faintStrip(c,k,1);const ry=lerp(-20,8,outBack(us/.9))*Math.PI/180;k.L(5,()=>PaperCard(c,{k,el:'paper',ry,...paper()}))}};
S['B2.S2']={tag:'REF',elements:[{id:'paper',in:0,out:8.4},{id:'ring',in:1,out:8.4},{id:'chips',in:3,out:8.4},{id:'bgstrip',in:0,out:8.4}],
 draw(c,us,k){faintStrip(c,k,1);k.L(5,()=>PaperCard(c,{k,el:'paper',...paper()}));
  const cr=k.cue('B2.c1','about 83%')-.1,rp=cubic((us-cr)/1.6),v=Math.round(83*rp);fact('paper.reported_accuracy_pct');
  k.L(4,()=>{if(us>=cr){Ring(c,{k,el:'ring',cx:1330,cy:434,p:.83*rp,text:v+'%',alpha:smooth((us-cr)/.2)});T(c,'Reported accuracy',1330,580,{size:24,color:P.muted,align:'center',alpha:smooth((us-cr-.6)/.4)})}
    Belt(c,{x0:140,x1:1780,y:768,t:us});const xs=chipXs(c);
    [['synchrosqueezed transform',0],['a CNN',1],['contrastive learning',2],['a GRU',3]].forEach(([ph,i])=>{const cu=k.cue('B2.c1',ph)-.25;Chip(c,{k,el:'chips',x:xs[i],y:740,text:CHIPS[i],drop:(us-cu)/.5})})})}};
S['B2.S3']={tag:'ILLU',elements:[{id:'paper',in:0,out:4.8},{id:'ring',in:0,out:4.8},{id:'beltP',in:0,out:4.8},{id:'beltO',in:.2,out:4.8}],
 draw(c,us,k){faintStrip(c,k,1);k.L(5,()=>PaperCard(c,{k,el:'paper',...paper()}));
  const c0=k.cue('B2.c2','We set out to reproduce it'),stopT=k.cue('B2.c2','we could not')+.3,decel=2.5;
  const dim=1-.55*smooth((us-c0)/.8);fact('paper.reported_accuracy_pct');
  k.L(4,()=>{Ring(c,{k,el:'ring',cx:1330,cy:434,p:.83,text:'83%',alpha:dim});T(c,'Reported accuracy',1330,580,{size:24,color:P.muted,align:'center',alpha:dim});
    Belt(c,{x0:140,x1:1780,y:768,t:us+8.4});const xs=chipXs(c);CHIPS.forEach((t,i)=>Chip(c,{k,el:'beltP',x:xs[i],y:740,text:t}));
    Belt(c,{x0:140,x1:1780,y:850,t:0,dashed:true});
    // spinner angle = integral of angular velocity (1 turn/s until stopT-decel, then smooth to 0)
    let ang=0;const t0=stopT-decel;for(let tt=0;tt<us;tt+=.02){const v=tt<t0?1:1-smooth((tt-t0)/decel);ang+=v*.02*2*Math.PI}
    CHIPS.forEach((t,i)=>{const a0=c0+i*.3;Chip(c,{k,el:'beltO',x:xs[i],y:822,text:t,ghost:true,drop:(us-a0)/.4,spin:i===3?ang:null})})})}};
S['B2.S4']={tag:'REF',elements:[{id:'paper',in:0,out:3.7},{id:'bgstrip',in:0,out:1}],
 draw(c,us,k){const f=1-smooth(us/.5);faintStrip(c,k,1-smooth(us/1));
  k.L(5,()=>PaperCard(c,{k,el:'paper',morph:clamp((us-.4)/1),...paper()}));
  if(f>0)k.L(4,()=>{Ring(c,{k,el:'ring',cx:1330,cy:434,p:.83,text:'83%',alpha:.45*f});const xs=chipXs(c);CHIPS.forEach((t,i)=>{Chip(c,{x:xs[i],y:740,text:t,alpha:f});Chip(c,{x:xs[i],y:822,text:t,ghost:true,alpha:f})})})}};
export const act1=S;
