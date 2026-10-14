"""Strict, read-only access to finalized SST cache artifacts."""
from __future__ import annotations
import json
import os
import hashlib
import stat
from io import BytesIO
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
import numpy as np
from numpy.lib import format as npy_format
from paper_faithful.sst.cache_manifest import ROUTES, canonical_hash, route_config, sha256_file
from paper_faithful.sst.cohort_cache import FULL_PAYLOAD_BYTES, FULL_ROUTES, load_phase2_binding
from .splits import EpochMember

class CacheValidationError(ValueError): pass
MAX_OPEN_MEMMAPS=8
MAX_CACHED_SNAPSHOT_BYTES=128*1024*1024
NPY_HEADER_BYTE_BUDGET=65536
MAX_TENSOR_SNAPSHOT_PAYLOAD_BYTES=128*1024*1024
# One epoch is at most 15 * 64 * 64 * 2 float values.  Keeping this above
# that size lets the scan use epoch-row views while bounding its temporary
# boolean array well below a full multi-epoch shard.
FINITE_SCAN_VALUES=131072
VALIDATION_RECEIPT_TYPE="FULL_CACHE_VALIDATION_RECEIPT_V1"
VALIDATION_RECEIPT_PRIOR_EVIDENCE_TYPE="FULL_CACHE_VALIDATION_RECEIPT_V1_PRIOR_EVIDENCE"
VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE="FULL_CACHE_VALIDATION_RECEIPT_V1_COMPACT_SELECTION"
VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE="FULL_CACHE_VALIDATION_RECEIPT_V1_COMPACT_SELECTION_METADATA"
RUN={"schema_version","phase2_manifest_path","phase2_manifest_sha256","completion_marker_path","completion_marker_sha256","routes","chunk_epochs","record_bindings","capacity","chunks"}
SIDE={"schema_version","record_id","subject_id","local_epoch_start","local_epoch_end_exclusive","local_epoch_indices","labels","source_path","source_sha256","config","config_sha256","tensor_file","tensor_shape","tensor_dtype","tensor_sha256","cohort_provenance"}
def _json(p):
    try: return json.loads(Path(p).read_text(encoding="utf8"))
    except (OSError,ValueError) as e: raise CacheValidationError("unreadable JSON") from e
def _path(root,p,allow_non_e=False):
    return _host_path(p,root,allow_non_e=allow_non_e)

def _lexical_path(value):
    """Normalize an already-approved host path without a filesystem resolve."""
    return Path(os.path.abspath(os.fspath(value)))

def _cache_child_path(root, value, allow_non_e=False):
    """Resolve a cache child lexically after the cache root is trusted.

    Full ``Path.resolve(strict=True)`` on every tensor and sidecar turns a
    finalized cache on WSL/DrvFS into an hours-long metadata scan.  The cache
    manifest and its approved root are still resolved strictly once; child
    paths are then normalized lexically, checked for root escape and symlinked
    leaf files, and opened/hash-checked by the existing immutable readers.
    """
    translated = _serialized_path_text(value, allow_non_e=allow_non_e)
    candidate = _lexical_path(translated)
    approved_root = _lexical_path(root)
    try:
        candidate.relative_to(approved_root)
    except ValueError as error:
        raise CacheValidationError("cache child escaped its approved root") from error
    try:
        if os.name == "nt":
            if not candidate.is_file() or candidate.is_symlink():
                raise CacheValidationError("cache child is missing or symlinked")
        else:
            # On WSL/DrvFS, separate is_file()+is_symlink() calls each issue
            # a 9p metadata round-trip.  Open once with O_NOFOLLOW and use
            # fstat on that descriptor; this preserves the regular-file and
            # symlink gate while avoiding the duplicate metadata probe.
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(candidate, flags)
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise CacheValidationError("cache child is missing or symlinked")
            finally:
                os.close(descriptor)
    except OSError as error:
        raise CacheValidationError("cache child metadata is unreadable") from error
    return candidate
def _sha(x):
    return isinstance(x,str) and len(x)==64 and all(c in "0123456789abcdef" for c in x)

def _serialized_path_text(value, host_os=None, allow_non_e=False):
    """Translate an absolute serialized path without changing provenance text."""
    if not isinstance(value,str) or not value or "\x00" in value:
        raise CacheValidationError("artifact path must be a non-empty string")
    host_os=os.name if host_os is None else host_os
    if value.startswith(("\\\\","//")):
        raise CacheValidationError("UNC/device paths are forbidden")
    windows=PureWindowsPath(value)
    if windows.drive:
        if not windows.is_absolute():
            raise CacheValidationError("drive-relative paths are forbidden")
        if windows.drive.upper()!="E:" and not allow_non_e:
            raise CacheValidationError("cache paths must use the E: drive")
        if host_os!="nt":
            if windows.drive.upper()!="E:":
                raise CacheValidationError("non-E Windows paths cannot be translated on WSL")
            return str(PurePosixPath("/mnt/e").joinpath(*windows.parts[1:]))
        return value
    if host_os=="nt":
        if not windows.is_absolute():
            raise CacheValidationError("artifact path must be absolute")
        return value
    if "\\" in value or not PurePosixPath(value).is_absolute():
        raise CacheValidationError("artifact path must be an absolute host path")
    return value

def _host_path(value,allowed_root=None,allow_non_e=False):
    try:
        translated=_serialized_path_text(value,allow_non_e=allow_non_e);resolved=Path(translated).resolve(strict=True)
        if not allow_non_e:
            if os.name=="nt":
                if resolved.drive.upper()!="E:": raise CacheValidationError("resolved cache path escaped E:")
            else:
                resolved.relative_to(Path("/mnt/e").resolve(strict=True))
        if allowed_root is not None:
            resolved.relative_to(Path(allowed_root).resolve(strict=True))
        return resolved
    except CacheValidationError:
        raise
    except (OSError,ValueError) as e:
        raise CacheValidationError("artifact missing or escapes its approved root") from e

@dataclass(frozen=True)
class CachedEpoch:
    member: EpochMember; route: str; tensor_path: Path; offset: int; label: int
@dataclass(frozen=True)
class _TensorSnapshotSpec:
    digest: str; byte_length: int; byte_budget: int; shape: tuple; dtype: np.dtype

def _tensor_byte_budget(shape):
    payload=np.dtype("float32").itemsize
    for dimension in shape: payload*=dimension
    if payload>MAX_TENSOR_SNAPSHOT_PAYLOAD_BYTES: raise CacheValidationError("tensor exceeds snapshot limit; rechunk required")
    return payload+NPY_HEADER_BYTE_BUDGET

def _read_verified_snapshot(path,spec):
    try:
        with open(str(path),"rb") as handle: data=handle.read(spec.byte_budget+1)
    except OSError as e: raise CacheValidationError("unreadable tensor") from e
    if len(data)>spec.byte_budget: raise CacheValidationError("tensor snapshot exceeds validated byte budget")
    if spec.byte_length is not None and len(data)!=spec.byte_length: raise CacheValidationError("tensor snapshot length differs")
    if hashlib.sha256(data).hexdigest()!=spec.digest: raise CacheValidationError("tensor snapshot hash differs")
    return data

def _array_from_verified_snapshot(snapshot,spec):
    try:
        source=BytesIO(snapshot);version=npy_format.read_magic(source)
        if version==(1,0): shape,fortran_order,dtype=npy_format.read_array_header_1_0(source)
        elif version in ((2,0),(3,0)): shape,fortran_order,dtype=npy_format.read_array_header_2_0(source)
        else: raise ValueError("unsupported npy version")
    except (OSError,ValueError) as e: raise CacheValidationError("unreadable tensor") from e
    expected_payload=spec.dtype.itemsize
    for dimension in spec.shape: expected_payload*=dimension
    if source.tell()>NPY_HEADER_BYTE_BUDGET or tuple(shape)!=spec.shape or np.dtype(dtype)!=spec.dtype or np.dtype(dtype).hasobject or fortran_order: raise CacheValidationError("tensor header differs from validated spec")
    if len(snapshot)-source.tell()!=expected_payload: raise CacheValidationError("tensor payload differs from validated spec")
    try: a=np.load(BytesIO(snapshot),allow_pickle=False)
    except (OSError,ValueError) as e: raise CacheValidationError("unreadable tensor") from e
    a.setflags(write=False)
    return a

class CanonicalCache:
    def __init__(self,path,entries,digest,phase2_manifest_path,phase2_manifest_hash,tensor_specs,members=None,max_open_mmaps=MAX_OPEN_MEMMAPS,max_cached_snapshot_bytes=MAX_CACHED_SNAPSHOT_BYTES):
        if isinstance(max_open_mmaps,bool) or not isinstance(max_open_mmaps,int) or max_open_mmaps<1: raise ValueError("max_open_mmaps must be positive")
        if isinstance(max_cached_snapshot_bytes,bool) or not isinstance(max_cached_snapshot_bytes,int) or max_cached_snapshot_bytes<1: raise ValueError("max_cached_snapshot_bytes must be positive")
        self.manifest_path,self.epoch_map,self.cache_hash=Path(path),dict(entries),digest
        self.phase2_manifest_path,self.phase2_manifest_hash=phase2_manifest_path,phase2_manifest_hash
        self._members=tuple(sorted(members if members is not None else {m for m,_ in self.epoch_map}))
        self._tensor_specs=dict(tensor_specs)
        self._max_open_mmaps,self._max_cached_snapshot_bytes=max_open_mmaps,max_cached_snapshot_bytes
        self._snapshot_cache=OrderedDict();self._cached_snapshot_bytes=0
    @property
    def members(self): return self._members
    def entry(self,member,route):
        try:return self.epoch_map[(member,route)]
        except KeyError as e: raise CacheValidationError("epoch absent from route") from e
    def array(self,e):
        path=e.tensor_path
        try:
            a=self._snapshot_cache.pop(path);self._cached_snapshot_bytes-=a.nbytes
        except KeyError:
            try: spec=self._tensor_specs[path]
            except KeyError as error: raise CacheValidationError("tensor was not fully validated") from error
            a=_array_from_verified_snapshot(_read_verified_snapshot(path,spec),spec)
        if a.nbytes<=self._max_cached_snapshot_bytes:
            self._snapshot_cache[path]=a;self._cached_snapshot_bytes+=a.nbytes
        while len(self._snapshot_cache)>self._max_open_mmaps or self._cached_snapshot_bytes>self._max_cached_snapshot_bytes:
            _,evicted=self._snapshot_cache.popitem(last=False);self._cached_snapshot_bytes-=evicted.nbytes
        return a
    def close(self):
        """Release cache-owned immutable snapshots without invalidating returned views."""
        self._snapshot_cache.clear();self._cached_snapshot_bytes=0
    def window(self,m,r): e=self.entry(m,r); return self.array(e)[e.offset]
    def split_windows(self,members,route):
        for m in members: e=self.entry(m,route); yield m,self.array(e)[e.offset],e.label
    def stage3_sequences(self,members,route): return self.split_windows(members,route)

def _all_finite_in_bounded_rows(a):
    """Strictly scan a validated tensor without a shard-sized boolean temporary."""
    row_values=int(np.prod(a.shape[1:],dtype=np.int64))
    rows=max(1,FINITE_SCAN_VALUES//row_values)
    for start in range(0,a.shape[0],rows):
        if not np.isfinite(a[start:start+rows]).all(): return False
    return True

def _record_bindings_digest(bindings):
    payload=json.dumps(bindings,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf8")
    return hashlib.sha256(payload).hexdigest()

def _receipt_destination(value, allow_non_e=False):
    """Normalize a new receipt path without requiring the file to exist yet."""
    translated=_serialized_path_text(str(value),allow_non_e=allow_non_e)
    candidate=_lexical_path(translated)
    if not allow_non_e:
        if os.name=="nt" and candidate.drive.upper()!="E:":
            raise CacheValidationError("receipt paths must use the E: drive")
        if os.name!="nt":
            try: candidate.relative_to(_lexical_path("/mnt/e"))
            except ValueError as error: raise CacheValidationError("receipt path escaped /mnt/e") from error
    return candidate

def _load_validation_receipt(manifest_path, run, root, destination, allow_non_e=False):
    """Load the receipt written by the separate full-cache validation process.

    The receipt is only a memory-lifecycle optimization: it is bound to the
    exact cache/Phase-2/completion artifacts and records every validated child
    artifact.  Tensor bytes are still re-hashed on first use by ``array``.
    """
    receipt_path = _host_path(str(destination), allow_non_e=allow_non_e)
    receipt = _json(receipt_path)
    base_keys = {
        "schema_version", "receipt_type", "cache_manifest_path",
        "cache_manifest_sha256", "phase2_manifest_path",
        "phase2_manifest_sha256", "completion_marker_path",
        "completion_marker_sha256", "chunks", "route_epoch_entries",
        "member_count", "record_bindings_sha256",
    }
    prior = receipt.get("receipt_type") in (
        VALIDATION_RECEIPT_PRIOR_EVIDENCE_TYPE,
        VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE,
        VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE,
    )
    compact = receipt.get("receipt_type") in (
        VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE,
        VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE,
    )
    compact_metadata = receipt.get("receipt_type") == VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE
    expected_keys = base_keys | ({
        "validation_mode", "validation_evidence_path", "validation_evidence_sha256",
    } if prior else set())
    if compact:
        expected_keys |= {
            "base_receipt_path", "base_receipt_sha256", "selection_mode",
            "selection_members_sha256", "selected_chunks",
        }
        if compact_metadata:
            expected_keys.add("selected_chunk_metadata")
    if set(receipt) != expected_keys or receipt.get("schema_version") != 1:
        raise CacheValidationError("validation receipt schema is invalid")
    if receipt.get("receipt_type") not in (
        VALIDATION_RECEIPT_TYPE,
        VALIDATION_RECEIPT_PRIOR_EVIDENCE_TYPE,
        VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE,
        VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE,
    ):
        raise CacheValidationError("validation receipt type is invalid")
    if receipt["cache_manifest_sha256"] != sha256_file(manifest_path):
        raise CacheValidationError("validation receipt cache manifest hash differs")
    if receipt["phase2_manifest_sha256"] != run["phase2_manifest_sha256"] or receipt["completion_marker_sha256"] != run["completion_marker_sha256"]:
        raise CacheValidationError("validation receipt finalized bindings differ")
    if _lexical_path(_serialized_path_text(receipt["cache_manifest_path"], allow_non_e=allow_non_e)) != _lexical_path(manifest_path):
        raise CacheValidationError("validation receipt cache path differs")
    if receipt["phase2_manifest_path"] != run["phase2_manifest_path"] or receipt["completion_marker_path"] != run["completion_marker_path"]:
        raise CacheValidationError("validation receipt provenance paths differ")
    if receipt["record_bindings_sha256"] != _record_bindings_digest(run.get("record_bindings")):
        raise CacheValidationError("validation receipt record bindings differ")
    if prior:
        if receipt["validation_mode"] != "prior_full_cache_validator_evidence":
            raise CacheValidationError("validation receipt prior-evidence mode is invalid")
        evidence_path = _host_path(receipt["validation_evidence_path"], allow_non_e=allow_non_e)
        if sha256_file(evidence_path) != receipt["validation_evidence_sha256"]:
            raise CacheValidationError("validation receipt evidence hash differs")
        valid_evidence = False
        try:
            for line in evidence_path.read_text(encoding="utf8").splitlines():
                if not line.strip():
                    continue
                event = json.loads(line)
                if (event.get("status") == "valid"
                        and event.get("cache_manifest_sha256") == receipt["cache_manifest_sha256"]
                        and event.get("phase2_manifest_sha256") == receipt["phase2_manifest_sha256"]
                        and event.get("route_epoch_entries") == receipt["route_epoch_entries"]):
                    valid_evidence = True
                    break
        except (OSError, UnicodeError, ValueError) as error:
            raise CacheValidationError("validation receipt evidence is unreadable") from error
        if not valid_evidence:
            raise CacheValidationError("validation receipt has no matching valid evidence")
    selected_chunk_keys = None
    if compact:
        if receipt["selection_mode"] != "required_members_chunk_union_v1":
            raise CacheValidationError("validation receipt compact selection mode is invalid")
        base_path = _host_path(receipt["base_receipt_path"], allow_non_e=allow_non_e)
        if sha256_file(base_path) != receipt["base_receipt_sha256"]:
            raise CacheValidationError("validation receipt base receipt hash differs")
        if not _sha(receipt["selection_members_sha256"]):
            raise CacheValidationError("validation receipt selection hash is invalid")
        if not isinstance(receipt["selected_chunks"], list) or not receipt["selected_chunks"]:
            raise CacheValidationError("validation receipt selected chunks are missing")
        selected_chunk_keys = set()
        for selected in receipt["selected_chunks"]:
            if not isinstance(selected, dict) or set(selected) != {"tensor", "sidecar"}:
                raise CacheValidationError("validation receipt selected chunk is malformed")
            if compact_metadata:
                tensor = _lexical_path(_serialized_path_text(selected["tensor"], allow_non_e=allow_non_e))
                sidecar = _lexical_path(_serialized_path_text(selected["sidecar"], allow_non_e=allow_non_e))
                try:
                    tensor.relative_to(_lexical_path(root))
                    sidecar.relative_to(_lexical_path(root))
                except ValueError as error:
                    raise CacheValidationError("validation receipt selected chunk escaped its root") from error
            else:
                tensor = _cache_child_path(root, selected["tensor"], allow_non_e=allow_non_e)
                sidecar = _cache_child_path(root, selected["sidecar"], allow_non_e=allow_non_e)
            key = (tensor, sidecar)
            if key in selected_chunk_keys:
                raise CacheValidationError("validation receipt selected chunks are duplicated")
            selected_chunk_keys.add(key)
    if not isinstance(receipt["chunks"], list) or not receipt["chunks"]:
        raise CacheValidationError("validation receipt chunks are missing")
    result = {}
    for item in receipt["chunks"]:
        if not isinstance(item, dict) or set(item) != {
            "tensor", "sidecar", "tensor_sha256", "tensor_byte_length",
            "tensor_shape", "tensor_dtype", "sidecar_sha256",
        }:
            raise CacheValidationError("validation receipt chunk is malformed")
        if compact_metadata:
            tensor = _lexical_path(_serialized_path_text(item["tensor"], allow_non_e=allow_non_e))
            sidecar = _lexical_path(_serialized_path_text(item["sidecar"], allow_non_e=allow_non_e))
            try:
                tensor.relative_to(_lexical_path(root))
                sidecar.relative_to(_lexical_path(root))
            except ValueError as error:
                raise CacheValidationError("validation receipt chunk escaped its root") from error
        else:
            tensor = _cache_child_path(root, item["tensor"], allow_non_e=allow_non_e)
            sidecar = _cache_child_path(root, item["sidecar"], allow_non_e=allow_non_e)
        if not _sha(item["tensor_sha256"]) or not _sha(item["sidecar_sha256"]):
            raise CacheValidationError("validation receipt chunk hash is invalid")
        if isinstance(item["tensor_byte_length"], bool) or not isinstance(item["tensor_byte_length"], int) or item["tensor_byte_length"] < 1:
            raise CacheValidationError("validation receipt tensor length is invalid")
        if not isinstance(item["tensor_shape"], list) or any(isinstance(x, bool) or not isinstance(x, int) or x < 1 for x in item["tensor_shape"]):
            raise CacheValidationError("validation receipt tensor shape is invalid")
        key = (tensor, sidecar)
        if key in result:
            raise CacheValidationError("validation receipt contains duplicate artifacts")
        result[key] = item
    if receipt["route_epoch_entries"] < 1 or receipt["member_count"] < 1:
        raise CacheValidationError("validation receipt counts are invalid")
    if compact and set(result) != selected_chunk_keys:
        raise CacheValidationError("validation receipt selected chunks do not match chunk records")
    selected_metadata = None
    if compact_metadata:
        raw_metadata = receipt.get("selected_chunk_metadata")
        if not isinstance(raw_metadata, list) or len(raw_metadata) != len(selected_chunk_keys):
            raise CacheValidationError("validation receipt selected chunk metadata is missing")
        selected_metadata = {}
        for item in raw_metadata:
            if not isinstance(item, dict) or set(item) != {"tensor", "sidecar", "sidecar_payload"}:
                raise CacheValidationError("validation receipt selected chunk metadata is malformed")
            tensor = _lexical_path(_serialized_path_text(item["tensor"], allow_non_e=allow_non_e))
            sidecar = _lexical_path(_serialized_path_text(item["sidecar"], allow_non_e=allow_non_e))
            key = (tensor, sidecar)
            payload = item["sidecar_payload"]
            if key not in selected_chunk_keys or key in selected_metadata or not isinstance(payload, dict) or set(payload) != SIDE:
                raise CacheValidationError("validation receipt selected chunk metadata does not match chunks")
            selected_metadata[key] = payload
        if set(selected_metadata) != selected_chunk_keys:
            raise CacheValidationError("validation receipt selected chunk metadata is incomplete")
    return {
        "chunks": result, "prior_evidence": prior, "compact_selection": compact,
        "compact_metadata": compact_metadata, "selected_chunk_keys": selected_chunk_keys,
        "selected_metadata": selected_metadata,
    }


def write_validation_receipt(cache, destination, allow_non_e=False):
    """Persist a collision-safe receipt after a full cache validation.

    This function is intentionally separate from ``load_canonical_cache`` so a
    validator process can exit before the training process starts.  The
    destination is never replaced.
    """
    path = _receipt_destination(destination, allow_non_e=allow_non_e)
    run = _json(cache.manifest_path)
    root = Path(cache.manifest_path).parent.resolve()
    chunks = []
    for chunk in run["chunks"]:
        tensor = _cache_child_path(root, chunk["tensor"], allow_non_e=allow_non_e)
        sidecar = _cache_child_path(root, chunk["sidecar"], allow_non_e=allow_non_e)
        try:
            spec = cache._tensor_specs[tensor]
        except KeyError as error:
            raise CacheValidationError("cannot receipt an unvalidated tensor") from error
        chunks.append({
            "tensor": str(tensor),
            "sidecar": str(sidecar),
            "tensor_sha256": spec.digest,
            "tensor_byte_length": spec.byte_length,
            "tensor_shape": list(spec.shape),
            "tensor_dtype": str(spec.dtype),
            "sidecar_sha256": sha256_file(sidecar),
        })
    payload = {
        "schema_version": 1,
        "receipt_type": VALIDATION_RECEIPT_TYPE,
        "cache_manifest_path": str(cache.manifest_path),
        "cache_manifest_sha256": cache.cache_hash,
        "phase2_manifest_path": cache.phase2_manifest_path,
        "phase2_manifest_sha256": cache.phase2_manifest_hash,
        "completion_marker_path": run["completion_marker_path"],
        "completion_marker_sha256": run["completion_marker_sha256"],
        "chunks": chunks,
        "route_epoch_entries": len(cache.epoch_map),
        "member_count": len(cache.members),
        "record_bindings_sha256": _record_bindings_digest(run["record_bindings"]),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise CacheValidationError("validation receipt already exists") from error
    except OSError as error:
        raise CacheValidationError("validation receipt is not writable") from error
    return path


def write_validation_receipt_from_prior_evidence(manifest_path, destination, evidence_path, allow_non_e=False):
    """Create a low-memory receipt from an unchanged prior full-validator log.

    This is Plan 2 for hosts where rehashing the already-validated full cohort
    exhausts RAM.  The prior log must contain a matching ``status=valid`` event;
    current manifest, Phase-2, completion-marker, sidecar, and tensor metadata
    bindings are still checked.  Tensor payload bytes remain fail-closed on
    first use by ``CanonicalCache.array``.
    """
    manifest_path=_host_path(str(manifest_path),allow_non_e=allow_non_e)
    evidence_path=_host_path(str(evidence_path),allow_non_e=allow_non_e)
    run=_json(manifest_path); root=manifest_path.parent.resolve()
    manifest_hash=sha256_file(manifest_path)
    evidence_hash=sha256_file(evidence_path)
    try:
        events=[json.loads(line) for line in evidence_path.read_text(encoding="utf8").splitlines() if line.strip()]
    except (OSError,UnicodeError,ValueError) as error:
        raise CacheValidationError("prior validation evidence is unreadable") from error
    matching=[event for event in events if event.get("status")=="valid" and event.get("cache_manifest_sha256")==manifest_hash and event.get("phase2_manifest_sha256")==run["phase2_manifest_sha256"]]
    if len(matching)!=1:
        raise CacheValidationError("prior validation evidence does not match current cache")
    event=matching[0]
    chunks=[]
    for chunk in run["chunks"]:
        tensor=_cache_child_path(root,chunk["tensor"],allow_non_e=allow_non_e)
        sidecar=_cache_child_path(root,chunk["sidecar"],allow_non_e=allow_non_e)
        side=_json(sidecar)
        shape=side.get("tensor_shape")
        if (set(side)!=SIDE or side.get("tensor_file")!=tensor.name or side.get("tensor_dtype")!="float32" or not _sha(side.get("tensor_sha256")) or not isinstance(shape,list)):
            raise CacheValidationError("prior-evidence sidecar metadata is invalid")
        chunks.append({
            "tensor":str(tensor), "sidecar":str(sidecar),
            "tensor_sha256":side["tensor_sha256"],
            "tensor_byte_length":tensor.stat().st_size,
            "tensor_shape":shape, "tensor_dtype":"float32",
            "sidecar_sha256":sha256_file(sidecar),
        })
    payload={
        "schema_version":1,
        "receipt_type":VALIDATION_RECEIPT_PRIOR_EVIDENCE_TYPE,
        "cache_manifest_path":str(manifest_path),
        "cache_manifest_sha256":manifest_hash,
        "phase2_manifest_path":run["phase2_manifest_path"],
        "phase2_manifest_sha256":run["phase2_manifest_sha256"],
        "completion_marker_path":run["completion_marker_path"],
        "completion_marker_sha256":run["completion_marker_sha256"],
        "chunks":chunks,
        "route_epoch_entries":event["route_epoch_entries"],
        "member_count":event["epochs"],
        "record_bindings_sha256":_record_bindings_digest(run["record_bindings"]),
        "validation_mode":"prior_full_cache_validator_evidence",
        "validation_evidence_path":str(evidence_path),
        "validation_evidence_sha256":evidence_hash,
    }
    path=_receipt_destination(destination,allow_non_e=allow_non_e)
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open("x",encoding="utf8",newline="\n") as handle:
            handle.write(json.dumps(payload,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
            handle.flush();os.fsync(handle.fileno())
    except FileExistsError as error:
        raise CacheValidationError("validation receipt already exists") from error
    except OSError as error:
        raise CacheValidationError("validation receipt is not writable") from error
    return path


def write_compact_selection_receipt_from_prior_evidence(
    manifest_path, destination, base_receipt_path, required_members, allow_non_e=False,
    include_sidecar_metadata=False, select_by_sidecar_filename=False,
):
    """Publish a create-only receipt containing only chunks needed by a plan.

    The base receipt remains the authority for the complete finalized cache.
    This derived receipt records its hash and selects whole immutable chunks by
    sidecar metadata, so WSL execution does not stat every cache child before
    the compact loader can begin.  Chunk neighbors are intentionally retained.
    """
    manifest_path = _host_path(str(manifest_path), allow_non_e=allow_non_e)
    base_receipt_path = _host_path(str(base_receipt_path), allow_non_e=allow_non_e)
    destination = _receipt_destination(destination, allow_non_e=allow_non_e)
    required_keys = {
        item.key if isinstance(item, EpochMember) else str(item)
        for item in required_members
    }
    if not required_keys:
        raise CacheValidationError("compact receipt required member set is empty")
    run = _json(manifest_path)
    root = manifest_path.parent.resolve()
    base_sha = sha256_file(base_receipt_path)
    base_state = _load_validation_receipt(
        manifest_path, run, root, base_receipt_path, allow_non_e=allow_non_e
    )
    base_chunks = base_state["chunks"]
    selected = []
    selected_metadata = []
    covered = set()

    # A Plan-16 compact receipt is built from an already hash-bound full-cache
    # receipt.  On WSL, opening every one of the many JSON sidecars merely to
    # discover its epoch range can spend hours in the Windows 9P bridge.  The
    # canonical chunk names already encode record, route, and epoch interval.
    # When explicitly enabled, use that immutable manifest metadata to reject
    # non-intersecting chunks without opening them, then still read and check
    # every selected sidecar before publishing the receipt.
    required_epochs_by_record = None
    if select_by_sidecar_filename:
        required_epochs_by_record = {}
        for key in required_keys:
            parts = key.split("/")
            if len(parts) != 3 or not all(parts) or not parts[2].isdigit():
                raise CacheValidationError("compact receipt required member key is malformed")
            subject, record_id, epoch_text = parts
            epoch = int(epoch_text)
            required_epochs_by_record.setdefault(record_id, set()).add((subject, epoch))

    def filename_intersects_required_member(serialized_sidecar):
        """Return parsed interval for a requested chunk without opening it."""

        name = PureWindowsPath(serialized_sidecar).name
        for route in FULL_ROUTES:
            marker = f".{route}."
            if marker not in name or not name.endswith(".json"):
                continue
            record_id, tail = name.rsplit(marker, 1)
            interval = tail[:-5]
            if not record_id or "-" not in interval:
                return None
            start_text, end_text = interval.split("-", 1)
            if not start_text.isdigit() or not end_text.isdigit():
                return None
            start, end = int(start_text), int(end_text)
            if end <= start:
                return None
            requested = required_epochs_by_record.get(record_id, ())
            if any(start <= epoch < end for _, epoch in requested):
                return record_id, start, end
            return None
        return None

    for chunk in run["chunks"]:
        tensor = _cache_child_path(root, chunk["tensor"], allow_non_e=allow_non_e)
        sidecar = _cache_child_path(root, chunk["sidecar"], allow_non_e=allow_non_e)
        parsed_interval = (
            filename_intersects_required_member(chunk["sidecar"])
            if required_epochs_by_record is not None else None
        )
        if required_epochs_by_record is not None and parsed_interval is None:
            continue
        side = _json(sidecar)
        rid = side.get("record_id")
        subject = side.get("subject_id")
        start = side.get("local_epoch_start")
        end = side.get("local_epoch_end_exclusive")
        if not isinstance(rid, str) or not isinstance(subject, str) or not isinstance(start, int) or not isinstance(end, int):
            raise CacheValidationError("compact receipt sidecar selection metadata is malformed")
        if parsed_interval is not None and (rid, start, end) != parsed_interval:
            raise CacheValidationError("compact receipt sidecar filename metadata disagrees")
        members = {f"{subject}/{rid}/{epoch:08d}" for epoch in range(start, end)}
        if not members & required_keys:
            continue
        key = (tensor, sidecar)
        item = base_chunks.get(key)
        if item is None:
            raise CacheValidationError("compact receipt base receipt is missing selected chunk")
        selected.append({
            "tensor": str(tensor),
            "sidecar": str(sidecar),
            "tensor_sha256": item["tensor_sha256"],
            "tensor_byte_length": item["tensor_byte_length"],
            "tensor_shape": item["tensor_shape"],
            "tensor_dtype": item["tensor_dtype"],
            "sidecar_sha256": item["sidecar_sha256"],
        })
        if include_sidecar_metadata:
            selected_metadata.append({
                "tensor": str(tensor), "sidecar": str(sidecar), "sidecar_payload": side,
            })
        covered.update(members)
    if not required_keys.issubset(covered):
        raise CacheValidationError("compact receipt selection does not cover required members")
    selected_keys = [(item["tensor"], item["sidecar"]) for item in selected]
    base_payload = _json(base_receipt_path)
    payload = {
        "schema_version": 1,
        "receipt_type": (
            VALIDATION_RECEIPT_COMPACT_SELECTION_METADATA_TYPE
            if include_sidecar_metadata else VALIDATION_RECEIPT_COMPACT_SELECTION_TYPE
        ),
        "cache_manifest_path": str(manifest_path),
        "cache_manifest_sha256": sha256_file(manifest_path),
        "phase2_manifest_path": run["phase2_manifest_path"],
        "phase2_manifest_sha256": run["phase2_manifest_sha256"],
        "completion_marker_path": run["completion_marker_path"],
        "completion_marker_sha256": run["completion_marker_sha256"],
        "chunks": selected,
        # Keep the full-evidence count so the copied prior-validator event can
        # still be matched; selected chunk counts are represented separately.
        "route_epoch_entries": base_payload["route_epoch_entries"],
        "member_count": len(covered),
        "record_bindings_sha256": _record_bindings_digest(run["record_bindings"]),
        "validation_mode": "prior_full_cache_validator_evidence",
        "validation_evidence_path": base_state.get("validation_evidence_path") or str(base_receipt_path),
        "validation_evidence_sha256": base_state.get("validation_evidence_sha256") or base_sha,
        "base_receipt_path": str(base_receipt_path),
        "base_receipt_sha256": base_sha,
        "selection_mode": "required_members_chunk_union_v1",
        "selection_members_sha256": hashlib.sha256(("\n".join(sorted(required_keys)) + "\n").encode("utf8")).hexdigest(),
        "selected_chunks": [{"tensor": tensor, "sidecar": sidecar} for tensor, sidecar in selected_keys],
    }
    if include_sidecar_metadata:
        payload["selected_chunk_metadata"] = selected_metadata
    # Preserve the evidence binding from the prior receipt rather than treating
    # the derived selection as a new full-cache validation.
    payload["validation_evidence_path"] = base_payload["validation_evidence_path"]
    payload["validation_evidence_sha256"] = base_payload["validation_evidence_sha256"]
    try:
        payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf8", newline="\n") as handle:
            handle.write(payload_text)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise CacheValidationError("validation receipt already exists") from error
    except OSError as error:
        raise CacheValidationError("validation receipt is not writable") from error
    return destination


def load_canonical_cache(manifest_path,allow_non_e=False,validated_receipt=None,required_members=None):
    manifest_path=_host_path(str(manifest_path),allow_non_e=allow_non_e); root=manifest_path.parent.resolve(); run=_json(manifest_path)
    required_keys = None if required_members is None else {
        item.key if isinstance(item, EpochMember) else str(item) for item in required_members
    }
    if required_keys is not None and not required_keys:
        raise CacheValidationError("required cache member set is empty")
    if set(run)!=RUN or run.get("schema_version")!=1 or run.get("routes")!=list(FULL_ROUTES) or not isinstance(run.get("chunk_epochs"),int) or run["chunk_epochs"]<1 or not all(_sha(run.get(k)) for k in ("phase2_manifest_sha256","completion_marker_sha256")): raise CacheValidationError("invalid full run manifest")
    phase_path=_host_path(run["phase2_manifest_path"],allow_non_e=allow_non_e);completion_path=_host_path(run["completion_marker_path"],allow_non_e=allow_non_e)
    receipt_state = _load_validation_receipt(manifest_path, run, root, validated_receipt, allow_non_e=allow_non_e) if validated_receipt is not None else None
    prior_or_receipted = receipt_state is not None
    if prior_or_receipted:
        phase = None
        phase_bindings = {
            b["record_id"]: {
                "record_id": b["record_id"], "subject_id": b["subject_id"],
                "path": b["shard_path"], "shard_sha256": b["shard_sha256"],
                "epochs": b["epochs"],
            }
            for b in run.get("record_bindings", [])
        }
    else:
        try: phase=load_phase2_binding(phase_path)
        except Exception as e: raise CacheValidationError("finalized SST Phase-2 gate rejected cache") from e
        if (_host_path(str(phase["manifest_path"]),allow_non_e=allow_non_e),phase["manifest_sha256"],_host_path(str(phase["completion_marker_path"]),allow_non_e=allow_non_e),phase["completion_marker_sha256"]) != (phase_path,run["phase2_manifest_sha256"],completion_path,run["completion_marker_sha256"]): raise CacheValidationError("Phase-2 bindings differ")
        phase_bindings={b["record_id"]:b for b in phase["bindings"]}
    serialized_bindings=run.get("record_bindings")
    if not isinstance(serialized_bindings,list) or len(serialized_bindings)!=len(phase_bindings): raise CacheValidationError("Phase-2 record bindings differ")
    if any(not isinstance(b,dict) or set(b)!={"record_id","subject_id","shard_path","shard_sha256","epochs"} for b in serialized_bindings): raise CacheValidationError("serialized record binding is malformed")
    serialized_ids=[b["record_id"] for b in serialized_bindings]
    if len(serialized_ids)!=len(set(serialized_ids)) or set(serialized_ids)!=set(phase_bindings): raise CacheValidationError("serialized record IDs are duplicate or incomplete")
    bindings=[];record_hosts={}
    for b in serialized_bindings:
        actual=phase_bindings.get(b["record_id"])
        if actual is None or (b["subject_id"],b["shard_sha256"],b["epochs"])!=(actual["subject_id"],actual["shard_sha256"],actual["epochs"]): raise CacheValidationError("Phase-2 record bindings differ")
        host=_host_path(b["shard_path"],allow_non_e=allow_non_e)
        if host!=_host_path(str(actual["path"]),allow_non_e=allow_non_e): raise CacheValidationError("Phase-2 shard path differs")
        bindings.append(b);record_hosts[b["record_id"]]=host
    if not isinstance(run["capacity"],dict) or run["capacity"].get("total_bytes")!=FULL_PAYLOAD_BYTES or set(run["capacity"].get("routes",{}))!=set(FULL_ROUTES): raise CacheValidationError("invalid full capacity")
    records={b["record_id"]:b for b in bindings}; covered={(r,t):set() for r in records for t in FULL_ROUTES}; entries={}; members={}; tensor_specs={}; declared=set(); verified_source_hashes={}
    if not isinstance(run["chunks"],list) or not run["chunks"]: raise CacheValidationError("no chunks")
    receipt_chunks = receipt_state["chunks"] if receipt_state is not None else None
    compact_selection = bool(receipt_state and receipt_state.get("compact_selection"))
    selected_chunk_keys = receipt_state.get("selected_chunk_keys") if compact_selection else None
    seen_receipt_chunks = set()
    for chunk in run["chunks"]:
        if not isinstance(chunk,dict) or set(chunk)!={"tensor","sidecar","resumed"} or type(chunk["resumed"]) is not bool: raise CacheValidationError("invalid chunk")
        if compact_selection:
            tensor_lexical = _lexical_path(_serialized_path_text(chunk["tensor"], allow_non_e=allow_non_e))
            sidecar_lexical = _lexical_path(_serialized_path_text(chunk["sidecar"], allow_non_e=allow_non_e))
            if (tensor_lexical, sidecar_lexical) not in selected_chunk_keys:
                continue
        if compact_selection and receipt_state.get("compact_metadata"):
            tensor = _lexical_path(_serialized_path_text(chunk["tensor"], allow_non_e=allow_non_e))
            sidecar = _lexical_path(_serialized_path_text(chunk["sidecar"], allow_non_e=allow_non_e))
            side = receipt_state["selected_metadata"].get((tensor, sidecar))
            if side is None:
                raise CacheValidationError("compact metadata receipt is missing selected chunk")
        else:
            tensor,sidecar=_cache_child_path(root,chunk["tensor"],allow_non_e),_cache_child_path(root,chunk["sidecar"],allow_non_e)
            side = _json(sidecar)
        if tensor in declared or sidecar in declared: raise CacheValidationError("duplicate artifact")
        declared|={tensor,sidecar}
        if set(side)!=SIDE: raise CacheValidationError("sidecar key set is not writer-exact")
        config=side.get("config")
        if not isinstance(config,dict) or not isinstance(config.get("route"),dict): raise CacheValidationError("sidecar config is malformed")
        rid,route=side["record_id"],config["route"].get("name")
        if rid not in records or route not in FULL_ROUTES or side["subject_id"]!=records[rid]["subject_id"]: raise CacheValidationError("mixed route or record")
        b=records[rid]; start,end=side["local_epoch_start"],side["local_epoch_end_exclusive"]
        if not isinstance(start,int) or not isinstance(end,int) or not 0<=start<end<=b["epochs"]: raise CacheValidationError("invalid indices/labels")
        expected_end=min(start+run["chunk_epochs"],b["epochs"])
        if start%run["chunk_epochs"] or end!=expected_end or side["local_epoch_indices"]!=list(range(start,end)) or not isinstance(side["labels"],list) or len(side["labels"])!=end-start or any(type(x)is not int or not 0<=x<=4 for x in side["labels"]): raise CacheValidationError("invalid indices/labels")
        if required_keys is not None and not any(
            f"{b['subject_id']}/{rid}/{epoch:08d}" in required_keys
            for epoch in range(start, end)
        ):
            # Compact loads still inspect every sidecar's routing/index
            # declarations, but retain tensor metadata only for chunks that
            # contain at least one requested epoch.  A chunk may contribute
            # neighboring epochs as well; the caller treats required_members
            # as a minimum selection rather than an exact chunk boundary.
            continue
        try: expected_config=route_config(ROUTES[route],side["config"]["transform_identity"])
        except Exception as e: raise CacheValidationError("invalid transform identity") from e
        if side["config"]!=expected_config or side["config_sha256"]!=canonical_hash(side["config"]): raise CacheValidationError("route config mismatch")
        p={"phase2_manifest_sha256":run["phase2_manifest_sha256"],"phase2_manifest_path":run["phase2_manifest_path"],"completion_marker_path":run["completion_marker_path"],"completion_marker_sha256":run["completion_marker_sha256"],"record_binding":b}
        if rid not in verified_source_hashes:
            verified_source_hashes[rid]=b["shard_sha256"] if prior_or_receipted else sha256_file(record_hosts[rid])
        if side["cohort_provenance"]!=p or side["source_path"]!=b["shard_path"] or side["source_sha256"]!=b["shard_sha256"] or verified_source_hashes[rid]!=b["shard_sha256"]: raise CacheValidationError("source/provenance mismatch")
        shape=[end-start,ROUTES[route].windows,64,64,2]
        if side["tensor_file"]!=tensor.name or side["tensor_shape"]!=shape or side["tensor_dtype"]!="float32" or not _sha(side["tensor_sha256"]): raise CacheValidationError("tensor metadata mismatch")
        provisional_spec=_TensorSnapshotSpec(side["tensor_sha256"],None,_tensor_byte_budget(shape),tuple(shape),np.dtype("float32"))
        if receipt_chunks is None:
            snapshot=_read_verified_snapshot(tensor,provisional_spec);spec=_TensorSnapshotSpec(side["tensor_sha256"],len(snapshot),provisional_spec.byte_budget,provisional_spec.shape,provisional_spec.dtype)
            a=_array_from_verified_snapshot(snapshot,spec)
            if list(a.shape)!=shape or a.dtype!=np.dtype("float32") or not _all_finite_in_bounded_rows(a): raise CacheValidationError("invalid tensor")
        else:
            receipt_item=receipt_chunks.get((tensor,sidecar))
            if receipt_item is None:
                raise CacheValidationError("validation receipt is incomplete")
            seen_receipt_chunks.add((tensor,sidecar))
            if receipt_item["tensor_sha256"] != side["tensor_sha256"] or tuple(receipt_item["tensor_shape"]) != tuple(shape) or receipt_item["tensor_dtype"] != "float32":
                raise CacheValidationError("validation receipt tensor metadata differs")
            if sha256_file(sidecar) != receipt_item["sidecar_sha256"]:
                raise CacheValidationError("validation receipt sidecar hash differs")
            spec=_TensorSnapshotSpec(receipt_item["tensor_sha256"],receipt_item["tensor_byte_length"],_tensor_byte_budget(shape),tuple(shape),np.dtype("float32"))
        tensor_specs[tensor]=spec
        for offset,epoch in enumerate(range(start,end)):
            if epoch in covered[(rid,route)]: raise CacheValidationError("overlap")
            covered[(rid,route)].add(epoch); key=(b["subject_id"],rid,epoch); m=members.get(key)
            if m is None: m=members[key]=EpochMember(*key)
            entries[(m,route)]=CachedEpoch(m,route,tensor,offset,side["labels"][offset])
    if required_keys is None:
        if any(s!=set(range(records[r]["epochs"])) for (r,_),s in covered.items()): raise CacheValidationError("missing coverage")
        if receipt_chunks is not None and seen_receipt_chunks != set(receipt_chunks): raise CacheValidationError("validation receipt has orphaned chunks")
        if {_lexical_path(p) for p in root.glob("*.npy")} != {_cache_child_path(root,c["tensor"],allow_non_e) for c in run["chunks"]}: raise CacheValidationError("orphan/missing tensors")
        exempt={manifest_path,phase_path,completion_path}
        if validated_receipt is not None:
            exempt.add(_host_path(str(validated_receipt),allow_non_e=allow_non_e))
        exempt_lexical={_lexical_path(p) for p in exempt}
        if {_lexical_path(p) for p in root.glob("*.json") if _lexical_path(p) not in exempt_lexical} != {_cache_child_path(root,c["sidecar"],allow_non_e) for c in run["chunks"]}: raise CacheValidationError("orphan/missing sidecars")
    else:
        loaded_keys={member.key for member in members.values()}
        if not required_keys.issubset(loaded_keys):
            raise CacheValidationError("compact cache member selection is incomplete")
    if not prior_or_receipted and any(sha256_file(record_hosts[rid])!=records[rid]["shard_sha256"] for rid in records): raise CacheValidationError("source changed during cache validation")
    return CanonicalCache(manifest_path,entries,sha256_file(manifest_path),run["phase2_manifest_path"],run["phase2_manifest_sha256"],tensor_specs,members.values())
