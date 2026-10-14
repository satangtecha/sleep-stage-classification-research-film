import hashlib,io,json,os,subprocess,sys,tempfile,textwrap,unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import numpy as np
from paper_faithful.training.cache_loader import CanonicalCache,CachedEpoch,CacheValidationError,NPY_HEADER_BYTE_BUDGET,_TensorSnapshotSpec,_all_finite_in_bounded_rows,_array_from_verified_snapshot,_cache_child_path,_serialized_path_text,_tensor_byte_budget,load_canonical_cache,write_validation_receipt,write_validation_receipt_from_prior_evidence,write_compact_selection_receipt_from_prior_evidence
from paper_faithful.training.validate_cache_cli import main as validate_cache_main
from paper_faithful.sst.cache_manifest import ROUTES,canonical_hash,route_config,sha256_file
from paper_faithful.sst.cohort_cache import FULL_PAYLOAD_BYTES
class CacheLoaderTests(unittest.TestCase):
 def fixture(self,root):
  root=Path(root);phase=root/"phase.json";marker=root/"done.json";phase.write_text("{}");marker.write_text("{}");shard=root/"SC4001.npz";shard.write_bytes(b"x")
  b={"record_id":"SC4001","subject_id":"SC400","shard_path":str(shard),"shard_sha256":sha256_file(shard),"epochs":2};identity={"callable":"x","transform_source_sha256":"0"*64,"ssqueezepy":"0","numpy":"0","python":"0","n_fft":512,"frequency_bins":256,"normalization":"x","resize":"x"};chunks=[]
  for route in ROUTES:
   for start,end in ((0,1),(1,2)):
    stem=f"SC4001.{route}.{start:08d}-{end:08d}";t=root/f"{stem}.npy";np.save(t,np.zeros((end-start,ROUTES[route].windows,64,64,2),np.float32));config=route_config(ROUTES[route],identity);s={"schema_version":1,"record_id":"SC4001","subject_id":"SC400","local_epoch_start":start,"local_epoch_end_exclusive":end,"local_epoch_indices":list(range(start,end)),"labels":[0]*(end-start),"source_path":str(shard),"source_sha256":b["shard_sha256"],"config":config,"config_sha256":canonical_hash(config),"tensor_file":t.name,"tensor_shape":[end-start,ROUTES[route].windows,64,64,2],"tensor_dtype":"float32","tensor_sha256":sha256_file(t),"cohort_provenance":{"phase2_manifest_sha256":sha256_file(phase),"phase2_manifest_path":str(phase),"completion_marker_path":str(marker),"completion_marker_sha256":sha256_file(marker),"record_binding":b}};sp=t.with_suffix(".json");sp.write_text(json.dumps(s));chunks.append({"tensor":str(t),"sidecar":str(sp),"resumed":False})
  run={"schema_version":1,"phase2_manifest_path":str(phase),"phase2_manifest_sha256":sha256_file(phase),"completion_marker_path":str(marker),"completion_marker_sha256":sha256_file(marker),"routes":["PAPER_PRETRAIN_V1","PAPER_STAGE3_V1","AUTHOR_CODE_V1"],"chunk_epochs":1,"record_bindings":[b],"capacity":{"total_bytes":FULL_PAYLOAD_BYTES,"routes":{x:1 for x in ROUTES}},"chunks":chunks};p=root/"sst_full_cohort_run_manifest.json";p.write_text(json.dumps(run));return p,phase,marker,b
 def binding(self,p,phase,marker,b):return {"manifest_path":phase,"manifest_sha256":sha256_file(phase),"completion_marker_path":marker,"completion_marker_sha256":sha256_file(marker),"bindings":[{"record_id":b["record_id"],"subject_id":b["subject_id"],"path":Path(b["shard_path"]),"shard_sha256":b["shard_sha256"],"epochs":2}]}
 def test_final_gate_readonly_snapshot_and_weak_cases(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)) as gate:
    c=load_canonical_cache(p,allow_non_e=True);self.assertEqual(len(c.members),2);self.assertTrue(gate.called);self.assertIsInstance(c.array(next(iter(c.epoch_map.values()))),np.ndarray);self.assertFalse(c.array(next(iter(c.epoch_map.values()))).flags.writeable);c.close()
   data=json.loads(p.read_text());side=Path(data["chunks"][0]["sidecar"]);v=json.loads(side.read_text());v["tensor_file"]="wrong.npy";side.write_text(json.dumps(v))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaises(CacheValidationError,load_canonical_cache,p,allow_non_e=True)
 def test_cache_child_path_avoids_per_file_resolve(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);child=root/"chunk.npy";child.write_bytes(b"cache")
   with patch("paper_faithful.training.cache_loader.Path.resolve",side_effect=AssertionError("child path must not resolve")):
    self.assertEqual(_cache_child_path(root,str(child),allow_non_e=True),child)
 def test_validation_receipt_allows_fast_load_after_full_validation(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):
    cache=load_canonical_cache(p,allow_non_e=True)
    receipt=Path(d)/"validation.receipt.json"
    write_validation_receipt(cache,receipt,allow_non_e=True)
    cache.close()
    with patch("paper_faithful.training.cache_loader._read_verified_snapshot",side_effect=AssertionError("fast load must not scan tensor bytes")):
     fast=load_canonical_cache(p,allow_non_e=True,validated_receipt=receipt)
    self.assertEqual(len(fast.members),2)
    fast.close()
    with self.assertRaisesRegex(CacheValidationError,"already exists"):
     write_validation_receipt(cache,receipt,allow_non_e=True)
 def test_prior_validation_evidence_receipt_skips_phase2_rehash(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d)
   evidence=Path(d)/"prior.stdout.log"
   evidence.write_text(json.dumps({"status":"valid","cache_manifest_sha256":sha256_file(p),"phase2_manifest_sha256":sha256_file(phase),"route_epoch_entries":6,"epochs":2})+"\n")
   receipt=Path(d)/"prior.receipt.json"
   write_validation_receipt_from_prior_evidence(p,receipt,evidence,allow_non_e=True)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",side_effect=AssertionError("prior evidence must avoid phase2 rehash")),patch("paper_faithful.training.cache_loader._read_verified_snapshot",side_effect=AssertionError("prior receipt must avoid full tensor scan")):
    fast=load_canonical_cache(p,allow_non_e=True,validated_receipt=receipt)
   self.assertEqual(len(fast.members),2)
   fast.close()
 def test_compact_load_retains_only_requested_chunks(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):
    full=load_canonical_cache(p,allow_non_e=True)
    required={full.members[0].key}
    full.close()
    with patch("paper_faithful.training.cache_loader._read_verified_snapshot",wraps=__import__("paper_faithful.training.cache_loader",fromlist=["_read_verified_snapshot"])._read_verified_snapshot) as snapshot_reader:
     compact=load_canonical_cache(p,allow_non_e=True,required_members=required)
   self.assertEqual({member.key for member in compact.members},required)
   self.assertEqual(snapshot_reader.call_count,len(ROUTES))
   compact.close()
 def test_compact_selection_receipt_skips_unselected_9p_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);evidence=Path(d)/"prior.stdout.log"
   evidence.write_text(json.dumps({"status":"valid","cache_manifest_sha256":sha256_file(p),"phase2_manifest_sha256":sha256_file(phase),"route_epoch_entries":6,"epochs":2})+"\n")
   base=Path(d)/"prior.receipt.json"
   write_validation_receipt_from_prior_evidence(p,base,evidence,allow_non_e=True)
   compact_receipt=Path(d)/"compact.receipt.json"
   required={"SC400/SC4001/00000000"}
   write_compact_selection_receipt_from_prior_evidence(p,compact_receipt,base,required,allow_non_e=True)
   with patch("paper_faithful.training.cache_loader._read_verified_snapshot",side_effect=AssertionError("receipt-bound compact load must not scan tensor bytes")):
    compact=load_canonical_cache(p,allow_non_e=True,validated_receipt=compact_receipt,required_members=required)
   self.assertEqual({member.key for member in compact.members},required)
   compact.close()
 def test_fast_compact_selection_avoids_unselected_sidecar_opens(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);evidence=Path(d)/"prior.stdout.log"
   evidence.write_text(json.dumps({"status":"valid","cache_manifest_sha256":sha256_file(p),"phase2_manifest_sha256":sha256_file(phase),"route_epoch_entries":6,"epochs":2})+"\n")
   base=Path(d)/"prior.receipt.json"
   write_validation_receipt_from_prior_evidence(p,base,evidence,allow_non_e=True)
   compact_receipt=Path(d)/"fast.compact.receipt.json"
   required={"SC400/SC4001/00000000"}
   real_json=__import__("paper_faithful.training.cache_loader",fromlist=["_json"])._json
   def no_unselected_sidecars(path):
    if str(path).endswith("00000001-00000002.json"):
     raise AssertionError("fast selection must not open non-intersecting sidecars")
    return real_json(path)
   with patch("paper_faithful.training.cache_loader._json",side_effect=no_unselected_sidecars):
    write_compact_selection_receipt_from_prior_evidence(p,compact_receipt,base,required,allow_non_e=True,select_by_sidecar_filename=True)
   compact=load_canonical_cache(p,allow_non_e=True,validated_receipt=compact_receipt,required_members=required)
   self.assertEqual({member.key for member in compact.members},required)
   compact.close()
 def test_valid_data_is_shared_across_routes_and_nonfinite_tensor_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):
    cache=load_canonical_cache(p,allow_non_e=True);member=cache.members[0]
    self.assertIs(cache.entry(member,"PAPER_PRETRAIN_V1").member,cache.entry(member,"PAPER_STAGE3_V1").member)
    self.assertEqual(cache.window(member,"PAPER_PRETRAIN_V1").dtype,np.dtype("float32"));cache.close()
   run=json.loads(p.read_text());tensor=Path(run["chunks"][0]["tensor"]);payload=np.load(tensor);payload[0,0,0,0,0]=np.inf;np.save(tensor,payload)
   side=Path(run["chunks"][0]["sidecar"]);metadata=json.loads(side.read_text());metadata["tensor_sha256"]=sha256_file(tensor);side.write_text(json.dumps(metadata))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaisesRegex(CacheValidationError,"invalid tensor",load_canonical_cache,p,allow_non_e=True)
 def test_finite_scan_uses_bounded_row_views(self):
  values=np.zeros((3,15,64,64,2),dtype=np.float32);seen=[];real_isfinite=np.isfinite
  def tracked(value):seen.append(value.size);return real_isfinite(value)
  with patch("paper_faithful.training.cache_loader.np.isfinite",side_effect=tracked):self.assertTrue(_all_finite_in_bounded_rows(values))
  self.assertEqual(seen,[15*64*64*2]*3)
  values[2,0,0,0,0]=np.nan;self.assertFalse(_all_finite_in_bounded_rows(values))
 def test_snapshot_evict_and_close_preserve_retained_view_in_subprocess(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);np.save(root/"one.npy",np.asarray([[11]],dtype=np.float32));np.save(root/"two.npy",np.asarray([[22]],dtype=np.float32))
   program=textwrap.dedent("""
    import sys
    from pathlib import Path
    import hashlib
    import numpy as np
    from paper_faithful.training.cache_loader import CanonicalCache, CachedEpoch, _TensorSnapshotSpec, _tensor_byte_budget
    from paper_faithful.training.splits import EpochMember
    root=Path(sys.argv[1]); member=EpochMember('S','R',0)
    one=CachedEpoch(member,'one',root/'one.npy',0,0); two=CachedEpoch(member,'two',root/'two.npy',0,0)
    specs={path:_TensorSnapshotSpec(hashlib.sha256(path.read_bytes()).hexdigest(),len(path.read_bytes()),_tensor_byte_budget([1,1]),(1,1),np.dtype('float32')) for path in (one.tensor_path,two.tensor_path)}
    cache=CanonicalCache(root/'manifest.json',{(member,'one'):one,(member,'two'):two},'x','p','h',specs,[member],max_open_mmaps=1,max_cached_snapshot_bytes=4)
    assert cache.array(one) is cache.array(one)
    retained=cache.window(member,'one')
    cache.window(member,'two')
    assert len(cache._snapshot_cache)==1 and cache._cached_snapshot_bytes==4 and int(retained[0])==11 and not retained.flags.writeable
    cache.close()
    assert not cache._snapshot_cache and int(retained[0])==11
   """)
   environment=dict(os.environ);environment["PYTHONPATH"]=str(Path(__file__).resolve().parents[3])+os.pathsep+environment.get("PYTHONPATH","")
   result=subprocess.run([sys.executable,"-c",program,str(root)],cwd=str(Path(__file__).resolve().parents[3]),env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   self.assertEqual(result.returncode,0,result.stderr.decode("utf8",errors="replace"))
 def test_mmap_limit_rejects_bool(self):
  with self.assertRaises(ValueError):CanonicalCache("manifest.json",{},"x","p","h",{},max_open_mmaps=True)
 def test_snapshot_is_immune_to_post_read_replacement_and_future_miss_rejects(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);run=json.loads(p.read_text());tensor=Path(run["chunks"][0]["tensor"]);real_load=np.load;changed=[False]
   def replace_after_snapshot(source,*args,**kwargs):
    if isinstance(source,io.BytesIO) and not changed[0]:
     replacement=np.full((1,ROUTES["PAPER_PRETRAIN_V1"].windows,64,64,2),7,dtype=np.float32);np.save(tensor,replacement);changed[0]=True
    return real_load(source,*args,**kwargs)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):
    cache=load_canonical_cache(p,allow_non_e=True);member=cache.members[0];entry=cache.entry(member,"PAPER_PRETRAIN_V1")
    with patch("paper_faithful.training.cache_loader.np.load",side_effect=replace_after_snapshot):approved=cache.array(entry)
    self.assertTrue(changed[0]);self.assertEqual(float(approved[0,0,0,0,0]),0.0);self.assertFalse(approved.flags.writeable)
    self.assertEqual(float(cache.array(entry)[0,0,0,0,0]),0.0)
    cache._max_open_mmaps=1;cache.array(cache.entry(cache.members[1],"PAPER_PRETRAIN_V1"))
    with self.assertRaisesRegex(CacheValidationError,"snapshot hash differs"):cache.array(entry)
    cache.close()
 def test_declared_tensor_growth_is_rejected_before_unbounded_read(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);tensor=Path(json.loads(p.read_text())["chunks"][0]["tensor"])
   with open(str(tensor),"ab") as handle:handle.write(b"x"*NPY_HEADER_BYTE_BUDGET)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaisesRegex(CacheValidationError,"exceeds validated byte budget",load_canonical_cache,p,allow_non_e=True)
 def test_chunks_must_follow_writer_chunk_boundaries(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);side=Path(json.loads(p.read_text())["chunks"][0]["sidecar"]);payload=json.loads(side.read_text());payload["local_epoch_end_exclusive"]=2;payload["local_epoch_indices"]=[0,1];payload["labels"]=[0,0];side.write_text(json.dumps(payload))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaisesRegex(CacheValidationError,"invalid indices/labels",load_canonical_cache,p,allow_non_e=True)
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);run=json.loads(p.read_text());run["chunk_epochs"]=2;p.write_text(json.dumps(run))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaisesRegex(CacheValidationError,"invalid indices/labels",load_canonical_cache,p,allow_non_e=True)
 def test_malicious_npy_header_is_rejected_before_array_load(self):
  stream=io.BytesIO();np.lib.format.write_array_header_1_0(stream,{"descr":"<f4","fortran_order":False,"shape":(2**60,)})
  snapshot=stream.getvalue();spec=_TensorSnapshotSpec(hashlib.sha256(snapshot).hexdigest(),len(snapshot),len(snapshot),(1,1),np.dtype("float32"))
  with patch("paper_faithful.training.cache_loader.np.load",side_effect=AssertionError("must not allocate")):
   with self.assertRaisesRegex(CacheValidationError,"header differs"):_array_from_verified_snapshot(snapshot,spec)
 def test_malformed_npy_header_is_rejected_before_array_load(self):
  snapshot=b"\x93NUMPY\x01\x00\x00";spec=_TensorSnapshotSpec(hashlib.sha256(snapshot).hexdigest(),len(snapshot),len(snapshot),(1,1),np.dtype("float32"))
  with patch("paper_faithful.training.cache_loader.np.load",side_effect=AssertionError("must not allocate")):
   with self.assertRaisesRegex(CacheValidationError,"unreadable tensor"):_array_from_verified_snapshot(snapshot,spec)
 def test_fortran_or_extra_payload_is_rejected_before_array_load(self):
  stream=io.BytesIO();np.save(stream,np.asfortranarray(np.zeros((2,2),dtype=np.float32)));fortran=stream.getvalue();spec=_TensorSnapshotSpec(hashlib.sha256(fortran).hexdigest(),len(fortran),len(fortran),(2,2),np.dtype("float32"))
  normal=io.BytesIO();np.save(normal,np.zeros((1,1),dtype=np.float32));extra=normal.getvalue()+b"x";extra_spec=_TensorSnapshotSpec(hashlib.sha256(extra).hexdigest(),len(extra),len(extra),(1,1),np.dtype("float32"))
  with patch("paper_faithful.training.cache_loader.np.load",side_effect=AssertionError("must not allocate")):
   with self.assertRaisesRegex(CacheValidationError,"header differs"):_array_from_verified_snapshot(fortran,spec)
   with self.assertRaisesRegex(CacheValidationError,"payload differs"):_array_from_verified_snapshot(extra,extra_spec)
 def test_extra_row_config_and_provenance_rejected(self):
  for mutate in ("row","config","provenance"):
   with tempfile.TemporaryDirectory() as d:
    p,phase,marker,b=self.fixture(d);side=Path(json.loads(p.read_text())["chunks"][0]["sidecar"]);v=json.loads(side.read_text())
    if mutate=="row":v["tensor_shape"][0]=2
    elif mutate=="config":v["config"]["output_shape"][0]=99
    else:v["cohort_provenance"]["record_binding"]["epochs"]=9
    side.write_text(json.dumps(v))
    with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaises(CacheValidationError,load_canonical_cache,p,allow_non_e=True)
 def test_cross_platform_serialized_path_rules(self):
  self.assertEqual(_serialized_path_text(r"E:\blp\cache\x.npy",host_os="posix"),"/mnt/e/blp/cache/x.npy")
  for host_os in ("posix","nt"):
   for value in (r"C:\cache\x.npy",r"E:relative.npy",r"\\server\share\x.npy","relative.npy"):
    with self.subTest(host_os=host_os,value=value):self.assertRaises(CacheValidationError,_serialized_path_text,value,host_os)
  self.assertEqual(_serialized_path_text(r"C:\fixture\x.npy",host_os="nt",allow_non_e=True),r"C:\fixture\x.npy")
 def test_duplicate_or_incomplete_record_binding_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);second=Path(d)/"SC4002.npz";second.write_bytes(b"y");b2={"record_id":"SC4002","subject_id":"SC400","shard_path":str(second),"shard_sha256":sha256_file(second),"epochs":2};binding=self.binding(p,phase,marker,b);binding["bindings"].append({"record_id":b2["record_id"],"subject_id":b2["subject_id"],"path":second,"shard_sha256":b2["shard_sha256"],"epochs":2});run=json.loads(p.read_text());run["record_bindings"]=[dict(b),dict(b)];p.write_text(json.dumps(run))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=binding):self.assertRaises(CacheValidationError,load_canonical_cache,p,allow_non_e=True)
 def test_source_shard_hash_is_verified_at_start_and_final_gate_not_per_chunk(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);real_sha256_file=sha256_file;calls=[]
   def tracked_sha256_file(path):calls.append(Path(path).resolve());return real_sha256_file(path)
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)),patch("paper_faithful.training.cache_loader.sha256_file",side_effect=tracked_sha256_file):load_canonical_cache(p,allow_non_e=True)
   shard=Path(b["shard_path"]).resolve();self.assertEqual(sum(path==shard for path in calls),2)
 def test_source_shard_replacement_between_chunks_is_rejected_at_final_gate(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);shard=Path(b["shard_path"]).resolve();real_sha256_file=sha256_file;mutated=[False]
   def mutate_after_initial_source_check(path):
    path=Path(path).resolve();digest=real_sha256_file(path)
    if path==shard and not mutated[0]:shard.write_bytes(b"replacement");mutated[0]=True
    return digest
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)),patch("paper_faithful.training.cache_loader.sha256_file",side_effect=mutate_after_initial_source_check):self.assertRaisesRegex(CacheValidationError,"source changed during cache validation",load_canonical_cache,p,allow_non_e=True)
   self.assertTrue(mutated[0])
 def test_malformed_nested_config_and_validation_cli_are_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p,phase,marker,b=self.fixture(d);side=Path(json.loads(p.read_text())["chunks"][0]["sidecar"]);payload=json.loads(side.read_text());payload["config"]="malformed";side.write_text(json.dumps(payload))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,b)):self.assertRaises(CacheValidationError,load_canonical_cache,p,allow_non_e=True)
  output=io.StringIO()
  with patch("paper_faithful.training.validate_cache_cli.load_canonical_cache",side_effect=AttributeError("malformed")),redirect_stdout(output):result=validate_cache_main(["--cache-manifest",r"E:\missing.json"])
  self.assertEqual(result,2);self.assertEqual(json.loads(output.getvalue().splitlines()[-1])["status"],"invalid")
 @unittest.skipUnless(os.name!="nt" and os.environ.get("SLEEP_STAGE_TEST_E_ROOT"),"requires an explicit writable WSL E-drive test root")
 def test_windows_serialized_paths_load_under_wsl_without_rewriting_provenance(self):
  def windows(path):
   relative=Path(path).resolve().relative_to(Path("/mnt/e").resolve())
   return "E:\\"+"\\".join(relative.parts)
  with tempfile.TemporaryDirectory(dir=os.environ["SLEEP_STAGE_TEST_E_ROOT"]) as d:
   p,phase,marker,b=self.fixture(d);host_b=dict(b);run=json.loads(p.read_text());serialized_b=dict(b);serialized_b["shard_path"]=windows(b["shard_path"])
   run["phase2_manifest_path"]=windows(phase);run["completion_marker_path"]=windows(marker);run["record_bindings"]=[serialized_b]
   for chunk in run["chunks"]:
    side=Path(chunk["sidecar"]);payload=json.loads(side.read_text());payload["source_path"]=serialized_b["shard_path"];payload["cohort_provenance"]["phase2_manifest_path"]=run["phase2_manifest_path"];payload["cohort_provenance"]["completion_marker_path"]=run["completion_marker_path"];payload["cohort_provenance"]["record_binding"]=serialized_b;side.write_text(json.dumps(payload));chunk["tensor"]=windows(chunk["tensor"]);chunk["sidecar"]=windows(chunk["sidecar"])
   p.write_text(json.dumps(run))
   with patch("paper_faithful.training.cache_loader.load_phase2_binding",return_value=self.binding(p,phase,marker,host_b)) as gate:
    cache=load_canonical_cache(p);gate.assert_called_once_with(phase.resolve());self.assertEqual(cache.phase2_manifest_path,run["phase2_manifest_path"]);self.assertEqual(len(cache.members),2)
