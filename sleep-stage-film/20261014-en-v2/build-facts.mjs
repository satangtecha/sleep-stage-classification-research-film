import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {fileURLToPath} from 'node:url';
const ROOT=path.dirname(fileURLToPath(import.meta.url));
const old=path.resolve(ROOT,'../20261013-v1/facts.json');
const source='\\\\wsl.localhost\\Ubuntu\\home\\techatat\\evidence-first-quant-research-os\\sleep_stage_simple';
const facts=JSON.parse(fs.readFileSync(old));
const dir=path.join(source,'results/closeout-and-exposure-audit-v1-20261013');
const loaded={};
for(const [file,expected] of Object.entries(facts.source_sha256)){
  const bytes=fs.readFileSync(path.join(dir,file));
  const actual=crypto.createHash('sha256').update(bytes).digest('hex');
  if(actual!==expected)throw Error('Frozen source changed: '+file);
  loaded[file]=JSON.parse(bytes);
}
const e=loaded['evidence.json'];
facts.comparison=e.historical_test_comparison;
facts.bootstrap={unit:'participant, paired across runs',resamples:1000,seed:20261011};
facts.pipeline={channel:'EEG Fpz-Cz',hz:100,epoch_seconds:30,shape:[129,29],cnn_channels:[32,64,128],embedding_size:128,gru_layers:2,gru_hidden_size:128,bidirectional:true,infer_stride:5};
fs.writeFileSync(path.join(ROOT,'facts.json'),JSON.stringify(facts,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({frozen_sources_verified:Object.keys(loaded).length,training:false,new_inference:false},null,2));
