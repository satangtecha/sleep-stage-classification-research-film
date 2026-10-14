"""Build model graphs and report parameter accounting without training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import build_stage1_cnn, build_stage2_supervised_contrastive, build_stage3_cnn_gru
from .storage import require_bulk_path


def _parameters(weights) -> int:
    return sum(int(weight.shape.num_elements()) for weight in weights)


def probe(protocol_id: str) -> dict[str, object]:
    stage1 = build_stage1_cnn(protocol_id)
    stage2 = build_stage2_supervised_contrastive(protocol_id, stage1)
    stage3 = build_stage3_cnn_gru(protocol_id, stage2)
    return {
        "protocol_id": protocol_id,
        "stage1_parameters": stage1.count_params(),
        "stage2_parameters": stage2.count_params(),
        "stage3_parameters": stage3.count_params(),
        "stage3_trainable_parameters": _parameters(stage3.trainable_weights),
        "stage3_non_trainable_parameters": _parameters(stage3.non_trainable_weights),
        "stage3_input_shape": list(stage3.input_shape),
        "stage3_output_shape": list(stage3.output_shape),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", choices=("PAPER_TEXT_V1", "AUTHOR_CODE_V1"), required=True)
    parser.add_argument("--output")
    arguments = parser.parse_args()
    result = probe(arguments.protocol)
    if arguments.output:
        destination = require_bulk_path(arguments.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
