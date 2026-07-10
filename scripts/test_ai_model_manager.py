"""Focused tests for the TimbrosaField AI model manager.

These tests do not call real package download functions.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/my_app"))

import ai_model_manager as manager  # noqa: E402


def _sleep_worker(result_queue) -> None:
    import time

    time.sleep(5)
    result_queue.put({"ok": True, "path": "late"})


class ModelManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.old_env = os.environ.get("TIMBROSA_MODELS_ROOT")
        os.environ["TIMBROSA_MODELS_ROOT"] = str(self.root)
        self._old_defs = dict(manager._MODEL_BY_ID)

    def tearDown(self) -> None:
        manager._MODEL_BY_ID.clear()
        manager._MODEL_BY_ID.update(self._old_defs)
        if self.old_env is None:
            os.environ.pop("TIMBROSA_MODELS_ROOT", None)
        else:
            os.environ["TIMBROSA_MODELS_ROOT"] = self.old_env
        self.temp_dir.cleanup()

    def _patch_definition(self, definition: manager.ModelDefinition) -> None:
        manager._MODEL_BY_ID[definition.model_id] = definition

    def test_modelroot_environment_override(self) -> None:
        self.assertEqual(manager.get_models_root(), self.root.resolve())
        self.assertEqual(manager.get_downloads_dir(), self.root.resolve() / ".downloads")
        self.assertEqual(manager.get_staging_dir(), self.root.resolve() / ".staging")

    def test_gitignore_contains_model_root(self) -> None:
        text = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/src/my_app/models/", text)

    def test_ast_validation_and_wrong_sha256(self) -> None:
        definition = manager.ModelDefinition(
            model_id="ast_audioset",
            display_name="AST test",
            backend="AST",
            version="test",
            relative_dir="ast/test",
            source="test",
            license="test",
            required_files=("config.json", "preprocessor_config.json", "model.safetensors"),
            primary_file="model.safetensors",
            primary_size=3,
            primary_sha256="bad",
        )
        self._patch_definition(definition)
        model_dir = manager.get_model_dir("ast_audioset")
        model_dir.mkdir(parents=True)
        (model_dir / "config.json").write_text("{}", encoding="utf-8")
        (model_dir / "preprocessor_config.json").write_text("{}", encoding="utf-8")
        (model_dir / "model.safetensors").write_bytes(b"abc")

        manager.validate_model("ast_audioset", full_hash=False)
        with self.assertRaises(manager.ModelCorruptError):
            manager.validate_model("ast_audioset", full_hash=True)

    def test_perch_savedmodel_validation_and_appledouble_ignored(self) -> None:
        model_dir = manager.get_model_dir(manager.PERCH_MODEL.model_id)
        for rel in manager.PERCH_MODEL.required_files:
            path = model_dir / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("x", encoding="utf-8")
        (model_dir / "._saved_model.pb").write_text("ignored", encoding="utf-8")
        (model_dir / ".DS_Store").write_text("ignored", encoding="utf-8")

        manager.validate_model(manager.PERCH_MODEL.model_id)
        source = self.root / "source"
        dest = self.root / "dest"
        shutil.copytree(model_dir, source)
        manager._copy_tree_clean(source, dest)
        self.assertFalse((dest / "._saved_model.pb").exists())
        self.assertFalse((dest / ".DS_Store").exists())

    def test_birdnet_model_size_and_labels(self) -> None:
        definition = manager.ModelDefinition(
            model_id="birdnet_acoustic",
            display_name="BirdNET test",
            backend="BirdNET",
            version="2.4",
            relative_dir="birdnet/acoustic/test",
            source="test",
            license="test",
            required_files=("model-fp32.tflite", "labels/en_us.txt"),
            primary_file="model-fp32.tflite",
            primary_size=4,
            label_file="labels/en_us.txt",
        )
        self._patch_definition(definition)
        model_dir = manager.get_model_dir("birdnet_acoustic")
        (model_dir / "labels").mkdir(parents=True)
        (model_dir / "model-fp32.tflite").write_bytes(b"1234")
        (model_dir / "labels/en_us.txt").write_text("Species\n", encoding="utf-8")
        manager.validate_model("birdnet_acoustic")
        (model_dir / "labels/en_us.txt").write_text("", encoding="utf-8")
        with self.assertRaises(manager.ModelCorruptError):
            manager.validate_model("birdnet_acoustic")

    def test_import_leaves_source_untouched_and_activates_atomically(self) -> None:
        definition = manager.ModelDefinition(
            model_id="tiny",
            display_name="Tiny",
            backend="Test",
            version="1",
            relative_dir="tiny/model",
            source="test",
            license="test",
            required_files=("file.bin",),
        )
        self._patch_definition(definition)
        source = self.root / "external-source"
        source.mkdir()
        (source / "file.bin").write_text("ok", encoding="utf-8")

        with mock.patch.object(manager, "find_existing_cache_source", return_value=source):
            activated = manager.import_existing_model("tiny")

        self.assertTrue((source / "file.bin").exists())
        self.assertEqual((activated / "file.bin").read_text(encoding="utf-8"), "ok")
        self.assertTrue((activated / "install.json").exists())

    def test_corrupt_staging_does_not_replace_active_model(self) -> None:
        definition = manager.ModelDefinition(
            model_id="tiny",
            display_name="Tiny",
            backend="Test",
            version="1",
            relative_dir="tiny/model",
            source="test",
            license="test",
            required_files=("file.bin",),
        )
        self._patch_definition(definition)
        active = manager.get_model_dir("tiny")
        active.mkdir(parents=True)
        (active / "file.bin").write_text("active", encoding="utf-8")
        staging = manager._fresh_staging("tiny")
        with self.assertRaises(manager.ModelCorruptError):
            manager._activate_staging("tiny", staging)
        self.assertEqual((active / "file.bin").read_text(encoding="utf-8"), "active")

    def test_corrupt_import_cleans_staging(self) -> None:
        definition = manager.ModelDefinition(
            model_id="tiny",
            display_name="Tiny",
            backend="Test",
            version="1",
            relative_dir="tiny/model",
            source="test",
            license="test",
            required_files=("required.bin",),
        )
        self._patch_definition(definition)
        source = self.root / "external-source"
        source.mkdir()
        (source / "wrong.bin").write_text("bad", encoding="utf-8")

        with mock.patch.object(manager, "find_existing_cache_source", return_value=source):
            with self.assertRaises(manager.ModelCorruptError):
                manager.import_existing_model("tiny")

        self.assertFalse((manager.get_staging_dir() / "tiny").exists())

    def test_child_process_timeout_is_reported(self) -> None:
        with mock.patch.object(manager, "_INSTALL_WORKER_TIMEOUT_SECONDS", 0.1):
            with self.assertRaises(manager.ModelInstallError) as ctx:
                manager._run_child_process(_sleep_worker, ())
        self.assertIn("timed out", str(ctx.exception))

    def test_backends_do_not_call_download_loaders_during_analysis(self) -> None:
        ast_source = (ROOT / "src/my_app/ai_backends/ast_backend.py").read_text(encoding="utf-8")
        perch_source = (ROOT / "src/my_app/ai_backends/perch_backend.py").read_text(encoding="utf-8")
        birdnet_source = (ROOT / "src/my_app/ai_backends/birdnet_backend.py").read_text(encoding="utf-8")

        self.assertNotIn("from_pretrained(_MODEL_ID", ast_source)
        self.assertNotIn("load_model_by_name", perch_source)
        self.assertNotIn("hub.resolve", perch_source)
        self.assertNotIn("birdnet.load(", birdnet_source)
        self.assertIn("birdnet.load_custom", birdnet_source)

    def test_model_dialog_uses_qthread_for_long_actions(self) -> None:
        from PyQt5.QtCore import QThread
        from ai_model_dialog import _InstallWorker

        self.assertTrue(issubclass(_InstallWorker, QThread))


if __name__ == "__main__":
    unittest.main()
