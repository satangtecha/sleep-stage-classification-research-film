import {clamp,rnd,outExpo,fmt} from './lib.mjs';
export {rnd};
export const linear=x=>clamp(x);
export const stagger=(i,step)=>i*step;
/** tabular number text: draw digit by digit at fixed width. returns array of {ch,dx} using width of "0" */
export function tnum(c,s,x,y,draw,{size=64,weight='bold',align='left'}={}){
  c.save();c.font=`${size}px ${weight==='bold'?'FilmBold':weight==='med'?'FilmMed':'Film'}`;const w0=c.measureText('0').width;c.restore();
  const wid=ch=>/\d/.test(ch)?w0:null;let total=0;for(const ch of s){total+=wid(ch)??(()=>{c.save();c.font=`${size}px ${weight==='bold'?'FilmBold':weight==='med'?'FilmMed':'Film'}`;const w=c.measureText(ch).width;c.restore();return w})()}
  let px=align==='center'?x-total/2:align==='right'?x-total:x;
  for(const ch of s){const w=wid(ch)??(()=>{c.save();c.font=`${size}px ${weight==='bold'?'FilmBold':weight==='med'?'FilmMed':'Film'}`;const w=c.measureText(ch).width;c.restore();return w})();draw(ch,px+(/\d/.test(ch)?w/2:w/2),y,w);px+=w}
  return total}
/** vertical shake (plan 6.5): hits are story-relative times */
export const shakeDy=(t,hits,{amp=1.5,tau=0.10,f=14,cap=3}={})=>clamp(hits.reduce((s,h,i)=>t<h?s:s+(rnd(i+7)<.5?-1:1)*amp*Math.exp(-(t-h)/tau)*Math.cos(2*Math.PI*f*(t-h)),0),-cap,cap);
/** counting value: 0 -> v over dur starting at t0, easing outExpo */
export const count=(t,t0,dur,v)=>v*outExpo((t-t0)/dur);
export {fmt};
/** truncated polyline with interpolated end point (smooth drawOn for any polyline) */
export function partial(pts,p){p=clamp(p);if(p<=0)return [];if(p>=1)return pts;let tot=0;const seg=[];for(let i=1;i<pts.length;i++){const d=Math.hypot(pts[i][0]-pts[i-1][0],pts[i][1]-pts[i-1][1]);seg.push(d);tot+=d}
  let rem=tot*p;const out=[pts[0]];for(let i=1;i<pts.length;i++){if(rem>=seg[i-1]){out.push(pts[i]);rem-=seg[i-1]}else{const a=rem/seg[i-1];out.push([lerp(pts[i-1][0],pts[i][0],a),lerp(pts[i-1][1],pts[i][1],a)]);break}}return out}
import {lerp} from './lib.mjs';
