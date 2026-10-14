#!/usr/bin/env bash
set -euo pipefail

bulk_root=/mnt/e/blp/sleep_stage_reproduction
runtime_root="$bulk_root/runtime"
tf_python=/home/techatat/.local/share/sleep-stage-paper/envs/tf24/bin/python
cache_manifest="$bulk_root/sst_cache/paper_faithful_v3_full_20260820/sst_full_cohort_run_manifest.json"

export LD_LIBRARY_PATH="/home/techatat/.local/share/sleep-stage-paper/envs/tf24/lib:/usr/lib/wsl/lib"
export TMPDIR="$runtime_root/training-tmp"
export XDG_CACHE_HOME="$runtime_root/xdg-cache"
export CUDA_CACHE_PATH="$runtime_root/cuda-cache"
export TF_FORCE_GPU_ALLOW_GROWTH=true
export TF_CPP_MIN_LOG_LEVEL=1
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

mkdir -p "$TMPDIR" "$XDG_CACHE_HOME" "$CUDA_CACHE_PATH"

exec "$tf_python" -u -m paper_faithful.training.cli pilot \
  --cache-manifest "$cache_manifest" \
  --protocol PAPER_TEXT_V1 \
  --stage all \
  --run-id paper-text-v1-pilot-cap128-seed42-r8-20260827 \
  --bulk-root "$bulk_root" \
  --source-manifest paper_faithful/manifests/source_manifest.json \
  --environment-manifest paper_faithful/environment/results/wsl_tf24_probe.json \
  --cap 128 \
  --weight-decay 0.0 \
  --stage1-batch 128 \
  --stage2-batch 128 \
  --stage3-batch 1
