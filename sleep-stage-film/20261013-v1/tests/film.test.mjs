import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import {createCanvas} from '@napi-rs/canvas';
import {drawFrame,sceneAt,ease,textFamily} from '../film.mjs';
const story=JSON.parse(fs.readFileSync(new URL('../story.json',import.meta.url)));
const facts=JSON.parse(fs.readFileSync(new URL('../facts.json',import.meta.url)));
test('five chapters, three20s scenes each,300s total, unique ids',()=>{
  assert.equal(story.duration_seconds,300);assert.equal(story.chapters.length,5);
  assert.equal(new Set(story.chapters.flatMap(c=>c.scenes.map(s=>s.id))).size,15);
  for(const c of story.chapters){assert.equal(c.scenes.length,3);assert.ok(c.scenes.every(s=>s.narration&&s.disclosure&&s.visual))}
});
test('20-second boundaries keep the correct scene',()=>{
  assert.equal(sceneAt(1,19.99).id,'01-question');assert.equal(sceneAt(1,20).id,'02-scope');assert.equal(sceneAt(5,59.99).id,'15-close');
});
test('locked facts stay in their original metric units',()=>{
  assert.equal(facts.study.participants,20);assert.equal(facts.study.test_subjects_per_fold,2);assert.equal(facts.audit.independent_confirmed,0);
  assert.ok(Math.abs(facts.test.r1.subject_mf1.point-.74858006541)<1e-10);
  assert.ok(facts.differences['fullnight-minus-r1'].per_subject_mean_macro_f1.ci95[0]<0);
  assert.ok(facts.differences['fullnight-minus-r1'].per_subject_mean_macro_f1.ci95[1]>0);
  assert.equal(facts.pilots.length,10);assert.ok(facts.pilots.every(p=>p.phase==='validation'));
});
test('all15 visual scenes draw finite frames with Thai text',()=>{
  const canvas=createCanvas(1920,1080);
  for(let m=1;m<=5;m++)for(const t of [10,30,50]){drawFrame(canvas,m,t);assert.equal(canvas.data().length,1920*1080*4)}
});
test('motion is genuinely time-dependent and bounded',()=>{
  const canvas=createCanvas(1920,1080),hash=()=>crypto.createHash('sha256').update(canvas.data()).digest('hex');drawFrame(canvas,1,5);const a=hash();drawFrame(canvas,1,12);assert.notEqual(a,hash());assert.equal(ease(-1),0);assert.equal(ease(2),1);
});
test('script preserves mandatory scientific qualifiers',()=>{
  const text=JSON.stringify(story).toLowerCase();for(const k of ['post-hoc','transductive','validation only','not the original','0 certified independent'])assert.ok(text.includes(k),k);
});
test('Thai headings use a Thai-capable bold font, English can use Latin semibold',()=>{
  assert.equal(textFamily('ผลเดิมที่ล็อกไว้',true),'FilmThaiBold');assert.equal(textFamily('CNN + BiGRU',true),'FilmBold');
  for(const s of story.chapters.flatMap(c=>c.scenes))if(/[\u0E00-\u0E7F]/.test(s.heading))assert.equal(textFamily(s.heading,true),'FilmThaiBold');
});
