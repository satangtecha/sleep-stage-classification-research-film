import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const ROOT=path.dirname(fileURLToPath(import.meta.url));
export function readPcm16(wav){
  if(wav.toString('ascii',0,4)!=='RIFF'||wav.toString('ascii',8,12)!=='WAVE')throw Error('Not RIFF WAVE');
  let fmt,data;
  for(let p=12;p+8<=wav.length;){const kind=wav.toString('ascii',p,p+4),len=wav.readUInt32LE(p+4);if(p+8+len>wav.length)throw Error('Truncated WAV');if(kind==='fmt ')fmt=wav.subarray(p+8,p+8+len);if(kind==='data')data=wav.subarray(p+8,p+8+len);p+=8+len+(len%2);}
  if(!fmt||!data||fmt.readUInt16LE(0)!==1||fmt.readUInt16LE(2)!==1||fmt.readUInt32LE(4)!==48000||fmt.readUInt16LE(14)!==16)throw Error('Expected PCM16 mono48000Hz');
  if(data.length%2)throw Error('Partial PCM sample');return data;
}
export function padPcm(pcm,seconds){const size=Math.round(seconds*48000)*2;if(!Number.isFinite(seconds)||seconds<=0||pcm.length%2||pcm.length>size)throw Error('Invalid duration or would truncate speech');return Buffer.concat([pcm,Buffer.alloc(size-pcm.length)]);}
export function pcmWav(pcm){const h=Buffer.alloc(44);h.write('RIFF');h.writeUInt32LE(36+pcm.length,4);h.write('WAVEfmt ',8);h.writeUInt32LE(16,16);h.writeUInt16LE(1,20);h.writeUInt16LE(1,22);h.writeUInt32LE(48000,24);h.writeUInt32LE(96000,28);h.writeUInt16LE(2,32);h.writeUInt16LE(16,34);h.write('data',36);h.writeUInt32LE(pcm.length,40);return Buffer.concat([h,pcm]);}
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const probe=p=>JSON.parse(execFileSync('ffprobe',['-v','error','-show_format','-show_streams','-show_chapters','-of','json',p],{encoding:'utf8'}));
function run(){
  const out=path.join(ROOT,'outputs','final'),dest=path.join(out,'SleepStageResearch-5min-v2.mp4');
  const alreadyMuxed=fs.existsSync(dest);
  if(fs.existsSync(path.join(out,'verification-v2.json')))throw Error('Synchronized finalization already complete; refusing overwrite');
  const story=JSON.parse(fs.readFileSync(path.join(ROOT,'story.json'))),pieces=[],measurements=[];
  const canonical=path.join(out,'audio-exact');fs.mkdirSync(canonical,{recursive:true});
  for(const s of story.chapters.flatMap(c=>c.scenes)){
    const stem=s.audio_stem||s.id,source=path.join(ROOT,'outputs','audio',stem+'-20s.wav'),pcm=readPcm16(fs.readFileSync(source));
    const seconds=pcm.length/96000;if(seconds<19.5||seconds>20)throw Error('Unexpected source duration '+seconds);
    const padded=padPcm(pcm,20);pieces.push(padded);
    const file=path.join(canonical,s.id+'.wav'),encoded=pcmWav(padded);
    if(fs.existsSync(file)){if(!fs.readFileSync(file).equals(encoded))throw Error('Existing canonical audio mismatch')}else fs.writeFileSync(file,encoded,{flag:'wx'});
    measurements.push({scene:s.id,source_sha256:sha(source),source_seconds:seconds,zero_padding_seconds:20-seconds,final_seconds:padded.length/96000});
  }
  const full=path.join(canonical,'narration-300s.wav'),fullEncoded=pcmWav(Buffer.concat(pieces));
  if(fs.existsSync(full)){if(!fs.readFileSync(full).equals(fullEncoded))throw Error('Existing full audio mismatch')}else fs.writeFileSync(full,fullEncoded,{flag:'wx'});
  const args=['-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',path.join(out,'concat.txt'),'-i',full,'-i',path.join(out,'chapters.ffmetadata'),'-map','0:v','-map','1:a','-map_metadata','2','-c:v','copy','-c:a','aac','-b:a','160k','-t','300','-avoid_negative_ts','disabled','-movflags','+faststart',dest];
  if(!alreadyMuxed)execFileSync('ffmpeg',args,{stdio:'inherit'});
  const p=probe(dest),video=p.streams.find(s=>s.codec_type==='video'),audio=p.streams.find(s=>s.codec_type==='audio');
  if(Number(video.nb_frames)!==7200||Math.abs(Number(video.duration)-300)>.001||Math.abs(Number(audio.duration)-300)>.001||Math.abs(Number(video.start_time))>.043||Math.abs(Number(audio.start_time))>.043)throw Error('Synchronized stream duration/start failed');
  const clips=[];fs.mkdirSync(path.join(out,'chapters-synchronized'),{recursive:true});
  for(let i=1;i<=5;i++){
    const name=`minute-${String(i).padStart(2,'0')}`,target=path.join(out,'chapters-synchronized',name+'.mp4'),wave=path.join(canonical,name+'-60s.wav');
    fs.writeFileSync(wave,pcmWav(Buffer.concat(pieces.slice((i-1)*3,i*3))),{flag:'wx'});
    execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-i',path.join(out,name+'.mp4'),'-i',wave,'-t','60','-map','0:v','-map','1:a','-map_metadata','-1','-c:v','copy','-c:a','aac','-b:a','160k','-avoid_negative_ts','disabled','-movflags','+faststart',target],{stdio:'inherit'});
    const check=probe(target),v=check.streams.find(s=>s.codec_type==='video'),a=check.streams.find(s=>s.codec_type==='audio');if(Math.abs(Number(v.duration)-60)>.05||Math.abs(Number(a.duration)-60)>.05||Number(v.nb_frames)!==1440)throw Error('Chapter duration failed');
    clips.push({file:path.relative(ROOT,target).replaceAll('\\','/'),sha256:sha(target),duration:Number(v.duration)});
  }
  const slides={slides:clips.map((c,i)=>({file:c.file,rev_file:c.file,loop:false,auto_next:false,playback_rate:1,notes:story.chapters[i].title})),resolution:[1920,1080],background_color:'#081321'};
  fs.writeFileSync(path.join(ROOT,'slides','SleepStageFilmSynchronized.json'),JSON.stringify(slides,null,2)+'\n',{flag:'wx'});
  const original=JSON.parse(fs.readFileSync(path.join(out,'verification.json')));
  const evidence={...original,sha256:sha(dest),duration_seconds:Number(p.format.duration),video_duration_seconds:Number(video.duration),audio_duration_seconds:Number(audio.duration),video_start_seconds:Number(video.start_time),audio_start_seconds:Number(audio.start_time),frames:Number(video.nb_frames),synchronized_chapters:clips,audio_alignment:measurements,audio_signal_policy:'Only zero-sample padding added after each complete scene narration; no original PCM sample changed or removed.',voice_pcm_seconds:readPcm16(fs.readFileSync(full)).length/96000};
  fs.writeFileSync(path.join(out,'verification-v2.json'),JSON.stringify(evidence,null,2)+'\n',{flag:'wx'});
  console.log(JSON.stringify({film:dest,duration:evidence.duration_seconds,video_seconds:evidence.video_duration_seconds,audio_seconds:evidence.audio_duration_seconds,frames:evidence.frames,sha256:evidence.sha256},null,2));
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url))run();
