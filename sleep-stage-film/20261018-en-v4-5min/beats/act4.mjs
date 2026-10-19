import {P,STAGE_COL,clamp,lerp,smooth,cubic,outBack,outExpo,rgba,mixCol,T,poly,dot,rect,typed,seg,measure,wrap} from '../lib.mjs';
import {HYPNO,n1Sim,vennDistance,lensArea} from '../shared.mjs';
import {NightStrip,tileX,stageColor,TRAY} from '../components/strip.mjs';
import {Roman,Pill,Bracket} from '../components/misc.mjs';
import {surface,bevel,glowRect,glowCircle} from '../light.mjs';
import {fact,factRaw,derived} from '../facts.mjs';
import {NumberCard,NumText,Stamp,Padlock} from '../components/cards.mjs';
import {Person} from '../components/people.mjs';
const S={};const E=(...ids)=>ids.map(id=>({id,in:0,out:99}));
const PINK='#FF8FA3',GRN='#7EE0A1',AMB='#FFC46B',SL=P.slate;
S['ActIV']={tag:null,elements:E('roman','name'),draw(c,us,k){k.rec('ActCard',{el:'roman'});Roman(c,'IV',470,513,seg(us,.5,.8,x=>x),{col:'#93A3B8'});
  const nm='What we can honestly say';T(c,typed(nm,(us-1.2)/(nm.length*.04)),800,534,{size:64,weight:'bold'})}};
// ---- B10
const SC0=12,SC1=84;
const strip10=(c,k,{al=1}={})=>NightStrip(c,{k,el:'strip',y:430,appear:1,act:4,alpha:al,mode:i=>i<SC0||i>=SC1?'unscored':'on'});
S['B10.S1']={tag:'CODE',elements:E('strip','bracket','label'),draw(c,us,k){strip10(c,k);const x0=tileX(SC0),x1=tileX(SC1),p=cubic((us-1)/.9);
  Bracket(c,{k,el:'bracket',x0,x1:lerp(x0,x1,p),y:395,dir:1,p:1,col:P.cyan,label:null,tip:12,width:4});
  T(c,'R1 range: scored epochs',(x0+x1)/2,350,{size:30,weight:'med',color:P.cyan,align:'center',alpha:smooth((us-1.8)/.5)})}};
S['B10.S2']={tag:'MEAS',elements:E('strip','brackets','card'),draw(c,us,k){strip10(c,k);const x0=tileX(SC0),x1=tileX(SC1);
  Bracket(c,{k,el:'bracket',x0,x1,y:395,dir:1,p:1,col:P.cyan,tip:12,width:4});T(c,'R1 range: scored epochs',(x0+x1)/2,350,{size:30,weight:'med',color:P.cyan,align:'center'});
  const e=cubic(us/1),a0=lerp(x0,104,e),a1=lerp(x1,1816,e);Bracket(c,{k,el:'bracket2',x0:a0,x1:a1,y:310,dir:1,p:1,col:AMB,tip:12,width:4});
  T(c,'Full-night range: whole recording',960,270,{size:30,weight:'med',color:AMB,align:'center',alpha:smooth((us-.9)/.4)});
  const ca=cubic((us-1.6)/.6);NumberCard(c,{k,el:'card',x:780,y:560+(1-ca)*40,size:'S',label:'Macro-F1',text:fact('test.fullnight.subject_mf1.point',{mul:100}),color:P.ink,sub:'full-night statistics',alpha:ca})}};
const DK='comparison',DIFF='differences.fullnight-minus-r1.per_subject_mean_macro_f1';
S['B10.S3']={tag:'MEAS',elements:E('axis','point','interval','labels'),draw(c,us,k){
  const X=v=>300+(v+8)/10*1320,y=520,pt=factRaw(DIFF+'.point')*100,[lo,hi]=factRaw(DIFF+'.ci95').map(v=>v*100);
  for(let v=-8;v<=2;v+=2){poly(c,[[X(v),y-110],[X(v),y+110]],{stroke:P.grid,width:1.5});T(c,(v<0?'−':v>0?'+':'')+Math.abs(v),X(v),y+160,{size:26,color:P.muted,align:'center'})}
  poly(c,[[300,y+120],[1620,y+120]],{stroke:P.line,width:2});poly(c,[[X(0),y-130],[X(0),y+120]],{stroke:P.ink,width:3});
  T(c,'0 = no difference',X(0),y-150,{size:28,weight:'med',align:'center',alpha:smooth((us-.4)/.4)});T(c,'Full-night minus R1 (points)',960,y+215,{size:28,color:P.muted,align:'center'});
  const pa=smooth((us-.8)/.4),L=cubic((us-1.4)/1.4),Rr=cubic((us-2.8)/1.2);
  poly(c,[[X(pt),y],[lerp(X(pt),X(lo),L),y]],{stroke:AMB,width:6});poly(c,[[X(pt),y],[lerp(X(pt),X(hi),Rr),y]],{stroke:AMB,width:6});
  if(L>.98)poly(c,[[X(lo),y-16],[X(lo),y+16]],{stroke:AMB,width:5});if(Rr>.98)poly(c,[[X(hi),y-16],[X(hi),y+16]],{stroke:AMB,width:5});
  dot(c,X(pt),y,13,P.ink,pa);T(c,fact(DIFF+'.point',{mul:100,signed:true}),X(pt),y-36,{size:34,weight:'bold',align:'center',alpha:pa});
  T(c,fact(DIFF+'.ci95',{idx:0,mul:100,signed:true}),X(lo),y+60,{size:28,color:P.muted,align:'center',alpha:L>.98?1:0});T(c,fact(DIFF+'.ci95',{idx:1,mul:100,signed:true}),X(hi),y+60,{size:28,color:P.muted,align:'center',alpha:Rr>.98?1:0})}};
S['B10.S4']={tag:'MEAS',elements:E('axis','point'),draw(c,us,k){
  const X=v=>300+(v+8)/10*1320,y=520,pt=factRaw(DIFF+'.point')*100,[lo,hi]=factRaw(DIFF+'.ci95').map(v=>v*100),f=1-smooth((us-.9)/.8),pl=Math.sin(Math.PI*clamp(us/.8));
  for(let v=-8;v<=2;v+=2){poly(c,[[X(v),y-110],[X(v),y+110]],{stroke:P.grid,width:1.5});T(c,(v<0?'−':v>0?'+':'')+Math.abs(v),X(v),y+160,{size:26,color:P.muted,align:'center'})}
  poly(c,[[300,y+120],[1620,y+120]],{stroke:P.line,width:2});poly(c,[[X(0),y-130],[X(0),y+120]],{stroke:P.ink,width:3});T(c,'0 = no difference',X(0),y-150,{size:28,weight:'med',align:'center'});T(c,'Full-night minus R1 (points)',960,y+215,{size:28,color:P.muted,align:'center'});
  poly(c,[[X(lo),y],[X(hi),y]],{stroke:AMB,width:6+4*pl,alpha:f});poly(c,[[X(lo),y-16],[X(lo),y+16]],{stroke:AMB,width:5,alpha:f});poly(c,[[X(hi),y-16],[X(hi),y+16]],{stroke:AMB,width:5,alpha:f});
  dot(c,X(pt),y,13,P.ink);T(c,fact(DIFF+'.point',{mul:100,signed:true}),X(pt),y-36,{size:34,weight:'bold',align:'center'})}};
// ---- B11
const CM=()=>factRaw('comparison.runs.r1.pooled_confusion');
const n1=()=>{const cm=CM();const row=cm[1].reduce((a,b)=>a+b,0),col=cm.reduce((a,r)=>a+r[1],0),both=cm[1][1];return {row,col,both}};
const fmtc=n=>n.toLocaleString('en-US');
const dark=(c,x,y,w,h,col,lit,alpha=1)=>{bevel(c,x,y,w,h,lit?col:mixCol(col,TRAY,.86),{r:3,half:!lit,alpha})};
S['B11.S1']={tag:'MIX',elements:E('rows','links'),draw(c,us,k){const {E:eIdx,both,M}=n1Sim(HYPNO,CM());const mset=new Set(M),bset=new Set(both),x=104,pw=1712/96,tw=pw-3,y0=400,y1=540;
  for(let i=0;i<96;i++){const a=smooth((us-i*.004)/.25);if(a<=0)continue;c.save();c.globalAlpha*=a;const col=stageColor(1,4)&&STAGE_COL[1],isN1=HYPNO[i]===1;
    dark(c,x+i*pw,y0,tw,56,STAGE_COL[HYPNO[i]],isN1);dark(c,x+i*pw,y1,tw,56,STAGE_COL[1],mset.has(i));
    if(bset.has(i)){const lp=smooth((us-1.6-i*.01)/.4);if(lp>0)poly(c,[[x+i*pw+tw/2,y0+56],[x+i*pw+tw/2,y0+56+(y1-y0-56)*lp]],{stroke:'#FFFFFF',width:2,alpha:.6})}c.restore()}
  T(c,'Expert',104,380,{size:30,weight:'med',color:P.muted});T(c,'Model',104,634,{size:30,weight:'med',color:P.muted})}};
S['B11.S2']={tag:'MEAS',elements:E('venn','nums','pct'),draw(c,us,k){const {row,col,both}=n1(),rB=175,rA=rB*Math.sqrt(row/col),d=vennDistance(rA,rB,Math.PI*rA*rA*both/row);
  const cx=520,cy=480,e=smooth(us/.9),t=n=>Math.round(n*outExpo((us-.6)/1.6));
  c.save();c.globalAlpha*=e;c.fillStyle=rgba(P.cyan,.22);c.strokeStyle=P.cyan;c.lineWidth=3;c.beginPath();c.arc(cx,cy,rA,0,Math.PI*2);c.fill();c.stroke();
  c.fillStyle=rgba(AMB,.22);c.strokeStyle=AMB;c.beginPath();c.arc(cx+d,cy,rB,0,Math.PI*2);c.fill();c.stroke();c.restore();
  const tn=(n,key)=>{const s=fmtc(t(n));if((us-.6)/1.6>=1)return derived(key,n,fmtc(n));return s};
  T(c,'True N1 · '+tn(row,'n1.true'),cx-rA+40,cy-rB-30,{size:30,weight:'bold',color:P.cyan,alpha:e});T(c,'Called N1 · '+tn(col,'n1.called'),cx+d+rB-40,cy+rB+50,{size:30,weight:'bold',color:AMB,align:'right',alpha:e});
  T(c,'Both · '+tn(both,'n1.both'),cx+d/2-(rB-rA)/2*0+(rA-rB)/2+0,cy+8,{size:28,weight:'bold',align:'center',alpha:e});
  const c1=k.cue('B11.c1','44.69%'),c2=k.cue('B11.c1','38.91%'),a1=smooth((us-c1)/.4),a2=smooth((us-c2)/.4);
  T(c,'Recall',1300,430,{size:30,weight:'med',color:P.cyan,alpha:a1});NumText(c,fact('test.r1.recall',{idx:1,pct:2}),1300,500,{size:72,weight:'bold',alpha:a1});
  T(c,'Precision',1300,590,{size:30,weight:'med',color:AMB,alpha:a2});NumText(c,derived('n1.precision',both/col,(100*both/col).toFixed(2)+'%'),1300,660,{size:72,weight:'bold',alpha:a2})}};
const PIL=['Logit adjustment','Head-only retraining','Sequence decoder'];
const rej=(c,k,us,{t0=[.8,1.6,2.4],shrink=0})=>{PIL.forEach((n,i)=>{const x=150+i*560,y=lerp(400,700,shrink),h=lerp(160,70,shrink);surface(c,[x,y,500,h],'#10213A',{level:'E2',r:14});T(c,n,x+250,y+h/2+(h>100?-4:10),{size:lerp(34,28,shrink),weight:'bold',align:'center'});
  Stamp(c,{k,el:'stamps',text:'REJECTED',cx:x+250,cy:y+h/2+(h>100?44:0)+(h<100?0:0),p:(us-t0[i])/.5,color:PINK,scale:.55,rot:i%2?4:-4,seed:i+3})})};
S['B11.S3']={tag:'MEAS',elements:E('venn','cards','stamps','label'),draw(c,us,k){const sh=smooth(us/.7);
  c.save();c.translate(lerp(0,-300,sh),lerp(0,-190,sh));c.scale(lerp(1,.3,sh),lerp(1,.3,sh));c.globalAlpha*=1-.0;
  const {row,col,both}=n1(),rB=175,rA=rB*Math.sqrt(row/col),d=vennDistance(rA,rB,Math.PI*rA*rA*both/row);c.fillStyle=rgba(P.cyan,.22);c.strokeStyle=P.cyan;c.lineWidth=3;c.beginPath();c.arc(520,480,rA,0,Math.PI*2);c.fill();c.stroke();c.fillStyle=rgba(AMB,.22);c.strokeStyle=AMB;c.beginPath();c.arc(520+d,480,rB,0,Math.PI*2);c.fill();c.stroke();c.restore();
  const k2=k.cue('B11.c2','rejected');rej(c,k,us,{t0:[Math.max(.9,k2-1.2),Math.max(1.7,k2-.6),Math.max(2.5,k2)]});T(c,'Validation only',960,700,{size:30,weight:'med',color:P.muted,align:'center',alpha:smooth((us-3)/.4)})}};
S['B11.S4']={tag:'MEAS',elements:E('cards','stamps'),draw(c,us,k){rej(c,k,us,{t0:[-9,-9,-9],shrink:smooth((us-.8)/1.2)});T(c,'Validation only',960,820,{size:30,weight:'med',color:P.muted,align:'center'})}};
// ---- B12
const NB=id=>`comparison.runs.base.selected_nights.${id}.accuracy`,NR=id=>`comparison.runs.r1.selected_nights.${id}.accuracy`,IDS=['SC4021','SC4062','SC4142'];
const ROWY=[310,470,630];
function Table(c,k,{rows=[1,1,1],hl=[0,0,0],ev=[1,1,1],cohort=1,head=1,miniStrip=0}){
  surface(c,[140,200,1640,610],'#0E1C30',{level:'E2',r:18});const a=smooth(head);
  T(c,'Finding',200,262,{size:28,weight:'med',color:P.muted,alpha:a});T(c,'Evidence',1040,262,{size:28,weight:'med',color:P.muted,alpha:a});poly(c,[[160,282],[1760,282]],{stroke:P.line,width:2,alpha:a});poly(c,[[1000,210],[1000,800]],{stroke:P.line,width:2,alpha:a});
  const F=['Averages hide failing nights','Per-night scaling rescued them','N1 stays hard'];
  const E=[IDS.map(i=>fact(NB(i),{mul:100})+'%').join(', '),IDS.map(i=>fact(NR(i),{mul:100})+'%').join(', '),`${fact('test.r1.recall',{idx:1,pct:2})} recall, 3 pilots rejected`];
  F.forEach((f,i)=>{const y=ROWY[i],r=rows[i];if(r<=0)return;c.save();c.globalAlpha*=smooth(r);
    if(hl[i]>0)rect(c,150,y-50,1620,130,rgba(i===2?AMB:GRN,.10*hl[i]),{r:12});
    T(c,f,200,y+20,{size:38,weight:'bold'});T(c,E[i],1040,y+20,{size:34,weight:'med',color:P.ink,alpha:smooth(ev[i])});
    if(i===1&&cohort>0)Pill(c,{k,x:1040,y:y+46,w:220,h:40,text:'in this cohort',color:AMB,size:24,alpha:cohort});
    if(i===0&&miniStrip>0)for(let j=0;j<8;j++)bevel(c,200+j*22,y+44,18,12,mixCol(STAGE_COL[HYPNO[(j*13)%96]],SL,.5),{r:2,alpha:miniStrip});c.restore()})}
S['B12.S1']={tag:'MEAS',elements:E('table'),draw(c,us,k){Table(c,k,{rows:[(us-1.2)/.5,(us-1.5)/.5,(us-.5)/.5],ev:[0,0,(us-1.6)/.4],cohort:0,head:us/.5,miniStrip:smooth((us-1)/.5)})}};
S['B12.S2']={tag:'MEAS',elements:E('table'),draw(c,us,k){const a=k.cue('B12.c1','an average can hide failing nights'),b=k.cue('B12.c1','per-night scaling rescued them');
  Table(c,k,{rows:[1,1,1],hl:[smooth((us-a)/.4)*(1-smooth((us-b+.1)/.4)),smooth((us-b)/.4),0],ev:[(us-a)/.4,(us-b)/.4,1],cohort:smooth((us-b-1.2)/.4),miniStrip:1})}};
S['B12.S3']={tag:'MEAS',elements:E('table'),draw(c,us,k){const f=1-smooth(us/2);Table(c,k,{rows:[1,1,1],hl:[0,.5*f,0],ev:[1,1,1],cohort:1,miniStrip:1})}};
// ---- B13
const gx=i=>400+(i%13)*90,gy=i=>300+Math.floor(i/13)*80;
const grid78=(c,k,{a=1,amber=0,qA=1,dim=1})=>{for(let i=0;i<78;i++){const p=typeof a==='function'?a(i):a;if(p<=0)continue;
  Person(c,{k,el:'grid78',x:gx(i)+40,y:gy(i)+30,s:30,state:'unknown',alpha:p*dim,q:qA>0,border:amber>0&&i<30?rgba(AMB,amber):null})}};
S['B13.S1']={tag:'MEAS',elements:E('table','head','grid78'),draw(c,us,k){const tp=smooth(us/1.2);
  if(tp<1){c.save();c.globalAlpha*=1-tp;c.translate(0,-120*tp);Table(c,k,{});c.restore()}
  T(c,'Not shown yet',960,230,{size:40,weight:'bold',align:'center',alpha:smooth((us-1)/.5)});grid78(c,k,{a:i=>(us-1.2-i*.012)/.3})}};
S['B13.S2']={tag:'MEAS',elements:E('head','grid78','counter'),draw(c,us,k){const am=smooth((us-1.2)/.8);T(c,'Not shown yet',960,230,{size:40,weight:'bold',align:'center'});grid78(c,k,{amber:am});
  T(c,'Certified independent:',760,820,{size:40,weight:'med',align:'right'});NumText(c,`${fact('audit.independent_confirmed')} / ${fact('audit.available')}`,790,820,{size:56,weight:'bold',color:AMB});
  const la=smooth((us-1.6)/.5);dot(c,520,880,9,AMB,la);T(c,`${fact('audit.counts.documented_development_exposure')} documented exposure`,540,888,{size:24,color:P.muted,alpha:la});dot(c,1000,880,9,P.muted,la);T(c,`${fact('audit.counts.completed_metadata_association_usage_not_fully_resolved')} usage unresolved`,1020,888,{size:24,color:P.muted,alpha:la})}};
const sheet=(c,k,x,y,{open=0,lockA=1,glow=0})=>{surface(c,[x,y,300,360],P.paper,{level:'E3',r:14,gradient:.02});for(let i=0;i<7;i++)rect(c,x+30,y+40+i*40,i%3===2?160:240,10,rgba(P.paperInk,.3),{r:5});Padlock(c,{k,el:'lock',x:x+122,y:y+150,open,alpha:lockA,glowA:glow,s:1.4})};
S['B13.S3']={tag:'CONCEPT',elements:E('grid78','sheet','box','arrow'),draw(c,us,k){const d=1-.9*smooth(us/.6);grid78(c,k,{dim:d*.45,qA:1});
  const s=smooth((us-.5)/.5);c.save();c.globalAlpha*=s;sheet(c,k,420,330,{});c.restore();
  const ap=cubic((us-1.2)/.5);if(ap>0){c.save();c.strokeStyle=P.muted;c.fillStyle=P.muted;c.lineWidth=4;c.beginPath();c.moveTo(780,510);c.lineTo(lerp(780,1020,ap),510);c.stroke();if(ap>.9){c.beginPath();c.moveTo(1040,510);c.lineTo(1020,498);c.lineTo(1020,522);c.fill()}c.restore()}
  const bp=cubic((us-1.7)/.5),fill=cubic((us-2.4)/1.2);if(bp>0){c.save();c.globalAlpha*=bp;c.setLineDash(fill<1?[10,8]:[]);c.strokeStyle=fill<1?P.muted:P.ink;c.lineWidth=3;c.beginPath();c.roundRect(1060,350,400,320,16);c.stroke();c.setLineDash([]);
    if(fill>0){c.strokeStyle=P.ink;c.lineWidth=3;c.beginPath();c.roundRect(1060,350,400,320,16);c.stroke()}T(c,'Independent data',1260,520,{size:34,weight:'bold',align:'center',color:P.ink});c.restore()}}};
S['B13.S4']={tag:'CONCEPT',elements:E('grid78','sheet','box'),draw(c,us,k){grid78(c,k,{dim:.07,qA:1});sheet(c,k,420,330,{glow:.6*Math.sin(Math.PI*clamp(us/1.4))});
  poly(c,[[780,510],[1020,510]],{stroke:P.muted,width:4});c.save();c.fillStyle=P.muted;c.beginPath();c.moveTo(1040,510);c.lineTo(1020,498);c.lineTo(1020,522);c.fill();c.restore();
  c.save();c.strokeStyle=P.ink;c.lineWidth=3;c.beginPath();c.roundRect(1060,350,400,320,16);c.stroke();T(c,'Independent data',1260,520,{size:34,weight:'bold',align:'center'});c.restore()}};
// ---- End
S['E1']={tag:null,elements:E('tile'),draw(c,us,k){const br=.5+.5*Math.sin(us*2.2);glowRect(c,900,340,120,120,STAGE_COL[0],{blur:30,alpha:.18+.15*br},14);bevel(c,900,340,120,120,STAGE_COL[0],{r:14});k.rec('EndTile',{el:'tile'})}};
S['E2']={tag:null,elements:E('tile','l1','l2','repo'),draw(c,us,k){const ub=us+1.2,br=.5+.5*Math.sin(ub*2.2);glowRect(c,900,340,120,120,STAGE_COL[0],{blur:30,alpha:.18+.15*br},14);bevel(c,900,340,120,120,STAGE_COL[0],{r:14});k.rec('EndTile',{el:'tile'});
  T(c,'Reading Sleep from One EEG Channel',960,580,{size:56,weight:'bold',align:'center',alpha:smooth((us-.2)/.5),rise:10});
  T(c,'Not a replication of the paper. Not clinical validation.',960,650,{size:32,color:P.muted,align:'center',alpha:smooth((us-1.2)/.5),rise:10});
  T(c,'satangtecha/sleep-stage-classification-research-film',1816,880,{size:24,color:P.dim,align:'right',alpha:smooth((us-2.2)/.5)})}};
export const act4=S;
