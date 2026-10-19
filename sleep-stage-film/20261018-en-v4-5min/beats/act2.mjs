import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,T,poly,dot,rect,typed,seg,measure,wrap} from '../lib.mjs';
import {HYPNO} from '../shared.mjs';
import {NightStrip,tileX} from '../components/strip.mjs';
import {Bracket,Pill,Roman} from '../components/misc.mjs';
import {glowCircle,glowRect,surface} from '../light.mjs';
import {fact,factRaw} from '../facts.mjs';
import {RefBadge,Padlock,NumText,Chip} from '../components/cards.mjs';
import {Person,MiniStrip,PeopleGrid,IconChip,foldState,gridPos} from '../components/people.mjs';
import {PipelineBlock,Slot,Connector} from '../components/model.mjs';
import {Spectrogram,Plates,Bar128} from '../components/spec.mjs';
import {EegFrame} from '../components/misc.mjs';
import {eeg,wavePts} from '../lib.mjs';
const S={};const E=(...ids)=>ids.map(id=>({id,in:0,out:99}));
const badge=(c,k,a=1)=>RefBadge(c,{k,el:'badge',alpha:a});
S['ActII']={tag:null,elements:E('roman','name'),draw(c,us,k){k.rec('ActCard',{el:'roman'});badge(c,k);Roman(c,'II',520,513,seg(us,.5,.8,x=>x),{col:P.violet});
  const nm='A different question';T(c,typed(nm,(us-1.2)/(nm.length*.04)),800,534,{size:64,weight:'bold'})}};
// ---- B3
S['B3.S1']={tag:'CONCEPT',elements:E('badge','bar','arrow'),draw(c,us,k){badge(c,k);
  const g=cubic((us-.9)/1.8),h=320*g;if(g>0){surface(c,[880,760-h,160,h],P.violet,{level:'E1',r:6,gradient:.06});
    const ay=760-h-24-120,a=g<1?1:1-.6*smooth((us-2.8)/.4);c.save();c.globalAlpha*=a*smooth((us-.9)/.3);c.strokeStyle=P.ink;c.fillStyle=P.ink;c.lineWidth=6;c.lineCap='round';
    c.beginPath();c.moveTo(960,ay+120);c.lineTo(960,ay+8);c.stroke();c.beginPath();c.moveTo(960,ay-6);c.lineTo(944,ay+20);c.lineTo(976,ay+20);c.closePath();c.fill();c.restore()}
  poly(c,[[760,760],[1160,760]],{stroke:P.line,width:3})}};
const Q1='How high can one number go?',Q2='does it still work on a person the model has never seen?';
S['B3.S2']={tag:'CONCEPT',elements:E('badge','cardL','cardR','person','strips'),draw(c,us,k){badge(c,k);
  const split=smooth((us-3.0)/1);for(let i=0;i<20;i++){const x=130+(i%10)*172,y=i<10?650:760;MiniStrip(c,{x,y,w:130,h:16,seed:i,alpha:.5*split*smooth((us-3.0-i*.04)/.3)})}
  const a=1-smooth((us-2.2)/.8),dx=-120*smooth((us-2.2)/.8);
  if(a>0){surface(c,[460+dx,250,1000,120],'#10213A',{level:'E2',r:18});T(c,Q1,960+dx,330,{size:52,weight:'bold',align:'center',alpha:a});
    const w=measure(c,Q1,52,'bold'),p=cubic((us-1.4)/.7);if(p>0)poly(c,[[960+dx-w/2,318],[960+dx-w/2+w*p,318]],{stroke:P.cyan,width:4,alpha:a})}
  const t0=2.4;if(us>t0){surface(c,[300,360,1320,200],'#10213A',{level:'E3',r:18,alpha:smooth((us-t0)/.4)});
    const words=Q2.split(' '),n=words.length,pr=clamp((us-t0-.3)/3.6),shown=Math.ceil(n*pr);const ln1=words.slice(0,6).join(' '),ln2=words.slice(6).join(' ');
    const txt=words.slice(0,shown).join(' ');const l1=txt.slice(0,ln1.length),l2=txt.length>ln1.length?txt.slice(ln1.length+1):'';
    T(c,l1,960,450,{size:52,weight:'bold',align:'center'});T(c,l2,960,520,{size:52,weight:'bold',align:'center'});
    const pi=words.indexOf('person'),pp=outBack((us-t0-.3-3.6*(pi+1)/n)/.5);if(pi<shown||pr>=1)Person(c,{k,el:'person',x:1480,y:455,s:84,state:'test',sc:clamp(pp),alpha:clamp(pp*2),glowA:.4})}}};
S['B3.S3']={tag:'CONCEPT',elements:E('badge','title','line','icons'),draw(c,us,k){badge(c,k);
  const sh=smooth(us/.8);T(c,Q2,960,lerp(450,230,sh),{size:lerp(52,32,sh),weight:'med',color:lerp(0,1,sh)>.5?P.muted:P.ink,align:'center'});
  const t0=k.cue('B3.c2','explain');T(c,typed('…and can we explain every step?',(us-.9)/1.2),960,430,{size:64,weight:'bold',align:'center'});
  const ic=['sigma','chart','check'],ph=['first principles','explain every step','step'];
  ic.forEach((n,i)=>{const lt=smooth((us-(1.6+i*.5))/.3),fade=i===2?1:1-.0;IconChip(c,{k,el:'icons',cx:620+i*340,y:560,icon:n,lit:lt,litCol:[P.violet,P.cyan,P.green][i],drop:(us-(1.5+i*.2))/.4})})}};
S['B3.S4']={tag:null,elements:E('badge','title','icons'),draw(c,us,k){badge(c,k,.82-.0*us);T(c,Q2,960,230,{size:32,weight:'med',color:P.muted,align:'center'});
  T(c,'…and can we explain every step?',960,430,{size:64,weight:'bold',align:'center'});['sigma','chart','check'].forEach((n,i)=>IconChip(c,{k,el:'icons',cx:620+i*340,y:560,icon:n,lit:.7,litCol:[P.violet,P.cyan,P.green][i],drop:1}))}};
// ---- B4
const COLX=[104,320,536,752],RX=[992,1208,1424,1640],BY=330;
const L4=[['sst','SST'],['cnn','CNN'],['contrastive','Contrastive'],['gru','GRU']];
function b4(c,k,{div=1,left=[1,1,1,1],right=[0,0,0],slot=1,leftA=1,glowC=0,slotText=0,badgeA=1,heads=1,icons=null}){
  RefBadge(c,{k,el:'badge',alpha:badgeA});poly(c,[[960,150],[960,150+740*div]],{stroke:P.line,width:2});
  T(c,'Our study',RX[0],178,{size:30,weight:'med',color:P.cyan,alpha:smooth(heads)});
  c.save();c.globalAlpha*=leftA;L4.forEach((b,i)=>{if(i<3)Connector(c,COLX[i]+176+4,BY+75,COLX[i+1]-4,{p:clamp(left[i+1]*2),alpha:left[i+1]>0?1:0});
    PipelineBlock(c,{k,el:'left',x:COLX[i],y:BY,kind:b[0],label:b[1],drop:left[i],glowC:i===2?P.amber:null,glowA:i===2?glowC*.6:0})});c.restore();
  const R=[['stft','STFT'],['cnn','CNN'],null,['bigru','BiGRU']];
  R.forEach((b,i)=>{if(!b){Slot(c,{x:RX[i],y:BY,alpha:slot,text:slotText>0?'no contrastive\nstage':null,tAlpha:slotText});return}
    const j=i===3?2:i;const dr=right[j];if(dr<=0)Slot(c,{x:RX[i],y:BY,alpha:slot});else PipelineBlock(c,{k,el:'right',x:RX[i],y:BY,kind:b[0],label:b[1],drop:dr,glowC:P.cyan,glowA:0});
    if(i>0&&dr>0){const pj=i===3?1:i-1;Connector(c,RX[i-1]+180,BY+75,RX[i]-4,{p:clamp(dr*2),col:P.cyan,alpha:i===3?1:1})}});
  if(icons)['pencil','sigma','check'].forEach((n,i)=>IconChip(c,{k,el:'icons',cx:RX[0]+88+i*216,y:560,icon:n,lit:icons[i],litCol:P.cyan,drop:clamp(icons[i]*3),label:['drawn','derived','checked'][i],labelY:740}))}
S['B4.S1']={tag:'CODE',elements:E('badge','left','right'),draw(c,us,k){const d=cubic(us/.8);
  b4(c,k,{div:d,left:[0,1,2,3].map(i=>(us-.9-i*.5)/.5),right:[0,0,0],slot:smooth((us-1)/.5),heads:(us-.8)/.3});}};
function pre4(us){return [1,1,1,1]}
S['B4.S2']={tag:'CODE',elements:E('badge','left','right','slot'),draw(c,us,k){
  const c1=k.cue('B4.c1','short-time Fourier'),c2=k.cue('B4.c1','CNN'),c3=k.cue('B4.c1','bidirectional'),g=us>2.0?Math.sin(Math.PI*clamp((us-2.4)/1.2)):0;
  b4(c,k,{left:pre4(),right:[(us-c1)/.5,(us-c2)/.5,(us-c3)/.5],glowC:g,slotText:smooth((us-2.8)/.4)});}};
S['B4.S3']={tag:'CODE',elements:E('badge','left','right','icons','reason'),draw(c,us,k){
  const g0=k.cue('B4.c2','contrastive'),r0=k.cue('B4.c2','time and compute'),a=k.cue('B4.c2','draw'),b=k.cue('B4.c2','derive'),d=k.cue('B4.c2','check');
  b4(c,k,{left:pre4(),right:[1,1,1],leftA:1-.3*smooth(us/.5),glowC:Math.sin(Math.PI*clamp((us-g0)/1.8)),slotText:smooth((us-g0)/.4),icons:[smooth((us-a)/.3),smooth((us-b)/.3),smooth((us-d)/.3)]});
  const ra=smooth((us-r0)/.4);T(c,'Not reproduced: time and compute limits',COLX[0],612,{size:28,weight:'med',color:P.amber,alpha:ra});
  rect(c,COLX[2],BY+160,176,8,rgba(P.amber,.6*ra),{r:3})}};
S['B4.S4']={tag:'CODE',elements:E('badge','left','right','icons','note'),draw(c,us,k){
  const h0=k.cue('B4.c3','helps or hurts');
  b4(c,k,{left:pre4(),right:[1,1,1],leftA:.55,slotText:1,icons:[1,1,1]});
  const n=smooth((us-h0)/.4);T(c,'Helps? Hurts?  Never compared.',960,830,{size:44,weight:'bold',color:P.amber,align:'center',alpha:n})}};
S['B4.S5']={tag:null,elements:E('badge','left','right'),camera:us=>({x:0,y:0,zoom:lerp(1,.96,smooth(us/1.5))}),draw(c,us,k){
  b4(c,k,{left:pre4(),right:[1,1,1],leftA:lerp(.55,1,smooth(us/.8)),slotText:1,icons:[1,1,1]});}};
// ---- B5
const EX=200,EW=1520;
S['B5.S1']={tag:'ILLU',elements:E('signal','label'),draw(c,us,k){
  const e=smooth(us/.8);surface(c,[EX,300,EW,220],'#0C1A2E',{level:'E1',r:12,alpha:e});
  const pts=wavePts(EX+12,410,EW-24,60,a=>eeg(a,3,'mixed'),400);poly(c,pts,{stroke:STAGE_COL[2],width:2.4,alpha:e});
  T(c,'one 30 s epoch of EEG',960,590,{size:30,weight:'med',color:P.muted,align:'center',alpha:smooth((us-.8)/.5)})}};
S['B5.S2']={tag:'ILLU',elements:E('strip','signal','spec','win'),draw(c,us,k){
  const sp=cubic((us-.8)/2.5);
  NightStrip(c,{k,el:'strip',y:180,h:44,x:104,appear:1,tray:false,alpha:.35,mode:i=>i===12?'on':'dim',lit:i=>i===12?1:0,range:[0,96]});
  const e=smooth(us/.7);const fy=250;surface(c,[EX,fy,EW,150],'#0C1A2E',{level:'E1',r:12,alpha:e});
  const pts=wavePts(EX+12,fy+75,EW-24,38,a=>eeg(a,3,'mixed'),400);poly(c,pts,{stroke:STAGE_COL[2],width:2.4,alpha:e});
  T(c,'30 s',EX+EW/2,fy+186,{size:26,weight:'med',color:P.muted,align:'center',alpha:e});
  const wu=(EW-24)/30,wx=EX+12+wu*Math.min(28,Math.floor(sp*29)),ww=wu*2;if(us>.8)rect(c,wx,fy+6,ww,138,rgba(P.cyan,.18*(1-.7*(sp>=1))),{stroke:P.cyan,sw:2,r:4});
  T(c,'2 s Hamming window · 1 s hop',EX+EW/2,fy-14,{size:26,weight:'med',color:P.cyan,align:'center',alpha:smooth((us-.5)/.4)});
  const sx=360,sy=470,sw=1200,sh=340;Spectrogram(c,{k,el:'spec',x:sx,y:sy,w:sw,h:sh,p:sp,alpha:smooth((us-.8)/.3)});
  const la=smooth((us-2.8)/.4);T(c,'frequency · '+fact('pipeline.shape',{idx:0})+' bins',sx-20,sy+sh/2,{size:26,weight:'med',color:P.muted,align:'right',alpha:la});
  T(c,'time · '+fact('pipeline.shape',{idx:1})+' frames',sx+sw/2,sy+sh+50,{size:26,weight:'med',color:P.muted,align:'center',alpha:la});
  Pill(c,{k,x:EX,y:200+0,w:0,h:0,text:'',alpha:0})}};
S['B5.S3']={tag:'ILLU',elements:E('spec','plates','label','bar'),draw(c,us,k){
  const sh=smooth(us/.8),sx=lerp(360,170,sh),sy=lerp(470,440,sh),sw=lerp(1200,260,sh),sHh=lerp(340,200,sh);
  Spectrogram(c,{k,el:'spec',x:sx,y:sy-60+60*0,w:sw,h:sHh,p:1});
  const t=us;Plates(c,{k,el:'plates',cx:880,cy:540,t,p:[(us-.8)/.5,(us-1.4)/.5,(us-2.0)/.5],squeeze:smooth((us-3)/1.5)});
  const bp=smooth((us-3.4)/1.2);Bar128(c,{k,el:'bar',x:1500,y:340,w:44,h:360,seed:1,p:bp});
  const m=smooth((us-4.4)/.8);T(c,fact('pipeline.shape',{idx:0})+' × '+fact('pipeline.shape',{idx:1}),1360,780,{size:60,weight:'bold',align:'center',alpha:(1-m)});
  T(c,fact('pipeline.embedding_size'),1360,780,{size:60,weight:'bold',align:'center',color:P.cyan,alpha:m})}};
S['B5.S4']={tag:'CODE',elements:E('bars','strip','bracket','arrows'),camera:us=>({x:0,y:0,zoom:lerp(1.06,1,smooth(us/1.2))}),draw(c,us,k){
  const n=fact('pipeline.window_epochs',{}),x0=200,pw=1520/20;
  for(let i=0;i<20;i++){const p=(us-.2-i*.05)/.4;Bar128(c,{x:x0+i*pw+4,y:300,w:pw-8,h:220,seed:i+3,p:clamp(p),lit:i===10?smooth((us-3.4)/.4):0,alpha:1})}
  NightStrip(c,{k,el:'strip',x:x0,w:1520,y:640,h:60,range:[38,58],appear:1,mode:'dim',lit:i=>0,tray:true,
    stage:i=>HYPNO[i]});
  const pr=smooth((us-4)/1.6);for(let i=0;i<20;i++){const q=smooth((us-4.2-Math.abs(i-10)*.08)/.3);if(q>0){const col=STAGE_COL[HYPNO[38+i]];rect(c,x0+i*pw+4,720,pw-8,36,col,{r:3,alpha:q})}}
  Bracket(c,{k,el:'bracket',x0:x0,x1:x0+1520,y:262,dir:1,p:cubic((us-1.2)/.6),col:P.ink,label:n+' epochs',lsize:30,labelAbove:true,tip:12,width:3});
  const ap=cubic((us-2.4)/1.0);if(ap>0){c.save();c.strokeStyle=P.cyan;c.lineWidth=4;c.lineCap='round';
    for(const dir of [1,-1]){c.beginPath();const y0=dir>0?560:590;c.moveTo(lerp(x0+100,x0+1420,dir>0?0:1),y0);c.bezierCurveTo(x0+500,y0+dir*60,x0+1000,y0+dir*60,lerp(x0+100,x0+1420,dir>0?ap:1-ap),y0);c.stroke()}c.restore()}
  T(c,'Bidirectional GRU',x0,232,{size:28,weight:'bold',color:P.cyan,align:'left',alpha:smooth((us-2.4)/.4)});T(c,'forward',x0+1560,570,{size:24,weight:'med',color:P.cyan,align:'right',alpha:smooth((us-3)/.3)});T(c,'backward',x0+1560,610,{size:24,weight:'med',color:P.cyan,align:'right',alpha:smooth((us-3)/.3)})}};
S['B5.S5']={tag:null,elements:E('bars','strip'),draw(c,us,k){const x0=200,pw=76;for(let i=0;i<20;i++)Bar128(c,{x:x0+i*pw+4,y:300,w:pw-8,h:220,seed:i+3,lit:i===10?1:0});
  NightStrip(c,{k,el:'strip',x:x0,w:1520,y:640,h:60,range:[38,58],appear:1,mode:'dim',stage:i=>HYPNO[i]});
  for(let i=0;i<20;i++)rect(c,x0+i*pw+4,720,pw-8,36,STAGE_COL[HYPNO[38+i]],{r:3});
  Bracket(c,{k,el:'bracket',x0,x1:x0+1520,y:262,dir:1,p:1,col:P.ink,label:'20 epochs',lsize:30,tip:12,width:3})}};
// ---- B6
const cnt=(t,v)=>Math.round(v*outExpo(clamp(t)));
const fmtc=n=>n.toLocaleString('en-US');
S['B6.S1']={tag:'MEAS',elements:E('grid','counter'),camera:us=>({x:0,y:0,zoom:lerp(1.06,1,smooth(us/.9))}),draw(c,us,k){
  PeopleGrid(c,{k,el:'grid',appear:i=>(us-.2-i*.05)/.35});
  fact('study.participants');fact('study.nights');fact('study.epochs',{comma:true});
  T(c,fact('study.participants')+' people',960,800,{size:44,weight:'bold',align:'center',alpha:smooth((us-1.0)/.3)})}};
const FOLDCOL={train:P.blue,choose:P.amber,test:P.coral};
S['B6.S2']={tag:'CODE',elements:E('grid','legend','counter'),draw(c,us,k){
  const f=us<2.6?0:Math.min(9,Math.floor((us-2.6)/.35)),st=i=>foldState(i,f);
  const testSet=new Set([2*f,2*f+1]);
  PeopleGrid(c,{k,el:'grid',state:st,glowSet:testSet,glowA:.55,strips:1});
  const la=smooth((us-.6)/.4)*(us<2.6?1:.0+1);const items=[['16 train',P.blue],['2 choose checkpoint',P.amber],['2 test',P.coral]];let x=420;
  items.forEach(([s,col],i)=>{dot(c,x,790,9,col,la);T(c,s,x+20,798,{size:28,weight:'med',color:P.ink,alpha:la});x+=measure(c,s,28,'med')+90});
  const tested=us<2.6?0:Math.min(20,2*(f+1));const t1=us>=2.6?1:0;
  T(c,`tested once: ${tested} / ${fact('study.participants')}`,1600,798,{size:28,weight:'med',color:P.muted,align:'right',alpha:t1});}};
S['B6.S3']={tag:'CODE',elements:E('person','strip','lock'),draw(c,us,k){
  const y=420;Person(c,{k,el:'person',x:960,y:y-60,s:150,state:'neutral',alpha:1});
  const split=us<2.4?smooth((us-.6)/1):1-smooth((us-3.6)/1),w=520,h=46;
  const lx=lerp(700,420,split),rx=lerp(960,1020,split),ly=lerp(600,600,split);
  const half=(x,col,lab,dyy)=>{for(let i=0;i<8;i++){const sc=STAGE_COL[HYPNO[(i*7+(lab==='test'?3:0))%96]];const tx=x+i*(w/2/8);surface(c,[tx,ly+dyy+(i%2)*0,w/2/8-3,h],sc,{level:'E1',r:3,gradient:.05})}};
  half(lx,P.blue,'train',0);half(rx,P.coral,'test',0);
  const sp=smooth((us-1.3)/.4)*(1-smooth((us-3.6)/.4));
  if(sp>0){T(c,'train',lx+130,560,{size:28,weight:'med',color:P.blue,align:'center',alpha:sp});T(c,'test',rx+130,560,{size:28,weight:'med',color:P.coral,align:'center',alpha:sp});
    c.save();c.globalAlpha*=sp;c.strokeStyle=P.red||'#FF5C6C';c.lineWidth=10;c.lineCap='round';c.beginPath();c.moveTo(930,650);c.lineTo(990,710);c.moveTo(990,650);c.lineTo(930,710);c.stroke();c.restore();
    T(c,'same person in both',960,780,{size:36,weight:'bold',color:'#FF8F9B',align:'center',alpha:sp})}
  const lk=smooth((us-4.4)/.5);if(lk>0){Padlock(c,{k,el:'lock',x:932,y:690,open:1-lk,alpha:lk});T(c,'one person → one set',960,810,{size:40,weight:'bold',align:'center',alpha:smooth((us-4.8)/.4)})}}};
S['B6.S4']={tag:'CODE',elements:E('grid'),draw(c,us,k){const t=new Set([18,19]);PeopleGrid(c,{k,el:'grid',state:i=>t.has(i)?'test':'neutral',glowSet:t,glowA:.4+.35*smooth(us/1.6)})}};
export const act2=S;
