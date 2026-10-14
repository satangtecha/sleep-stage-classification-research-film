import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from paper_faithful.training.cli import TrainingContractError, _ordered_seed_values, _run_multi_seed_child, main
from paper_faithful.training.trainer import _hash


class MultiSeedPilotTests(unittest.TestCase):
 def _args(self):
  return ["multi-seed-pilot","--cache-manifest","cache.json","--source-manifest","source.json","--environment-manifest","environment.json","--bulk-root","E:/bulk","--run-id-prefix","paper-text-v1-r9","--seeds","3","7"]
 def _cache(self):
  return SimpleNamespace(cache_hash="a"*64,phase2_manifest_path=Path("phase2.json"),phase2_manifest_hash="p"*64)
 def _record(self,config):
  return {"status":"planned","config":config,"stage_artifacts":{},"stage_progress":{"next_stage":"stage1","last_epoch":0,"checkpoint":None,"inflight":False}}
 def test_loads_once_for_two_children_and_seed_cleanup_is_ordered(self):
  cache=self._cache();children=[(Path("E:/runs/one"),self._record({})),(Path("E:/runs/two"),self._record({}))]
  events=[]
  def seeded(seed):events.append(("seed",seed));return SimpleNamespace(keras=SimpleNamespace(backend=SimpleNamespace(clear_session=lambda:None)))
  def child(_cache,_args,split_seed,model_seed):events.append(("child",split_seed,model_seed));return children.pop(0)
  def verify(directory):events.append(("verify",str(directory)));return {"status":"verified"}
  def cleaned(_tf):events.append(("cleanup",None))
  with patch("paper_faithful.training.cli.load_canonical_cache",return_value=cache) as loaded,patch("paper_faithful.training.cli.seed_model",side_effect=seeded),patch("paper_faithful.training.cli._run_multi_seed_child",side_effect=child),patch("paper_faithful.training.cli._verify_completed_child",side_effect=verify),patch("paper_faithful.training.cli.cleanup_model_state",side_effect=cleaned):
   self.assertEqual(main(self._args()),0)
  self.assertEqual(loaded.call_count,1)
  self.assertEqual(events,[("seed",3),("child",3,3),("verify",str(Path("E:/runs/one"))),("cleanup",None),("seed",7),("child",7,7),("verify",str(Path("E:/runs/two"))),("cleanup",None)])
 def test_children_bind_distinct_seed_configs_and_split_hashes(self):
  cache=self._cache();args=SimpleNamespace(cache_manifest="cache.json",source_manifest="source.json",environment_manifest="environment.json",bulk_root="E:/bulk",run_id_prefix="paper-text-v1-r9",cap=128,weight_decay=0.0);configs=[]
  def split(_cache,_protocol,seed):
   return SimpleNamespace(seed=seed,membership_hashes={name:hashlib.sha256((name+str(seed)).encode()).hexdigest() for name in ("train","validation","test")})
  def prepared(run_id,config,bulk_root):configs.append((run_id,config));return Path("E:/runs")/run_id,self._record(config)
  def transition(_directory,record,status,**updates):result=dict(record);result.update(updates);result["status"]=status;return result
  def stage(_cache,_plan,_protocol,stage,_directory,**_kwargs):
   return {"checkpoint_path":stage+".weights.h5","checkpoint_hash":stage[0]*64,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":stage,"route":"PAPER_STAGE3_V1" if stage=="stage3" else "PAPER_PRETRAIN_V1","metrics_path":stage+".metrics.json","metrics":{"artifact_sha256":"m"*64}}
  with patch("paper_faithful.training.cli.make_split",side_effect=split),patch("paper_faithful.training.cli.cap_split_plan",side_effect=lambda plan,_cap:plan),patch("paper_faithful.training.cli._file_hash",return_value=("file","f"*64)),patch("paper_faithful.training.cli.prepare_run",side_effect=prepared),patch("paper_faithful.training.cli.transition_run",side_effect=transition),patch("paper_faithful.training.cli.run_stage",side_effect=stage),patch("paper_faithful.training.cli.sha256_file",return_value="h"*64):
   _run_multi_seed_child(cache,args,3,3);_run_multi_seed_child(cache,args,7,7)
  self.assertEqual([item[0] for item in configs],["paper-text-v1-r9-split3-model3","paper-text-v1-r9-split7-model7"])
  first,second=configs[0][1],configs[1][1]
  self.assertEqual((first["split_seed"],first["model_seed"],first["seed"]),(3,3,3));self.assertEqual((second["split_seed"],second["model_seed"],second["seed"]),(7,7,7))
  self.assertNotEqual(first["split_hashes"],second["split_hashes"]);self.assertNotEqual(_hash(first),_hash(second));self.assertEqual(first["batches"],{"stage1":128,"stage2":128,"stage3":1})
 def test_r10_child_binds_post_accumulation_clip_in_config_and_stage3_call(self):
  cache=self._cache();args=SimpleNamespace(cache_manifest="cache.json",source_manifest="source.json",environment_manifest="environment.json",bulk_root="E:/bulk",run_id_prefix="paper-text-v1-r10",cap=128,weight_decay=0.0,stage3_gradient_clip_norm=1.0,stage3_stability_adaptation_id="PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1");configs=[]
  plan=SimpleNamespace(seed=42,membership_hashes={name:hashlib.sha256(name.encode()).hexdigest() for name in ("train","validation","test")})
  def prepared(_run_id,config,bulk_root):configs.append(config);return Path("E:/runs/r10"),self._record(config)
  def transition(_directory,record,status,**updates):result=dict(record);result.update(updates);result["status"]=status;return result
  def stage(_cache,_plan,_protocol,stage,_directory,**_kwargs):return {"checkpoint_path":stage+".weights.h5","checkpoint_hash":stage[0]*64,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":stage,"route":"PAPER_STAGE3_V1" if stage=="stage3" else "PAPER_PRETRAIN_V1","metrics_path":stage+".metrics.json","metrics":{"artifact_sha256":"m"*64}}
  with patch("paper_faithful.training.cli.make_split",return_value=plan),patch("paper_faithful.training.cli.cap_split_plan",return_value=plan),patch("paper_faithful.training.cli._file_hash",return_value=("file","f"*64)),patch("paper_faithful.training.cli.prepare_run",side_effect=prepared),patch("paper_faithful.training.cli.transition_run",side_effect=transition),patch("paper_faithful.training.cli.run_stage",side_effect=stage) as run,patch("paper_faithful.training.cli.sha256_file",return_value="h"*64):
   _run_multi_seed_child(cache,args,42,42)
  config=configs[0];adaptation=config["adaptations"]["stage3"]
  self.assertEqual((config["stage3_gradient_clip_norm"],config["stage3_stability_adaptation_id"]),(1.0,"PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1"))
  self.assertEqual((adaptation["strategy"],adaptation["gradient_clip_norm"],adaptation["gradient_clip_application"]),("gradient_accumulation+post_accumulation_global_norm_clipping",1.0,"after_effective_batch_average_before_optimizer_step"))
  stage3_call=[item for item in run.call_args_list if item[0][3]=="stage3"][0]
  self.assertEqual((stage3_call[1]["stage3_gradient_clip_norm"],stage3_call[1]["stage3_stability_adaptation_id"]),(1.0,"PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1"))
 def test_existing_id_refusal_halts_before_a_second_child(self):
  cache=self._cache();child=Mock(side_effect=TrainingContractError("run exists; explicit resume required"))
  with patch("paper_faithful.training.cli.load_canonical_cache",return_value=cache),patch("paper_faithful.training.cli.seed_model",return_value=object()),patch("paper_faithful.training.cli.cleanup_model_state"),patch("paper_faithful.training.cli._run_multi_seed_child",child),patch("paper_faithful.training.cli._verify_completed_child") as verify:
   self.assertEqual(main(self._args()),2)
  self.assertEqual(child.call_count,1);verify.assert_not_called()
 def test_verifier_refusal_halts_and_preserves_completed_child(self):
  cache=self._cache();record=self._record({});child=Mock(return_value=(Path("E:/runs/one"),record))
  completed=SimpleNamespace(returncode=2,stdout='{"status":"refused"}',stderr="")
  with patch("paper_faithful.training.cli.load_canonical_cache",return_value=cache),patch("paper_faithful.training.cli.seed_model",return_value=object()),patch("paper_faithful.training.cli.cleanup_model_state") as cleaned,patch("paper_faithful.training.cli._run_multi_seed_child",child),patch("paper_faithful.training.cli.subprocess.run",return_value=completed):
   self.assertEqual(main(self._args()),2)
  self.assertEqual(child.call_count,1);cleaned.assert_called_once()
 def test_cleanup_failure_halts_before_later_seed(self):
  cache=self._cache();child=Mock(return_value=(Path("E:/runs/one"),self._record({})))
  with patch("paper_faithful.training.cli.load_canonical_cache",return_value=cache),patch("paper_faithful.training.cli.seed_model",return_value=object()),patch("paper_faithful.training.cli.cleanup_model_state",side_effect=RuntimeError("cleanup failed")),patch("paper_faithful.training.cli._run_multi_seed_child",child),patch("paper_faithful.training.cli._verify_completed_child",return_value={"status":"verified"}):
   self.assertEqual(main(self._args()),2)
  self.assertEqual(child.call_count,1)
 def test_seed_list_must_be_strictly_ordered_and_unique(self):
  with self.assertRaises(TrainingContractError):_ordered_seed_values((7,3))
  with self.assertRaises(TrainingContractError):_ordered_seed_values((3,3))
  self.assertEqual(_ordered_seed_values((0,2**32-1)),(0,2**32-1))
  with self.assertRaises(TrainingContractError):_ordered_seed_values((-1,0))
  with self.assertRaises(TrainingContractError):_ordered_seed_values((0,2**32))
 def test_cap_must_be_128_before_cache_load(self):
  with patch("paper_faithful.training.cli.load_canonical_cache") as loaded:
   self.assertEqual(main(self._args()+["--cap","127"]),2)
  loaded.assert_not_called()
 def test_tensorflow_style_exception_persists_failed_child_state(self):
  class TensorflowStyleFailure(Exception):pass
  cache=self._cache();args=SimpleNamespace(cache_manifest="cache.json",source_manifest="source.json",environment_manifest="environment.json",bulk_root="E:/bulk",run_id_prefix="paper-text-v1-r10",cap=128,weight_decay=0.0,stage3_gradient_clip_norm=1.0,stage3_stability_adaptation_id="PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1")
  plan=SimpleNamespace(seed=43,membership_hashes={name:hashlib.sha256(name.encode()).hexdigest() for name in ("train","validation","test")})
  transitions=[]
  def prepared(_run_id,config,bulk_root):return Path("E:/runs/failed"),self._record(config)
  def transition(_directory,record,status,**updates):
   result=dict(record);result.update(updates);result["status"]=status;transitions.append((status,updates));return result
  with patch("paper_faithful.training.cli.make_split",return_value=plan),patch("paper_faithful.training.cli.cap_split_plan",return_value=plan),patch("paper_faithful.training.cli._file_hash",return_value=("file","f"*64)),patch("paper_faithful.training.cli.prepare_run",side_effect=prepared),patch("paper_faithful.training.cli.transition_run",side_effect=transition),patch("paper_faithful.training.cli.run_stage",side_effect=TensorflowStyleFailure("non-finite microbatch gradient")):
   with self.assertRaises(TensorflowStyleFailure):_run_multi_seed_child(cache,args,43,43)
  self.assertEqual(transitions[-1][0],"failed")
  failure=transitions[-1][1]["failure"]
  self.assertEqual((failure["type"],failure["message"]),("TensorflowStyleFailure","non-finite microbatch gradient"));self.assertEqual(len(failure["fingerprint"]),64)
 def test_unexpected_exception_halts_before_later_seed(self):
  class TensorflowStyleFailure(Exception):pass
  cache=self._cache();child=Mock(side_effect=TensorflowStyleFailure("non-finite microbatch gradient"))
  with patch("paper_faithful.training.cli.load_canonical_cache",return_value=cache),patch("paper_faithful.training.cli.seed_model",return_value=object()),patch("paper_faithful.training.cli.cleanup_model_state"),patch("paper_faithful.training.cli._run_multi_seed_child",child),patch("paper_faithful.training.cli._verify_completed_child") as verify:
   self.assertEqual(main(self._args()),2)
  self.assertEqual(child.call_count,1);verify.assert_not_called()


if __name__ == "__main__":unittest.main()
