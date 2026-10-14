"""Deterministic NumPy metrics and atomic metric artifacts."""
from __future__ import annotations
import hashlib,json,os,tempfile
from pathlib import Path
import numpy as np
LABELS=("W","N1","N2","N3","REM")
SILHOUETTE_DISTANCE_BLOCK_SIZE=32
SILHOUETTE_FEATURE_BLOCK_SIZE=16
def _labels(x):
    a=np.asarray(x).ravel()
    if not a.size or not np.issubdtype(a.dtype,np.number) or not np.all(np.isfinite(a)) or not np.all(a==np.floor(a)): raise ValueError("labels must be finite integral class IDs")
    a=a.astype(np.int64)
    if np.any((a<0)|(a>4)): raise ValueError("labels must be canonical class IDs")
    return a
def classification_metrics(y_true,y_pred):
    truth,predicted=_labels(y_true),_labels(y_pred)
    if truth.shape!=predicted.shape: raise ValueError("labels must align")
    matrix=np.zeros((5,5),dtype=int); np.add.at(matrix,(truth,predicted),1)
    support,tp=matrix.sum(1),np.diag(matrix); pc=matrix.sum(0)
    precision=np.divide(tp,pc,out=np.zeros(5),where=pc!=0); recall=np.divide(tp,support,out=np.zeros(5),where=support!=0)
    f1=np.divide(2*precision*recall,precision+recall,out=np.zeros(5),where=(precision+recall)!=0)
    per={n:{"precision":float(precision[i]),"recall":float(recall[i]),"f1":float(f1[i]),"support":int(support[i])} for i,n in enumerate(LABELS)}
    weighted=lambda x:float(np.average(x,weights=support))
    return {"accuracy":float(np.mean(truth==predicted)),"macro":{"precision":float(precision.mean()),"recall":float(recall.mean()),"f1":float(f1.mean())},"weighted":{"precision":weighted(precision),"recall":weighted(recall),"f1":weighted(f1)},"per_class":per,"confusion_matrix":matrix.tolist(),"n1_rem":{n:per[n] for n in ("N1","REM")}}
def silhouette_metric(embeddings,labels,*,distance_block_size=SILHOUETTE_DISTANCE_BLOCK_SIZE):
    values,y=np.asarray(embeddings,dtype=float),_labels(labels)
    if values.ndim!=2 or values.shape[0]!=y.size or not np.isfinite(values).all(): raise ValueError("embeddings and labels must align and be finite")
    if not isinstance(distance_block_size,int) or isinstance(distance_block_size,bool) or distance_block_size<1: raise ValueError("distance block size must be a positive integer")
    out={"sample_count":int(y.size),"silhouette":None,"undefined_reason":None}; classes=np.unique(y)
    if classes.size<2:out["undefined_reason"]="requires_at_least_two_classes";return out
    if y.size<=classes.size:out["undefined_reason"]="samples_must_exceed_classes";return out
    if any(np.count_nonzero(y==c)<2 for c in classes):out["undefined_reason"]="singleton_class";return out
    _,class_index=np.unique(y,return_inverse=True);counts=np.bincount(class_index,minlength=classes.size);distance_sums=np.empty((y.size,classes.size),dtype=float)
    for start in range(0,y.size,distance_block_size):
        end=min(y.size,start+distance_block_size);distances=np.zeros((end-start,y.size),dtype=float)
        for feature_start in range(0,values.shape[1],SILHOUETTE_FEATURE_BLOCK_SIZE):
            feature_end=min(values.shape[1],feature_start+SILHOUETTE_FEATURE_BLOCK_SIZE);delta=values[start:end,None,feature_start:feature_end]-values[None,:,feature_start:feature_end];distances+=np.einsum("ijk,ijk->ij",delta,delta,optimize=False)
        np.sqrt(distances,out=distances)
        if not np.isfinite(distances).all():raise ValueError("pairwise distances must be finite")
        distances[np.arange(end-start),np.arange(start,end)]=0.0
        for index in range(classes.size):distance_sums[start:end,index]=distances[:,class_index==index].sum(axis=1)
    rows=np.arange(y.size);own=distance_sums[rows,class_index]/(counts[class_index]-1);between=distance_sums/counts[None,:];between[rows,class_index]=np.inf;nearest=np.min(between,axis=1);denominator=np.maximum(own,nearest);scores=np.divide(nearest-own,denominator,out=np.zeros_like(own),where=denominator!=0)
    out["silhouette"]=float(np.mean(scores));return out
def write_metrics_artifact(path,metrics,provenance):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True); metrics_digest=hashlib.sha256(json.dumps(metrics,sort_keys=True,separators=(",",":")).encode()).hexdigest();payload={"metrics":metrics,"provenance":provenance};digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest();result={"metrics":metrics,"metrics_sha256":metrics_digest,"provenance":provenance,"artifact_sha256":digest}
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=str(path.parent));os.close(fd)
    try:Path(tmp).write_text(json.dumps(result,sort_keys=True,indent=2)+"\n");os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()
    return result
