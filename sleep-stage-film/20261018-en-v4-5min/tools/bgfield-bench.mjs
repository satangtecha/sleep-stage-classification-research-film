import {createCanvas} from '@napi-rs/canvas';
const W=1920,H=1080,N=W*H;
const rnd=i=>{const s=Math.sin(i*12.9898)*43758.5453;return s-Math.floor(s)};
const noise=new Float32Array(N);for(let i=0;i<N;i++)noise[i]=rnd(i)+rnd(i+N)-1;
const vig=new Float32Array(N);for(let y=0;y<H;y++)for(let x=0;x<W;x++){const dx=(x-W/2)/(W/2),dy=(y-H/2)/(H/2);vig[y*W+x]=Math.min(1,Math.hypot(dx,dy)/1.414)**2}
const base=[7,16,28],wc=[91,107,128];
const cv=createCanvas(W,H),ctx=cv.getContext('2d');const img=ctx.createImageData(W,H);
const d32=new Uint8ClampedArray(img.data.buffer);
function bg(vigAmt,wash){const d=d32;
 const r=base[0]+(wc[0]-base[0])*wash,g=base[1]+(wc[1]-base[1])*wash,b=base[2]+(wc[2]-base[2])*wash;
 for(let i=0,o=0;i<N;i++,o+=4){const v=1-vigAmt*vig[i],n=noise[i];
  d[o]=r*v+n;d[o+1]=g*v+n;d[o+2]=b*v+n;d[o+3]=255}}
for(let k=0;k<3;k++)bg(.08,.04);
const R=30;let t=performance.now();for(let k=0;k<R;k++)bg(.08,.04+k*.001);
console.log('opt bg ms',((performance.now()-t)/R).toFixed(1));
// correctness vs reference rounding: Uint8ClampedArray rounds half-to-even, floor(x+.5) equivalent here
