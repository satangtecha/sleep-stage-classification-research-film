// concat parts, add 21 chapter markers, write verification.json
import fs from 'node:fs';import path from 'node:path';import {spawnSync} from 'node:child_process';
import {SCENES,FRAMES,FPS,DURATION,ROOT} from '../film.mjs';
const OUT=path.join(ROOT,'outputs'),P=path.join(OUT,'parts');
const parts=fs.readdirSync(P).filter(f=>/^part-\d+\.mp4$/.test(f)).sort((a,b)=>parseInt(a.slice(5))-parseInt(b.slice(5)));
fs.writeFileSync(path.join(P,'list.txt'),parts.map(f=>`file '${f}'`).join('\n')+'\n');
const NAMES={T1:'Title',B1:'1 · Problem',P1:'1 · Input, process, output',B2:'2 · The paper and the split',B3:'2 · The question',Q2:'2 · Scope and hypotheses',B3b:'3 · The data',D2:'3 · Variables',M1:'4 · STFT',M2:'4 · CNN',M3:'4 · BiGRU',M4:'4 · Contrastive dropped',M5:'4 · Test protocol',E1:'5 · Baseline',E2:'5 · The ruler',E3:'5 · The catch',E4:'5 · The weak spot',L1:'6 · What we can say',L2:'6 · Audit',L3:'6 · Summary',End:'Close'};
let meta=';FFMETADATA1\ntitle=Reading Sleep from One EEG Channel\n';
SCENES.forEach((s,i)=>{const end=i+1<SCENES.length?SCENES[i+1].t0:DURATION;meta+=`[CHAPTER]\nTIMEBASE=1/1000\nSTART=${Math.round(s.t0*1000)}\nEND=${Math.round(end*1000)}\ntitle=${NAMES[s.id]||s.id}\n`});
fs.writeFileSync(path.join(OUT,'chapters.txt'),meta);
const final=path.join(OUT,'reading-sleep-from-one-eeg-channel-4m40-en-silent.mp4');
let r=spawnSync('ffmpeg',['-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',path.join(P,'list.txt'),'-i',path.join(OUT,'chapters.txt'),'-map_metadata','1','-map','0:v','-c','copy','-movflags','+faststart',final],{stdio:'inherit'});if(r.status)throw Error('concat failed');
const probe=JSON.parse(spawnSync('ffprobe',['-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames,width,height,r_frame_rate,codec_name,pix_fmt,color_space,duration','-show_entries','format=duration,size','-of','json',final]).stdout);
const ch=JSON.parse(spawnSync('ffprobe',['-v','error','-show_chapters','-of','json',final]).stdout).chapters.length;
const size=fs.statSync(final).size;
const v={file:path.basename(final),frames:+probe.streams[0].nb_read_frames,expected_frames:FRAMES,width:probe.streams[0].width,height:probe.streams[0].height,fps:probe.streams[0].r_frame_rate,codec:probe.streams[0].codec_name,pix_fmt:probe.streams[0].pix_fmt,duration_s:+probe.format.duration,expected_duration_s:DURATION,audio_streams:0,chapters:ch,size_mb:+(size/1048576).toFixed(1),size_cap_mb:100,ok:+probe.streams[0].nb_read_frames===FRAMES&&ch===SCENES.length&&size<100*1048576};
fs.writeFileSync(path.join(OUT,'verification.json'),JSON.stringify(v,null,1)+'\n');console.log(v);if(!v.ok)process.exit(2)
