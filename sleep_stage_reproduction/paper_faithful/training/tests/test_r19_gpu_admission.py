import json, os, tempfile, types, unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from paper_faithful.training.run_manifest import sha256_file
from paper_faithful.training.trainer import R17_GPU_ADMISSION_DESIGN_ID, R17_GPU_ADMISSION_RUN_PREFIX, R19_GPU_ADMISSION_RUN_PREFIX, TrainingContractError, _r17_gpu_admission, _r19_binding_capability_sha, _r19_supervisor_binding


class FakeTensor:
 def numpy(self): return 0.0
class FakeTF:
 def __init__(self,events): self.events=events;self.config=types.SimpleNamespace(list_physical_devices=lambda kind:[object()])
 @contextmanager
 def device(self,name): self.events.append("context");yield
 def constant(self,value): self.events.append("scalar");return FakeTensor()


class GPUAdmissionTests(unittest.TestCase):
 def setUp(self): self.env={"PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT":"","PAPER_FAITHFUL_R17_RUN_PREFIX":"","PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS":"5"}
 def _environment(self,root):
  values=dict(self.env);values["PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT"]=str(root);values["PAPER_FAITHFUL_R17_RUN_PREFIX"]="r19";return patch.dict(os.environ,values,clear=False)
 def _response(self,request_path,status="approved"):
  request=json.loads(request_path.read_text());value={"schema_version":1,"design_id":R17_GPU_ADMISSION_DESIGN_ID,"status":status,"run_id_prefix":request["run_id_prefix"],"run_id":request["run_id"],"stage":request["stage"],"nonce":request["nonce"],"request_sha256":sha256_file(request_path),"absolute_third_party_exclusivity_claimed":False}
  if status=="approved":value.update({"baseline_pids":[2140],"current_pids":[4,2140],"expected_wsl_system_pid":4,"observability_limit":"bounded WDDM observation","approved_at":"2026-09-02T00:00:00+07:00"})
  else:value.update({"reason":"injected peer process","refused_at":"2026-09-02T00:00:00+07:00"})
  return value
 def _attempt_fit(self,tf,run_dir,model):
  _r17_gpu_admission(tf,run_dir,"stage1");return model.fit()
 def test_no_environment_is_exact_noop_for_non_r19_identity(self):
  with patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT":"","PAPER_FAITHFUL_R17_RUN_PREFIX":""},clear=False),patch("paper_faithful.training.trainer.os.environ.get",side_effect=lambda key,default=None:None):
   _r17_gpu_admission(None,"r19-split42-model42","stage1")
 def test_exact_r19_identity_without_environment_prevents_fit(self):
  model=Mock()
  run_dir=Path("E:/runs")/"paper-text-v1-multiseed-cap128-r19-20260905-split42-model42"
  with patch("paper_faithful.training.trainer.os.environ.get",side_effect=lambda key,default=None:None):
   with self.assertRaisesRegex(TrainingContractError,"exact r19 run identity requires"):
    self._attempt_fit(None,run_dir,model)
  model.fit.assert_not_called()
 def test_context_request_approval_precedes_fit(self):
  events=[];published=[]
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory);tf=FakeTF(events);original=__import__("paper_faithful.training.trainer",fromlist=["_r17_publish_request"])._r17_publish_request
   model=types.SimpleNamespace(fit=lambda:events.append("fit"))
   def publish(path,value):
    original(path,value);published.append(value);events.append("request");Path(str(path).replace(".request.json",".approval.json")).write_text(json.dumps(self._response(Path(path))))
   with patch("paper_faithful.training.trainer._r17_publish_request",side_effect=publish):
    self._attempt_fit(tf,root/"r19-split42-model42",model)
  self.assertEqual(events,["context","scalar","request","fit"])
  self.assertEqual((published[0]["schema_version"],published[0]["run_id_prefix"],published[0]["run_id"],published[0]["stage"],published[0]["device"],published[0]["context_acquired"]),(1,"r19","r19-split42-model42","stage1","/GPU:0",True))
  self.assertRegex(published[0]["nonce"],r"^[0-9a-f]{32}$");self.assertIsInstance(published[0]["linux_pid"],int)
 def test_refusal_prevents_fit(self):
  model=Mock()
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory);original=__import__("paper_faithful.training.trainer",fromlist=["_r17_publish_request"])._r17_publish_request
   def publish(path,value):
    original(path,value);Path(str(path).replace(".request.json",".refusal.json")).write_text(json.dumps(self._response(Path(path),"refused")))
   with patch("paper_faithful.training.trainer._r17_publish_request",side_effect=publish):
    with self.assertRaisesRegex(TrainingContractError,"refused"):self._attempt_fit(FakeTF([]),root/"r19-split42-model42",model)
   model.fit.assert_not_called()
 def test_direct_cli_cannot_bypass_supervisor_binding(self):
  model=Mock()
  prefix="paper-text-v1-multiseed-cap128-r19-20260905"
  run_dir=Path("E:/runs")/(prefix+"-split42-model42")
  with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT":directory,"PAPER_FAITHFUL_R17_RUN_PREFIX":prefix,"PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS":"5","PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_PATH":"","PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_LOCK_PATH":""},clear=False):
   with self.assertRaisesRegex(TrainingContractError,"supervisor GPU admission binding is required"):
    self._attempt_fit(FakeTF([]),run_dir,model)
  model.fit.assert_not_called()
 def test_forged_binding_without_supervisor_lease_prevents_fit(self):
  model=Mock()
  prefix="paper-text-v1-multiseed-cap128-r19-20260905"
  run_id=prefix+"-split42-model42"
  with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT":directory,"PAPER_FAITHFUL_R17_RUN_PREFIX":prefix,"PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS":"5"},clear=False):
   root=Path(directory);binding_path=root/"binding.json";lock_path=root/"binding.lock"
   binding={"schema_version":1,"binding_id":"a"*32,"run_id_prefix":prefix,"expected_children":[prefix+"-split42-model42",prefix+"-split43-model43"],"canonical_gate_sha256":"0"*64,"user_confirmation_sha256":"0"*64,"task_name":"SleepStagePaper-r19-Canary-forged","dispatch_marker_path":"/missing/dispatch.lock","attempt_marker_path":"/missing/attempt.lock","lock_path":str(lock_path),"supervisor_pid":1,"created_at":"2026-09-05T00:00:00+07:00"}
   binding_path.write_text(json.dumps(binding),encoding="utf-8")
   with patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_PATH":str(binding_path),"PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_LOCK_PATH":str(lock_path)},clear=False):
    with self.assertRaisesRegex(TrainingContractError,"identity"):
     self._attempt_fit(FakeTF([]),Path("E:/runs")/run_id,model)
  model.fit.assert_not_called()
 def test_forged_binding_with_independently_held_lease_is_rejected(self):
  prefix=R19_GPU_ADMISSION_RUN_PREFIX;run_id=prefix+"-split42-model42";case="a"*32
  with tempfile.TemporaryDirectory() as directory,patch("paper_faithful.training.trainer.R19_RUNTIME_ROOT",(Path(directory)/"runtime").as_posix()):
   from paper_faithful.training import trainer as module
   paths=module._r19_expected_binding_paths("SleepStagePaper-r19-Canary-"+case)
   for key in ("gate","confirmation"):Path(paths[key]).parent.mkdir(parents=True,exist_ok=True);Path(paths[key]).write_text(json.dumps({"artifact":key}),encoding="utf-8")
   for key in ("dispatch","attempt","lock"):Path(paths[key]).touch()
   Path(paths["binding"]).parent.mkdir(parents=True,exist_ok=True)
   attacker_token="a"*64
   binding={"schema_version":2,"binding_id":"b"*32,"run_id_prefix":prefix,"expected_children":[prefix+"-split42-model42",prefix+"-split43-model43"],"canonical_gate_sha256":sha256_file(paths["gate"]),"user_confirmation_sha256":sha256_file(paths["confirmation"]),"canonical_gate_path":paths["gate"],"user_confirmation_path":paths["confirmation"],"task_name":"SleepStagePaper-r19-Canary-"+case,"dispatch_marker_path":paths["dispatch"],"attempt_marker_path":paths["attempt"],"lock_path":paths["lock"],"capability_token_sha256":__import__("hashlib").sha256(attacker_token.encode("ascii")).hexdigest(),"capability_sha256":"pending","supervisor_pid":1,"created_at":"2026-09-05T00:00:00+07:00"}
   binding["capability_sha256"]=_r19_binding_capability_sha(binding,attacker_token)
   Path(paths["binding"]).write_text(json.dumps(binding),encoding="utf-8")
   with patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_PATH":paths["binding"],"PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_LOCK_PATH":paths["lock"],"PAPER_FAITHFUL_R19_SUPERVISOR_CAPABILITY_TOKEN":"b"*64},clear=False),patch("paper_faithful.training.trainer.os.open",side_effect=PermissionError):
    with self.assertRaisesRegex(TrainingContractError,"capability token"):_r19_supervisor_binding(Path("E:/runs")/run_id,prefix)
 def test_r19_timeout_override_is_rejected(self):
  with patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS":"5"},clear=False):
   from paper_faithful.training.trainer import _r17_admission_timeout
   with self.assertRaisesRegex(TrainingContractError,"fixed at 240"):_r17_admission_timeout(R19_GPU_ADMISSION_RUN_PREFIX)
 def test_malformed_approval_fails_closed(self):
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory);original=__import__("paper_faithful.training.trainer",fromlist=["_r17_publish_request"])._r17_publish_request
   def publish(path,value): original(path,value);Path(str(path).replace(".request.json",".approval.json")).write_text("{")
   with patch("paper_faithful.training.trainer._r17_publish_request",side_effect=publish),self.assertRaisesRegex(TrainingContractError,"malformed"):_r17_gpu_admission(FakeTF([]),root/"r19-split42-model42","stage1")
 def test_timeout_and_collision_fail_closed(self):
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory)
   with patch("paper_faithful.training.trainer.time.monotonic",side_effect=[0,6]),self.assertRaisesRegex(TrainingContractError,"timed out"):_r17_gpu_admission(FakeTF([]),root/"r19-split42-model42","stage1")
   (root/"r19-split42-model42.stage1.request.json").write_text("{}")
   with self.assertRaisesRegex(TrainingContractError,"collision"):_r17_gpu_admission(FakeTF([]),root/"r19-split42-model42","stage1")


if __name__ == "__main__": unittest.main()
