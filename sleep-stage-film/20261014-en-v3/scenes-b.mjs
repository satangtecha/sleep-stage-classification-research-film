// Scenes for chapters 3-5: normalization, the network, learning.
import {P,STAGE_COL,STAGES,clamp,lerp,smooth,cubic,outExpo,outBack,seg,rgba,shade,heat,mixCol,T,wrap,fmt,EQ,poly,drawOn,dot,rect,arrow,pill,panel,wavePts,rnd,eeg,axes,World,measure} from './lib.mjs';
import {SPEC} from './scenes-a.mjs';
const fin=(u,a,d=.6)=>seg(u,a,d,smooth);
const TAU=Math.PI*2;
const gauss=i=>{const u1=rnd(i*3+1)||.5,u2=rnd(i*3+2);return Math.sqrt(-2*Math.log(u1))*Math.cos(TAU*u2)};

function miniSpec(c,x,y,w,h,{alpha=1,seed=0,gain=1,band=-1}={}){if(alpha<=0)return;c.save();c.globalAlpha*=alpha;const cols=14,rows=16;for(let t=0;t<cols;t++)for(let f=0;f<rows;f++){const v=clamp(SPEC[(t*2+seed)%29][f*8]*gain);c.fillStyle=heat(v);c.fillRect(x+t*w/cols,y+(rows-1-f)*h/rows,w/cols-.5,h/rows-.5)}
  if(band>=0){c.strokeStyle=P.white;c.lineWidth=2;c.strokeRect(x-2,y+(rows-1-band)*h/rows-1,w+4,h/rows+2)}c.restore()}

export const scenesB=[
// ---------------------------------------------------------------- CH3 NORMALIZATION
{id:'zscore',ch:3,tag:'MATH',dur:12,cap:[[0,'Standardizing asks one question: how many standard deviations is this value from the mean?'],[6,'12, with mean 10 and SD 2, becomes z = 1. The pattern of the data does not change, only its center and scale.']],
draw(c,u){
  const x0=260,x1=1660,y1=360,y2=640,X=v=>x0+(v-4)/12*(x1-x0),Z=z=>x0+(z+3)/6*(x1-x0);
  const a=fin(u,0);poly(c,[[x0,y1],[x1,y1]],{stroke:P.line,width:2,alpha:a});for(let v=4;v<=16;v+=2){poly(c,[[X(v),y1-8],[X(v),y1+8]],{stroke:P.muted,width:2,alpha:a});T(c,String(v),X(v),y1+42,{size:22,color:P.muted,align:'center',alpha:a})}
  T(c,'raw value a',x0,y1-110,{size:24,color:P.muted,alpha:a});
  const b=fin(u,5.2);poly(c,[[x0,y2],[x1,y2]],{stroke:P.line,width:2,alpha:b});for(let z=-3;z<=3;z++){poly(c,[[Z(z),y2-8],[Z(z),y2+8]],{stroke:P.muted,width:2,alpha:b});T(c,String(z),Z(z),y2+42,{size:22,color:P.muted,align:'center',alpha:b})}
  T(c,'z-score',x0,y2-110,{size:24,color:P.muted,alpha:b});
  for(let i=0;i<34;i++){const v=10+2*clamp(gauss(i),-2.6,2.6),k=seg(u,.3+i*.03,.5,outBack),d=seg(u,5.4+i*.02,1.2,cubic);const yy=lerp(y1-28-(i%4)*16,y2-28-(i%4)*16,d);dot(c,X(v),yy,7*clamp(k,0,1.3),i===5?P.amber:P.cyan,.85)}
  const m=fin(u,1.6);poly(c,[[X(10),y1-120],[X(10),y1+10]],{stroke:P.violet,width:3,alpha:m});EQ(c,'\\mu=10',X(10),y1-150,{size:30,color:P.violet,p:m});
  const s=fin(u,2.4);poly(c,[[X(10),y1-80],[X(12),y1-80]],{stroke:P.amber,width:3,alpha:s});EQ(c,'\\sigma=2',X(11),y1-100,{size:26,color:P.amber,p:s});
  const hl=fin(u,3.2);dot(c,X(12),y1,12,P.amber,hl,16);arrow(c,X(12),y1+60,Z(1),y2-60,{col:P.amber,width:3,p:seg(u,5.6,1),alpha:hl});dot(c,Z(1),y2,12,P.amber,fin(u,6.4),16);
  EQ(c,'z_i=\\frac{a_i-\\mu}{\\sigma}',560,800,{size:44,p:seg(u,.8,1.2)});EQ(c,'z=\\frac{12-10}{2}=1',1360,800,{size:44,color:P.amber,p:seg(u,6.4,1.2)});
}},
{id:'perfreq',ch:3,tag:'CODE',dur:13,cap:[[0,'Our statistics are computed separately for each frequency bin, across every epoch and time step of a night.'],[6.5,'That gives 129 means and 129 standard deviations. A floor of 10⁻³ stops division by a tiny SD.']],
draw(c,u){
  const n=7;for(let e=0;e<n;e++){const g=seg(u,.2+e*.12,.6,outBack);miniSpec(c,150+e*28,220+e*28,280,250,{alpha:clamp(g),seed:e*3,band:e===n-1&&u>2?Math.floor((u-2)*3.2)%16:-1})}
  T(c,'epochs e = 1 … E of one night',150,690,{size:22,color:P.muted,alpha:fin(u,1)});
  // stats strip
  const filled=Math.floor(129*seg(u,2.2,4.2,smooth));const sx=830,sy=230,rh=3.4;
  for(let f=0;f<filled;f++){const mu=.2+.6*Math.exp(-f/40)+.08*Math.sin(f*.3),sd=.25+.25*Math.exp(-f/60);c.fillStyle=mixCol('#183152',P.violet,mu);c.fillRect(sx,sy+(128-f)*rh,60,rh-.4);c.fillStyle=mixCol('#183152',P.amber,sd*1.6);c.fillRect(sx+70,sy+(128-f)*rh,60,rh-.4)}
  EQ(c,'\\mu_f',sx+30,sy-30,{size:30,color:P.violet,p:fin(u,2.2)});EQ(c,'\\sigma_f',sx+100,sy-30,{size:30,color:P.amber,p:fin(u,2.2)});
  T(c,`${filled} / 129`,sx+65,sy+129*rh+40,{size:26,color:P.ink,align:'center',weight:'bold',alpha:fin(u,2.2)});
  EQ(c,'\\mu_f=\\frac{1}{E\\,T}\\sum_{e=1}^{E}\\sum_{t=1}^{T}F_{e,f,t}',1420,260,{size:36,color:P.violet,p:seg(u,1,1.4)});
  EQ(c,'\\sigma_f^2=\\frac{1}{E\\,T}\\sum_{e,t}\\left(F_{e,f,t}-\\mu_f\\right)^2',1420,400,{size:36,color:P.amber,p:seg(u,2.8,1.4)});
  EQ(c,'\\widetilde F_{e,f,t}=\\frac{F_{e,f,t}-\\mu_f}{\\max(\\sigma_f,\\ \\epsilon_{\\text{std}})}',1420,560,{size:38,p:seg(u,5,1.4)});
  EQ(c,'\\epsilon_{\\text{std}}=10^{-3}\\qquad T=29',1420,690,{size:32,color:P.muted,p:seg(u,7,1)});
}},
{id:'baser1',ch:3,tag:'CODE',dur:14,cap:[[0,'Baseline: the statistics come only from the training participants, then the same numbers are used for every night.'],[7,'R1: every night uses its own statistics, including validation and test nights. That makes R1 transductive.']],
draw(c,u){
  // left: baseline
  const la=fin(u,0);T(c,'Baseline',480,200,{size:34,weight:'bold',align:'center',color:P.violet,alpha:la});
  for(let i=0;i<8;i++){const x=180+(i%4)*95,y=260+Math.floor(i/4)*80,a=fin(u,.3+i*.06);rect(c,x,y,76,56,rgba(P.cyan,.15),{r:8,stroke:P.cyan,sw:1.5,alpha:a});arrow(c,x+38,y+56,480,470,{col:rgba(P.cyan,.5),width:1.5,p:seg(u,1.2+i*.05,.8),head:8})}
  T(c,'training nights',360,232,{size:20,color:P.cyan,alpha:fin(u,.3)});
  panel(c,360,460,240,90,{alpha:fin(u,1.8),col:P.violet});EQ(c,'\\mu_f^{\\text{train}},\\ \\sigma_f^{\\text{train}}',480,505,{size:30,color:P.violet,p:fin(u,2)});
  [[260,P.amber,'val'],[480,P.coral,'test'],[700,P.coral,'test']].forEach(([x,col,l],i)=>{arrow(c,480,550,x,640,{col:rgba(P.violet,.7),width:2,p:seg(u,2.6+i*.2,.8),head:10});const a=fin(u,3.2+i*.2);rect(c,x-50,650,100,62,rgba(col,.15),{r:8,stroke:col,sw:1.5,alpha:a});T(c,l,x,690,{size:22,color:col,align:'center',alpha:a})});
  // divider
  poly(c,[[960,200],[960,760]],{stroke:P.line,width:2,alpha:fin(u,6)});
  // right: R1
  const ra=fin(u,6.6);T(c,'R1',1440,200,{size:34,weight:'bold',align:'center',color:P.cyan,alpha:ra});
  for(let i=0;i<9;i++){const x=1130+(i%3)*215,y=260+Math.floor(i/3)*165,a=fin(u,6.8+i*.12);const col=i===4?P.amber:i>6?P.coral:P.cyan;
    rect(c,x,y,110,64,rgba(col,.15),{r:8,stroke:col,sw:1.5,alpha:a});
    // loop arrow to own stats chip
    const p=seg(u,7.4+i*.12,.8);c.save();c.globalAlpha=a;c.strokeStyle=rgba(col,.8);c.lineWidth=2;c.beginPath();c.arc(x+140,y+32,26,-Math.PI*.9,-Math.PI*.9+Math.PI*1.8*p);c.stroke();c.restore();
    EQ(c,'\\mu_n,\\sigma_n',x+55,y+100,{size:20,color:col,alpha:fin(u,7.8+i*.12)})}
  pill(c,'uses the evaluated night\'s unlabeled signal',1440,770,{size:24,color:P.amber,alpha:fin(u,9)});
}},
{id:'gain',ch:3,tag:'MATH',dur:16,cap:[[0,'Why might per-night statistics help? Suppose one night was recorded with a different gain a.'],[5,'The STFT is linear, so the gain becomes a constant shift ln a in the log-magnitude features.'],[9.5,'Per-night standardization cancels the shift. Ideal case only: real nights can differ in more complex ways.']],
draw(c,u){
  const x0=140,x1=860;poly(c,[[x0,300],[x1,300]],{stroke:P.grid,width:1.5,alpha:fin(u,0)});
  drawOn(c,wavePts(x0,300,x1-x0,40,a=>eeg(a*3,5),400),seg(u,.3,1.2),{stroke:P.cyan,width:2.4});
  drawOn(c,wavePts(x0,300,x1-x0,40*2.5,a=>eeg(a*3,5),400),seg(u,1.2,1.2),{stroke:P.amber,width:2.4,alpha:.85});
  T(c,'night 1: x',x0,200,{size:24,color:P.cyan,alpha:fin(u,.3)});T(c,'night 2: a·x  (a = 2.5)',x0+180,200,{size:24,color:P.amber,alpha:fin(u,1.2)});
  // feature distributions
  const ax0=140,ax1=860,ay=720,sh=Math.log(2.5)*120,norm=seg(u,10,1.8,cubic);
  poly(c,[[ax0,ay],[ax1,ay]],{stroke:P.line,width:2,alpha:fin(u,5)});
  const bump=(cx,col,a)=>{const pts=[];for(let i=0;i<=120;i++){const x=lerp(ax0,ax1,i/120);pts.push([x,ay-180*Math.exp(-(((x-cx)/70)**2))])}poly(c,[[ax0,ay],...pts,[ax1,ay]],{stroke:col,width:2.5,fill:rgba(col,.15),alpha:a,close:false})};
  const c1=lerp(420,500,norm),c2=lerp(420+sh,500,norm);bump(c1,P.cyan,fin(u,5.2));bump(c2,P.amber,fin(u,5.8));
  if(u>5.8&&norm<.5){arrow(c,c1,ay-200,c2,ay-200,{col:P.ink,width:2.5,alpha:fin(u,6.2)*(1-norm*2)});EQ(c,'\\ln a',(c1+c2)/2,ay-230,{size:28,alpha:fin(u,6.2)*(1-norm*2)})}
  T(c,norm>.5?'after normalization: identical':'log-magnitude features',ax0,ay+40,{size:22,color:P.muted,alpha:fin(u,5)});
  const eqs=[['x\'[n]=a\\,x[n],\\quad a>0',.6],['X\'[m,k]=a\\,X[m,k]',3.2],['F\'=\\ln|aX|=\\ln a+\\ln|X|',4.6],['\\mu\'=\\mu+\\ln a,\\qquad \\sigma\'=\\sigma',6.6],['\\frac{F\'-\\mu\'}{\\sigma\'}=\\frac{F+\\ln a-\\mu-\\ln a}{\\sigma}=\\frac{F-\\mu}{\\sigma}',8.4]];
  eqs.forEach(([e,t],i)=>EQ(c,e,1380,220+i*120,{size:i===4?32:36,color:i===4?P.green:P.ink,p:seg(u,t,1.2)}));
}},
{id:'mix',ch:3,tag:'MATH',dur:13,cap:[[0,'There is a catch. A night\'s mean also depends on how much of each sleep stage the night contains.'],[6.5,'A wake-heavy night and a deep-sleep-heavy night get different statistics even with perfect recording. Per-night normalization is a trade-off.']],
draw(c,u){
  EQ(c,'\\mu=\\sum_c\\pi_c\\,\\mu_c',600,215,{size:44,p:seg(u,.3,1.2)});
  EQ(c,'\\sigma^2=\\sum_c\\pi_c\\left[\\sigma_c^2+(\\mu_c-\\mu)^2\\right]',1340,215,{size:40,p:seg(u,1.4,1.4)});
  const cm=[1.6,.8,.2,-1.2,.6],nights=[['Night A: mostly wake',[.45,.08,.3,.07,.1]],['Night B: mostly deep sleep',[.08,.05,.4,.35,.12]]];
  const fx=v=>1240+v*200;
  nights.forEach(([lab,pi],r)=>{const y=380+r*230,a=fin(u,2.4+r*1.8);T(c,lab,160,y-30,{size:26,color:P.ink,alpha:a,weight:'med'});
    let x=160;pi.forEach((p,k)=>{const w=600*p*seg(u,2.6+r*1.8+k*.1,.6);rect(c,x,y,w,56,STAGE_COL[k],{alpha:a});if(p>.09)T(c,STAGES[k],x+w/2,y+37,{size:22,align:'center',color:'#07101C',weight:'bold',alpha:a});x+=600*p});
    poly(c,[[fx(-1.6),y+28],[fx(2),y+28]],{stroke:P.line,width:2,alpha:a});
    cm.forEach((m,k)=>{dot(c,fx(m),y+28,9*pi[k]/.45+3,STAGE_COL[k],a*.9)});
    const mu=pi.reduce((s,p,k)=>s+p*cm[k],0),q=seg(u,4+r*1.8,1,outBack);
    c.save();c.globalAlpha=clamp(q);c.translate(fx(mu),y+28);c.rotate(Math.PI/4);c.fillStyle=P.white;c.fillRect(-11,-11,22,22);c.restore();
    T(c,`μ = ${mu.toFixed(2)}`,fx(mu),y-12,{size:26,weight:'bold',align:'center',alpha:clamp(q)})});
  T(c,'feature axis · dot size = share of the night',fx(.2),715,{size:22,color:P.muted,align:'center',alpha:fin(u,3)});
  pill(c,'may remove nuisance gain  —  may also remove useful amplitude',960,815,{size:24,color:P.amber,alpha:fin(u,8),align:'center'});
}},
// ---------------------------------------------------------------- CH4 THE NETWORK
{id:'tensor',ch:4,tag:'CODE',dur:13,cap:[[0,'A training batch holds 32 sequences. Each sequence has 20 consecutive epochs, and each epoch is a 1 × 129 × 29 image.'],[7,'Twenty epochs cover ten minutes. The CNN reads all 640 images at once, then they are regrouped into sequences for the GRU.']],
draw(c,u){
  const w=new World({box:[96,150,1728,560],center:[0,.2,.5],phi:1.08,theta:-1.25+.18*Math.sin(u/5),frameHeight:6.4});
  const m=seg(u,7.4,2,cubic);
  for(let r=0;r<4;r++)for(let i=0;i<20;i++){const g=seg(u,.2+r*.25+i*.03,.5,outBack);if(g<=0)continue;const x0=-3.2+i*.34,y0=(r-1.5)*1.05,k=r*20+i;const x=lerp(x0,-4+k*.1,m),y=lerp(y0,0,m);
    w.box3([x,y,.55*clamp(g,0,1.2)],[.06,.6,1.1*clamp(g)],k%2?'#4C7DB8':P.cyan,{alpha:clamp(g)})}
  w.draw(c);
  const dims=[['B','32','sequences',P.cyan],['S','20','epochs each',P.amber],['C','1','channel',P.muted],['F','129','frequencies',P.violet],['T','29','time steps',P.coral]];
  const hi=u<1.5?-1:Math.min(4,Math.floor((u-1.5)/1.1));
  dims.forEach(([s,n,l,col],i)=>{const x=560+i*200,a=fin(u,.5+i*.12),on=i===hi&&u<7;rect(c,x-80,700,160,96,on?rgba(col,.2):rgba('#0E1C30',.8),{r:12,stroke:on?col:P.line,sw:2,alpha:a});T(c,n,x,748,{size:38,weight:'bold',align:'center',color:col,alpha:a});T(c,l,x,780,{size:20,align:'center',color:P.muted,alpha:a})});
  T(c,'[',455,768,{size:80,color:P.muted,alpha:fin(u,.5)*(1-m)});T(c,']',1465,768,{size:80,color:P.muted,alpha:fin(u,.5)*(1-m)});
  pill(c,'reshape  [B, S, 1, 129, 29]  →  [B·S, 1, 129, 29]  =  [640, 1, 129, 29]',960,200,{size:26,color:P.amber,alpha:fin(u,8.6),weight:'mono'});
  T(c,'4 of 32 sequences drawn',1800,860,{size:20,color:P.dim,align:'right',alpha:fin(u,1)});
}},
{id:'conv',ch:4,tag:'CONC',dur:13,cap:[[0,'A single unit multiplies inputs by learned weights and adds a bias: 0.5·1 − 0.2·2 + 0.3 = 0.4.'],[5.5,'Convolution slides the same 3 × 3 weights over the whole image, producing a feature map. In PyTorch this is technically cross-correlation.']],
draw(c,u){
  EQ(c,'a=\\sum_i w_ix_i+b',480,210,{size:42,p:seg(u,.2,1)});
  EQ(c,'0.5(1)-0.2(2)+0.3=0.4',1380,210,{size:42,color:P.amber,p:seg(u,1.6,1.4)});
  const N=9,cs=46,gx=200,gy=300,K=[[1,0,-1],[2,0,-2],[1,0,-1]];const inp=Array.from({length:N},(_,r)=>Array.from({length:N},(_,k)=>Math.round(3*(.5+.5*Math.sin(r*.7+k*.4))+rnd(r*9+k)*1.2)));
  const out=Array.from({length:N-2},(_,r)=>Array.from({length:N-2},(_,k)=>{let s=0;for(let i=0;i<3;i++)for(let j=0;j<3;j++)s+=K[i][j]*inp[r+i][k+j];return s}));
  const a=fin(u,4);const pos=u<5.4?-1:Math.min(48,Math.floor((u-5.4)/.14));
  for(let r=0;r<N;r++)for(let k=0;k<N;k++){rect(c,gx+k*cs,gy+r*cs,cs-3,cs-3,heat(inp[r][k]/5),{alpha:a,r:4});T(c,String(inp[r][k]),gx+k*cs+cs/2-1,gy+r*cs+31,{size:20,align:'center',color:'#07101C',weight:'bold',alpha:a})}
  if(pos>=0){const pr=Math.floor(pos/7),pk=pos%7;rect(c,gx+pk*cs-3,gy+pr*cs-3,3*cs+3,3*cs+3,null,{stroke:P.amber,sw:4})}
  // kernel
  const kx=780,ky=390;T(c,'shared 3×3 weights',kx+cs*1.5,ky-30,{size:22,color:P.amber,align:'center',alpha:a});
  for(let i=0;i<3;i++)for(let j=0;j<3;j++){rect(c,kx+j*cs,ky+i*cs,cs-3,cs-3,rgba(P.amber,.15),{r:4,stroke:P.amber,sw:1.5,alpha:a});T(c,String(K[i][j]),kx+j*cs+cs/2-1,ky+i*cs+31,{size:20,align:'center',color:P.amber,alpha:a})}
  arrow(c,kx+3*cs+30,ky+cs*1.5,1060,ky+cs*1.5,{col:P.muted,width:2.5,alpha:a,p:a});
  const ox=1110,oy=345,mx=Math.max(...out.flat().map(Math.abs));
  for(let i=0;i<=pos&&pos>=0;i++){const r=Math.floor(i/7),k=i%7;rect(c,ox+k*cs,oy+r*cs,cs-3,cs-3,heat(.5+out[r][k]/mx/2),{r:4});T(c,String(out[r][k]),ox+k*cs+cs/2-1,oy+r*cs+31,{size:18,align:'center',color:'#07101C',weight:'bold'})}
  T(c,'feature map',ox+3.5*cs,oy-30,{size:22,color:P.muted,align:'center',alpha:fin(u,5.4)});
  EQ(c,'A_o[i,j]=b_o+\\sum_c\\sum_{u,v}W_{o,c,u,v}\\,X_c[i+u-p,\\,j+v-p]',960,800,{size:32,color:P.muted,p:seg(u,6,1.6)});
}},
{id:'relu',ch:4,tag:'CONC',dur:12,cap:[[0,'ReLU keeps positive values and turns negatives into zero. Without it, stacked linear layers collapse into one linear map.'],[6,'Max pooling keeps the largest value in each 2 × 2 block, halving height and width.']],
draw(c,u){
  const ax=axes(c,{x:180,y:260,w:560,h:440,xmin:-3,xmax:3,ymin:-1,ymax:3,xt:[-3,0,3],yt:[0,1,2,3],alpha:fin(u,0)});
  poly(c,[[ax.X(0),ax.Y(-1)],[ax.X(0),ax.Y(3)]],{stroke:P.line,width:1.5,alpha:fin(u,0)});
  drawOn(c,[[ax.X(-3),ax.Y(0)],[ax.X(0),ax.Y(0)],[ax.X(3),ax.Y(3)]],seg(u,.4,1.4),{stroke:P.cyan,width:4,glow:10});
  const xv=-2.6+((u*1.3)%5.2);dot(c,ax.X(xv),ax.Y(Math.max(0,xv)),11,P.amber,fin(u,1.6),14);
  T(c,`a = ${xv.toFixed(1)}  →  ${Math.max(0,xv).toFixed(1)}`,460,240,{size:28,weight:'mono',color:P.amber,align:'center',alpha:fin(u,1.6)});
  EQ(c,'\\operatorname{ReLU}(a)=\\max(0,a)',460,800,{size:40,p:seg(u,.8,1.2)});
  // pooling
  const A=[[1,3,2,0],[5,2,1,4],[0,1,6,2],[3,2,1,1]],cs=90,gx=1000,gy=290,regCol=[P.cyan,P.violet,P.amber,P.coral];
  for(let r=0;r<4;r++)for(let k=0;k<4;k++){const reg=Math.floor(r/2)*2+Math.floor(k/2),a=fin(u,5.6+reg*.15);const isMax=A[r][k]===Math.max(...[0,1].flatMap(i=>[0,1].map(j=>A[Math.floor(r/2)*2+i][Math.floor(k/2)*2+j])));
    rect(c,gx+k*cs,gy+r*cs,cs-6,cs-6,rgba(regCol[reg],isMax&&u>7?.45:.15),{r:8,stroke:regCol[reg],sw:2,alpha:a});T(c,String(A[r][k]),gx+k*cs+cs/2-3,gy+r*cs+56,{size:34,align:'center',weight:'bold',alpha:a})}
  for(let reg=0;reg<4;reg++){const r0=Math.floor(reg/2)*2,k0=(reg%2)*2;let best=-1,br=0,bk=0;for(let i=0;i<2;i++)for(let j=0;j<2;j++)if(A[r0+i][k0+j]>best){best=A[r0+i][k0+j];br=r0+i;bk=k0+j}
    const d=seg(u,7.4+reg*.35,.9,cubic);const tx=1500+(reg%2)*110,ty=360+Math.floor(reg/2)*110;
    const x=lerp(gx+bk*cs,tx,d),y=lerp(gy+br*cs,ty,d);if(d>0){rect(c,x,y,cs-6,cs-6,rgba(regCol[reg],.45),{r:8,stroke:regCol[reg],sw:2});T(c,String(best),x+cs/2-3,y+56,{size:34,align:'center',weight:'bold'})}}
  EQ(c,'P[i,j]=\\max_{u,v\\in\\{0,1\\}}A[2i+u,\\,2j+v]',1360,800,{size:36,p:seg(u,6.6,1.2)});
}},
{id:'cnn3d',ch:4,tag:'CODE',dur:14,cap:[[0,'Three blocks of convolution, BatchNorm, ReLU and pooling shrink the image while adding feature channels.'],[7,'Global average pooling turns 128 feature maps into one vector, then a linear layer gives the 128-number epoch embedding.']],
draw(c,u){
  const w=new World({box:[96,150,1728,620],center:[0,0,1.4],phi:1.1,theta:lerp(-1.65,-1.05,seg(u,0,14,smooth)),frameHeight:6.6});w.floor({size:7,alpha:.3});
  const blocks=[[1,129,29,P.muted],[32,64,14,P.cyan],[64,32,7,P.violet],[128,16,3,P.amber]];const xs=[-5.2,-3.1,-.9,1.2];
  blocks.forEach(([C,F,Tt,col],i)=>{const g=seg(u,.3+i*1.4,1.1,outBack);const th=i?.35*Math.sqrt(C/8):.08,hh=F/42,dd=Tt/10;
    w.grow([xs[i],0,0],[th,dd,hh],col,g,{alpha:.95});
    if(i>0&&g>0){const [Cp,Fp,Tp]=blocks[i-1],pth=i>1?.35*Math.sqrt(Cp/8):.08;for(const [sy,sz] of [[-1,0],[1,0],[-1,1],[1,1]])w.line([[xs[i-1]+pth/2,sy*Tp/20,sz*Fp/42],[xs[i]-th/2,sy*Tt/20,sz*F/42]],rgba(col,.35),1.2,{alpha:clamp(g)})}});
  const gv=seg(u,6.6,1.2,outBack);for(let k=0;k<16;k++)w.box3([3.1,0,.1+k*.17],[.16,.16,.14*clamp(gv)],mixCol(P.amber,P.coral,k/16),{alpha:clamp(gv)});
  const ge=seg(u,8.4,1.2,outBack);for(let k=0;k<16;k++)w.box3([4.6,0,.1+k*.17],[.16,.16,.14*clamp(ge)],mixCol(P.cyan,P.green,k/16),{alpha:clamp(ge)});
  w.draw(c);
  const labs=[['1×129×29','input'],['32×64×14','block 1'],['64×32×7','block 2'],['128×16×3','block 3'],['128','avg pool'],['e_t (128)','embedding']];
  const lx=[w.px([xs[0],0,0]),w.px([xs[1],0,0]),w.px([xs[2],0,0]),w.px([xs[3],0,0]),w.px([3.1,0,0]),w.px([4.6,0,0])];
  labs.forEach(([a,b],i)=>{const al=fin(u,[.6,1.9,3.3,4.7,7,8.8][i]);T(c,a,lx[i][0],lx[i][1]+50,{size:24,weight:'bold',align:'center',alpha:al,color:[P.muted,P.cyan,P.violet,P.amber,P.coral,P.green][i]});T(c,b,lx[i][0],lx[i][1]+80,{size:20,align:'center',alpha:al,color:P.muted})});
  EQ(c,'v_c=\\frac{1}{16\\cdot 3}\\sum_{i=1}^{16}\\sum_{j=1}^{3}A_c[i,j]',620,830,{size:30,p:seg(u,7.2,1.2)});
  pill(c,'128 learned features — not 128 frequencies, not 128 stages',1340,830,{size:22,color:P.coral,alpha:fin(u,10)});
}},
{id:'bndrop',ch:4,tag:'CODE',dur:14,cap:[[0,'BatchNorm normalizes activations inside the CNN, per feature channel. It is a different step from our per-night input normalization.'],[7,'Dropout with p = 0.3 switches off random activations during training only. model.eval() makes both layers fixed rules.']],
draw(c,u){
  const ev=u>10.2;
  panel(c,130,200,780,520,{title:'BatchNorm (inside the CNN)',col:P.violet,alpha:fin(u,0)});
  EQ(c,'\\operatorname{BN}(a)=\\gamma\\,\\frac{a-\\mu_B}{\\sqrt{\\sigma_B^2+\\epsilon_B}}+\\beta',520,320,{size:34,p:seg(u,.4,1.2)});
  const n=seg(u,2,2,cubic);for(let i=0;i<26;i++){const v=gauss(i+50);const x=lerp(560+v*90,520+v*50,ev?1:n);dot(c,x,560+(i%5)*22,8,P.violet,fin(u,1.6+i*.02))}
  poly(c,[[260,640],[780,640]],{stroke:P.line,width:2,alpha:fin(u,1.6)});T(c,ev?'eval: running statistics':'train: batch statistics',520,690,{size:22,color:P.muted,align:'center',alpha:fin(u,1.6)});
  panel(c,1010,200,780,520,{title:'Dropout  p = 0.3',col:P.amber,alpha:fin(u,6.6)});
  const tick=Math.floor(u*2.2);for(let i=0;i<12;i++){const x=1110+(i%6)*116,y=380+Math.floor(i/6)*150,off=!ev&&u>7.2&&rnd(i*17+tick*3)<.3;const a=fin(u,6.8+i*.04);
    dot(c,x,y,30,off?'#1A2638':P.amber,a,off?0:10);if(!off&&u>7.2&&!ev)T(c,'×1/0.7',x,y+62,{size:18,color:P.muted,align:'center',alpha:a});if(off)T(c,'0',x,y+9,{size:24,color:P.dim,align:'center',alpha:a})}
  EQ(c,'\\widetilde a_i=\\frac{m_i}{1-p}\\,a_i,\\quad m_i\\sim\\operatorname{Bernoulli}(1-p)',1400,650,{size:28,color:P.muted,p:seg(u,7.6,1.2)});
  // switch
  const sx=960,sy=790,on=seg(u,10,.6,cubic);rect(c,sx-60,sy-24,120,48,rgba(on>.5?P.green:P.cyan,.25),{r:24,stroke:on>.5?P.green:P.cyan,sw:2,alpha:fin(u,8.6)});dot(c,lerp(sx-34,sx+34,on),sy,18,on>.5?P.green:P.cyan,fin(u,8.6));
  T(c,'model.train()',sx-90,sy+9,{size:26,weight:'mono',color:on<.5?P.cyan:P.dim,align:'right',alpha:fin(u,8.6)});T(c,'model.eval()',sx+90,sy+9,{size:26,weight:'mono',color:on>.5?P.green:P.dim,alpha:fin(u,8.6)});
}},
{id:'gru',ch:4,tag:'CODE',dur:14,cap:[[0,'A GRU carries a hidden state h from one epoch to the next, mixing in each new epoch embedding e_t.'],[7,'The reset gate r limits old context when proposing a candidate n. The update gate z decides how much old state to keep.']],
draw(c,u){
  const a=fin(u,0);const L=170,R=830,top=330,bot=640;
  poly(c,[[L,top],[R,top]],{stroke:P.cyan,width:4,alpha:a});EQ(c,'h_{t-1}',L-10,top-40,{size:32,color:P.cyan,alpha:a});EQ(c,'h_t',R+10,top-40,{size:32,color:P.cyan,alpha:a});arrow(c,R-40,top,R+30,top,{col:P.cyan,width:4,alpha:a});
  poly(c,[[200,bot+70],[200,bot],[700,bot]],{stroke:P.amber,width:3,alpha:fin(u,.8)});EQ(c,'\\mathbf e_t',200,bot+100,{size:32,color:P.amber,alpha:fin(u,.8)});
  const gates=[['r_t','\\sigma',360,P.coral,1.4],['z_t','\\sigma',520,P.violet,2],['n_t','\\tanh',680,P.green,2.6]];
  gates.forEach(([n,f,x,col,t])=>{const g=fin(u,t);poly(c,[[x,top],[x,bot]],{stroke:rgba(col,.6),width:2,alpha:g});rect(c,x-50,470,100,80,rgba(col,.18),{r:12,stroke:col,sw:2,alpha:g});EQ(c,f,x,495,{size:28,color:col,alpha:g});EQ(c,n,x,530,{size:26,color:col,alpha:g})});
  // flowing particles
  for(let k=0;k<5;k++){const p=((u*.45+k/5)%1);if(u>3){dot(c,lerp(L,R,p),top,6,P.cyan,.9,10);dot(c,lerp(200,700,p),bot,5,P.amber,.9,8)}}
  // z gauge
  const z=.5+.45*Math.sin(u*1.1);const gz=fin(u,8.4);rect(c,330,760,470,22,'#13233A',{r:11,alpha:gz});rect(c,330,760,470*z,22,P.violet,{r:11,alpha:gz});
  T(c,'take new',330,815,{size:22,color:P.green,alpha:gz});T(c,'keep old',800,815,{size:22,color:P.cyan,align:'right',alpha:gz});T(c,`z = ${z.toFixed(2)}`,565,748,{size:24,align:'center',weight:'bold',color:P.violet,alpha:gz});
  const eqs=[['\\mathbf r_t=\\sigma(W_{ir}\\mathbf e_t+\\mathbf b_{ir}+W_{hr}\\mathbf h_{t-1}+\\mathbf b_{hr})',P.coral,1.2],['\\mathbf z_t=\\sigma(W_{iz}\\mathbf e_t+\\mathbf b_{iz}+W_{hz}\\mathbf h_{t-1}+\\mathbf b_{hz})',P.violet,2.4],['\\mathbf n_t=\\tanh\\!\\big(W_{in}\\mathbf e_t+\\mathbf b_{in}+\\mathbf r_t\\odot(W_{hn}\\mathbf h_{t-1}+\\mathbf b_{hn})\\big)',P.green,3.6],['\\mathbf h_t=(1-\\mathbf z_t)\\odot\\mathbf n_t+\\mathbf z_t\\odot\\mathbf h_{t-1}',P.cyan,5]];
  eqs.forEach(([e,col,t],i)=>EQ(c,e,1380,260+i*130,{size:i===2?25:27,color:col,p:seg(u,t,1.2)}));
  EQ(c,'\\sigma(a)=\\frac{1}{1+e^{-a}}\\in(0,1)',1380,780,{size:28,color:P.muted,p:seg(u,6.2,1)});
}},
{id:'bigru',ch:4,tag:'CODE',dur:12,cap:[[0,'A bidirectional GRU runs twice: once forward in time and once backward. Two layers, 128 hidden units per direction.'],[6,'Each epoch gets 128 + 128 = 256 context features. Context stops at the 20-epoch window; there is no memory of the whole night.']],
draw(c,u){
  const w=new World({box:[96,170,1728,600],center:[0,0,1.2],phi:1.12,theta:-1.45+.1*Math.sin(u/4),frameHeight:5.4});
  const n=12,xs=i=>-5.5+i*1.0;const fwd=(u-1.5)*2.2,bwd=n-1-(u-3)*2.2;
  for(let i=0;i<n;i++){const g=seg(u,.1+i*.06,.6,outBack);w.grow([xs(i),0,0],[.55,.55,.7],P.amber,g);
    const fa=u>1.5&&fwd>=i?1:.25,ba=u>3&&bwd<=i?1:.25;w.sphere([xs(i),-.0,1.55],.17*clamp(g),fa>.5?P.cyan:'#2A4A66',{seg:8});w.sphere([xs(i),0,2.25],.17*clamp(g),ba>.5?P.coral:'#4A2A3A',{seg:8});
    if(i<n-1){w.line([[xs(i)+.2,0,1.55],[xs(i+1)-.2,0,1.55]],P.cyan,2.4,{alpha:clamp(g)*fa});w.line([[xs(i)+.2,0,2.25],[xs(i+1)-.2,0,2.25]],P.coral,2.4,{alpha:clamp(g)*ba})}}
  if(u>1.5&&fwd<n)w.sphere([xs(clamp(fwd,0,n-1)),0,1.55],.3,P.white);if(u>3&&bwd>0)w.sphere([xs(clamp(bwd,0,n-1)),0,2.25],.3,P.white);
  w.draw(c);
  const l=w.px([xs(0)-.7,0,1.55]),l2=w.px([xs(0)-.7,0,2.25]),l3=w.px([xs(0)-.7,0,.35]);
  T(c,'forward →',l[0],l[1]+8,{size:24,color:P.cyan,align:'right',alpha:fin(u,1.5)});T(c,'← backward',l2[0],l2[1]+8,{size:24,color:P.coral,align:'right',alpha:fin(u,3)});T(c,'epoch embeddings',l3[0],l3[1]+8,{size:24,color:P.amber,align:'right',alpha:fin(u,.3)});
  EQ(c,'\\mathbf h_t=\\big[\\overrightarrow{\\mathbf h_t}\\,;\\,\\overleftarrow{\\mathbf h_t}\\big]\\in\\mathbb R^{128+128=256}',700,820,{size:34,p:seg(u,6,1.2)});
  pill(c,'context = one 20-epoch window (10 min)',1450,820,{size:24,color:P.amber,alpha:fin(u,7.5)});
}},
{id:'softmax',ch:4,tag:'MATH',dur:16,cap:[[0,'The classifier maps 256 features to five logits per epoch. Logits can be negative and need not sum to 1.'],[5,'Softmax exponentiates and divides by the total. With logit ln 4 for N2 and 0 for the rest, N2 gets 4 / 8 = 0.5.'],[9.6,'The prediction is the largest logit. A probability of 0.9 is not automatically right 90% of the time.']],
draw(c,u){
  const logits=[0,0,Math.log(4),0,0],ex=logits.map(Math.exp),pr=ex.map(v=>v/8);
  const ph1=seg(u,4,1.4,cubic),ph2=seg(u,7.2,1.4,cubic);const base=650,sc=160,x0=260;
  poly(c,[[x0-40,base],[x0+5*170,base]],{stroke:P.line,width:2,alpha:fin(u,0)});
  for(let k=0;k<5;k++){const v=lerp(lerp(logits[k],ex[k]/2,ph1),pr[k]*4,ph2),h=v*sc*seg(u,.3+k*.1,.8,outBack),x=x0+k*170;
    rect(c,x,base-h,120,Math.max(3,h),STAGE_COL[k],{r:6,alpha:k===2||u<10.2?1:.45});
    const lab=ph2>.5?pr[k].toFixed(3):ph1>.5?(ex[k]).toFixed(0):logits[k].toFixed(2);T(c,lab,x+60,base-h-16,{size:30,align:'center',weight:'bold',alpha:fin(u,.6+k*.1)});
    T(c,STAGES[k],x+60,base+40,{size:28,align:'center',color:STAGE_COL[k],weight:'bold',alpha:fin(u,.3)})}
  T(c,ph2>.5?'probabilities':ph1>.5?'exp(logit)':'logits a',x0,240,{size:30,color:P.muted,alpha:fin(u,.3)});
  EQ(c,'\\mathbf a_t=W_o\\mathbf h_t+\\mathbf b_o,\\quad W_o\\in\\mathbb R^{5\\times256}',1420,260,{size:32,p:seg(u,.6,1.2)});
  EQ(c,'p_{t,c}=\\frac{e^{a_{t,c}}}{\\sum_{k=0}^{4}e^{a_{t,k}}}',1420,400,{size:40,p:seg(u,4.4,1.2)});
  EQ(c,'p_{\\mathrm{N2}}=\\frac{4}{4+1+1+1+1}=0.5',1420,530,{size:36,color:P.amber,p:seg(u,7.4,1.2)});
  EQ(c,'\\widehat y_t=\\arg\\max_c a_{t,c}',1420,660,{size:36,color:P.green,p:seg(u,10,1)});
  if(u>10.2)rect(c,x0+2*170-10,base-.5*4*sc-60,140,.5*4*sc+60+60,null,{stroke:P.green,sw:3,r:10,alpha:fin(u,10.2)});
}},
// ---------------------------------------------------------------- CH5 LEARNING
{id:'ce',ch:5,tag:'MATH',dur:12,cap:[[0,'Training uses cross-entropy: minus the log of the probability the model gives to the true class.'],[6,'Confident and correct costs little. Confident and wrong is punished hard: p = 0.01 costs 4.6.']],
draw(c,u){
  const ax=axes(c,{x:200,y:230,w:900,h:500,xmin:0,xmax:1,ymin:0,ymax:5,xt:[0,.25,.5,.75,1],yt:[0,1,2,3,4,5],xl:'probability of the true class',yl:'loss',alpha:fin(u,0)});
  const pts=[];for(let i=0;i<=300;i++){const p=.0068+i/300*(1-.0068);pts.push([ax.X(p),ax.Y(-Math.log(p))])}drawOn(c,pts,seg(u,.4,2),{stroke:P.cyan,width:4,glow:10});
  const rows=[[.9,'0.105'],[.5,'0.693'],[.1,'2.303'],[.01,'4.605']];
  rows.forEach(([p,l],i)=>{const a=fin(u,2.6+i*.6);dot(c,ax.X(p),ax.Y(-Math.log(p)),10,P.amber,a,14);
    T(c,String(p),1300,330+i*80,{size:32,align:'right',alpha:a,weight:'mono'});T(c,'→',1360,330+i*80,{size:30,color:P.muted,align:'center',alpha:a});T(c,l,1530,330+i*80,{size:32,align:'right',weight:'mono',color:i===3?P.coral:P.amber,alpha:a})});
  T(c,'p(true)',1300,265,{size:22,color:P.muted,align:'right',alpha:fin(u,2.6)});T(c,'loss',1530,265,{size:22,color:P.muted,align:'right',alpha:fin(u,2.6)});
  EQ(c,'\\ell=-\\ln p_y',1420,690,{size:40,p:seg(u,.8,1)});EQ(c,'=-a_y+\\ln\\sum_c e^{a_c}',1420,780,{size:34,color:P.muted,p:seg(u,6.4,1.2)});
}},
{id:'weights',ch:5,tag:'CODE',dur:12,cap:[[0,'N1 is rare and hard, so N1 mistakes are weighted 1.5 times. The loss is divided by the sum of the weights used.'],[6.5,'A sequence does not get one answer: all 20 epochs keep their own label and add their own term to the loss.']],
draw(c,u){
  const wts=[1,1.5,1,1,1],base=500;
  wts.forEach((v,k)=>{const h=v*180*seg(u,.3+k*.12,.9,outBack),x=200+k*150;rect(c,x,base-h,100,h,STAGE_COL[k],{r:6});T(c,v.toFixed(1),x+50,base-h-14,{size:30,align:'center',weight:'bold',alpha:fin(u,.6+k*.12)});T(c,STAGES[k],x+50,base+36,{size:26,align:'center',weight:'bold',color:STAGE_COL[k],alpha:fin(u,.3)})});
  T(c,'class weights',200,230,{size:26,color:P.muted,alpha:fin(u,.2)});
  EQ(c,'\\mathcal L=\\frac{\\sum_{i=1}^{N}w_{y_i}\\left(-\\ln p_{i,y_i}\\right)}{\\sum_{i=1}^{N}w_{y_i}}',1350,330,{size:42,p:seg(u,1.6,1.4)});
  // sequence of 20 epochs with their own loss bars
  const sx=230,sy=720;for(let i=0;i<20;i++){const a=fin(u,6.8+i*.06),st=[2,2,1,2,3,3,2,2,4,4,2,1,0,2,2,3,2,4,4,2][i];rect(c,sx+i*72,sy,62,44,STAGE_COL[st],{r:6,alpha:a});const l=.2+rnd(i*5)*(st===1?2.2:1);rect(c,sx+i*72+18,sy-12-l*50,26,l*50,P.coral,{r:3,alpha:fin(u,7.6+i*.05)})}
  T(c,'one sequence: 20 labels, 20 loss terms',sx,sy+86,{size:22,color:P.muted,alpha:fin(u,7)});
  pill(c,'[B, S, 5] → [B·S, 5]',1560,600,{size:26,color:P.amber,weight:'mono',alpha:fin(u,8.4)});
}},
{id:'grad',ch:5,tag:'MATH',dur:13,cap:[[0,'The gradient of the loss for each logit is simple: p − 1 for the true class and p for every other class.'],[6.5,'True class N1 with p = 0.2 gives −0.8, so its score should rise. N2 with p = 0.6 gives +0.6, so its score should fall.']],
draw(c,u){
  const p=[.1,.2,.6,.05,.05],y=1,g=p.map((v,k)=>v-(k===y?1:0));const step=seg(u,8.6,1.6,cubic);const p2=[.08,.45,.37,.05,.05];
  const base=560,x0=200;for(let k=0;k<5;k++){const v=lerp(p[k],p2[k],step),h=v*500*seg(u,.3+k*.1,.8,outBack),x=x0+k*150;rect(c,x,base-h,100,h,STAGE_COL[k],{r:6,alpha:k===y?1:.75});T(c,v.toFixed(2),x+50,base-h-14,{size:28,align:'center',weight:'bold',alpha:fin(u,.6)});T(c,STAGES[k],x+50,base+36,{size:26,align:'center',color:STAGE_COL[k],weight:'bold',alpha:fin(u,.3)});
    const ga=fin(u,3.4+k*.2)*(1-step*.7);T(c,(g[k]>0?'+':'')+g[k].toFixed(2),x+50,base+90,{size:28,align:'center',weight:'mono',color:g[k]<0?P.green:P.coral,alpha:ga});
    if(k===y||k===2)arrow(c,x+50,base-h-60,x+50,base-h-60+(g[k]<0?-90:90)*.9,{col:g[k]<0?P.green:P.coral,width:5,head:18,p:seg(u,6.8,1),alpha:1-step})}
  T(c,'true class',x0+150+50,base+140,{size:22,color:P.green,align:'center',alpha:fin(u,1.4)});
  EQ(c,'\\frac{\\partial\\ell}{\\partial a_c}=p_c-\\mathbf{1}(c=y)',1380,250,{size:42,p:seg(u,1.2,1.2)});
  EQ(c,'\\frac{\\partial\\ell}{\\partial a_{N1}}=0.2-1=-0.8\\qquad \\frac{\\partial\\ell}{\\partial a_{N2}}=0.6',1380,390,{size:30,color:P.amber,p:seg(u,4.4,1.4)});
  EQ(c,'\\frac{\\partial\\mathcal L}{\\partial\\theta}=\\frac{\\partial\\mathcal L}{\\partial a}\\frac{\\partial a}{\\partial h}\\frac{\\partial h}{\\partial e}\\frac{\\partial e}{\\partial\\theta}',1340,560,{size:32,p:seg(u,8,1.4)});
  pill(c,'backprop computes gradients · the optimizer applies them',1380,700,{size:22,color:P.muted,alpha:fin(u,9.6)});
}},
{id:'adamw',ch:5,tag:'CODE',dur:14,cap:[[0,'AdamW keeps a running average of the gradient (m) and of its square (v), then scales each step parameter by parameter.'],[7,'Learning rate 10⁻³, weight decay 10⁻⁴, and gradients clipped to a norm of 1 to avoid occasional violent steps.']],
draw(c,u){
  const L=(x,y)=>.18*x*x+1.6*y*y+.25*Math.sin(x*1.4)*.6;
  const w=new World({box:[96,160,1060,640],center:[0,0,.6],phi:1.0,theta:-1.0+.25*Math.sin(u/6),frameHeight:6.6});
  const N=22,M=14,sx=5.2,sy=2.6,mesh=seg(u,0,1.2);
  for(let i=0;i<N;i++)for(let j=0;j<M;j++){const x0=-sx+i*2*sx/N,x1=x0+2*sx/N,y0=-sy+j*2*sy/M,y1=y0+2*sy/M;const z=(x,y)=>Math.min(3.2,L(x,y))*.55*mesh;const h=L((x0+x1)/2,(y0+y1)/2);
    w.quad([[x0,y0,z(x0,y0)],[x1,y0,z(x1,y0)],[x1,y1,z(x1,y1)],[x0,y1,z(x0,y1)]],mixCol('#1B3A63','#5BE0F0',clamp(1-h/3)),{alpha:.92,edge:'rgba(150,220,255,0.12)'})}
  // paths: plain GD zigzag vs Adam smooth
  const path=(kind)=>{const pts=[];let x=-4.6,y=2.2,m=[0,0],v=[0,0];for(let t=1;t<=60;t++){const gx=.36*x+.21*Math.cos(x*1.4),gy=3.2*y;if(kind==='gd'){x-=.55*gx;y-=.58*gy}else{m=[.9*m[0]+.1*gx,.9*m[1]+.1*gy];v=[.999*v[0]+.001*gx*gx,.999*v[1]+.001*gy*gy];const mh=[m[0]/(1-.9**t),m[1]/(1-.9**t)],vh=[v[0]/(1-.999**t),v[1]/(1-.999**t)];x-=.22*mh[0]/(Math.sqrt(vh[0])+1e-8);y-=.22*mh[1]/(Math.sqrt(vh[1])+1e-8)}pts.push([x,y,Math.min(3.2,L(x,y))*.55+.06])}return pts};
  const gd=path('gd'),ad=path('adam'),k=Math.floor(60*seg(u,2,8,smooth));
  if(k>1){w.line(gd.slice(0,k),P.violet,2.4,{alpha:.9});w.line(ad.slice(0,k),P.amber,3.4,{glow:8});w.sphere(ad[k-1],.14,P.white,{seg:8})}
  w.draw(c);
  T(c,'plain gradient descent',150,820,{size:22,color:P.violet,alpha:fin(u,2.4)});T(c,'Adam-style steps',460,820,{size:22,color:P.amber,alpha:fin(u,2.4)});T(c,'(illustrative loss surface)',720,820,{size:20,color:P.dim,alpha:fin(u,2.4)});
  const eqs=[['m_t=\\beta_1m_{t-1}+(1-\\beta_1)g_t',.6],['v_t=\\beta_2v_{t-1}+(1-\\beta_2)g_t^2',1.6],['\\widehat m_t=\\frac{m_t}{1-\\beta_1^t},\\quad \\widehat v_t=\\frac{v_t}{1-\\beta_2^t}',2.8],['\\theta_t=(1-\\alpha\\lambda)\\theta_{t-1}-\\alpha\\frac{\\widehat m_t}{\\sqrt{\\widehat v_t}+\\epsilon}',4.2],['g_{\\text{clip}}=g\\cdot\\min\\!\\left(1,\\frac{1}{\\|g\\|_2}\\right)',7.6]];
  eqs.forEach(([e,t],i)=>EQ(c,e,1500,230+i*110,{size:i===3?30:30,color:i===4?P.coral:P.ink,p:seg(u,t,1.2)}));
  const chips=[['α = 10⁻³',P.cyan],['λ = 10⁻⁴',P.violet],['‖g‖ ≤ 1',P.coral]];chips.forEach(([s,col],i)=>pill(c,s,1290+i*210,800,{size:26,color:col,alpha:fin(u,7.2+i*.3),weight:'mono'}));
}},
{id:'general',ch:5,tag:'ILLU',dur:13,cap:[[0,'Low training loss is not the goal. The goal is good predictions for people the model has never seen.'],[6.5,'We keep the checkpoint with the best validation macro-F1, stopping after 10 epochs without improvement or at 60 epochs.']],
draw(c,u){
  EQ(c,'\\widehat R_{\\text{train}}(\\theta)=\\frac{1}{N}\\sum_i\\ell(f_\\theta(X_i),y_i)',540,215,{size:34,color:P.cyan,p:seg(u,.3,1.2)});
  EQ(c,'R(\\theta)=\\mathbb E_{(X,Y)\\sim P}\\big[\\ell(f_\\theta(X),Y)\\big]',1380,215,{size:34,color:P.amber,p:seg(u,1.6,1.2)});
  const ax=axes(c,{x:200,y:310,w:1300,h:440,xmin:0,xmax:40,ymin:0,ymax:1,xt:[0,10,20,30,40],yt:[],xl:'training epoch',alpha:fin(u,2.6)});
  const tr=e=>.95*Math.exp(-e/9)+.05,va=e=>.42+.36*(1-Math.exp(-e/6))-.0035*Math.max(0,e-22)+.012*Math.sin(e*1.3);
  const best=Array.from({length:41},(_,e)=>[e,va(e)]).reduce((a,b)=>b[1]>a[1]?b:a);const stopAt=Math.min(40,best[0]+10);
  const P1=[],P2=[];for(let e=0;e<=stopAt;e+=.25){P1.push([ax.X(e),ax.Y(tr(e))]);P2.push([ax.X(e),ax.Y(va(e))])}
  drawOn(c,P1,seg(u,3,3),{stroke:P.cyan,width:3.4});drawOn(c,P2,seg(u,3,3),{stroke:P.amber,width:3.4});
  T(c,'training loss',ax.X(4),ax.Y(tr(4))-18,{size:24,color:P.cyan,alpha:fin(u,3.6)});T(c,'validation macro-F1',ax.X(30),ax.Y(va(30))-26,{size:24,color:P.amber,alpha:fin(u,5)});
  const b=fin(u,7);poly(c,[[ax.X(best[0]),ax.Y(0)],[ax.X(best[0]),ax.Y(1)]],{stroke:P.green,width:2.5,dash:[8,6],alpha:b});dot(c,ax.X(best[0]),ax.Y(best[1]),11,P.green,b,16);EQ(c,'t^*=\\arg\\max_t\\operatorname{MF1}_{\\text{val}}(t)',ax.X(best[0])+30,ax.Y(1)+30,{size:28,color:P.green,align:'left',p:b});
  const pa=fin(u,8.6);poly(c,[[ax.X(best[0]),ax.Y(.12)],[ax.X(stopAt),ax.Y(.12)]],{stroke:P.coral,width:3,alpha:pa});T(c,'patience 10 → stop',ax.X((best[0]+stopAt)/2),ax.Y(.12)-14,{size:22,color:P.coral,align:'center',alpha:pa});
}},
];
