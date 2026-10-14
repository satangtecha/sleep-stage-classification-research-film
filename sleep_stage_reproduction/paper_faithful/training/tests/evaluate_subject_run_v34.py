import argparse, hashlib, json, os
from pathlib import Path

NAMES = ("W", "N1", "N2", "N3", "REM")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_once(p, obj):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, sort_keys=True, indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
    except BaseException:
        try: p.unlink()
        except FileNotFoundError: pass
        raise

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--runs-root',required=True); ap.add_argument('--run-prefix',required=True); ap.add_argument('--destination',required=True); ap.add_argument('--protocol',required=True); args=ap.parse_args()
    root=Path(args.runs_root); children=sorted(root.glob(args.run_prefix+'-fold*-test-*'))
    if len(children)!=6: raise SystemExit(f'expected 6 children, found {len(children)}')
    rows=[]; pooled=[[0]*5 for _ in range(5)]
    for child in children:
        m=child/'stage3.metrics.json'; d=json.loads(m.read_text(encoding='utf-8')); c=d['metrics']['test']['classification']; cm=c['confusion_matrix']
        for i in range(5):
            for j in range(5): pooled[i][j]+=int(cm[i][j])
        rows.append({'subject':child.name.rsplit('-test-',1)[1], 'run_id':child.name, 'accuracy':c['accuracy'], 'macro_f1':c['macro']['f1'], 'per_class':c['per_class'], 'confusion_matrix':cm, 'metrics_path':str(m.resolve()), 'metrics_sha256':sha(m)})
    n=sum(map(sum,pooled)); correct=sum(pooled[i][i] for i in range(5)); per=[]
    for k,name in enumerate(NAMES):
        support=sum(pooled[k]); predicted=sum(pooled[i][k] for i in range(5)); tp=pooled[k][k]
        precision=tp/predicted if predicted else 0.0; recall=tp/support if support else 0.0; f1=2*precision*recall/(precision+recall) if precision+recall else 0.0
        per.append({'class':name,'support':support,'predicted':predicted,'precision':precision,'recall':recall,'f1':f1})
    out={'schema_version':1,'artifact_type':'SUBJECT_GENERALIZATION_V34_EVALUATION_V1','status':'verified','run_prefix':args.run_prefix,'protocol_path':str(Path(args.protocol).resolve()),'protocol_sha256':sha(args.protocol),'fold_count':6,'folds':rows,'aggregate':{'fold_mean_accuracy':sum(r['accuracy'] for r in rows)/6,'fold_mean_macro_f1':sum(r['macro_f1'] for r in rows)/6,'pooled_accuracy':correct/n,'pooled_macro_f1':sum(x['f1'] for x in per)/5,'pooled_support':n,'pooled_confusion_matrix':pooled,'per_class':per},'comparators':{'v17':{'accuracy':0.2526041666666667,'macro_f1':0.22196424982227989,'pooled_macro_f1':0.24312217069995556},'v11':{'accuracy':0.21875,'macro_f1':0.18838969197477892},'cpu_spectral_baseline':{'accuracy':0.16927083333333334,'macro_f1':0.12621860717198}},'interpretation':'Cap32/e6 balanced-CE quality pilot; subject-held-out and not paper-exact. Compare only against the listed same-protocol pilots.'}
    write_once(args.destination,out); print(json.dumps({'status':'created','path':str(Path(args.destination).resolve()),'sha256':sha(args.destination)},sort_keys=True))
if __name__=='__main__': main()
