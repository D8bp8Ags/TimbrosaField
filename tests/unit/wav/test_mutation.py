"""Unit tests for wav_analyzer.py chunk mutation (INFO/iXML injection & removal).

Captures the current, expected mutation behavior of wav_analyzer.py without
changing any file format or metadata representation.
"""

from __future__ import annotations

import struct

import pytest

import wav_analyzer as wa
from tests.fixtures.wav import builder as wavbuild


def _riff_size(wav_bytes: bytes) -> int:
    return struct.unpack("<I", wav_bytes[4:8])[0]


# ---------------------------------------------------------------------------
# inject_info_chunk
# ---------------------------------------------------------------------------


def test_inject_info_chunk_adds_new_info(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.inject_info_chunk(source, output, {"INAM": "Forest Recording"})

    result = wa.wav_analyze(output)
    assert result["info"]["INAM"] == "Forest Recording"


def test_inject_info_chunk_replacing_existing_info(write_wav, tmp_path):
    original_info = wavbuild.make_list_info_chunk({"INAM": "Old Name"})
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[original_info]))
    output = str(tmp_path / "out.wav")

    wa.inject_info_chunk(source, output, {"INAM": "New Name"})

    result = wa.wav_analyze(output)
    # inject_info_chunk() appends a new LIST/INFO chunk; wav_analyze() keeps
    # the last one seen while iterating chunks in file order, so the new
    # value wins. Both chunks physically exist in the file (this is captured
    # as the current, existing behavior of inject_info_chunk(), not changed
    # here).
    assert result["info"]["INAM"] == "New Name"


def test_inject_info_chunk_updates_riff_size(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.inject_info_chunk(source, output, {"INAM": "X"})

    with open(output, "rb") as f:
        out_bytes = f.read()
    # RIFF size = total file size - 8 (the "RIFF" id + size field itself)
    assert _riff_size(out_bytes) == len(out_bytes) - 8


def test_inject_info_chunk_rejects_non_wave_file(tmp_path):
    bad_source = tmp_path / "not_a_wav.wav"
    bad_source.write_bytes(b"this is not a wave file at all")
    output = str(tmp_path / "out.wav")

    with pytest.raises(ValueError, match="not a valid WAVE file"):
        wa.inject_info_chunk(str(bad_source), output, {"INAM": "X"})


def test_inject_info_chunk_preserves_other_chunks(write_wav, tmp_path):
    cue = wavbuild.make_cue_chunk([{"id": 1, "sample_offset": 500}])
    bext = wavbuild.make_bext_chunk(description="Preserve me")
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[cue, bext]))
    output = str(tmp_path / "out.wav")

    wa.inject_info_chunk(source, output, {"INAM": "New"})

    result = wa.wav_analyze(output)
    assert result["cue_points"][0]["Sample Offset"] == 500
    assert result["bext"]["Description"] == "Preserve me"
    assert result["info"]["INAM"] == "New"


def test_inject_info_chunk_output_is_re_parseable(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.inject_info_chunk(source, output, {"INAM": "Reparsed"})

    with open(output, "rb") as f:
        chunks = wa.read_chunks(f)
    assert any(c[0] == "LIST" for c in chunks)


# ---------------------------------------------------------------------------
# inject_ixml_chunk
# ---------------------------------------------------------------------------


def test_inject_ixml_chunk_adds_gps_data(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.inject_ixml_chunk(source, output, {"latitude": 52.37, "longitude": 4.9})

    result = wa.wav_analyze(output)
    assert result["gps"]["latitude"] == 52.37
    assert result["gps"]["longitude"] == 4.9


def test_inject_ixml_chunk_replaces_existing_ixml(write_wav, tmp_path):
    old_ixml = wavbuild.make_ixml_chunk(
        "<BWFXML><LOCATION><GPS_LATITUDE>1.0</GPS_LATITUDE>"
        "<GPS_LONGITUDE>1.0</GPS_LONGITUDE></LOCATION></BWFXML>"
    )
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[old_ixml]))
    output = str(tmp_path / "out.wav")

    wa.inject_ixml_chunk(source, output, {"latitude": 99.0, "longitude": -99.0})

    result = wa.wav_analyze(output)
    assert result["gps"]["latitude"] == 99.0
    assert result["gps"]["longitude"] == -99.0
    # Only one iXML chunk should remain (old one dropped, not duplicated).
    with open(output, "rb") as f:
        chunks = wa.read_chunks(f)
    ixml_chunks = [c for c in chunks if c[0] == "iXML"]
    assert len(ixml_chunks) == 1


def test_inject_ixml_chunk_preserves_other_chunks(write_wav, tmp_path):
    info = wavbuild.make_list_info_chunk({"INAM": "Keep me"})
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[info]))
    output = str(tmp_path / "out.wav")

    wa.inject_ixml_chunk(source, output, {"latitude": 1.0, "longitude": 2.0})

    result = wa.wav_analyze(output)
    assert result["info"]["INAM"] == "Keep me"
    # build_ixml_chunk() defaults a missing "altitude" key to 0.0 (not None)
    # when writing the iXML GPS_ALTITUDE element, so re-parsing yields 0.0.
    assert result["gps"] == {"latitude": 1.0, "longitude": 2.0, "altitude": 0.0}


def test_inject_ixml_chunk_updates_riff_size(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.inject_ixml_chunk(source, output, {"latitude": 1.0, "longitude": 2.0})

    with open(output, "rb") as f:
        out_bytes = f.read()
    assert _riff_size(out_bytes) == len(out_bytes) - 8


def test_inject_ixml_chunk_output_is_re_parseable(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.inject_ixml_chunk(source, output, {"latitude": 1.0, "longitude": 2.0})

    with open(output, "rb") as f:
        chunks = wa.read_chunks(f)
    assert any(c[0] == "iXML" for c in chunks)


def test_inject_ixml_chunk_rejects_non_wave_file(tmp_path):
    bad_source = tmp_path / "not_a_wav.wav"
    bad_source.write_bytes(b"garbage")
    output = str(tmp_path / "out.wav")

    with pytest.raises(ValueError, match="not a valid WAVE file"):
        wa.inject_ixml_chunk(str(bad_source), output, {"latitude": 1.0, "longitude": 2.0})


# ---------------------------------------------------------------------------
# remove_ixml_chunk
# ---------------------------------------------------------------------------


def test_remove_ixml_chunk_removes_existing_ixml(write_wav, tmp_path):
    ixml = wavbuild.make_ixml_chunk(
        "<BWFXML><LOCATION><GPS_LATITUDE>1.0</GPS_LATITUDE>"
        "<GPS_LONGITUDE>2.0</GPS_LONGITUDE></LOCATION></BWFXML>"
    )
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[ixml]))
    output = str(tmp_path / "out.wav")

    wa.remove_ixml_chunk(source, output)

    result = wa.wav_analyze(output)
    assert result["ixml"] is None
    assert result["gps"] is None


def test_remove_ixml_chunk_is_noop_when_absent(write_wav, tmp_path):
    source = write_wav(wavbuild.make_minimal_wav())
    output = str(tmp_path / "out.wav")

    wa.remove_ixml_chunk(source, output)

    result = wa.wav_analyze(output)
    assert result["ixml"] is None


def test_remove_ixml_chunk_preserves_other_chunks(write_wav, tmp_path):
    ixml = wavbuild.make_ixml_chunk(
        "<BWFXML><LOCATION><GPS_LATITUDE>1.0</GPS_LATITUDE>"
        "<GPS_LONGITUDE>2.0</GPS_LONGITUDE></LOCATION></BWFXML>"
    )
    info = wavbuild.make_list_info_chunk({"INAM": "Keep me"})
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[ixml, info]))
    output = str(tmp_path / "out.wav")

    wa.remove_ixml_chunk(source, output)

    result = wa.wav_analyze(output)
    assert result["ixml"] is None
    assert result["info"]["INAM"] == "Keep me"


def test_remove_ixml_chunk_updates_riff_size(write_wav, tmp_path):
    ixml = wavbuild.make_ixml_chunk(
        "<BWFXML><LOCATION><GPS_LATITUDE>1.0</GPS_LATITUDE>"
        "<GPS_LONGITUDE>2.0</GPS_LONGITUDE></LOCATION></BWFXML>"
    )
    source = write_wav(wavbuild.make_minimal_wav(extra_chunks=[ixml]))
    output = str(tmp_path / "out.wav")

    wa.remove_ixml_chunk(source, output)

    with open(output, "rb") as f:
        out_bytes = f.read()
    assert _riff_size(out_bytes) == len(out_bytes) - 8


def test_remove_ixml_chunk_rejects_non_wave_file(tmp_path):
    bad_source = tmp_path / "not_a_wav.wav"
    bad_source.write_bytes(b"garbage")
    output = str(tmp_path / "out.wav")

    with pytest.raises(ValueError, match="not a valid WAVE file"):
        wa.remove_ixml_chunk(str(bad_source), output)
