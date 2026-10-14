"""Fail-closed, resumable Keras execution for finalized SST caches."""
from __future__ import annotations
import gc, hashlib, hmac, json, os, random, secrets, subprocess, tempfile, time
from contextlib import contextmanager
from pathlib import Path
import numpy as np
from .splits import SplitPlan, plan_epoch_split, plan_subject_split, validate_no_leakage
from .storage import run_directory
from .run_manifest import sha256_file
from .metrics import classification_metrics, silhouette_metric, write_metrics_artifact
from .quality_sampling import QUALITY_CLASS_WEIGHTING_ID, QUALITY_EARLY_STOPPING_ID, balanced_class_weights

class TrainingContractError(ValueError): pass
R17_GPU_ADMISSION_DESIGN_ID="R17_DEDICATED_HOST_OBSERVED_IDLE_GPU_ADMISSION_V1"
R17_GPU_ADMISSION_RUN_PREFIX="paper-text-v1-multiseed-cap128-r18-20260902"
R19_GPU_ADMISSION_RUN_PREFIX="paper-text-v1-multiseed-cap128-r19-20260905"
R19_RUNTIME_ROOT="/mnt/e/blp/sleep_stage_reproduction/runtime"
PARAM_GATE={"total":3340885,"trainable":1764229,"non_trainable":1576656}
STAGES=("stage1","stage2","stage3")
STAGE3_STABILITY_ADAPTATION_ID="PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1"
STAGE3_STABILITY_GLOBAL_NORM=1.0
QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID="QUALITY_STAGE3_CONSERVATIVE_SGD_LR002_V1"
QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID="QUALITY_STAGE3_FOCAL_LOSS_GAMMA2_V1"
QUALITY_STAGE3_FOCAL_LOSS_GAMMA=2.0
SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID="QUALITY_SUBJECT_AWARE_UNLABELED_ZSCORE_V1"
TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID="QUALITY_TRAIN_ONLY_SST_TIME_MASK_V1"
SILHOUETTE_RESERVOIR_CAP=4096
SILHOUETTE_RESERVOIR_SEED=42
SUBJECT_GENERALIZATION_PREFIX="subject-generalization-v1-pilot-20260906"
def _atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent));os.close(fd)
 try:Path(tmp).write_text(json.dumps(value,sort_keys=True,indent=2)+"\n");os.replace(tmp,path)
 finally:
  if Path(tmp).exists():Path(tmp).unlink()
def _hash(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":")).encode()).hexdigest()
def _r17_admission_environment():
 root=os.environ.get("PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT");prefix=os.environ.get("PAPER_FAITHFUL_R17_RUN_PREFIX")
 if root is None and prefix is None:return None
 if not root or not prefix:raise TrainingContractError("r17 GPU admission requires both environment variables")
 path=Path(root)
 if not path.is_dir():raise TrainingContractError("r17 GPU admission root is invalid")
 return path,prefix
def _r19_binding_capability_sha(binding, capability_token):
 material="\x00".join(str(binding[key]) for key in ("binding_id","canonical_gate_sha256","user_confirmation_sha256","task_name","supervisor_pid","dispatch_marker_path","attempt_marker_path","lock_path"))+"\x00"+capability_token
 return hashlib.sha256(material.encode("utf-8")).hexdigest()
def _r19_expected_binding_paths(task_name):
 match=__import__("re").fullmatch(r"SleepStagePaper-r19-(COM|Canary)-([0-9a-f]{32})",task_name)
 if match is None:raise TrainingContractError("r19 supervisor GPU admission task identity is invalid")
 if match.group(1)=="COM":
  root=f"{R19_RUNTIME_ROOT}/training-logs"
  return {"binding":f"{root}/{R19_GPU_ADMISSION_RUN_PREFIX}.supervisor-binding.json","lock":f"{root}/{R19_GPU_ADMISSION_RUN_PREFIX}.supervisor-binding.lock","gate":f"{R19_RUNTIME_ROOT}/driver-recovery/canonical-r19-multiseed-launch-gate-20260905.json","confirmation":f"{R19_RUNTIME_ROOT}/driver-recovery/r19-explicit-user-launch-confirmation-20260905.json","dispatch":f"{root}/{R19_GPU_ADMISSION_RUN_PREFIX}.dispatch.lock","attempt":f"{root}/{R19_GPU_ADMISSION_RUN_PREFIX}.launch.lock"}
 root=f"{R19_RUNTIME_ROOT}/driver-recovery/r19-live-gpu-admission-canaries/{match.group(2)}"
 return {"binding":f"{root}/supervisor-binding.json","lock":f"{root}/supervisor-binding.lock","gate":f"{root}/canary-gate.json","confirmation":f"{root}/canary-confirmation.json","dispatch":f"{root}/dispatch.lock","attempt":f"{root}/attempt.lock"}
def _r19_supervisor_binding(run_dir,prefix):
 binding_path=os.environ.get("PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_PATH")
 lock_path=os.environ.get("PAPER_FAITHFUL_R17_GPU_ADMISSION_BINDING_LOCK_PATH")
 if not binding_path or not lock_path:raise TrainingContractError("r19 supervisor GPU admission binding is required")
 try:binding=json.loads(Path(binding_path).read_text(encoding="utf-8"))
 except (OSError,UnicodeError,ValueError) as e:raise TrainingContractError("r19 supervisor GPU admission binding is unavailable") from e
 run_id=Path(run_dir).name
 expected=(prefix+"-split42-model42",prefix+"-split43-model43")
 expected_paths=_r19_expected_binding_paths(str(binding.get("task_name","")))
 required={"schema_version","binding_id","run_id_prefix","expected_children","canonical_gate_sha256","user_confirmation_sha256","canonical_gate_path","user_confirmation_path","task_name","dispatch_marker_path","attempt_marker_path","lock_path","capability_token_sha256","capability_sha256","supervisor_pid","created_at"}
 if not isinstance(binding,dict) or set(binding)!=required or binding.get("schema_version")!=2 or binding.get("binding_id") is None or not isinstance(binding.get("binding_id"),str) or len(binding["binding_id"])!=32 or binding["binding_id"]!=binding["binding_id"].lower() or binding.get("run_id_prefix")!=prefix or tuple(binding.get("expected_children",()))!=expected or binding.get("canonical_gate_path")!=expected_paths["gate"] or binding.get("user_confirmation_path")!=expected_paths["confirmation"] or binding.get("dispatch_marker_path")!=expected_paths["dispatch"] or binding.get("attempt_marker_path")!=expected_paths["attempt"] or binding.get("lock_path")!=expected_paths["lock"] or Path(binding_path).as_posix()!=Path(expected_paths["binding"]).as_posix() or Path(lock_path).as_posix()!=Path(expected_paths["lock"]).as_posix() or not isinstance(binding.get("supervisor_pid"),int) or isinstance(binding.get("supervisor_pid"),bool) or binding.get("supervisor_pid")<1 or not isinstance(binding.get("capability_token_sha256"),str) or not __import__("re").fullmatch(r"[0-9a-f]{64}",binding["capability_token_sha256"]) or not isinstance(binding.get("capability_sha256"),str) or not __import__("re").fullmatch(r"[0-9a-f]{64}",binding["capability_sha256"]):raise TrainingContractError("r19 supervisor GPU admission binding identity is invalid")
 if run_id not in expected:raise TrainingContractError("r19 GPU admission run_id is invalid")
 for key in ("gate","confirmation","dispatch","attempt"):
  if not Path(expected_paths[key]).is_file():raise TrainingContractError("r19 supervisor GPU admission binding artifact is unavailable")
 for key in ("dispatch_marker_path","attempt_marker_path"):
  if Path(binding[key]).stat().st_size!=0:raise TrainingContractError("r19 supervisor GPU admission marker content is invalid")
 try:
  if sha256_file(expected_paths["gate"])!=binding["canonical_gate_sha256"] or sha256_file(expected_paths["confirmation"])!=binding["user_confirmation_sha256"]:raise TrainingContractError("r19 supervisor GPU admission trust anchor mismatch")
 except OSError as e:raise TrainingContractError("r19 supervisor GPU admission trust anchor is unavailable") from e
 capability_token=os.environ.get("PAPER_FAITHFUL_R19_SUPERVISOR_CAPABILITY_TOKEN")
 if isinstance(capability_token,str):capability_token=capability_token.lstrip("\ufeff")
 if not isinstance(capability_token,str) or not __import__("re").fullmatch(r"[0-9a-f]{64}",capability_token):raise TrainingContractError("r19 supervisor GPU admission capability token is unavailable")
 token_sha=hashlib.sha256(capability_token.encode("ascii")).hexdigest()
 if not hmac.compare_digest(token_sha,binding["capability_token_sha256"]):raise TrainingContractError("r19 supervisor GPU admission capability token is invalid")
 if not hmac.compare_digest(_r19_binding_capability_sha(binding,capability_token),binding["capability_sha256"]):raise TrainingContractError("r19 supervisor GPU admission capability is invalid")
 if not Path(lock_path).is_file():raise TrainingContractError("r19 supervisor GPU admission binding lease is unavailable")
 try:
  handle=os.open(lock_path,os.O_RDONLY)
  os.close(handle)
 except PermissionError:
  return binding
 except FileNotFoundError as e:raise TrainingContractError("r19 supervisor GPU admission binding lease is unavailable") from e
 except OSError as e:raise TrainingContractError("r19 supervisor GPU admission binding lease cannot be proven") from e
 raise TrainingContractError("r19 supervisor GPU admission binding lease is not held")
def _r17_admission_timeout(expected_prefix=None):
 raw=os.environ.get("PAPER_FAITHFUL_R17_GPU_ADMISSION_TIMEOUT_SECONDS","120")
 if expected_prefix==R19_GPU_ADMISSION_RUN_PREFIX and raw!="240":raise TrainingContractError("r19 GPU admission timeout is fixed at 240 seconds")
 try:value=int(raw)
 except (TypeError,ValueError):raise TrainingContractError("r17 GPU admission timeout is invalid")
 if str(value)!=raw or not 5<=value<=300:raise TrainingContractError("r17 GPU admission timeout is outside 5..300 seconds")
 return value
def _r17_admission_run_id(run_dir,prefix):
 run_id=Path(run_dir).name
 if run_id not in (prefix+"-split42-model42",prefix+"-split43-model43"):raise TrainingContractError("r17 GPU admission run_id is invalid")
 return run_id
def _r17_json(path,label):
 try:value=json.loads(Path(path).read_text(encoding="utf-8"))
 except (OSError,UnicodeError,ValueError) as e:raise TrainingContractError("r17 GPU admission "+label+" is malformed") from e
 if not isinstance(value,dict):raise TrainingContractError("r17 GPU admission "+label+" is malformed")
 return value
def _r17_publish_request(path,value):
 path=Path(path);temporary=path.with_name(path.name+"."+secrets.token_hex(8)+".tmp")
 try:
  with temporary.open("x",encoding="utf-8",newline="\n") as handle:
   handle.write(json.dumps(value,sort_keys=True,separators=(",",":"))+"\n");handle.flush();os.fsync(handle.fileno())
  try:os.link(str(temporary),str(path))
  except FileExistsError as e:raise TrainingContractError("r17 GPU admission request collision") from e
  except OSError as e:raise TrainingContractError("r17 GPU admission request publish failed") from e
 finally:
  try:temporary.unlink()
  except FileNotFoundError:pass
def _r17_validate_response(value,request,request_sha256,status,label):
 required={"schema_version","design_id","status","run_id_prefix","run_id","stage","nonce","request_sha256","absolute_third_party_exclusivity_claimed"}
 if status=="approved":required|={"baseline_pids","current_pids","expected_wsl_system_pid","observability_limit","approved_at"}
 else:required|={"reason","refused_at"}
 if set(value)!=required or value.get("schema_version")!=1 or value.get("design_id")!=R17_GPU_ADMISSION_DESIGN_ID or value.get("status")!=status or value.get("run_id_prefix")!=request["run_id_prefix"] or value.get("run_id")!=request["run_id"] or value.get("stage")!=request["stage"] or value.get("nonce")!=request["nonce"] or value.get("request_sha256")!=request_sha256 or value.get("absolute_third_party_exclusivity_claimed") is not False:raise TrainingContractError("r17 GPU admission "+label+" identity is invalid")
 if status=="approved":
  baseline=value.get("baseline_pids");current=value.get("current_pids")
  if not isinstance(baseline,list) or not isinstance(current,list) or any(isinstance(pid,bool) or not isinstance(pid,int) or pid<1 for pid in baseline+current) or value.get("expected_wsl_system_pid")!=4 or 4 in baseline or 4 not in current or not isinstance(value.get("observability_limit"),str) or not value["observability_limit"] or not isinstance(value.get("approved_at"),str) or not value["approved_at"]:raise TrainingContractError("r17 GPU admission approval evidence is invalid")
 elif not isinstance(value.get("reason"),str) or not value["reason"] or not isinstance(value.get("refused_at"),str) or not value["refused_at"]:raise TrainingContractError("r17 GPU admission refusal evidence is invalid")
def _r17_gpu_admission(tf,run_dir,stage):
 run_id=Path(run_dir).name
 environment=_r17_admission_environment()
 if environment is None:
  if run_id in (R17_GPU_ADMISSION_RUN_PREFIX+"-split42-model42",R17_GPU_ADMISSION_RUN_PREFIX+"-split43-model43"):raise TrainingContractError("exact r18 run identity requires GPU admission environment")
  if run_id in (R19_GPU_ADMISSION_RUN_PREFIX+"-split42-model42",R19_GPU_ADMISSION_RUN_PREFIX+"-split43-model43"):raise TrainingContractError("exact r19 run identity requires GPU admission environment")
  return
 root,prefix=environment;run_id=_r17_admission_run_id(run_dir,prefix)
 if prefix==R19_GPU_ADMISSION_RUN_PREFIX:_r19_supervisor_binding(run_dir,prefix)
 if stage not in STAGES:raise TrainingContractError("r17 GPU admission stage is invalid")
 timeout=_r17_admission_timeout(prefix);physical=tf.config.list_physical_devices("GPU")
 if len(physical)!=1:raise TrainingContractError("r17 GPU admission requires exactly one physical GPU")
 with tf.device("/GPU:0"):
  try:np.asarray(tf.constant(0.0).numpy()).item()
  except BaseException as e:raise TrainingContractError("r17 GPU admission could not acquire /GPU:0 context") from e
 nonce=secrets.token_hex(16);request={"schema_version":1,"design_id":R17_GPU_ADMISSION_DESIGN_ID,"run_id_prefix":prefix,"run_id":run_id,"stage":stage,"nonce":nonce,"linux_pid":os.getpid(),"device":"/GPU:0","context_acquired":True}
 request_path=root/(run_id+"."+stage+".request.json");approval_path=root/(run_id+"."+stage+".approval.json");refusal_path=root/(run_id+"."+stage+".refusal.json")
 _r17_publish_request(request_path,request);request_sha256=sha256_file(request_path);deadline=time.monotonic()+timeout
 while True:
  if refusal_path.exists():
   _r17_validate_response(_r17_json(refusal_path,"refusal"),request,request_sha256,"refused","refusal");raise TrainingContractError("r17 GPU admission was refused")
  if approval_path.exists():
   _r17_validate_response(_r17_json(approval_path,"approval"),request,request_sha256,"approved","approval");return
  if time.monotonic()>=deadline:raise TrainingContractError("r17 GPU admission approval timed out")
  time.sleep(.05)
def _subject_generalization_gpu_admission(tf,run_dir,stage):
 """Observe GPU context and exclude peers, not the current training PID.

 WSL/WDDM visibility is incomplete; this is not an exclusivity guarantee.
 Unknown or unparseable owners are refused, not assumed to be this process.
 """
 execution_path=Path(run_dir)/"execution.json"
 subject_run=False
 if execution_path.is_file():
  try:subject_run=json.loads(execution_path.read_text(encoding="utf-8")).get("config",{}).get("evaluation_protocol_id")=="SUBJECT_GENERALIZATION_V1"
  except (ValueError,OSError,AttributeError) as error:raise TrainingContractError("subject-generalization execution identity unreadable") from error
 enabled=os.environ.get("PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION")=="1"
 if not enabled:
  if subject_run:raise TrainingContractError("subject-generalization GPU admission environment is required")
  return
 if not subject_run:raise TrainingContractError("subject-generalization GPU admission requires subject execution identity")
 if getattr(tf,"__version__",None)!="2.4.0":raise TrainingContractError("subject-generalization requires TensorFlow 2.4.0")
 run_id=Path(run_dir).name
 prefix=os.environ.get("PAPER_FAITHFUL_SUBJECT_RUN_PREFIX")
 if not prefix or not run_id.startswith(prefix+"-fold") or stage not in STAGES:raise TrainingContractError("subject-generalization GPU admission run identity is invalid")
 root=os.environ.get("PAPER_FAITHFUL_SUBJECT_GPU_ADMISSION_ROOT")
 if not isinstance(root,str) or not root:raise TrainingContractError("subject-generalization GPU admission root is unavailable")
 root_path=Path(root);evidence_path=root_path/(run_id+"."+stage+".json")
 if evidence_path.exists():raise TrainingContractError("subject-generalization GPU admission evidence collision")
 physical=tf.config.list_physical_devices("GPU")
 if len(physical)!=1:raise TrainingContractError("subject-generalization GPU admission requires exactly one physical GPU")
 try:
  with tf.device("/GPU:0"):
   # TensorFlow 2.4 may place a scalar constant on CPU even inside an
   # explicit GPU device scope.  Use a one-element tensor so this admission
   # probe tests actual GPU placement rather than scalar constant folding.
   scalar=tf.ones((1,))
   if "GPU:0" not in getattr(scalar,"device",""):raise TrainingContractError("subject-generalization scalar was not placed on GPU")
   np.asarray(scalar.numpy()).item()
  probe=subprocess.run(["nvidia-smi","--query-compute-apps=pid,process_name,used_gpu_memory","--format=csv,noheader,nounits"],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=30,check=False)
 except (OSError,subprocess.SubprocessError) as error:raise TrainingContractError("subject-generalization GPU admission probe failed") from error
 processes=tuple(line.strip() for line in probe.stdout.splitlines() if line.strip())
 if probe.returncode!=0:raise TrainingContractError("subject-generalization GPU admission probe failed")
 try:pids=[int(line.split(",",1)[0].strip()) for line in processes]
 except ValueError as error:raise TrainingContractError("subject-generalization GPU owner is unobservable") from error
 if any(pid!=os.getpid() for pid in pids):raise TrainingContractError("subject-generalization GPU admission found a peer or unknown compute process")
 _atomic(evidence_path,{"schema_version":2,"status":"approved","design_id":"SUBJECT_GENERALIZATION_OBSERVED_SELF_GPU_V2","run_id":run_id,"stage":stage,"physical_gpu_count":len(physical),"compute_processes":list(processes),"linux_pid":os.getpid(),"observability_limit":"WSL/WDDM may omit compute processes; empty output is not proof of exclusivity","absolute_third_party_exclusivity_claimed":False})
def failure_record(exc):
 message=str(exc);return {"type":type(exc).__name__,"message":message,"fingerprint":_hash({"type":type(exc).__name__,"message":message})}
def route_for_stage(protocol_id,stage):
 if protocol_id not in ("PAPER_TEXT_V1","AUTHOR_CODE_V1") or stage not in STAGES:raise TrainingContractError("invalid protocol/stage")
 return "AUTHOR_CODE_V1" if protocol_id=="AUTHOR_CODE_V1" else ("PAPER_STAGE3_V1" if stage=="stage3" else "PAPER_PRETRAIN_V1")
def _gradient_clip_norm(value):
 if value is None:return None
 if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)) or not np.isfinite(float(value)) or float(value)<=0:raise TrainingContractError("gradient clip norm must be a positive finite number")
 return float(value)
def stage_spec(protocol_id,stage,*,microbatch=128,stage2_loss_adaptation=None,author_stage3_epochs=None,weight_decay=None,stage3_gradient_clip_norm=None,stage3_stability_adaptation_id=None,stage3_optimizer_adaptation_id=None,stage3_loss_adaptation_id=None,epochs_override=None,quality_class_weighting_id=None,quality_early_stopping_id=None,subject_normalization_id=None,train_augmentation_id=None):
 if protocol_id not in ("PAPER_TEXT_V1","AUTHOR_CODE_V1") or stage not in STAGES or not isinstance(microbatch,int) or not 1<=microbatch<=128:raise TrainingContractError("invalid protocol/stage/microbatch")
 if stage in ("stage1","stage3") and 128%microbatch:raise TrainingContractError("Stage1/3 hardware microbatch must divide nominal batch 128 for gradient accumulation")
 if stage=="stage2" and microbatch<128 and stage2_loss_adaptation!="adapted_pairwise_objective":raise TrainingContractError("Stage2 batch below 128 requires the implemented adapted_pairwise_objective")
 if (stage!="stage2" or microbatch==128) and stage2_loss_adaptation is not None:raise TrainingContractError("Stage2 loss adaptation is invalid at batch 128 or outside Stage2")
 if stage=="stage1" and weight_decay is None:raise TrainingContractError("Stage1 AdamW weight_decay must be explicitly supplied as an assumption")
 clip_norm=_gradient_clip_norm(stage3_gradient_clip_norm)
 stability_requested=clip_norm is not None or stage3_stability_adaptation_id is not None
 if stability_requested and (protocol_id!="PAPER_TEXT_V1" or stage!="stage3" or clip_norm!=STAGE3_STABILITY_GLOBAL_NORM or stage3_stability_adaptation_id!=STAGE3_STABILITY_ADAPTATION_ID):raise TrainingContractError("Stage3 stability adaptation requires the exact PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1 binding with global norm 1.0")
 if epochs_override is not None and (isinstance(epochs_override,bool) or not isinstance(epochs_override,int) or not 1<=epochs_override<=1000):raise TrainingContractError("epochs override must be an integer in [1, 1000]")
 epochs=50 if protocol_id=="AUTHOR_CODE_V1" and stage=="stage3" else 20
 if epochs_override is not None:epochs=epochs_override
 if author_stage3_epochs is not None and author_stage3_epochs!=epochs:raise TrainingContractError("AUTHOR Stage3 is locked to 50 epochs")
 author=protocol_id=="AUTHOR_CODE_V1"
 quality_requested=quality_class_weighting_id is not None or quality_early_stopping_id is not None
 if quality_requested and (protocol_id!="PAPER_TEXT_V1" or stage!="stage3" or quality_class_weighting_id!=QUALITY_CLASS_WEIGHTING_ID or quality_early_stopping_id!=QUALITY_EARLY_STOPPING_ID):raise TrainingContractError("quality Stage3 requires exact train-only class weighting and early-stopping bindings")
 if stage3_optimizer_adaptation_id is not None and (protocol_id!="PAPER_TEXT_V1" or stage!="stage3" or not quality_requested or stage3_optimizer_adaptation_id!=QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID):raise TrainingContractError("Stage3 optimizer adaptation requires the quality Stage3 contract")
 if stage3_loss_adaptation_id is not None and (protocol_id!="PAPER_TEXT_V1" or stage!="stage3" or not quality_requested or stage3_loss_adaptation_id!=QUALITY_STAGE3_FOCAL_LOSS_ADAPTATION_ID):raise TrainingContractError("Stage3 focal-loss adaptation requires the quality Stage3 contract")
 if subject_normalization_id is not None and (protocol_id!="PAPER_TEXT_V1" or subject_normalization_id!=SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID):raise TrainingContractError("subject-aware normalization requires the exact quality normalization binding")
 if train_augmentation_id is not None and (protocol_id!="PAPER_TEXT_V1" or train_augmentation_id!=TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID):raise TrainingContractError("train augmentation requires the exact SST time-mask binding")
 conservative_optimizer=stage3_optimizer_adaptation_id==QUALITY_STAGE3_OPTIMIZER_ADAPTATION_ID
 accumulation_steps=128//microbatch if stage in ("stage1","stage3") else 1
 adaptation_reason=("gradient_accumulation_for_hardware_batch_limit" if accumulation_steps>1 else ("hardware_batch_limit" if microbatch!=128 else None))
 result={"stage":stage,"epochs":epochs,"optimizer":{"stage1":"AdamW","stage2":"SGD","stage3":"SGD"}[stage],"learning_rate":.05 if stage=="stage1" else (.02 if conservative_optimizer else .1),"weight_decay":weight_decay,"loss":"supervised_contrastive_temperature_0.05" if stage=="stage2" else ("sparse_categorical_focal_gamma_2" if stage3_loss_adaptation_id is not None else "sparse_categorical_crossentropy"),"nominal_batch":128,"microbatch":microbatch,"effective_batch":microbatch*accumulation_steps,"gradient_accumulation_steps":accumulation_steps,"drop_remainder":True,"stage2_loss_adaptation":stage2_loss_adaptation,"hardware_adaptation":microbatch!=128,"adaptation_reason":adaptation_reason,"stage3_stability_adaptation_id":stage3_stability_adaptation_id,"stage3_optimizer_adaptation_id":stage3_optimizer_adaptation_id,"stage3_loss_adaptation":{"id":stage3_loss_adaptation_id,"gamma":QUALITY_STAGE3_FOCAL_LOSS_GAMMA,"scope":"stage3_train_only","fit_uses_labels":True} if stage3_loss_adaptation_id is not None else None,"subject_normalization":{"id":subject_normalization_id,"scope":"per_subject_unlabeled_split_tensor_values","fit_uses_labels":False} if subject_normalization_id is not None else None,"train_augmentation":{"id":train_augmentation_id,"scope":"train_split_only","type":"deterministic_time_mask","masked_time_columns":4,"fit_uses_labels":False} if train_augmentation_id is not None else None,"gradient_clip_norm":clip_norm,"gradient_clip_application":"after_effective_batch_average_before_optimizer_step" if clip_norm is not None else None,"numerical_stability_adaptation":clip_norm is not None,"paper_exact":microbatch==128 and stage2_loss_adaptation is None and clip_norm is None and stage3_loss_adaptation_id is None and subject_normalization_id is None and train_augmentation_id is None and not quality_requested and epochs==(50 if author and stage=="stage3" else 20),"scheduler":{"name":"ReduceLROnPlateau","factor":(.5 if (author or conservative_optimizer) else .2),"patience":(2 if conservative_optimizer else (5 if author else 1)),"min_lr":(1e-5 if conservative_optimizer else (1e-6 if author else 1e-4))},"early_stopping":{"id":QUALITY_EARLY_STOPPING_ID,"monitor":"val_loss","mode":"min","patience":3,"min_delta":1e-4,"restore_best_weights":True} if quality_requested else ({"monitor":"val_loss","patience":30,"restore_best_weights":True} if author else None)}
 if quality_requested:result["class_weighting"]={"id":QUALITY_CLASS_WEIGHTING_ID,"formula":"n_train/(5*n_class)","source_split":"train_only"}
 return result
def make_split(cache,protocol_id,*,subject_generalization=False,seed=42,fractions=(.8,.1,.1)):
 plan=plan_subject_split(cache.members,seed=seed,fractions=fractions) if subject_generalization else plan_epoch_split(cache.members,seed=seed,fractions=fractions,protocol_id=protocol_id);validate_no_leakage(plan,require_subject_disjoint=subject_generalization);return plan
def cap_split_plan(plan,cap):
 if not isinstance(cap,int) or cap<1:raise TrainingContractError("pilot cap must be positive")
 parts={name:tuple(getattr(plan,name)[:cap]) for name in ("train","validation","test")}
 if any(not value for value in parts.values()):raise TrainingContractError("pilot cap leaves an empty split")
 digest=lambda items:hashlib.sha256(("\n".join(sorted(item.key for item in items))+"\n").encode()).hexdigest()
 capped=SplitPlan(plan.protocol_id,plan.seed,parts["train"],parts["validation"],parts["test"],{name:digest(items) for name,items in parts.items()})
 validate_no_leakage(capped,require_subject_disjoint=plan.protocol_id=="SUBJECT_GENERALIZATION_V1");return capped
def validate_checkpoint(path,digest,parent=None,expected_contract=None):
 if not isinstance(digest,str) or len(digest)!=64 or not Path(path).is_file() or sha256_file(path)!=digest:raise TrainingContractError("checkpoint SHA-256 gate failed")
 if parent is not None and (parent.get("checkpoint_hash")!=digest or any(parent.get(k)!=v for k,v in (expected_contract or {}).items())):raise TrainingContractError("parent lineage failed")
def validate_stage3_parameter_gate(model):
 n=lambda ws:sum(int(w.shape.num_elements()) for w in ws);counts={"total":int(model.count_params()),"trainable":n(model.trainable_weights),"non_trainable":n(model.non_trainable_weights)}
 if counts!=PARAM_GATE:raise TrainingContractError("Stage3 parameter gate failed: {0}".format(counts))
 return counts
def _validate_stage_artifact(stage,artifact,config):
 required={"checkpoint_path","checkpoint_hash","parent_checkpoint_path","parent_checkpoint_hash","route","metrics_path","metrics_file_sha256","metrics_artifact_sha256"}
 if stage not in STAGES or not isinstance(artifact,dict) or set(artifact)!=required:raise TrainingContractError("stage artifact schema is invalid")
 if artifact["route"]!=route_for_stage(config.get("protocol_id"),stage) or not isinstance(artifact["checkpoint_hash"],str) or len(artifact["checkpoint_hash"])!=64 or not isinstance(artifact["metrics_file_sha256"],str) or len(artifact["metrics_file_sha256"])!=64 or not isinstance(artifact["metrics_artifact_sha256"],str) or len(artifact["metrics_artifact_sha256"])!=64:raise TrainingContractError("stage artifact route or hash is invalid")
 if stage=="stage1" and (artifact["parent_checkpoint_path"] is not None or artifact["parent_checkpoint_hash"] is not None):raise TrainingContractError("Stage1 artifact cannot have a parent checkpoint")
 if stage!="stage1" and (not isinstance(artifact["parent_checkpoint_path"],str) or not isinstance(artifact["parent_checkpoint_hash"],str) or len(artifact["parent_checkpoint_hash"])!=64):raise TrainingContractError("later-stage artifact parent checkpoint is invalid")
 if not Path(artifact["checkpoint_path"]).is_file() or sha256_file(artifact["checkpoint_path"])!=artifact["checkpoint_hash"]:raise TrainingContractError("stage artifact checkpoint hash failed")
 if not Path(artifact["metrics_path"]).is_file() or sha256_file(artifact["metrics_path"])!=artifact["metrics_file_sha256"]:raise TrainingContractError("stage artifact metric-file hash failed")
 try:metric=json.loads(Path(artifact["metrics_path"]).read_text())
 except (OSError,ValueError) as e:raise TrainingContractError("stage metric artifact is unreadable") from e
 provenance=metric.get("provenance")
 if set(metric)!={"metrics","metrics_sha256","provenance","artifact_sha256"} or not isinstance(metric.get("metrics"),dict) or metric.get("metrics_sha256")!=_hash(metric["metrics"]) or metric.get("artifact_sha256")!=_hash({"metrics":metric["metrics"],"provenance":provenance}) or metric["artifact_sha256"]!=artifact["metrics_artifact_sha256"] or not isinstance(provenance,dict) or provenance.get("protocol_id")!=config.get("protocol_id") or provenance.get("stage")!=stage or provenance.get("route")!=artifact["route"] or provenance.get("cache_hash")!=config.get("cache_hash") or provenance.get("checkpoint_sha256")!=artifact["checkpoint_hash"] or provenance.get("split_membership_hashes")!=config.get("split_hashes"):raise TrainingContractError("stage metric provenance does not bind the execution contract")
def _validate_stage_artifacts(artifacts,config):
 if not isinstance(artifacts,dict):raise TrainingContractError("stage artifacts must be an object")
 for stage,artifact in artifacts.items():_validate_stage_artifact(stage,artifact,config)
 for stage,predecessor in (("stage2","stage1"),("stage3","stage2")):
  if stage not in artifacts:continue
  parent=artifacts.get(predecessor)
  if parent is None:
   external=config.get("external_parent")
   if config.get("stage")!=stage or not isinstance(external,dict):raise TrainingContractError("stage artifact has no approved predecessor lineage")
   expected={"cache_hash":config.get("cache_hash"),"protocol_id":config.get("protocol_id"),"stage":predecessor,"route":route_for_stage(config.get("protocol_id"),predecessor)}
   validate_checkpoint(external["checkpoint_path"],external["checkpoint_hash"],external,expected);parent=external
  if artifacts[stage]["parent_checkpoint_path"]!=parent["checkpoint_path"] or artifacts[stage]["parent_checkpoint_hash"]!=parent["checkpoint_hash"]:raise TrainingContractError("stage artifact parent lineage does not bind its predecessor")
def _validate_progress_lineage(progress,artifacts,config):
 if not isinstance(progress,dict) or progress.get("next_stage") not in STAGES+(None,):raise TrainingContractError("stage progress is invalid")
 stage=progress["next_stage"];parent=progress.get("checkpoint")
 if stage is None:
  terminal_stage="stage3" if config.get("stage","all")=="all" else config.get("stage")
  artifact=artifacts.get(terminal_stage)
  required_artifacts=set(STAGES if config.get("stage","all")=="all" else (terminal_stage,))
  if terminal_stage not in STAGES or set(artifacts)!=required_artifacts or artifact is None or not isinstance(parent,dict) or parent.get("checkpoint_path")!=artifact["checkpoint_path"] or parent.get("checkpoint_hash")!=artifact["checkpoint_hash"]:raise TrainingContractError("terminal progress does not bind the completed stage artifact set")
  expected={"cache_hash":config.get("cache_hash"),"protocol_id":config.get("protocol_id"),"stage":terminal_stage,"route":artifact["route"]};validate_checkpoint(parent["checkpoint_path"],parent["checkpoint_hash"],parent,expected);return
 if stage=="stage1":
  if parent is not None:raise TrainingContractError("Stage1 progress cannot have a parent checkpoint")
  return
 predecessor={"stage2":"stage1","stage3":"stage2"}[stage];artifact=artifacts.get(predecessor)
 if artifact is not None:
  expected={"cache_hash":config.get("cache_hash"),"protocol_id":config.get("protocol_id"),"stage":predecessor,"route":artifact["route"]}
  if not isinstance(parent,dict) or parent.get("checkpoint_path")!=artifact["checkpoint_path"] or parent.get("checkpoint_hash")!=artifact["checkpoint_hash"]:raise TrainingContractError("progress checkpoint does not bind the preceding stage artifact")
  validate_checkpoint(parent["checkpoint_path"],parent["checkpoint_hash"],parent,expected);return
 external=config.get("external_parent")
 if config.get("stage")==stage and isinstance(external,dict) and parent==external:
  expected={"cache_hash":config.get("cache_hash"),"protocol_id":config.get("protocol_id"),"stage":predecessor,"route":route_for_stage(config.get("protocol_id"),predecessor)}
  validate_checkpoint(parent["checkpoint_path"],parent["checkpoint_hash"],parent,expected);return
 raise TrainingContractError("progress checkpoint has no immutable predecessor lineage")
@contextmanager
def _record_lock(directory):
 lock=Path(directory)/"execution.json.lock"
 try:fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
 except FileExistsError as e:raise TrainingContractError("execution record is locked") from e
 try:yield
 finally:
  try:lock.unlink()
  except FileNotFoundError:pass
def _latest(directory):
 path=Path(directory)/"execution.json"
 if not path.is_file():raise TrainingContractError("execution record missing")
 try:return json.loads(path.read_text())
 except ValueError as e:raise TrainingContractError("execution record unreadable") from e
def prepare_run(run_id,config,*,bulk_root=None,resume=False):
 directory=run_directory(run_id,bulk_root) if bulk_root is not None else run_directory(run_id);manifest=directory/"execution.json";digest=_hash(config)
 if directory.exists():
  if not resume or not manifest.is_file():raise TrainingContractError("run exists; explicit resume required")
  old=_latest(directory)
  if not isinstance(old.get("config"),dict) or _hash(old["config"])!=old.get("immutable_config_hash") or old.get("immutable_config_hash")!=digest or old.get("status") not in ("running","failed"):raise TrainingContractError("resume immutable contract mismatch")
  progress=old.get("stage_progress")
  if not isinstance(progress,dict) or progress.get("next_stage") not in STAGES or not isinstance(progress.get("last_epoch"),int) or progress.get("inflight") is not False:raise TrainingContractError("resume progress is absent, incomplete, or invalid; refusing restart")
  _validate_stage_artifacts(old.get("stage_artifacts"),old.get("config",{}));_validate_progress_lineage(progress,old.get("stage_artifacts"),old.get("config",{}))
  return directory,old
 record={"status":"planned","immutable_config_hash":digest,"config":config,"last_epoch":0,"checkpoint_hash":None,"stage_artifacts":{},"stage_progress":{"next_stage":"stage1","last_epoch":0,"checkpoint":None,"inflight":False}};_atomic(manifest,record);return directory,record
def transition_run(directory,record,status,**updates):
 if status not in ("planned","running","completed","failed"):raise TrainingContractError("illegal state")
 with _record_lock(directory):
  current=_latest(directory);old=current.get("status")
  if not isinstance(current.get("config"),dict) or _hash(current["config"])!=current.get("immutable_config_hash") or not isinstance(record.get("config"),dict) or _hash(record["config"])!=record.get("immutable_config_hash") or current.get("immutable_config_hash")!=record.get("immutable_config_hash"):raise TrainingContractError("stale execution record")
  if (old,status) not in {("planned","running"),("running","running"),("running","completed"),("running","failed"),("failed","running"),("failed","failed")}:raise TrainingContractError("illegal or immutable state transition")
  if status=="failed" and (not isinstance(updates.get("failure"),dict) or set(updates["failure"])!={"type","message","fingerprint"}):raise TrainingContractError("failed runs require type/message/fingerprint")
  old_artifacts=current.get("stage_artifacts",{})
  new_artifacts=updates.get("stage_artifacts",old_artifacts)
  if not isinstance(old_artifacts,dict) or not isinstance(new_artifacts,dict) or any(name not in new_artifacts or new_artifacts[name]!=artifact for name,artifact in old_artifacts.items()):raise TrainingContractError("stage artifacts are append-only")
  _validate_stage_artifacts(new_artifacts,current.get("config",{}))
  new_progress=updates.get("stage_progress",current.get("stage_progress"));_validate_progress_lineage(new_progress,new_artifacts,current.get("config",{}))
  if status=="completed" and (new_progress.get("next_stage") is not None or new_progress.get("inflight") is not False):raise TrainingContractError("completed runs require terminal, non-inflight progress")
  result=dict(current);result.update(updates);result["status"]=status;_atomic(Path(directory)/"execution.json",result);return result
class CacheSequence:
 def __init__(self,cache,members,route,batch,sequence=False,drop_remainder=True,nominal_batch=None,class_weights=None,subject_normalization_id=None,train_augmentation_id=None):
  self.cache,self.members,self.route,self.batch,self.sequence,self.drop_remainder=cache,tuple(members),route,batch,sequence,drop_remainder
  self.nominal_batch=batch if nominal_batch is None else nominal_batch
  self.class_weights=class_weights
  self.subject_normalization_id=subject_normalization_id
  self.train_augmentation_id=train_augmentation_id
  if not isinstance(batch,int) or not isinstance(self.nominal_batch,int) or batch<1 or self.nominal_batch<batch or self.nominal_batch%batch:raise TrainingContractError("cache sequence batch contract is invalid")
  if class_weights is not None and (not self.sequence or not isinstance(class_weights,dict) or set(class_weights)!={0,1,2,3,4} or any(isinstance(value,bool) or not isinstance(value,(int,float,np.integer,np.floating)) or not np.isfinite(float(value)) or float(value)<=0 for value in class_weights.values())):raise TrainingContractError("cache sequence class weights are invalid")
  if subject_normalization_id not in (None,SUBJECT_AWARE_ZSCORE_NORMALIZATION_ID):raise TrainingContractError("cache sequence subject normalization is invalid")
  if train_augmentation_id not in (None,TRAIN_ONLY_SST_TIME_MASK_AUGMENTATION_ID):raise TrainingContractError("cache sequence augmentation is invalid")
  self._subject_stats=self._fit_subject_stats() if subject_normalization_id is not None else None
  self._windows_per_member=None
  if not self.sequence and self.members:
   entry=self.cache.entry(self.members[0],self.route);self._windows_per_member=int(self.cache.array(entry).shape[1])
 def _sample_count(self):
  if self.sequence:return len(self.members)
  return 0 if self._windows_per_member is None else len(self.members)*self._windows_per_member
 def _fit_subject_stats(self):
  """Fit channel-wise z-score statistics from unlabeled tensors per subject."""
  totals={}
  for member in self.members:
   entry=self.cache.entry(member,self.route);values=np.asarray(self.cache.array(entry)[entry.offset],dtype=np.float64)
   if values.ndim<1 or values.shape[-1]<1 or not np.all(np.isfinite(values)):raise TrainingContractError("subject normalization tensor is non-finite or malformed")
   flat=values.reshape((-1,values.shape[-1]));count,total,square=totals.get(member.subject_id,(0,None,None))
   current_total=flat.sum(axis=0);current_square=np.square(flat).sum(axis=0)
   totals[member.subject_id]=(count+flat.shape[0],current_total if total is None else total+current_total,current_square if square is None else square+current_square)
  result={}
  for subject,(count,total,square) in totals.items():
   mean=total/count;variance=np.maximum(square/count-np.square(mean),1e-12);std=np.sqrt(variance)
   if count<1 or not np.all(np.isfinite(mean)) or not np.all(np.isfinite(std)):raise TrainingContractError("subject normalization statistics are invalid")
   result[subject]=(mean.astype(np.float32),std.astype(np.float32))
  if set(result)!={member.subject_id for member in self.members}:raise TrainingContractError("subject normalization subject coverage is incomplete")
  return result
 def _normalized(self,value,subject_id):
  if self._subject_stats is None:return value
  try:mean,std=self._subject_stats[subject_id]
  except KeyError as error:raise TrainingContractError("subject normalization statistic is missing") from error
  return (np.asarray(value,dtype=np.float32)-mean)/std
 def _augmented(self,value,member_key,window_index):
  if self.train_augmentation_id is None:return value
  result=np.asarray(value,dtype=np.float32).copy()
  if result.ndim<3 or result.shape[-1]!=2 or result.shape[-2]<4:raise TrainingContractError("SST time-mask input is malformed")
  digest=hashlib.sha256((self.train_augmentation_id+"\\0"+member_key+"\\0"+str(window_index)).encode("utf-8")).digest()
  start=int.from_bytes(digest[:8],"big")%(result.shape[-2]-3)
  result[..., :, start:start+4, :]=0.0
  return result
 def __len__(self):
  total=self._sample_count()
  if self.drop_remainder:total-=total%self.nominal_batch
  return total//self.batch if self.drop_remainder else (total+self.batch-1)//self.batch
 def __getitem__(self,index):
  total=self._sample_count()
  if self.drop_remainder:total-=total%self.nominal_batch
  start=index*self.batch;end=min(total,start+self.batch)
  if index<0 or start>=total or self.drop_remainder and end-start!=self.batch:raise IndexError(index)
  if self.sequence:
   count=end-start;x=y=None
   for output_index,m in enumerate(self.members[start:end]):
    e=self.cache.entry(m,self.route);a=self.cache.array(e)
    if x is None:x=np.empty((count,)+a[e.offset].shape,dtype=np.float32);y=np.empty((count,),dtype=np.int32)
    x[output_index]=self._augmented(self._normalized(a[e.offset],m.subject_id),m.key,0);y[output_index]=e.label;del a
   if self.class_weights is not None:return x,y,np.asarray([self.class_weights[int(label)] for label in y],dtype=np.float32)
   return x,y
  windows=self._windows_per_member;x=y=None
  for position in range(start,end):
   member=self.members[position//windows];window_index=position%windows;e=self.cache.entry(member,self.route);a=self.cache.array(e)
   output_index=position-start
   if x is None:x=np.empty((end-start,)+a[e.offset,window_index].shape,dtype=np.float32);y=np.empty((end-start,),dtype=np.int32)
   x[output_index]=self._augmented(self._normalized(a[e.offset,window_index],member.subject_id),member.key,window_index);y[output_index]=e.label;del a
  return x,y
def _tf():
 try:import tensorflow as tf;return tf
 except ImportError as e:raise RuntimeError("use locked TensorFlow 2.4") from e
def seed_model(seed):
 if not isinstance(seed,int) or not 0<=seed<2**32:raise TrainingContractError("model seed must be an unsigned 32-bit integer")
 random.seed(seed);np.random.seed(seed);tf=_tf();tf.random.set_seed(seed);return tf
def cleanup_model_state(tf):
 clear_failed=False
 try:
  try:tf.keras.backend.clear_session()
  except BaseException:
   clear_failed=True;raise
 finally:
  try:gc.collect()
  except BaseException:
   if not clear_failed:raise
def keras_sequence_type(tf):return type("KerasCacheSequence",(CacheSequence,tf.keras.utils.Sequence),{})
def make_callbacks(tf,spec,checkpoint):
 scheduler={k:v for k,v in spec["scheduler"].items() if k!="name"};out=[tf.keras.callbacks.TerminateOnNaN(),tf.keras.callbacks.ReduceLROnPlateau(**scheduler),tf.keras.callbacks.ModelCheckpoint(str(checkpoint),save_best_only=True,save_weights_only=True,monitor="val_loss")]
 if spec["early_stopping"]:
  early={k:v for k,v in spec["early_stopping"].items() if k!="id"};out.append(tf.keras.callbacks.EarlyStopping(**early))
 return out
def _enable_gradient_accumulation(tf,model,steps,gradient_clip_norm=None):
 if not isinstance(steps,int) or steps<1:raise TrainingContractError("gradient accumulation steps must be positive")
 clip_norm=_gradient_clip_norm(gradient_clip_norm)
 if steps==1 and clip_norm is None:return model
 variables=tuple(model.trainable_variables)
 if not variables:raise TrainingContractError("gradient accumulation requires trainable variables")
 accumulators=tuple(tf.Variable(tf.zeros_like(variable),trainable=False) for variable in variables)
 counter=tf.Variable(0,dtype=tf.int32,trainable=False)
 last_microbatch_norm=tf.Variable(0.0,dtype=tf.float32,trainable=False)
 max_microbatch_norm=tf.Variable(0.0,dtype=tf.float32,trainable=False)
 last_effective_norm=tf.Variable(0.0,dtype=tf.float32,trainable=False)
 max_effective_norm=tf.Variable(0.0,dtype=tf.float32,trainable=False)
 last_applied_norm=tf.Variable(0.0,dtype=tf.float32,trainable=False)
 max_applied_norm=tf.Variable(0.0,dtype=tf.float32,trainable=False)
 clipped_update_count=tf.Variable(0,dtype=tf.int64,trainable=False)
 applied_update_count=tf.Variable(0,dtype=tf.int64,trainable=False)
 def train_step(data):
  if not isinstance(data,(tuple,list)) or len(data) not in (2,3):raise TrainingContractError("gradient accumulation requires (x, y[, sample_weight]) batches")
  x,y=data[0],data[1];sample_weight=data[2] if len(data)==3 else None
  with tf.GradientTape() as tape:
   prediction=model(x,training=True)
   loss=model.compiled_loss(y,prediction,sample_weight=sample_weight,regularization_losses=model.losses)
  gradients=tape.gradient(loss,variables)
  if any(gradient is None for gradient in gradients):raise TrainingContractError("gradient accumulation found a missing gradient")
  checked=[tf.debugging.check_numerics(gradient,"non-finite microbatch gradient") for gradient in gradients]
  microbatch_norm=tf.debugging.check_numerics(tf.cast(tf.linalg.global_norm(checked),tf.float32),"non-finite microbatch gradient global norm")
  with tf.control_dependencies(checked):updates=[accumulator.assign_add(tf.cast(gradient,accumulator.dtype)) for accumulator,gradient in zip(accumulators,gradients)]
  updates.extend((last_microbatch_norm.assign(microbatch_norm),max_microbatch_norm.assign(tf.maximum(max_microbatch_norm,microbatch_norm))))
  with tf.control_dependencies(updates):count=counter.assign_add(1)
  def apply_accumulated():
   averaged=[tf.debugging.check_numerics(accumulator/tf.cast(steps,accumulator.dtype),"non-finite accumulated gradient") for accumulator in accumulators]
   effective_norm=tf.debugging.check_numerics(tf.cast(tf.linalg.global_norm(averaged),tf.float32),"non-finite accumulated gradient global norm")
   if clip_norm is None:
    applied_gradients=averaged;was_clipped=tf.constant(False)
   else:
    applied_gradients,_=tf.clip_by_global_norm(averaged,clip_norm);was_clipped=tf.greater(effective_norm,tf.cast(clip_norm,tf.float32))
   applied_gradients=[tf.debugging.check_numerics(gradient,"non-finite applied gradient") for gradient in applied_gradients]
   applied_norm=tf.debugging.check_numerics(tf.cast(tf.linalg.global_norm(applied_gradients),tf.float32),"non-finite applied gradient global norm")
   telemetry=[last_effective_norm.assign(effective_norm),max_effective_norm.assign(tf.maximum(max_effective_norm,effective_norm)),last_applied_norm.assign(applied_norm),max_applied_norm.assign(tf.maximum(max_applied_norm,applied_norm)),clipped_update_count.assign_add(tf.cast(was_clipped,tf.int64)),applied_update_count.assign_add(1)]
   with tf.control_dependencies(telemetry):applied=model.optimizer.apply_gradients(zip(applied_gradients,variables))
   dependencies=[] if applied is None else [applied]
   with tf.control_dependencies(dependencies):resets=[accumulator.assign(tf.zeros_like(accumulator)) for accumulator in accumulators]
   with tf.control_dependencies(resets):return counter.assign(0)
  with tf.control_dependencies([count]):applied=tf.cond(tf.equal(counter,steps),apply_accumulated,lambda:tf.identity(counter))
  with tf.control_dependencies([applied]):model.compiled_metrics.update_state(y,prediction,sample_weight=sample_weight)
  return {metric.name:metric.result() for metric in model.metrics}
 model.train_step=train_step
 object.__setattr__(model,"_gradient_accumulation_state",{"steps":steps,"gradient_clip_norm":clip_norm,"counter":counter,"last_microbatch_gradient_global_norm":last_microbatch_norm,"max_microbatch_gradient_global_norm":max_microbatch_norm,"last_effective_gradient_global_norm":last_effective_norm,"max_effective_gradient_global_norm":max_effective_norm,"last_applied_gradient_global_norm":last_applied_norm,"max_applied_gradient_global_norm":max_applied_norm,"clipped_update_count":clipped_update_count,"applied_update_count":applied_update_count})
 return model
def _gradient_accumulation_metrics(model):
 state=getattr(model,"_gradient_accumulation_state",None)
 if not isinstance(state,dict):return None
 result={"gradient_accumulation_steps":state["steps"],"gradient_clip_norm":state["gradient_clip_norm"],"optimizer_iterations":int(model.optimizer.iterations.numpy()),"clipped_update_count":int(state["clipped_update_count"].numpy()),"applied_update_count":int(state["applied_update_count"].numpy())}
 for name in ("last_microbatch_gradient_global_norm","max_microbatch_gradient_global_norm","last_effective_gradient_global_norm","max_effective_gradient_global_norm","last_applied_gradient_global_norm","max_applied_gradient_global_norm"):
  value=float(state[name].numpy())
  if not np.isfinite(value):raise TrainingContractError("gradient accumulation telemetry is non-finite: "+name)
  result[name]=value
 if int(state["counter"].numpy())!=0:raise TrainingContractError("gradient accumulation ended with an incomplete effective batch")
 return result
def _validate_fit_history(history,spec,initial_epoch):
 values=getattr(history,"history",None);expected=spec["epochs"]-initial_epoch
 if not isinstance(values,dict) or not all(name in values for name in ("loss","val_loss")):raise TrainingContractError("training history is incomplete")
 lengths={len(series) for series in values.values() if isinstance(series,(list,tuple))}
 if len(lengths)!=1:
  if spec["early_stopping"] is None:raise TrainingContractError("training history must complete every requested epoch")
  raise TrainingContractError("training history metric lengths differ")
 actual=next(iter(lengths),0)
 for name,series in values.items():
  if not isinstance(series,(list,tuple)) or (len(series)!=expected if spec["early_stopping"] is None else not 1<=len(series)<=expected):
   if spec["early_stopping"] is None:raise TrainingContractError("training history must complete every requested epoch")
   raise TrainingContractError("training history epoch count violates the stage contract")
  try:finite=all(np.isfinite(float(value)) for value in series)
  except (TypeError,ValueError):finite=False
  if not finite:raise TrainingContractError("training history contains non-finite metric: "+str(name))
 return values
def _evaluations(model,sequence,stage,*,split_name="unknown",membership_hash=None,silhouette_cap=SILHOUETTE_RESERVOIR_CAP):
 if stage=="stage2":
  if not isinstance(silhouette_cap,int) or silhouette_cap<2:raise TrainingContractError("silhouette cap must be at least two")
  rng=np.random.default_rng(SILHOUETTE_RESERVOIR_SEED);features=labels=None;seen=0
  for i in range(len(sequence)):
   x,y=sequence[i];y=np.asarray(y,dtype=np.int32);pred=np.asarray(model.predict_on_batch(x))
   if pred.shape[0]!=y.size:raise TrainingContractError("prediction batch does not align with labels")
   pred=pred.reshape((pred.shape[0],-1))
   if features is None:features=np.empty((silhouette_cap,pred.shape[1]),dtype=pred.dtype);labels=np.empty((silhouette_cap,),dtype=np.int32)
   for value,label in zip(pred,y):
    target=seen if seen<silhouette_cap else int(rng.integers(0,seen+1))
    if target<silhouette_cap:features[target],labels[target]=value,label
    seen+=1
  if not seen:raise TrainingContractError("evaluation split has no batches")
  retained=min(seen,silhouette_cap)
  return {"silhouette":silhouette_metric(features[:retained],labels[:retained]),"scope":{"split":split_name,"base_epoch_membership_hash":membership_hash,"split_sample_count":seen,"evaluated_sample_count":retained,"evaluation_mode":"deterministic_uniform_reservoir","reservoir_seed":SILHOUETTE_RESERVOIR_SEED,"reservoir_cap":silhouette_cap}}
 labels=[];predictions=[]
 for i in range(len(sequence)):
  x,y=sequence[i];pred=np.asarray(model.predict_on_batch(x));y=np.asarray(y,dtype=np.int32)
  if pred.shape[0]!=y.size:raise TrainingContractError("prediction batch does not align with labels")
  labels.append(y);predictions.append(np.argmax(pred,axis=-1))
 if not labels:raise TrainingContractError("evaluation split has no batches")
 y=np.concatenate(labels);pred=np.concatenate(predictions)
 return {"classification":classification_metrics(y,pred),"scope":{"split":split_name,"base_epoch_membership_hash":membership_hash,"split_sample_count":int(y.size),"evaluated_sample_count":int(y.size),"evaluation_mode":"complete_split"}}
def sparse_categorical_focal_loss(tf, gamma=QUALITY_STAGE3_FOCAL_LOSS_GAMMA):
 if gamma!=QUALITY_STAGE3_FOCAL_LOSS_GAMMA:raise TrainingContractError("focal loss gamma must use the reviewed fixed value")
 def loss(labels,predictions):
  cross_entropy=tf.keras.losses.sparse_categorical_crossentropy(labels,predictions)
  return tf.math.pow(tf.math.maximum(0.0,1.0-tf.exp(-cross_entropy)),gamma)*cross_entropy
 return loss
def run_stage(cache,plan,protocol_id,stage,run_dir,*,parent=None,weight_decay=0.0,microbatch=128,stage2_loss_adaptation=None,initial_epoch=0,stage3_gradient_clip_norm=None,stage3_stability_adaptation_id=None,stage3_optimizer_adaptation_id=None,stage3_loss_adaptation_id=None,epochs_override=None,quality_class_weighting_id=None,quality_early_stopping_id=None,subject_normalization_id=None,train_augmentation_id=None):
 tf=_tf();from .models import build_stage1_cnn,build_stage2_supervised_contrastive,build_stage3_cnn_gru,supervised_contrastive_loss
 spec=stage_spec(protocol_id,stage,microbatch=microbatch,stage2_loss_adaptation=stage2_loss_adaptation,weight_decay=weight_decay if stage=="stage1" else None,stage3_gradient_clip_norm=stage3_gradient_clip_norm,stage3_stability_adaptation_id=stage3_stability_adaptation_id,stage3_optimizer_adaptation_id=stage3_optimizer_adaptation_id,stage3_loss_adaptation_id=stage3_loss_adaptation_id,epochs_override=epochs_override,quality_class_weighting_id=quality_class_weighting_id,quality_early_stopping_id=quality_early_stopping_id,subject_normalization_id=subject_normalization_id,train_augmentation_id=train_augmentation_id);route=route_for_stage(protocol_id,stage);checkpoint=Path(run_dir)/(stage+".weights.h5")
 if stage in ("stage2","stage3") and not parent:raise TrainingContractError(stage+" requires a validated parent checkpoint")
 if parent:
  expected="stage1" if stage=="stage2" else "stage2"
  if parent.get("stage")!=expected:raise TrainingContractError("parent stage lineage failed")
  validate_checkpoint(parent["checkpoint_path"],parent["checkpoint_hash"],parent,{"cache_hash":cache.cache_hash,"protocol_id":protocol_id,"route":route_for_stage(protocol_id,expected)})
 if stage=="stage1":
  try:import tensorflow_addons as tfa
  except ImportError as e:raise TrainingContractError("Stage1 requires TensorFlow Addons AdamW in the locked TF2.4 environment") from e
  model=build_stage1_cnn(protocol_id,input_shape=(64,64,2));opt=tfa.optimizers.AdamW(weight_decay=weight_decay,learning_rate=.05)
 elif stage=="stage2":
  s1=build_stage1_cnn(protocol_id,input_shape=(64,64,2));s1.load_weights(parent["checkpoint_path"]);model=build_stage2_supervised_contrastive(protocol_id,s1,input_shape=(64,64,2));opt=tf.keras.optimizers.SGD(.1)
 else:
  s1=build_stage1_cnn(protocol_id,input_shape=(64,64,2));s2=build_stage2_supervised_contrastive(protocol_id,s1,input_shape=(64,64,2));s2.load_weights(parent["checkpoint_path"]);model=build_stage3_cnn_gru(protocol_id,s2,input_shape=(64,64,2));validate_stage3_parameter_gate(model);opt=tf.keras.optimizers.SGD(spec["learning_rate"])
 loss=(lambda y,x:supervised_contrastive_loss(y,x,.05)) if stage=="stage2" else (sparse_categorical_focal_loss(tf) if stage3_loss_adaptation_id is not None else "sparse_categorical_crossentropy");model.compile(optimizer=opt,loss=loss,metrics=["accuracy"]);_enable_gradient_accumulation(tf,model,spec["gradient_accumulation_steps"],gradient_clip_norm=spec["gradient_clip_norm"])
 class_weights=None
 if quality_class_weighting_id is not None:
  try:weight_record=balanced_class_weights(plan.train,lambda member:cache.entry(member,route).label)
  except ValueError as error:raise TrainingContractError(str(error)) from error
  spec=dict(spec);spec["class_weighting"]=weight_record;class_weights={int(label):float(value) for label,value in weight_record["weights"].items()}
 Adapter=keras_sequence_type(tf);train=Adapter(cache,plan.train,route,microbatch,stage=="stage3",spec["drop_remainder"],spec["nominal_batch"],class_weights=class_weights,subject_normalization_id=subject_normalization_id,train_augmentation_id=train_augmentation_id);valid=Adapter(cache,plan.validation,route,microbatch,stage=="stage3",False,subject_normalization_id=subject_normalization_id)
 if not len(train) or len(train)%spec["gradient_accumulation_steps"]:raise TrainingContractError("training split cannot form complete nominal batches")
 _r17_gpu_admission(tf,run_dir,stage)
 _subject_generalization_gpu_admission(tf,run_dir,stage)
 history=model.fit(train,validation_data=valid,initial_epoch=initial_epoch,epochs=spec["epochs"],callbacks=make_callbacks(tf,spec,checkpoint),workers=1,use_multiprocessing=False,max_queue_size=1)
 validated_history=_validate_fit_history(history,spec,initial_epoch);epochs_completed=len(validated_history["loss"])
 _gradient_accumulation_metrics(model)
 if not checkpoint.is_file():raise TrainingContractError("best validation checkpoint was not written")
 model.load_weights(str(checkpoint));checkpoint_hash=sha256_file(checkpoint);split_hashes=getattr(plan,"membership_hashes",{});metrics={"validation":_evaluations(model,valid,stage,split_name="validation",membership_hash=split_hashes.get("validation")),"test":_evaluations(model,Adapter(cache,plan.test,route,microbatch,stage=="stage3",False,subject_normalization_id=subject_normalization_id),stage,split_name="test",membership_hash=split_hashes.get("test"))}
 metric_path=Path(run_dir)/(stage+".metrics.json");provenance={"schema_version":1,"protocol_id":protocol_id,"stage":stage,"route":route,"cache_hash":cache.cache_hash,"checkpoint_path":str(checkpoint),"checkpoint_sha256":checkpoint_hash,"split_membership_hashes":split_hashes,"initial_epoch":initial_epoch,"stage_spec":spec,"training_outcome":{"epochs_completed":epochs_completed,"max_epochs":spec["epochs"],"early_stopped":epochs_completed<spec["epochs"],"best_checkpoint_restored":bool(spec["early_stopping"] and spec["early_stopping"].get("restore_best_weights"))}};artifact=write_metrics_artifact(metric_path,metrics,provenance)
 return {"checkpoint_path":str(checkpoint),"checkpoint_hash":checkpoint_hash,"cache_hash":cache.cache_hash,"protocol_id":protocol_id,"stage":stage,"route":route,"history":history.history,"metrics_path":str(metric_path),"metrics":artifact,"initial_epoch":initial_epoch}
