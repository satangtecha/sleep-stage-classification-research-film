import {rnd} from './lib.mjs';
export const YC=513;
export const STRIP={x:104,w:1712,h:64,n:96};
export const FULL_PAD=8;
export const BADGE={x:104,y:148,w:300,h:48};
export const SEED_POOLED=6500;
export const SEEDS={SC4021:4021,SC4062:4062,SC4142:4142,N1:1253};
export const DEMO_TILES=[1,7,12];
export const STAMP_ONE_SEED=false;
// HYPNO: synthetic 96-epoch night (plan 5.2). 0=W 1=N1 2=N2 3=N3 4=REM
const RUNS=[[0,2],[1,2],[2,6],[3,8],[2,4],[4,4],[2,6],[3,6],[2,4],[4,6],[2,6],[1,2],[2,6],[4,8],[2,4],[1,2],[4,6],[2,4],[1,2],[0,2],[2,2],[4,2],[0,2]];
export const HYPNO=RUNS.flatMap(([s,n])=>Array(n).fill(s));
export function perm(seed,n){const a=Array.from({length:n},(_,i)=>i);for(let i=n-1;i>0;i--){const j=Math.floor(rnd(seed*131+i)*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a}
export const matchSet=(seed,n,k)=>new Set(perm(seed,n).slice(0,k));
export function n1Sim(hypno,cm){
  const E=hypno.flatMap((s,i)=>s===1?[i]:[]);
  const rowN1=cm[1].reduce((a,b)=>a+b),colN1=cm.reduce((a,r)=>a+r[1],0);
  const nBoth=Math.round(E.length*cm[1][1]/rowN1),nCall=Math.round(E.length*colN1/rowN1);
  const pe=perm(SEEDS.N1,E.length),both=pe.slice(0,nBoth).map(i=>E[i]);
  const others=hypno.flatMap((s,i)=>s!==1?[i]:[]),po=perm(SEEDS.N1+1,others.length);
  return {E,both,M:[...both,...po.slice(0,nCall-nBoth).map(i=>others[i])]}}
// Venn: area of lens between circles radius r1, r2 at distance d
export function lensArea(r1,r2,d){if(d>=r1+r2)return 0;if(d<=Math.abs(r1-r2))return Math.PI*Math.min(r1,r2)**2;
  const a=r1*r1*Math.acos((d*d+r1*r1-r2*r2)/(2*d*r1)),b=r2*r2*Math.acos((d*d+r2*r2-r1*r1)/(2*d*r2));
  const c=.5*Math.sqrt((-d+r1+r2)*(d+r1-r2)*(d-r1+r2)*(d+r1+r2));return a+b-c}
export function vennDistance(r1,r2,target){let lo=Math.abs(r1-r2),hi=r1+r2;for(let i=0;i<80;i++){const m=(lo+hi)/2;if(lensArea(r1,r2,m)>target)lo=m;else hi=m}return (lo+hi)/2}
