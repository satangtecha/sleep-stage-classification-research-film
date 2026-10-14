import test from 'node:test';
import assert from 'node:assert/strict';
import {readPcm16,padPcm,pcmWav} from '../sync-audio.mjs';
test('padding to exact20seconds preserves every original PCM sample',()=>{const p=Buffer.alloc(19.8429166667*96000|0,3);if(p.length%2)throw Error('fixture sample');const q=padPcm(p,20);assert.equal(q.length,1920000);assert.deepEqual(q.subarray(0,p.length),p);assert.ok(q.subarray(p.length).every(v=>v===0));assert.equal(readPcm16(pcmWav(q)).length/96000,20)});
test('300second canonical PCM has exact duration',()=>{const q=Buffer.concat(Array.from({length:15},()=>padPcm(Buffer.alloc(2),20)));assert.equal(readPcm16(pcmWav(q)).length/96000,300)});
test('audio correction refuses truncation, fractional samples and invalid inputs',()=>{assert.throws(()=>padPcm(Buffer.alloc(1920002),20));assert.throws(()=>padPcm(Buffer.alloc(3),20));assert.throws(()=>padPcm(Buffer.alloc(2),0));assert.throws(()=>readPcm16(Buffer.alloc(44)))});
