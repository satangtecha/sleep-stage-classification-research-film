// Assemble rendered parts into the silent film, add chapter markers, cut chapter clips for Manim Slides, verify.
// Usage: node deliver.mjs            (concat + verify)
//        node deliver.mjs slides     (chapter clips + Manim Slides config)
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {ROOT,SCENES,CHAPTERS,DURATION,FRAMES,FPS,storyJSON} from './film.mjs';
import {FACTS} from './scenes-c.mjs';

const OUT=path.join(ROOT,'outputs'),MOVIE=path.join(OUT,'SleepStage-English-Silent-v3.mp4');
const sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const probe=f=>JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-show_chapters','-count_packets','-of','json',f],{encoding:'utf8'}));
const run=(args)=>execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-y',...args],{stdio:'inherit'});
// chapter boundaries: chapter card start (or 0 for the opening)
const chapters=CHAPTERS.map(ch=>{const s=SCENES.filter(x=>x.ch===ch.n);return {title:ch.n?`${ch.n}. ${ch.title}`:'Opening',start:s[0].start,end:s.at(-1).end}});
chapters.forEach((c,i)=>{if(i+1<chapters.length)c.end=chapters[i+1].start;else c.end=DURATION});

if(process.argv[2]==='slides'){
  const dir=path.join(OUT,'slides-media');fs.mkdirSync(dir,{recursive:true});
  const slides=chapters.map((c,i)=>{const f=path.join(dir,`chapter-${i}.mp4`);run(['-ss',c.start.toFixed(3),'-i',MOVIE,'-t',(c.end-c.start).toFixed(3),'-an','-vf','scale=1280:720','-c:v','libx264','-preset','fast','-crf','27','-pix_fmt','yuv420p','-movflags','+faststart',f]);
    const rel=path.relative(ROOT,f).replaceAll('\\','/');return {file:rel,rev_file:rel,auto_next:false,loop:false,notes:c.title+'\n'+SCENES.filter(s=>s.start>=c.start-0.01&&s.start<c.end-0.5).flatMap(s=>s.cap.map(x=>x[1])).join('\n')}});
  fs.mkdirSync(path.join(ROOT,'slides'),{recursive:true});
  fs.writeFileSync(path.join(ROOT,'slides/SleepStageEnglishV3.json'),JSON.stringify({slides,resolution:[1280,720],background_color:'#07101C'},null,2)+'\n');
  console.log('slides config written',slides.length);process.exit(0)}

const parts=fs.readdirSync(path.join(OUT,'parts')).filter(f=>/^part-\d+\.mp4$/.test(f)).sort((a,b)=>parseInt(a.slice(5))-parseInt(b.slice(5))).map(f=>path.join(OUT,'parts',f));
const list=path.join(OUT,'parts','concat.txt');fs.writeFileSync(list,parts.map(f=>`file '${f.replaceAll('\\','/')}'`).join('\n')+'\n');
const meta=path.join(OUT,'parts','chapters.ffmetadata');
fs.writeFileSync(meta,';FFMETADATA1\ntitle=Reading Sleep from One EEG Channel (English, silent, v3)\n'+chapters.map(c=>`[CHAPTER]\nTIMEBASE=1/1000\nSTART=${Math.round(c.start*1000)}\nEND=${Math.round(c.end*1000)}\ntitle=${c.title}\n`).join(''));
const crf=process.env.CRF;
const enc=crf?['-c:v','libx264','-preset',process.env.PRESET||'medium','-tune','animation','-crf',crf,'-pix_fmt','yuv420p']:['-c:v','copy'];
run(['-f','concat','-safe','0','-i',list,'-i',meta,'-map','0:v','-map_metadata','1','-an',...enc,'-movflags','+faststart',MOVIE]);
const p=probe(MOVIE),v=p.streams.find(s=>s.codec_type==='video');
const frames=+v.nb_read_packets,dur=+p.format.duration;
const checks={no_audio:!p.streams.some(s=>s.codec_type==='audio'),frames_match:frames===FRAMES,duration_close:Math.abs(dur-DURATION)<0.1,size_1080p:+v.width===1920&&+v.height===1080,chapters:p.chapters.length===chapters.length,under_100MB:fs.statSync(MOVIE).size<100e6};
const evidence={file:path.relative(ROOT,MOVIE),sha256:sha(MOVIE),bytes:fs.statSync(MOVIE).size,duration_seconds:dur,frames,fps:FPS,width:+v.width,height:+v.height,audio_streams:p.streams.filter(s=>s.codec_type==='audio').length,chapters:chapters.map(c=>({title:c.title,start:+c.start.toFixed(3),end:+c.end.toFixed(3)})),scenes:SCENES.length,checks,
  source_sha256:Object.fromEntries(['film.mjs','lib.mjs','scenes-a.mjs','scenes-b.mjs','scenes-c.mjs','facts.json','deliver.mjs'].map(f=>[f,sha(path.join(ROOT,f))])),research_source_sha256:FACTS.source_sha256,source_commit:FACTS.source_commit,closeout_result_commit:FACTS.closeout_result_commit,training:false,new_inference:false,new_test_evaluation:false};
fs.writeFileSync(path.join(OUT,'verification.json'),JSON.stringify(evidence,null,2)+'\n');
console.log(JSON.stringify({bytes:evidence.bytes,dur,frames,checks},null,1));
if(Object.values(checks).some(x=>!x))process.exit(1);
