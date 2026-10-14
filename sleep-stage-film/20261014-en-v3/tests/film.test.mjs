import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createCanvas} from '@napi-rs/canvas';
import {SCENES,XF,CPS,DURATION,frameAt,ROOT} from '../film.mjs';
import {FACTS} from '../scenes-c.mjs';
import {wrap} from '../lib.mjs';

const pct=x=>(100*x).toFixed(2);
const allCaps=SCENES.flatMap(s=>s.cap.map(c=>c[1])).join('\n');

test('headline numbers in captions match facts.json',()=>{
  for(const k of ['base','r1','fullnight'])assert.ok(allCaps.includes(pct(FACTS.test[k].subject_mf1.point)+'%'),k+' MF1');
  for(const k of ['base','r1'])assert.ok(allCaps.includes(pct(FACTS.test[k].pooled_accuracy.point)+'%'),k+' accuracy');
  const d=FACTS.differences['fullnight-minus-r1'].per_subject_mean_macro_f1;
  assert.ok(allCaps.includes((d.point*100).toFixed(2).replace('-','−')));
  assert.ok(allCaps.includes((d.ci95[0]*100).toFixed(2).replace('-','−'))&&allCaps.includes('+'+(d.ci95[1]*100).toFixed(2)));
  const cm=FACTS.comparison.runs.r1.pooled_confusion;assert.equal(cm[1].reduce((a,b)=>a+b),2804);assert.equal(cm.reduce((a,r)=>a+r[1],0),3220);assert.equal(cm[1][1],1253);
  assert.equal(cm.reduce((a,r,i)=>a+r[i],0),34266);assert.equal(FACTS.study.epochs,42307);
});

test('captions are readable without audio',()=>{
  const c=createCanvas(10,10).getContext('2d');
  for(const s of SCENES)s.cap.forEach(([t,x],i)=>{const end=i+1<s.cap.length?s.cap[i+1][0]:s.dur-XF/2;const d=end-t-(i===0?XF/2:0);
    assert.ok(x.length/d<=CPS+1e-6,`${s.id} caption ${i} too fast`);assert.ok(wrap(c,x,1620,33).length<=2,`${s.id} caption ${i} > 2 lines`)});
});

test('every scene renders a frame without throwing',()=>{
  const canvas=createCanvas(1920,1080);for(const s of SCENES)for(const f of [.1,.5,.95])frameAt(canvas,Math.min(DURATION-1e-3,s.start+s.dur*f));
});

test('final film is silent when present',()=>{
  const v=path.join(ROOT,'outputs/verification.json');if(!fs.existsSync(v))return;const e=JSON.parse(fs.readFileSync(v));
  assert.equal(e.audio_streams,0);assert.ok(Object.values(e.checks).every(Boolean));
});
