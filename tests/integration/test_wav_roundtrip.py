"""Integration test: open a WAV, read metadata, mutate it, save, re-parse.

Exercises wav_analyzer.py's parser/mutator functions together with a real
save strategy from wav_save_strategies.py against a small synthetic WAV
file, end to end — no personal field recordings, no Qt/GUI involved.
"""

from __future__ import annotations

import wav_analyzer as wa
import wav_save_strategies as wss
from tests.fixtures.wav import builder as wavbuild


def test_wav_open_edit_and_resave_roundtrip(write_wav):
    # 1. Create a small synthetic WAV with some pre-existing metadata and a
    #    cue point, resembling a minimal real field recording.
    original_cue = wavbuild.make_cue_chunk([{"id": 1, "sample_offset": 2000}])
    original_info = wavbuild.make_list_info_chunk({"INAM": "Original Name"})
    wav_bytes = wavbuild.make_minimal_wav(
        sample_rate=48000, extra_chunks=[original_cue, original_info]
    )
    source_path = write_wav(wav_bytes, name="roundtrip_source.wav")

    # 2. Read metadata with the current parser.
    before = wa.wav_analyze(source_path)
    assert before["info"]["INAM"] == "Original Name"
    assert before["cue_points"][0]["Sample Offset"] == 2000
    assert before["gps"] is None

    # 3. Adjust INFO and add iXML/GPS via the current production mutation
    #    functions (as production code does), producing an edited copy.
    new_metadata = {"INAM": "Edited In Field", "ICMT": "birds, wind"}
    edit_result = wss.WavSaveStrategies.save_as_edit_copy(
        source_path,
        new_metadata,
        gps_data={"latitude": 52.37, "longitude": 4.90, "altitude": 5.0},
    )
    assert edit_result.success is True
    saved_path = edit_result.output_path

    # 4. Re-parse the saved output.
    after = wa.wav_analyze(saved_path)

    # 5. Confirm the changed metadata is present.
    assert after["info"]["INAM"] == "Edited In Field"
    assert after["info"]["ICMT"] == "birds, wind"
    assert after["gps"] == {"latitude": 52.37, "longitude": 4.9, "altitude": 5.0}

    # 6. Confirm essential pre-existing chunks survived the save.
    assert after["fmt"]["Sample rate"] == 48000
    assert after["cue_points"][0]["Sample Offset"] == 2000

    # 7. The original source file must be untouched (edit-copy never
    #    modifies the source).
    original_after = wa.wav_analyze(source_path)
    assert original_after["info"]["INAM"] == "Original Name"
