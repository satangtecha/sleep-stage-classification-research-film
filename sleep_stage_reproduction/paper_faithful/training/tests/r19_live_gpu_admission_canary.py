import json
import os
from pathlib import Path

import tensorflow as tf

from paper_faithful.training.trainer import _r17_gpu_admission


root = Path(os.environ["PAPER_FAITHFUL_R17_GPU_ADMISSION_ROOT"])
prefix = os.environ["PAPER_FAITHFUL_R17_RUN_PREFIX"]
run_dir = root / (prefix + "-split42-model42")
_r17_gpu_admission(tf, run_dir, "stage1")
print(json.dumps({"status": "pass", "run_id": run_dir.name, "training_started": False, "pilot_launched": False}, sort_keys=True))


