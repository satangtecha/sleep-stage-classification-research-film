#!/usr/bin/env bash
# r15 is single-exec: the Windows Task Scheduler-owned supervisor supplies the immutable binding.
set -euo pipefail
bulk_root=/mnt/e/blp/sleep_stage_reproduction
runtime_root="$bulk_root/runtime"
tf_python=/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python
cache_manifest="$bulk_root/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json"
prefix=paper-text-v1-multiseed-cap128-r15-20260831
[[ -x "$tf_python" ]] || { echo 'Locked TF2.4 Python is unavailable' >&2; exit 70; }
[[ -f "$cache_manifest" ]] || { echo 'Cache manifest is unavailable' >&2; exit 71; }
[[ -f "$runtime_root/integrity-logs/full-cache-validation-v2.stdout.log" ]] || { echo 'Strict cache validator evidence is unavailable' >&2; exit 72; }
export LD_LIBRARY_PATH="/home/techatat/.local/share/sleep-stage-paper/envs/tf24/lib:/usr/lib/wsl/lib"
export TMPDIR="$runtime_root/training-tmp" XDG_CACHE_HOME="$runtime_root/xdg-cache" CUDA_CACHE_PATH="$runtime_root/cuda-cache"
export TF_FORCE_GPU_ALLOW_GROWTH=true TF_CPP_MIN_LOG_LEVEL=1 PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$CUDA_CACHE_PATH"
exec "$tf_python" -u -m paper_faithful.training.cli multi-seed-pilot \
  --cache-manifest "$cache_manifest" --source-manifest paper_faithful/manifests/source_manifest.json \
  --environment-manifest paper_faithful/environment/results/wsl_tf24_probe.json --bulk-root "$bulk_root" \
  --run-id-prefix "$prefix" --seeds 42 43 --cap 128 --weight-decay 0.0 \
  --stage3-gradient-clip-norm 1.0 --stage3-stability-adaptation-id PAPER_TEXT_STAGE3_GLOBAL_NORM_CLIP_V1
