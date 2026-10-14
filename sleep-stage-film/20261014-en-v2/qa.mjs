import fs from 'node:fs';
import path from 'node:path';
import {createCanvas,loadImage} from '@napi-rs/canvas';
import {ROOT,STORY,renderStills} from './film.mjs';
renderStills();
const canvas=createCanvas(1920,1350),ctx=canvas.getContext('2d');
for(let m=1;m<=5;m++)for(let i=0;i<4;i++){const image=await loadImage(path.join(ROOT,'outputs/frames',`minute-${m}-scene-${i+1}-11s.png`));ctx.drawImage(image,i*480,(m-1)*270,480,270)}
fs.writeFileSync(path.join(ROOT,'outputs/storyboard-contact.png'),canvas.toBuffer('image/png'));
const stamp=seconds=>`${Math.floor(seconds/3600).toString().padStart(2,'0')}:${Math.floor(seconds/60)%60<10?'0':''}${Math.floor(seconds/60)%60}:${String(Math.floor(seconds)%60).padStart(2,'0')},${String(Math.round(seconds%1*1000)).padStart(3,'0')}`;
let entries=[],n=1;
STORY.chapters.forEach((c,m)=>c.scenes.forEach((s,i)=>s.captions.forEach((cap,j)=>{const start=m*60+i*15+j*7.5;entries.push(`${n++}\n${stamp(start)} --> ${stamp(start+7.5)}\n${cap}\n`)})));
fs.writeFileSync(path.join(ROOT,'outputs/captions-en.srt'),entries.join('\n'));
