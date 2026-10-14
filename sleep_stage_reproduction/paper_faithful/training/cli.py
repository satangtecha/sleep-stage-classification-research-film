"""Bounded training CLI; every non-smoke run has hash-bound provenance."""
from __future__ import print_function
import argparse,json,subprocess,sys
from pathlib import Path
from .cache_loader import load_canonical_cache,CacheValidationError
from .run_manifest import sha256_file
from .trainer import STAGE3_STABILITY_ADAPTATION_ID,TrainingContractError,cap_split_plan,cleanup_model_state,make_split,prepare_run,run_stage,seed_model,stage_spec,transition_run,failure_record,STAGES
_LINEAGE_KEYS=("checkpoint_path","checkpoint_hash","cache_hash","protocol_id","stage","route")
def _file_hash(path,label):
 p=Path(path)
 if not p.is_file():raise TrainingContractError(label+" must name a readable file")
 return str(p.resolve()),sha256_file(p)
def _external_parent(path,metadata,cache_hash,protocol):
 _,actual=_file_hash(path,"external checkpoint");mp,md=_file_hash(metadata,"external parent metadata")
 try:record=json.loads(Path(mp).read_text())
 except ValueError as e:raise TrainingContractError("external parent metadata is invalid JSON") from e
 required={"checkpoint_path","checkpoint_hash","cache_hash","protocol_id","stage","route"}
 if not required.issubset(record) or record["checkpoint_hash"]!=actual or record["cache_hash"]!=cache_hash or record["protocol_id"]!=protocol:raise TrainingContractError("external parent metadata does not bind checkpoint/cache/protocol")
 record["metadata_path"],record["metadata_hash"]=mp,md;return record
def _lineage_checkpoint(stage_result):
 if not isinstance(stage_result,dict) or any(not isinstance(stage_result.get(key),str) for key in _LINEAGE_KEYS):raise TrainingContractError("stage result has no serializable checkpoint lineage")
 return {key:stage_result[key] for key in _LINEAGE_KEYS}
def _ordered_seed_values(values):
 if len(values)<2 or any(not isinstance(value,int) or not 0<=value<2**32 for value in values) or tuple(values)!=tuple(sorted(set(values))):raise TrainingContractError("--seeds must contain two or more strictly increasing unique unsigned 32-bit integers")
 return tuple(values)
def _stage_spec_for_args(protocol,stage,batch,a):
 return stage_spec(protocol,stage,microbatch=batch,stage2_loss_adaptation=getattr(a,"stage2_loss_adaptation",None) if stage=="stage2" else None,weight_decay=a.weight_decay if stage=="stage1" else None,stage3_gradient_clip_norm=getattr(a,"stage3_gradient_clip_norm",None) if stage=="stage3" else None,stage3_stability_adaptation_id=getattr(a,"stage3_stability_adaptation_id",None) if stage=="stage3" else None)
def _adaptation_record(spec,batch):
 strategies=[]
 if spec["gradient_accumulation_steps"]>1:strategies.append("gradient_accumulation")
 if spec["stage2_loss_adaptation"]:strategies.append(spec["stage2_loss_adaptation"])
 if spec["gradient_clip_norm"] is not None:strategies.append("post_accumulation_global_norm_clipping")
 return {"batch":batch,"nominal_batch":spec["nominal_batch"],"effective_batch":spec["effective_batch"],"gradient_accumulation_steps":spec["gradient_accumulation_steps"],"strategy":"+".join(strategies) if strategies else None,"gradient_clip_norm":spec["gradient_clip_norm"],"gradient_clip_application":spec["gradient_clip_application"],"stability_adaptation_id":spec["stage3_stability_adaptation_id"],"recorded":bool(strategies)}
def _verify_completed_child(directory):
 completed=subprocess.run([sys.executable,"-m","paper_faithful.training.verify_run","--run-dir",str(directory)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
 try:result=json.loads(completed.stdout)
 except (TypeError,ValueError) as error:raise TrainingContractError("child verifier returned invalid JSON") from error
 if completed.returncode!=0 or not isinstance(result,dict) or result.get("status")!="verified":raise TrainingContractError("child verifier refused completed run")
 return result
def _run_multi_seed_child(cache,a,split_seed,model_seed):
 directory=record=None
 try:
  plan=cap_split_plan(make_split(cache,"PAPER_TEXT_V1",seed=split_seed),a.cap);batches={"stage1":128,"stage2":128,"stage3":1}
  specs={stage:_stage_spec_for_args("PAPER_TEXT_V1",stage,batches[stage],a) for stage in STAGES}
  adaptations={stage:_adaptation_record(specs[stage],batches[stage]) for stage in STAGES}
  source_path,source_hash=_file_hash(a.source_manifest,"source manifest");environment_path,environment_hash=_file_hash(a.environment_manifest,"environment manifest");cache_path,cache_manifest_hash=_file_hash(str(getattr(cache,"manifest_path",a.cache_manifest)),"cache manifest");phase2_path,phase2_hash=str(cache.phase2_manifest_path),cache.phase2_manifest_hash
  config={"protocol_id":"PAPER_TEXT_V1","source_manifest":source_path,"source_manifest_hash":source_hash,"environment_manifest":environment_path,"environment_manifest_hash":environment_hash,"data_manifest":phase2_path,"data_manifest_hash":phase2_hash,"cache_manifest":cache_path,"cache_manifest_hash":cache_manifest_hash,"cache_hash":cache.cache_hash,"phase2_manifest":phase2_path,"split_hashes":plan.membership_hashes,"seed":split_seed,"split_seed":split_seed,"model_seed":model_seed,"mode":"pilot","per_split_epoch_cap":a.cap,"stage":"all","external_parent":None,"weight_decay":a.weight_decay,"batches":batches,"stage2_loss_adaptation":None,"stage3_gradient_clip_norm":getattr(a,"stage3_gradient_clip_norm",None),"stage3_stability_adaptation_id":getattr(a,"stage3_stability_adaptation_id",None),"protocol_assumptions":{"stage1_weight_decay":a.weight_decay},"adaptations":adaptations}
  run_id="{0}-split{1}-model{2}".format(a.run_id_prefix,split_seed,model_seed);directory,record=prepare_run(run_id,config,bulk_root=a.bulk_root)
  record=transition_run(directory,record,"running",stage_progress={"next_stage":"stage1","last_epoch":0,"checkpoint":None,"inflight":False});parent=None
  for stage in STAGES:
   record=transition_run(directory,record,"running",stage_progress={"next_stage":stage,"last_epoch":0,"checkpoint":parent,"inflight":True});parent_input=parent;stage_result=run_stage(cache,plan,"PAPER_TEXT_V1",stage,directory,parent=parent_input,weight_decay=a.weight_decay,microbatch=batches[stage],stage3_gradient_clip_norm=getattr(a,"stage3_gradient_clip_norm",None) if stage=="stage3" else None,stage3_stability_adaptation_id=getattr(a,"stage3_stability_adaptation_id",None) if stage=="stage3" else None)
   artifacts=dict(record.get("stage_artifacts",{}));artifacts[stage]={"checkpoint_path":stage_result["checkpoint_path"],"checkpoint_hash":stage_result["checkpoint_hash"],"parent_checkpoint_path":None if stage=="stage1" else parent_input["checkpoint_path"],"parent_checkpoint_hash":None if stage=="stage1" else parent_input["checkpoint_hash"],"route":stage_result["route"],"metrics_path":stage_result["metrics_path"],"metrics_file_sha256":sha256_file(stage_result["metrics_path"]),"metrics_artifact_sha256":stage_result["metrics"]["artifact_sha256"]};parent=_lineage_checkpoint(stage_result);next_stage=STAGES[STAGES.index(stage)+1] if stage!="stage3" else None;record=transition_run(directory,record,"running",last_epoch=0,checkpoint_hash=parent["checkpoint_hash"],checkpoint_path=parent["checkpoint_path"],stage_artifacts=artifacts,stage_progress={"next_stage":next_stage,"last_epoch":0,"checkpoint":parent,"inflight":False})
  record=transition_run(directory,record,"completed");return directory,record
 except Exception as error:
  if directory is not None and record is not None:
   try:transition_run(directory,record,"failed",failure=failure_record(error))
   except (TrainingContractError,OSError):pass
  raise
def _run_multi_seed_pilot(cache,a):
 results=[]
 for seed in _ordered_seed_values(a.seeds):
  tf=None
  try:
   tf=seed_model(seed);directory,record=_run_multi_seed_child(cache,a,seed,seed);verification=_verify_completed_child(directory);results.append({"run_id":"{0}-split{1}-model{1}".format(a.run_id_prefix,seed),"directory":str(directory),"verification":verification})
  finally:
   if tf is not None:cleanup_model_state(tf)
 return {"status":"completed","mode":"multi-seed-pilot","children":results}
def main(argv=None):
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest="command",required=True)
 smoke=sub.add_parser("smoke");smoke.add_argument("--protocol",choices=("PAPER_TEXT_V1","AUTHOR_CODE_V1"),default="AUTHOR_CODE_V1")
 for name in ("pilot","full"):
  q=sub.add_parser(name);q.add_argument("--cache-manifest",required=True);q.add_argument("--protocol",choices=("PAPER_TEXT_V1","AUTHOR_CODE_V1"),default="PAPER_TEXT_V1");q.add_argument("--stage",choices=("stage1","stage2","stage3","all"),default="all");q.add_argument("--run-id",required=True);q.add_argument("--bulk-root",required=True);q.add_argument("--resume",action="store_true");q.add_argument("--checkpoint");q.add_argument("--parent-metadata");q.add_argument("--source-manifest",required=True);q.add_argument("--environment-manifest",required=True);q.add_argument("--cap",type=int,default=128);q.add_argument("--weight-decay",type=float,default=0.0);q.add_argument("--stage1-batch",type=int,default=128);q.add_argument("--stage2-batch",type=int,default=128);q.add_argument("--stage3-batch",type=int,default=128);q.add_argument("--stage2-loss-adaptation",choices=("adapted_pairwise_objective",));q.add_argument("--stage3-gradient-clip-norm",type=float);q.add_argument("--stage3-stability-adaptation-id",choices=(STAGE3_STABILITY_ADAPTATION_ID,))
 multi=sub.add_parser("multi-seed-pilot");multi.add_argument("--cache-manifest",required=True);multi.add_argument("--source-manifest",required=True);multi.add_argument("--environment-manifest",required=True);multi.add_argument("--bulk-root",required=True);multi.add_argument("--run-id-prefix",required=True);multi.add_argument("--seeds",nargs="+",type=int,required=True);multi.add_argument("--cap",type=int,default=128);multi.add_argument("--weight-decay",type=float,default=0.0);multi.add_argument("--stage3-gradient-clip-norm",type=float);multi.add_argument("--stage3-stability-adaptation-id",choices=(STAGE3_STABILITY_ADAPTATION_ID,))
 a=p.parse_args(argv);directory=record=None
 try:
  if a.command=="smoke":
   from .smoke import run
   out=run(a.protocol);out["mode"]="smoke"
   if out["status"]!="pass":raise TrainingContractError("synthetic gradient/model smoke failed")
  else:
   if a.command=="multi-seed-pilot" and a.cap!=128:raise TrainingContractError("multi-seed-pilot requires cap 128")
   cache=load_canonical_cache(a.cache_manifest)
   if a.command=="multi-seed-pilot":
    out=_run_multi_seed_pilot(cache,a);print(json.dumps(out,sort_keys=True));return 0
   if a.command=="full" and a.cap!=128:raise TrainingContractError("full accepts no cap")
   if bool(a.checkpoint)!=bool(a.parent_metadata):raise TrainingContractError("--checkpoint and --parent-metadata must be supplied together")
   if a.checkpoint and a.stage not in ("stage2","stage3"):raise TrainingContractError("external checkpoint is only valid for a standalone Stage 2 or Stage 3 run")
   if a.stage in ("stage2","stage3") and not a.checkpoint:raise TrainingContractError("standalone Stage 2/3 requires --checkpoint and --parent-metadata")
   external_parent=_external_parent(a.checkpoint,a.parent_metadata,cache.cache_hash,a.protocol) if a.checkpoint else None
   source_path,source_hash=_file_hash(a.source_manifest,"source manifest");environment_path,environment_hash=_file_hash(a.environment_manifest,"environment manifest");cache_path,cache_manifest_hash=_file_hash(str(getattr(cache,"manifest_path",a.cache_manifest)),"cache manifest");phase2_path,phase2_hash=str(cache.phase2_manifest_path),cache.phase2_manifest_hash
   plan=make_split(cache,a.protocol)
   if a.command=="pilot":plan=cap_split_plan(plan,a.cap)
   batches={"stage1":a.stage1_batch,"stage2":a.stage2_batch,"stage3":a.stage3_batch}
   specs={stage:_stage_spec_for_args(a.protocol,stage,batches[stage],a) for stage in STAGES}
   adaptations={stage:_adaptation_record(specs[stage],batches[stage]) for stage in STAGES}
   config={"protocol_id":a.protocol,"source_manifest":source_path,"source_manifest_hash":source_hash,"environment_manifest":environment_path,"environment_manifest_hash":environment_hash,"data_manifest":phase2_path,"data_manifest_hash":phase2_hash,"cache_manifest":cache_path,"cache_manifest_hash":cache_manifest_hash,"cache_hash":cache.cache_hash,"phase2_manifest":phase2_path,"split_hashes":plan.membership_hashes,"seed":plan.seed,"mode":a.command,"per_split_epoch_cap":a.cap if a.command=="pilot" else None,"stage":a.stage,"external_parent":external_parent,"weight_decay":a.weight_decay,"batches":batches,"stage2_loss_adaptation":a.stage2_loss_adaptation,"stage3_gradient_clip_norm":a.stage3_gradient_clip_norm,"stage3_stability_adaptation_id":a.stage3_stability_adaptation_id,"protocol_assumptions":{"stage1_weight_decay":a.weight_decay},"adaptations":adaptations}
   stages=STAGES if a.stage=="all" else (a.stage,);directory,record=prepare_run(a.run_id,config,bulk_root=a.bulk_root,resume=a.resume)
   initial={"next_stage":stages[0],"last_epoch":0,"checkpoint":external_parent,"inflight":False};record=transition_run(directory,record,"running",**({} if a.resume else {"stage_progress":initial}))
   progress=record["stage_progress"]
   if progress["next_stage"] not in stages:raise TrainingContractError("recorded resume stage is outside requested stage scope")
   start=stages.index(progress["next_stage"]);parent=progress.get("checkpoint")
   if start and not parent:raise TrainingContractError("recorded resume has no checkpoint lineage")
   for offset,stage in enumerate(stages[start:]):
    initial=progress["last_epoch"] if offset==0 else 0;record=transition_run(directory,record,"running",stage_progress={"next_stage":stage,"last_epoch":initial,"checkpoint":parent,"inflight":True})
    parent_input=parent;stage_result=run_stage(cache,plan,a.protocol,stage,directory,parent=parent_input,weight_decay=a.weight_decay,microbatch=batches[stage],stage2_loss_adaptation=a.stage2_loss_adaptation if stage=="stage2" else None,initial_epoch=initial,stage3_gradient_clip_norm=a.stage3_gradient_clip_norm if stage=="stage3" else None,stage3_stability_adaptation_id=a.stage3_stability_adaptation_id if stage=="stage3" else None)
    next_stage=STAGES[STAGES.index(stage)+1] if stage!=stages[-1] else None;artifacts=dict(record.get("stage_artifacts",{}));artifacts[stage]={"checkpoint_path":stage_result["checkpoint_path"],"checkpoint_hash":stage_result["checkpoint_hash"],"parent_checkpoint_path":None if stage=="stage1" else parent_input["checkpoint_path"],"parent_checkpoint_hash":None if stage=="stage1" else parent_input["checkpoint_hash"],"route":stage_result["route"],"metrics_path":stage_result["metrics_path"],"metrics_file_sha256":sha256_file(stage_result["metrics_path"]),"metrics_artifact_sha256":stage_result["metrics"]["artifact_sha256"]};parent=_lineage_checkpoint(stage_result);record=transition_run(directory,record,"running",last_epoch=0,checkpoint_hash=parent["checkpoint_hash"],checkpoint_path=parent["checkpoint_path"],stage_artifacts=artifacts,stage_progress={"next_stage":next_stage,"last_epoch":0,"checkpoint":parent,"inflight":False})
   record=transition_run(directory,record,"completed");out={"status":"completed","mode":a.command,"run":record,"checkpoint":parent}
  print(json.dumps(out,sort_keys=True));return 0
 except Exception as e:
  if directory is not None and record is not None:
   try:transition_run(directory,record,"failed",failure=failure_record(e))
   except (TrainingContractError,OSError):pass
  print(json.dumps({"status":"refused","reason":str(e)},sort_keys=True));return 2
if __name__=="__main__":raise SystemExit(main())
