import hashlib, json, tempfile, unittest
from pathlib import Path
import numpy as np
from unittest.mock import patch
from paper_faithful.training.cli import _lineage_checkpoint, main as cli_main
from paper_faithful.training.metrics import classification_metrics, silhouette_metric
from paper_faithful.training.cache_loader import CacheValidationError
from paper_faithful.training.splits import EpochMember
from paper_faithful.training.trainer import STAGE3_STABILITY_ADAPTATION_ID, TrainingContractError, cleanup_model_state, make_split, prepare_run, seed_model, stage_spec, transition_run, validate_checkpoint

class FakeCache:
 members=tuple(EpochMember('S%d'%i,'R%d'%i,0) for i in range(10))
class TrainerTests(unittest.TestCase):
 def test_lineage_checkpoint_drops_non_json_training_payloads(self):
  result={"checkpoint_path":"stage1.weights.h5","checkpoint_hash":"a"*64,"cache_hash":"b"*64,"protocol_id":"PAPER_TEXT_V1","stage":"stage1","route":"PAPER_PRETRAIN_V1","history":{"loss":[np.float32(1.25)]},"metrics":{"nested":np.float32(.5)}}
  lineage=_lineage_checkpoint(result)
  self.assertEqual(set(lineage),{"checkpoint_path","checkpoint_hash","cache_hash","protocol_id","stage","route"})
  self.assertEqual(json.loads(json.dumps(lineage)),lineage)
 def test_split_first_subject_and_adaptation_gates(self):
  plan=make_split(FakeCache(),'PAPER_TEXT_V1'); self.assertEqual(sum(map(len,(plan.train,plan.validation,plan.test))),10)
  subject=make_split(FakeCache(),'PAPER_TEXT_V1',subject_generalization=True,seed=1); self.assertFalse({x.subject_id for x in subject.train}&{x.subject_id for x in subject.test})
  with self.assertRaises(TrainingContractError): stage_spec('PAPER_TEXT_V1','stage2',microbatch=8)
  self.assertFalse(stage_spec('PAPER_TEXT_V1','stage2',microbatch=8,stage2_loss_adaptation='adapted_pairwise_objective')['paper_exact'])
 def test_checkpoint_resume_and_metrics(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'c'; p.write_bytes(b'x'); digest=hashlib.sha256(b'x').hexdigest(); validate_checkpoint(p,digest,parent={'checkpoint_hash':digest},expected_contract={}); self.assertRaises(TrainingContractError,validate_checkpoint,p,'0'*64)
  m=classification_metrics([0,1,4],[0,1,3]); self.assertEqual(m['confusion_matrix'][4][3],1); self.assertEqual(classification_metrics([0,1,4],[0,1,3]),m); self.assertIsNone(silhouette_metric([[1,2],[1,2]],[0,0])['silhouette'])
  with self.assertRaises(ValueError): classification_metrics([.5],[0])
  self.assertEqual(silhouette_metric([[0],[1],[2]],[0,0,1])['undefined_reason'],'singleton_class')
 def test_silhouette_is_exact_and_distance_memory_is_block_bounded(self):
  values=np.asarray([[0.,0.],[0.,1.],[1.,0.],[8.,8.],[8.,9.],[9.,8.]])
  labels=np.asarray([0,0,0,1,1,1]);distances=np.sqrt(np.maximum(0,((values[:,None,:]-values[None,:,:])**2).sum(2)));reference=[]
  for index,label in enumerate(labels):
   own=np.where(labels==label)[0];own=own[own!=index];a=np.mean(distances[index,own]);b=min(np.mean(distances[index,labels==other]) for other in np.unique(labels) if other!=label);reference.append((b-a)/max(a,b))
  with patch('paper_faithful.training.metrics.np.einsum',wraps=np.einsum) as einsum:
   actual=silhouette_metric(values,labels,distance_block_size=2)
  self.assertAlmostEqual(actual['silhouette'],float(np.mean(reference)),places=12)
  self.assertTrue(einsum.call_args_list);self.assertTrue(all(call[0][1].shape[0]<=2 and call[0][1].shape[1]==6 and call[0][1].shape[2]<=16 for call in einsum.call_args_list))
  offset=1e12+np.asarray([[0.],[1.],[10.],[11.]])
  self.assertAlmostEqual(silhouette_metric(offset,[0,0,1,1],distance_block_size=2)['silhouette'],0.899749373433584,places=12)
  spread=np.asarray([[1e12],[1e12+1],[1e12+10],[1e12+11],[-1e12],[-1e12+1]])
  self.assertAlmostEqual(silhouette_metric(spread,[0,0,1,1,2,2],distance_block_size=2)['silhouette'],0.933166248955556,places=12)
  with self.assertRaises(ValueError):silhouette_metric(values,labels,distance_block_size=0)
 def test_c_output_and_resume_contract(self):
  with self.assertRaises(ValueError): prepare_run('x',{},bulk_root=r'C:\tmp')
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'runs'/'x'
   with patch('paper_faithful.training.trainer.run_directory',return_value=root):
    directory, record=prepare_run('x',{'seed':42}); record=transition_run(directory,record,'running',last_epoch=3)
    resumed, again=prepare_run('x',{'seed':42},resume=True); self.assertEqual((resumed,again['last_epoch']),(root,3))
    with self.assertRaises(TrainingContractError): prepare_run('x',{'seed':7},resume=True)
    failure={'type':'ValueError','message':'x','fingerprint':'f'}
    failed=transition_run(root,again,'failed',failure=failure)
    self.assertEqual(failed['status'],'failed')
    with self.assertRaises(TrainingContractError): transition_run(root,failed,'completed')
 def test_author_and_paper_recipes(self):
  paper=stage_spec('PAPER_TEXT_V1','stage1',weight_decay=0.0); author=stage_spec('AUTHOR_CODE_V1','stage3')
  self.assertEqual((paper['epochs'],paper['scheduler']['factor'],paper['scheduler']['patience']),(20,.2,1))
  self.assertEqual((author['epochs'],author['scheduler']['factor'],author['scheduler']['patience'],author['scheduler']['min_lr']), (50,.5,5,1e-6))
  self.assertIsNotNone(author['early_stopping'])
  with self.assertRaises(TrainingContractError): stage_spec('PAPER_TEXT_V1','stage1')
 def test_stage3_stability_adaptation_requires_exact_binding(self):
  spec=stage_spec('PAPER_TEXT_V1','stage3',microbatch=1,stage3_gradient_clip_norm=1.0,stage3_stability_adaptation_id=STAGE3_STABILITY_ADAPTATION_ID)
  self.assertEqual((spec['learning_rate'],spec['nominal_batch'],spec['effective_batch'],spec['gradient_accumulation_steps']),(.1,128,128,128))
  self.assertEqual((spec['gradient_clip_norm'],spec['gradient_clip_application'],spec['stage3_stability_adaptation_id']),(1.0,'after_effective_batch_average_before_optimizer_step',STAGE3_STABILITY_ADAPTATION_ID))
  self.assertTrue(spec['numerical_stability_adaptation']);self.assertFalse(spec['paper_exact'])
  for value in (0.0,-1.0,0.5,2.0,float('nan'),float('inf'),True):
   with self.assertRaises(TrainingContractError):stage_spec('PAPER_TEXT_V1','stage3',microbatch=1,stage3_gradient_clip_norm=value,stage3_stability_adaptation_id=STAGE3_STABILITY_ADAPTATION_ID)
  with self.assertRaises(TrainingContractError):stage_spec('PAPER_TEXT_V1','stage3',microbatch=1,stage3_gradient_clip_norm=1.0)
  with self.assertRaises(TrainingContractError):stage_spec('PAPER_TEXT_V1','stage3',microbatch=1,stage3_stability_adaptation_id=STAGE3_STABILITY_ADAPTATION_ID)
  with self.assertRaises(TrainingContractError):stage_spec('AUTHOR_CODE_V1','stage3',microbatch=1,stage3_gradient_clip_norm=1.0,stage3_stability_adaptation_id=STAGE3_STABILITY_ADAPTATION_ID)
  with self.assertRaises(TrainingContractError):stage_spec('PAPER_TEXT_V1','stage2',microbatch=128,stage3_gradient_clip_norm=1.0,stage3_stability_adaptation_id=STAGE3_STABILITY_ADAPTATION_ID)
 def test_model_seed_and_cleanup_boundary(self):
  tf=type('TF',(),{'random':type('Random',(),{'set_seed':staticmethod(lambda seed:None)})(),'keras':type('Keras',(),{'backend':type('Backend',(),{'clear_session':staticmethod(lambda:None)})()})()})()
  with patch('paper_faithful.training.trainer._tf',return_value=tf),patch('paper_faithful.training.trainer.random.seed') as python_seed,patch('paper_faithful.training.trainer.np.random.seed') as numpy_seed,patch('paper_faithful.training.trainer.gc.collect') as collected:
   self.assertIs(seed_model(11),tf);cleanup_model_state(tf)
  python_seed.assert_called_once_with(11);numpy_seed.assert_called_once_with(11);collected.assert_called_once_with()
  with patch('paper_faithful.training.trainer._tf') as loader:
   with self.assertRaises(TrainingContractError):seed_model(-1)
   with self.assertRaises(TrainingContractError):seed_model(2**32)
  loader.assert_not_called()
  broken=type('TF',(),{'keras':type('Keras',(),{'backend':type('Backend',(),{'clear_session':staticmethod(lambda:(_ for _ in ()).throw(RuntimeError('clear failed')))})()})()})()
  with patch('paper_faithful.training.trainer.gc.collect') as collected:
   with self.assertRaisesRegex(RuntimeError,'clear failed'):cleanup_model_state(broken)
  collected.assert_called_once_with()
 def test_cli_smoke_wiring_and_full_refusal(self):
  with patch('paper_faithful.training.smoke.run',return_value={'status':'pass'}) as smoke:
   self.assertEqual(cli_main(['smoke']),0);self.assertTrue(smoke.called)
  with patch('paper_faithful.training.cli.load_canonical_cache',side_effect=CacheValidationError('bad')):
   self.assertEqual(cli_main(['full','--cache-manifest','x','--run-id','x','--bulk-root',r'C:\tmp','--cap','7','--source-manifest','x','--environment-manifest','x']),2)
 def test_standalone_stage2_cli_binds_and_uses_external_parent(self):
  cache=type('Cache',(),{'cache_hash':'a'*64,'phase2_manifest_path':Path('phase2.json'),'phase2_manifest_hash':'p'*64})()
  plan=type('Plan',(),{'seed':42,'membership_hashes':{'train':'t'*64,'validation':'v'*64,'test':'e'*64}})()
  external={'checkpoint_path':'stage1.weights.h5','checkpoint_hash':'c'*64,'cache_hash':'a'*64,'protocol_id':'PAPER_TEXT_V1','stage':'stage1','route':'PAPER_PRETRAIN_V1','metadata_path':'stage1.parent.json','metadata_hash':'m'*64}
  output={'checkpoint_path':'stage2.weights.h5','checkpoint_hash':'d'*64,'cache_hash':'a'*64,'protocol_id':'PAPER_TEXT_V1','stage':'stage2','route':'PAPER_PRETRAIN_V1','metrics_path':'stage2.metrics.json','metrics':{'artifact_sha256':'z'*64}}
  record={'status':'planned','stage_progress':{'next_stage':'stage1','last_epoch':0,'checkpoint':None,'inflight':False},'stage_artifacts':{}}
  def transition(directory,current,status,**updates):
   result=dict(current);result.update(updates);result['status']=status;return result
  with patch('paper_faithful.training.cli.load_canonical_cache',return_value=cache),patch('paper_faithful.training.cli._file_hash',return_value=('file','f'*64)),patch('paper_faithful.training.cli._external_parent',return_value=external),patch('paper_faithful.training.cli.make_split',return_value=plan),patch('paper_faithful.training.cli.cap_split_plan',return_value=plan),patch('paper_faithful.training.cli.prepare_run',return_value=(Path('E:/run'),record)) as prepared,patch('paper_faithful.training.cli.transition_run',side_effect=transition),patch('paper_faithful.training.cli.run_stage',return_value=output) as run,patch('paper_faithful.training.cli.sha256_file',return_value='h'*64):
   self.assertEqual(cli_main(['pilot','--cache-manifest','cache.json','--source-manifest','source.json','--environment-manifest','environment.json','--bulk-root','E:/bulk','--run-id','standalone-stage2','--stage','stage2','--checkpoint','stage1.weights.h5','--parent-metadata','stage1.parent.json']),0)
  self.assertEqual(run.call_args[1]['parent'],external);self.assertEqual(prepared.call_args[0][1]['external_parent'],external)
if __name__ == '__main__': unittest.main()
