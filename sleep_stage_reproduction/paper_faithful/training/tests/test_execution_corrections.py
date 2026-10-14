import hashlib, json, tempfile, unittest, sys, types
from pathlib import Path
import numpy as np
from unittest.mock import patch
from paper_faithful.training.splits import EpochMember
from paper_faithful.training.metrics import write_metrics_artifact
from paper_faithful.training.trainer import (CacheSequence, TrainingContractError, _evaluations,
 _validate_fit_history, cap_split_plan, failure_record, keras_sequence_type, make_callbacks, make_split, prepare_run,
 route_for_stage, stage_spec, transition_run, validate_checkpoint, run_stage)

class Entry:
 def __init__(self,offset,label):self.offset,self.label=offset,label
class Cache:
 cache_hash="a"*64
 def __init__(self):self.data=np.arange(2*3*2*2*2,dtype=np.float32).reshape(2,3,2,2,2)
 def entry(self,m,route):return Entry(m.epoch_index,m.epoch_index+1)
 def array(self,e):return self.data
class FakeSequence: pass
class FakeCallbacks:
 def __init__(self):self.calls=[]
 def TerminateOnNaN(self):self.calls.append(("terminate",{}));return {}
 def ReduceLROnPlateau(self,**kwargs):self.calls.append(("reduce",kwargs));return kwargs
 def ModelCheckpoint(self,*args,**kwargs):self.calls.append(("checkpoint",kwargs));return kwargs
 def EarlyStopping(self,**kwargs):self.calls.append(("early",kwargs));return kwargs
class FakeModel:
 def predict_on_batch(self,x):return np.eye(5,dtype=np.float32)[np.arange(len(x))%5]

class ExecutionCorrectionTests(unittest.TestCase):
 def members(self):return (EpochMember("S","R",0),EpochMember("S","R",1))
 def test_rank_label_shapes_and_adapter_mro(self):
  cache=Cache();flat=CacheSequence(cache,self.members(),"PAPER_PRETRAIN_V1",2);x,y=flat[0]
  self.assertEqual(len(flat),3);self.assertEqual(x.shape,(2,2,2,2));self.assertEqual(y.tolist(),[1,1])
  _,second_labels=flat[1];self.assertEqual(second_labels.tolist(),[1,2])
  seq=CacheSequence(cache,self.members(),"PAPER_STAGE3_V1",2,sequence=True);x,y=seq[0];self.assertEqual(x.shape,(2,3,2,2,2));self.assertEqual(y.tolist(),[1,2])
  TF=type("TF",(),{"keras":type("K",(),{"utils":type("U",(),{"Sequence":FakeSequence})})})
  Adapter=keras_sequence_type(TF);self.assertIs(Adapter.__mro__[1],CacheSequence);self.assertIsInstance(Adapter(cache,self.members(),"x",2),FakeSequence)
 def test_pretraining_batch_is_window_count_not_epoch_count(self):
  members=tuple(EpochMember("S","R",i) for i in range(44));cache=type("C",(),{"data":np.zeros((44,3,2,2,2),np.float32),"entry":lambda self,m,r:Entry(m.epoch_index,m.epoch_index%5),"array":lambda self,e:self.data})()
  windows=CacheSequence(cache,members,"PAPER_PRETRAIN_V1",128);x,y=windows[0]
  self.assertEqual((len(windows),x.shape,y.shape),(1,(128,2,2,2),(128,)))
 def test_routes_callback_kwargs_and_stage2_refusal(self):
  self.assertEqual(route_for_stage("AUTHOR_CODE_V1","stage3"),"AUTHOR_CODE_V1")
  self.assertEqual(route_for_stage("PAPER_TEXT_V1","stage3"),"PAPER_STAGE3_V1")
  with self.assertRaises(TrainingContractError):stage_spec("PAPER_TEXT_V1","stage2",microbatch=8)
  self.assertEqual(stage_spec("PAPER_TEXT_V1","stage2",microbatch=8,stage2_loss_adaptation="adapted_pairwise_objective")["adaptation_reason"],"hardware_batch_limit")
  accumulated=stage_spec("PAPER_TEXT_V1","stage3",microbatch=1)
  self.assertEqual((accumulated["gradient_accumulation_steps"],accumulated["effective_batch"],accumulated["drop_remainder"]),(128,128,True))
  self.assertEqual(accumulated["adaptation_reason"],"gradient_accumulation_for_hardware_batch_limit")
  with self.assertRaises(TrainingContractError):stage_spec("PAPER_TEXT_V1","stage3",microbatch=3)
  callbacks=FakeCallbacks();TF=type("TF",(),{"keras":type("K",(),{"callbacks":callbacks})});make_callbacks(TF,stage_spec("AUTHOR_CODE_V1","stage3"),"x")
  self.assertEqual(callbacks.calls[0][0],"terminate");self.assertNotIn("name",callbacks.calls[1][1]);self.assertEqual(callbacks.calls[1][1]["factor"],.5)
 def test_fit_history_is_complete_and_finite(self):
  spec=stage_spec("PAPER_TEXT_V1","stage3")
  history=type("H",(),{"history":{"loss":[1.]*20,"val_loss":[1.]*20,"accuracy":[.5]*20}})()
  self.assertEqual(_validate_fit_history(history,spec,0)["loss"],history.history["loss"])
  history.history["val_loss"][7]=float("nan")
  with self.assertRaisesRegex(TrainingContractError,"non-finite"): _validate_fit_history(history,spec,0)
  history.history["val_loss"]=[1.]*19
  with self.assertRaisesRegex(TrainingContractError,"complete every requested epoch"): _validate_fit_history(history,spec,0)
 def test_integrated_metrics_and_zero_distance(self):
  seq=type("S",(),{"__len__":lambda self:1,"__getitem__":lambda self,i:(np.zeros((4,2)),np.array([0,0,1,1]))})()
  self.assertIn("classification",_evaluations(FakeModel(),seq,"stage1"))
  values=type("M",(),{"predict_on_batch":lambda self,x:np.zeros((4,2))})()
  result=_evaluations(values,seq,"stage2",silhouette_cap=4);self.assertEqual(result["silhouette"]["silhouette"],0.0);self.assertEqual(result["scope"]["evaluated_sample_count"],4)
  big=type("S",(),{"__len__":lambda self:5,"__getitem__":lambda self,i:(np.zeros((1000,2)),np.arange(1000)%5)})()
  full=_evaluations(FakeModel(),big,"stage1");self.assertEqual(full["classification"]["per_class"]["W"]["support"],1000);self.assertEqual(full["scope"]["evaluation_mode"],"complete_split")
  big_values=type("M",(),{"predict_on_batch":lambda self,x:np.zeros((len(x),2))})();sampled=_evaluations(big_values,big,"stage2",silhouette_cap=4);self.assertEqual((sampled["scope"]["split_sample_count"],sampled["scope"]["evaluated_sample_count"]),(5000,4))
 def test_latest_completed_stale_and_resume_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x"
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",{"a":1});running=transition_run(directory,record,"running")
    with self.assertRaises(TrainingContractError):transition_run(directory,running,"completed")
    root.joinpath("execution.json").write_text(json.dumps({"status":"failed","immutable_config_hash":running["immutable_config_hash"]}))
    with self.assertRaises(TrainingContractError):prepare_run("x",{"a":1},resume=True)
    root.joinpath("execution.json").write_text(json.dumps({"status":"failed","immutable_config_hash":running["immutable_config_hash"],"stage_progress":{"next_stage":"stage2","last_epoch":4,"checkpoint":None,"inflight":True}}))
    with self.assertRaises(TrainingContractError):prepare_run("x",{"a":1},resume=True)
 def test_pilot_split_hashes_and_stage_artifacts_are_bound_immutably(self):
  cache=type("C",(),{"members":tuple(EpochMember("S%d"%index,"R%d"%index,0) for index in range(50))})()
  capped=cap_split_plan(make_split(cache,"PAPER_TEXT_V1"),3)
  for name in ("train","validation","test"):
   actual=hashlib.sha256(("\n".join(sorted(item.key for item in getattr(capped,name)))+"\n").encode()).hexdigest()
   self.assertEqual(capped.membership_hashes[name],actual)
  config={"protocol_id":"PAPER_TEXT_V1","cache_hash":"a"*64,"split_hashes":capped.membership_hashes}
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x"
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",config);record=transition_run(directory,record,"running")
    checkpoint=root/"stage1.weights.h5";checkpoint.write_bytes(b"checkpoint")
    checkpoint_hash=hashlib.sha256(b"checkpoint").hexdigest();metrics_path=root/"stage1.metrics.json"
    metrics=write_metrics_artifact(metrics_path,{"validation":{}},{"protocol_id":"PAPER_TEXT_V1","stage":"stage1","route":"PAPER_PRETRAIN_V1","cache_hash":"a"*64,"checkpoint_sha256":checkpoint_hash,"split_membership_hashes":capped.membership_hashes})
    artifact={"checkpoint_path":str(checkpoint),"checkpoint_hash":checkpoint_hash,"parent_checkpoint_path":None,"parent_checkpoint_hash":None,"route":"PAPER_PRETRAIN_V1","metrics_path":str(metrics_path),"metrics_file_sha256":hashlib.sha256(metrics_path.read_bytes()).hexdigest(),"metrics_artifact_sha256":metrics["artifact_sha256"]}
    parent={"checkpoint_path":str(checkpoint),"checkpoint_hash":checkpoint_hash,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage1","route":"PAPER_PRETRAIN_V1"}
    record=transition_run(directory,record,"running",stage_artifacts={"stage1":artifact},stage_progress={"next_stage":"stage2","last_epoch":0,"checkpoint":parent,"inflight":False})
    changed=dict(artifact);changed["checkpoint_hash"]="0"*64
    with self.assertRaises(TrainingContractError):transition_run(directory,record,"running",stage_artifacts={"stage1":changed})
    failed=transition_run(directory,record,"failed",failure=failure_record(RuntimeError("expected")))
    self.assertEqual(prepare_run("x",config,resume=True)[1]["status"],"failed")
    alternate=root/"alternate.weights.h5";alternate.write_bytes(b"alternate");alternate_hash=hashlib.sha256(b"alternate").hexdigest()
    execution=json.loads((root/"execution.json").read_text());execution["stage_progress"]["checkpoint"]={"checkpoint_path":str(alternate),"checkpoint_hash":alternate_hash,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage1","route":"PAPER_PRETRAIN_V1"};(root/"execution.json").write_text(json.dumps(execution))
    with self.assertRaises(TrainingContractError):prepare_run("x",config,resume=True)
    execution["stage_progress"]["checkpoint"]=parent;(root/"execution.json").write_text(json.dumps(execution))
    metric_payload=json.loads(metrics_path.read_text());metric_payload["metrics"]["validation"]["forged_accuracy"]=1.0;metrics_path.write_text(json.dumps(metric_payload))
    execution=json.loads((root/"execution.json").read_text());execution["stage_artifacts"]["stage1"]["metrics_file_sha256"]=hashlib.sha256(metrics_path.read_bytes()).hexdigest();(root/"execution.json").write_text(json.dumps(execution))
    with self.assertRaises(TrainingContractError):prepare_run("x",config,resume=True)
 def test_persisted_external_parent_config_cannot_be_rewritten_on_resume(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x";checkpoint=Path(d)/"stage1.weights.h5";checkpoint.write_bytes(b"stage1");checkpoint_hash=hashlib.sha256(b"stage1").hexdigest()
   external={"checkpoint_path":str(checkpoint),"checkpoint_hash":checkpoint_hash,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage1","route":"PAPER_PRETRAIN_V1","metadata_path":"external.json","metadata_hash":"m"*64}
   config={"protocol_id":"PAPER_TEXT_V1","cache_hash":"a"*64,"split_hashes":{"train":"t"*64,"validation":"v"*64,"test":"e"*64},"stage":"stage2","external_parent":external}
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",config);record=transition_run(directory,record,"running",stage_progress={"next_stage":"stage2","last_epoch":0,"checkpoint":external,"inflight":False});transition_run(directory,record,"failed",failure=failure_record(RuntimeError("expected")))
    alternate=Path(d)/"alternate.weights.h5";alternate.write_bytes(b"alternate");alternate_parent=dict(external,checkpoint_path=str(alternate),checkpoint_hash=hashlib.sha256(b"alternate").hexdigest())
    execution=json.loads((root/"execution.json").read_text());execution["config"]["external_parent"]=alternate_parent;execution["stage_progress"]["checkpoint"]=alternate_parent;(root/"execution.json").write_text(json.dumps(execution))
    with self.assertRaises(TrainingContractError):prepare_run("x",config,resume=True)
 def test_all_stage_transitions_persist_terminal_stage3(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x";config={"protocol_id":"PAPER_TEXT_V1","cache_hash":"a"*64,"split_hashes":{"train":"t"*64,"validation":"v"*64,"test":"e"*64},"stage":"all","external_parent":None}
   def artifact(stage,parent_input=None):
    route="PAPER_STAGE3_V1" if stage=="stage3" else "PAPER_PRETRAIN_V1";checkpoint=root/(stage+".weights.h5");checkpoint.write_bytes(stage.encode());digest=hashlib.sha256(stage.encode()).hexdigest();metric_path=root/(stage+".metrics.json");metric=write_metrics_artifact(metric_path,{},{"protocol_id":"PAPER_TEXT_V1","stage":stage,"route":route,"cache_hash":"a"*64,"checkpoint_sha256":digest,"split_membership_hashes":config["split_hashes"]});return {"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"parent_checkpoint_path":None if parent_input is None else parent_input["checkpoint_path"],"parent_checkpoint_hash":None if parent_input is None else parent_input["checkpoint_hash"],"route":route,"metrics_path":str(metric_path),"metrics_file_sha256":hashlib.sha256(metric_path.read_bytes()).hexdigest(),"metrics_artifact_sha256":metric["artifact_sha256"]},{"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":stage,"route":route}
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",config);record=transition_run(directory,record,"running")
    artifacts={};previous=None
    for stage,next_stage in (("stage1","stage2"),("stage2","stage3"),("stage3",None)):
     stage_artifact,parent=artifact(stage,previous);artifacts[stage]=stage_artifact;record=transition_run(directory,record,"running",stage_artifacts=dict(artifacts),stage_progress={"next_stage":next_stage,"last_epoch":0,"checkpoint":parent,"inflight":False});previous=parent
    self.assertEqual(transition_run(directory,record,"completed")["status"],"completed")
 def test_standalone_stage2_can_complete_only_at_its_terminal_state(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x";stage1=Path(d)/"stage1.weights.h5";stage1.write_bytes(b"stage1");stage1_hash=hashlib.sha256(b"stage1").hexdigest();external={"checkpoint_path":str(stage1),"checkpoint_hash":stage1_hash,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage1","route":"PAPER_PRETRAIN_V1","metadata_path":"external.json","metadata_hash":"m"*64};config={"protocol_id":"PAPER_TEXT_V1","cache_hash":"a"*64,"split_hashes":{"train":"t"*64,"validation":"v"*64,"test":"e"*64},"stage":"stage2","external_parent":external}
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",config);record=transition_run(directory,record,"running",stage_progress={"next_stage":"stage2","last_epoch":0,"checkpoint":external,"inflight":False});checkpoint=root/"stage2.weights.h5";checkpoint.write_bytes(b"stage2");digest=hashlib.sha256(b"stage2").hexdigest();metric_path=root/"stage2.metrics.json";metric=write_metrics_artifact(metric_path,{},{"protocol_id":"PAPER_TEXT_V1","stage":"stage2","route":"PAPER_PRETRAIN_V1","cache_hash":"a"*64,"checkpoint_sha256":digest,"split_membership_hashes":config["split_hashes"]});artifact={"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"parent_checkpoint_path":external["checkpoint_path"],"parent_checkpoint_hash":external["checkpoint_hash"],"route":"PAPER_PRETRAIN_V1","metrics_path":str(metric_path),"metrics_file_sha256":hashlib.sha256(metric_path.read_bytes()).hexdigest(),"metrics_artifact_sha256":metric["artifact_sha256"]};parent={"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage2","route":"PAPER_PRETRAIN_V1"};record=transition_run(directory,record,"running",stage_artifacts={"stage2":artifact},stage_progress={"next_stage":None,"last_epoch":0,"checkpoint":parent,"inflight":False});self.assertEqual(transition_run(directory,record,"completed")["status"],"completed")
 def test_all_stage_refuses_stage2_artifact_with_unrelated_stage1_parent(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x";config={"protocol_id":"PAPER_TEXT_V1","cache_hash":"a"*64,"split_hashes":{"train":"t"*64,"validation":"v"*64,"test":"e"*64},"stage":"all","external_parent":None}
   def stage_artifact(stage,contents,parent_input=None):
    route="PAPER_PRETRAIN_V1";checkpoint=root/(stage+".weights.h5");checkpoint.write_bytes(contents);digest=hashlib.sha256(contents).hexdigest();metric_path=root/(stage+".metrics.json");metric=write_metrics_artifact(metric_path,{},{"protocol_id":"PAPER_TEXT_V1","stage":stage,"route":route,"cache_hash":"a"*64,"checkpoint_sha256":digest,"split_membership_hashes":config["split_hashes"]});artifact={"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"parent_checkpoint_path":None if parent_input is None else parent_input["checkpoint_path"],"parent_checkpoint_hash":None if parent_input is None else parent_input["checkpoint_hash"],"route":route,"metrics_path":str(metric_path),"metrics_file_sha256":hashlib.sha256(metric_path.read_bytes()).hexdigest(),"metrics_artifact_sha256":metric["artifact_sha256"]};return artifact,{"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":stage,"route":route}
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",config);record=transition_run(directory,record,"running");stage1,parent1=stage_artifact("stage1",b"stage1");record=transition_run(directory,record,"running",stage_artifacts={"stage1":stage1},stage_progress={"next_stage":"stage2","last_epoch":0,"checkpoint":parent1,"inflight":False});unrelated=Path(d)/"unrelated.weights.h5";unrelated.write_bytes(b"unrelated");unrelated_parent={"checkpoint_path":str(unrelated),"checkpoint_hash":hashlib.sha256(b"unrelated").hexdigest()};stage2,parent2=stage_artifact("stage2",b"stage2",unrelated_parent)
    with self.assertRaises(TrainingContractError):transition_run(directory,record,"running",stage_artifacts={"stage1":stage1,"stage2":stage2},stage_progress={"next_stage":"stage3","last_epoch":0,"checkpoint":parent2,"inflight":False})
 def test_all_stage_terminal_refuses_stage3_without_earlier_artifacts(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/"x";config={"protocol_id":"PAPER_TEXT_V1","cache_hash":"a"*64,"split_hashes":{"train":"t"*64,"validation":"v"*64,"test":"e"*64},"stage":"all","external_parent":None}
   with patch("paper_faithful.training.trainer.run_directory",return_value=root):
    directory,record=prepare_run("x",config);record=transition_run(directory,record,"running");checkpoint=root/"stage3.weights.h5";checkpoint.write_bytes(b"stage3");digest=hashlib.sha256(b"stage3").hexdigest();metric_path=root/"stage3.metrics.json";metric=write_metrics_artifact(metric_path,{},{"protocol_id":"PAPER_TEXT_V1","stage":"stage3","route":"PAPER_STAGE3_V1","cache_hash":"a"*64,"checkpoint_sha256":digest,"split_membership_hashes":config["split_hashes"]});artifact={"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"parent_checkpoint_path":None,"parent_checkpoint_hash":None,"route":"PAPER_STAGE3_V1","metrics_path":str(metric_path),"metrics_file_sha256":hashlib.sha256(metric_path.read_bytes()).hexdigest(),"metrics_artifact_sha256":metric["artifact_sha256"]};parent={"checkpoint_path":str(checkpoint),"checkpoint_hash":digest,"cache_hash":"a"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage3","route":"PAPER_STAGE3_V1"}
    with self.assertRaises(TrainingContractError):transition_run(directory,record,"running",stage_artifacts={"stage3":artifact},stage_progress={"next_stage":None,"last_epoch":0,"checkpoint":parent,"inflight":False})
 def test_checkpoint_lineage_and_failure_fingerprint(self):
  with tempfile.TemporaryDirectory() as d:
   checkpoint=Path(d)/"c";checkpoint.write_bytes(b"c")
   import hashlib
   digest=hashlib.sha256(b"c").hexdigest();parent={"checkpoint_hash":digest,"cache_hash":"a"*64,"protocol_id":"AUTHOR_CODE_V1","route":"AUTHOR_CODE_V1"}
   validate_checkpoint(checkpoint,digest,parent,parent)
   with self.assertRaises(TrainingContractError):validate_checkpoint(checkpoint,digest,parent,{"route":"PAPER_STAGE3_V1"})
  self.assertEqual(failure_record(ValueError("x")),failure_record(ValueError("x")))
 def test_fit_invocation_uses_adapter_and_metrics(self):
  class Callback:
   def __init__(self,*args,**kwargs):self.args,self.kwargs=args,kwargs
  class Model(FakeModel):
   def compile(self,**kwargs):self.compiled=kwargs
   def fit(self,train,**kwargs):
    self.fit_args=(train,kwargs)
    for callback in kwargs["callbacks"]:
     if isinstance(callback,Callback) and callback.args:
      Path(callback.args[0]).write_bytes(b"checkpoint")
    return type("H",(),{"history":{"loss":[1.]*20,"val_loss":[1.]*20}})()
   def load_weights(self,path):self.loaded=path
  model=Model();callbacks=type("Callbacks",(),{"TerminateOnNaN":Callback,"ReduceLROnPlateau":Callback,"ModelCheckpoint":Callback,"EarlyStopping":Callback})
  tf=type("TF",(),{"keras":type("K",(),{"utils":type("U",(),{"Sequence":FakeSequence}),"callbacks":callbacks,"optimizers":type("O",(),{"SGD":lambda *a,**k:"sgd"})})})
  module=types.ModuleType("paper_faithful.training.models");module.build_stage1_cnn=lambda *a,**k:type("S",(),{"load_weights":lambda self,p:None})();module.build_stage2_supervised_contrastive=lambda *a,**k:model;module.build_stage3_cnn_gru=lambda *a,**k:model;module.supervised_contrastive_loss=lambda *a:0
  members=tuple(EpochMember("S","R",i) for i in range(50));cache=type("C",(),{"cache_hash":"a"*64,"data":np.zeros((50,3,2,2,2),np.float32),"entry":lambda self,m,r:Entry(m.epoch_index,m.epoch_index%5),"array":lambda self,e:self.data})()
  plan=type("P",(),{"train":members[:44],"validation":members[44:47],"test":members[47:],"membership_hashes":{"train":"a"*64,"validation":"b"*64,"test":"c"*64}})()
  with tempfile.TemporaryDirectory() as d:
   parent_path=Path(d)/"parent";parent_path.write_bytes(b"parent");import hashlib
   parent={"checkpoint_path":str(parent_path),"checkpoint_hash":hashlib.sha256(b"parent").hexdigest(),"cache_hash":"a"*64,"protocol_id":"AUTHOR_CODE_V1","stage":"stage1","route":"AUTHOR_CODE_V1"}
   with patch("paper_faithful.training.trainer._tf",return_value=tf),patch.dict(sys.modules,{"paper_faithful.training.models":module}):
    result=run_stage(cache,plan,"AUTHOR_CODE_V1","stage2",d,parent=parent)
   self.assertIsInstance(model.fit_args[0],FakeSequence);self.assertEqual(result["route"],"AUTHOR_CODE_V1");self.assertIn("silhouette",result["metrics"]["metrics"]["validation"]);self.assertEqual(result["metrics"]["provenance"]["split_membership_hashes"],plan.membership_hashes);self.assertIn("artifact_sha256",result["metrics"])
