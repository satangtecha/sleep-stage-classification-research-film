import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
const root = '\\\\wsl.localhost\\Ubuntu\\home\\techatat\\evidence-first-quant-research-os\\sleep_stage_simple';
const dir = path.join(root, 'results', 'closeout-and-exposure-audit-v1-20261013');
const bound = {
  'evidence.json':'49e978d68aeb8eac31f7e424830227b6114b662d612392d24ba37bfc2a4e33ec',
  'participant_exposure.json':'e0d3fd892df2b591ee4d384f58a7ddd96a257f40e339c0f24da366a7134054f1'
};
const loaded = {};
for (const [name,hash] of Object.entries(bound)) {
  const data=fs.readFileSync(path.join(dir,name));
  if(crypto.createHash('sha256').update(data).digest('hex')!==hash)throw Error('Source changed: '+name);
  loaded[name]=JSON.parse(data);
}
const e=loaded['evidence.json'],x=loaded['participant_exposure.json'];
const facts={
  source_commit:e.source_commit,closeout_result_commit:'25f93f893e5977a61c9aa9e6911e30b361184101',
  source_sha256:bound,study:{participants:20,nights:39,epochs:42307,epoch_seconds:30,folds:10,test_subjects_per_fold:2},
  test:Object.fromEntries(['base','r1','fullnight'].map(k=>[k,{
    subject_mf1:e.historical_ci.runs[k].per_subject_mean_macro_f1,
    pooled_accuracy:e.historical_ci.runs[k].pooled_accuracy,
    recall:e.historical_test_comparison.runs[k].per_class_recall
  }])),differences:e.historical_ci.differences,pilots:e.validation_pilots,
  audit:{available:x.available_participants,nights:x.available_psg_filenames,counts:x.counts,independent_confirmed:x.independent_confirmed.length,parsed_json:e.coverage.reduce((a,c)=>a+c.parsed,0)},
  disclosures:['R1 post-hoc','R1/fullnight offline/transductive','Fullnight-vs-R1 CI includes zero','Three pilots validation only, all rejected','No independent cohort certified','Not original paper replication or clinical validation'],
  visual_policy:'EEG traces, spectra, meshes and network edges are illustrative; only charts of archived results are measured evidence.'
};
fs.writeFileSync('facts.json',JSON.stringify(facts,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({source_hashes_verified:2,base_mf1:facts.test.base.subject_mf1.point,r1_mf1:facts.test.r1.subject_mf1.point,fullnight_mf1:facts.test.fullnight.subject_mf1.point,audit:facts.audit},null,2));
