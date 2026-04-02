#!/usr/bin/env python3
"""Minimal runtime compatibility checks for torch and tensorflow.

Run this inside the target conda environment to see whether importing the two
ML runtimes in one Python process is stable on this machine.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Callable


def _step(label: str, fn: Callable[[], None]) -> None:
    print(f"[STEP] {label}", flush=True)
    fn()
    print(f"[OK] {label}", flush=True)


def _import_torch() -> None:
    torch = importlib.import_module("torch")
    print(f"torch={torch.__version__}", flush=True)
    mps = bool(getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
    print(f"torch.mps_available={mps}", flush=True)


def _import_tensorflow() -> None:
    tf = importlib.import_module("tensorflow")
    print(f"tensorflow={tf.__version__}", flush=True)


def _load_ast_bits() -> None:
    transformers = importlib.import_module("transformers")
    print(f"transformers={transformers.__version__}", flush=True)
    auto_feature_extractor = getattr(transformers, "AutoFeatureExtractor")
    ast_model = getattr(transformers, "ASTForAudioClassification")
    auto_feature_extractor.from_pretrained(
        "MIT/ast-finetuned-audioset-10-10-0.448",
        local_files_only=True,
    )
    ast_model.from_pretrained(
        "MIT/ast-finetuned-audioset-10-10-0.448",
        local_files_only=True,
    )
    print("AST model load: local cache ok", flush=True)


def _load_perch_bits() -> None:
    model_configs = importlib.import_module("perch_hoplite.zoo.model_configs")
    model = model_configs.load_model_by_name("perch_v2")
    print(
        f"perch_v2 sample_rate={model.sample_rate} window={model.window_size_s}",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--order",
        choices=("torch-tf", "tf-torch", "torch-only", "tf-only"),
        required=True,
        help="Import order to test inside one Python process.",
    )
    parser.add_argument(
        "--load-models",
        action="store_true",
        help="Also try loading AST and/or Perch model objects after imports.",
    )
    args = parser.parse_args()

    try:
        if args.order == "torch-tf":
            _step("import torch", _import_torch)
            _step("import tensorflow", _import_tensorflow)
        elif args.order == "tf-torch":
            _step("import tensorflow", _import_tensorflow)
            _step("import torch", _import_torch)
        elif args.order == "torch-only":
            _step("import torch", _import_torch)
        elif args.order == "tf-only":
            _step("import tensorflow", _import_tensorflow)

        if args.load_models:
            if "torch" in args.order:
                _step("load AST cached model", _load_ast_bits)
            if "tf" in args.order:
                _step("load Perch model config", _load_perch_bits)

    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] {type(exc).__name__}: {exc}", flush=True)
        return 1

    print("[DONE] runtime sequence completed", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
