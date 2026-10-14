import json, os, tempfile, types, unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from paper_faithful.training.run_manifest import sha256_file
from paper_faithful.training.trainer import R17_GPU_ADMISSION_DESIGN_ID, R17_GPU_ADMISSION_RUN_PREFIX, TrainingContractError, _r17_gpu_admission


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
  values=dict(self.env);values["PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT"]=str(root);values["PAPER_FAITHFUL_R17_RUN_PREFIX"]="r17";return patch.dict(os.environ,values,clear=False)
 def _response(self,request_path,status="approved"):
  request=json.loads(request_path.read_text());value={"schema_version":1,"design_id":R17_GPU_ADMISSION_DESIGN_ID,"status":status,"run_id_prefix":request["run_id_prefix"],"run_id":request["run_id"],"stage":request["stage"],"nonce":request["nonce"],"request_sha256":sha256_file(request_path),"absolute_third_party_exclusivity_claimed":False}
  if status=="approved":value.update({"baseline_pids":[2140],"current_pids":[4,2140],"expected_wsl_system_pid":4,"observability_limit":"bounded WDDM observation","approved_at":"2026-09-02T00:00:00+07:00"})
  else:value.update({"reason":"injected peer process","refused_at":"2026-09-02T00:00:00+07:00"})
  return value
 def _attempt_fit(self,tf,run_dir,model):
  _r17_gpu_admission(tf,run_dir,"stage1");return model.fit()
 def test_no_environment_is_exact_noop_for_non_r17_identity(self):
  with patch.dict(os.environ,{"PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT":"","PAPER_FAITHFUL_R17_RUN_PREFIX":""},clear=False),patch("paper_faithful.training.trainer.os.environ.get",side_effect=lambda key,default=None:None):
   _r17_gpu_admission(None,"r17-split42-model42","stage1")
 def test_exact_r17_identity_without_environment_prevents_fit(self):
  model=Mock()
  run_dir=Path("E:/runs")/(R17_GPU_ADMISSION_RUN_PREFIX+"-split42-model42")
  with patch("paper_faithful.training.trainer.os.environ.get",side_effect=lambda key,default=None:None):
   with self.assertRaisesRegex(TrainingContractError,"exact r17 run identity requires"):
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
    self._attempt_fit(tf,root/"r17-split42-model42",model)
  self.assertEqual(events,["context","scalar","request","fit"])
  self.assertEqual((published[0]["schema_version"],published[0]["run_id_prefix"],published[0]["run_id"],published[0]["stage"],published[0]["device"],published[0]["context_acquired"]),(1,"r17","r17-split42-model42","stage1","/GPU:0",True))
  self.assertRegex(published[0]["nonce"],r"^[0-9a-f]{32}$");self.assertIsInstance(published[0]["linux_pid"],int)
 def test_refusal_prevents_fit(self):
  model=Mock()
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory);original=__import__("paper_faithful.training.trainer",fromlist=["_r17_publish_request"])._r17_publish_request
   def publish(path,value):
    original(path,value);Path(str(path).replace(".request.json",".refusal.json")).write_text(json.dumps(self._response(Path(path),"refused")))
   with patch("paper_faithful.training.trainer._r17_publish_request",side_effect=publish):
    with self.assertRaisesRegex(TrainingContractError,"refused"):self._attempt_fit(FakeTF([]),root/"r17-split42-model42",model)
   model.fit.assert_not_called()
 def test_malformed_approval_fails_closed(self):
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory);original=__import__("paper_faithful.training.trainer",fromlist=["_r17_publish_request"])._r17_publish_request
   def publish(path,value): original(path,value);Path(str(path).replace(".request.json",".approval.json")).write_text("{")
   with patch("paper_faithful.training.trainer._r17_publish_request",side_effect=publish),self.assertRaisesRegex(TrainingContractError,"malformed"):_r17_gpu_admission(FakeTF([]),root/"r17-split42-model42","stage1")
 def test_timeout_and_collision_fail_closed(self):
  with tempfile.TemporaryDirectory() as directory,self._environment(directory):
   root=Path(directory)
   with patch("paper_faithful.training.trainer.time.monotonic",side_effect=[0,6]),self.assertRaisesRegex(TrainingContractError,"timed out"):_r17_gpu_admission(FakeTF([]),root/"r17-split42-model42","stage1")
   (root/"r17-split42-model42.stage1.request.json").write_text("{}")
   with self.assertRaisesRegex(TrainingContractError,"collision"):_r17_gpu_admission(FakeTF([]),root/"r17-split42-model42","stage1")


if __name__ == "__main__": unittest.main()
