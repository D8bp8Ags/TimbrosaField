"""Unit tests for wav_analyzer.py chunk parsing.

Captures the current, expected parsing behavior of wav_analyzer.py without
changing any file format or metadata representation. These tests use small,
synthetic WAV byte streams built by tests/fixtures/wav/builder.py — no
personal field recordings are used.
"""

from __future__ import annotations

import io

import pytest

import my_app.wav.analyzer as wa
from tests.fixtures.wav import builder as wavbuild


# ---------------------------------------------------------------------------
# read_chunks / RIFF structure
# ---------------------------------------------------------------------------


def test_read_chunks_returns_all_chunks_in_order():
    wav_bytes = wavbuild.build_wav(
        [
            wavbuild.make_fmt_chunk(),
            wavbuild.make_data_chunk(),
            wavbuild.make_unknown_chunk(b"JUNK", b"abc"),
        ]
    )
    with io.BytesIO(wav_bytes) as f:
        chunks = wa.read_chunks(f)

    assert [c[0] for c in chunks] == ["fmt ", "data", "JUNK"]


def test_read_chunks_rejects_non_riff_file():
    with io.BytesIO(b"NOTAWAVFILEHEADERBYTES") as f:
        with pytest.raises(ValueError, match="Not a valid WAVE file"):
            wa.read_chunks(f)


def test_read_chunks_handles_odd_byte_padding():
    """An odd-sized chunk must be padded on disk, and the next chunk must
    still be read at the correct, padding-adjusted offset."""
    odd_chunk = wavbuild.make_chunk(b"ODDC", b"\x01\x02\x03")  # 3 bytes -> padded to 4
    marker_chunk = wavbuild.make_unknown_chunk(b"MARK", b"after-padding")
    wav_bytes = wavbuild.build_wav(
        [wavbuild.make_fmt_chunk(), wavbuild.make_data_chunk(), odd_chunk, marker_chunk]
    )

    with io.BytesIO(wav_bytes) as f:
        chunks = wa.read_chunks(f)

    odd = next(c for c in chunks if c[0] == "ODDC")
    assert odd[1] == 3  # declared size reflects real (unpadded) data length
    assert odd[2] == b"\x01\x02\x03"

    mark = next(c for c in chunks if c[0] == "MARK")
    assert mark[2] == b"after-padding"


def test_read_chunks_truncated_chunk_returns_short_data_without_raising():
    """Current behavior: a chunk whose declared size exceeds the remaining
    file bytes is not treated as an error by read_chunks() itself — it
    silently returns whatever bytes remain. This is captured as-is; changing
    it would be a behavior change outside the scope of this test task."""
    full_wav = wavbuild.build_wav([wavbuild.make_fmt_chunk()])
    truncated = full_wav[:-4]  # cut the last 4 bytes off the fmt chunk's data

    with io.BytesIO(truncated) as f:
        chunks = wa.read_chunks(f)

    assert len(chunks) == 1
    chunk_id, declared_size, data = chunks[0]
    assert chunk_id == "fmt "
    assert declared_size == 16
    assert len(data) == 12  # shorter than declared


# ---------------------------------------------------------------------------
# fmt chunk
# ---------------------------------------------------------------------------


def test_parse_fmt_chunk_basic_pcm_fields():
    data = wavbuild.make_fmt_chunk(
        audio_format=1, num_channels=2, sample_rate=48000, bits_per_sample=24
    )[8:]  # strip chunk header, parser expects raw payload

    result = wa.parse_fmt_chunk(data)

    assert result["Audio format"] == 1
    assert result["Audio format name"] == "PCM"
    assert result["Channels"] == 2
    assert result["Sample rate"] == 48000
    assert result["Bits per sample"] == 24


def test_parse_fmt_chunk_too_short_raises_value_error():
    with pytest.raises(ValueError, match="fmt chunk too short"):
        wa.parse_fmt_chunk(b"\x00" * 10)


# ---------------------------------------------------------------------------
# cue chunk
# ---------------------------------------------------------------------------


def test_parse_cue_chunk_extracts_all_points():
    data = wavbuild.make_cue_chunk(
        [
            {"id": 1, "sample_offset": 1000},
            {"id": 2, "sample_offset": 5000},
        ]
    )[8:]

    result = wa.parse_cue_chunk(data)

    assert len(result) == 2
    assert result[0]["ID"] == 1
    assert result[0]["Sample Offset"] == 1000
    assert result[1]["ID"] == 2
    assert result[1]["Sample Offset"] == 5000


def test_parse_cue_chunk_truncated_data_returns_partial_results():
    """Current behavior: declared count exceeding available data does not
    raise — it logs a warning and returns as many complete cue points as
    fit."""
    data = wavbuild.make_cue_chunk([{"id": 1, "sample_offset": 42}])[8:]
    truncated = data[:4] + data[4:]  # header + one full 24-byte record
    # Now corrupt the declared count to claim there are 5 points.
    import struct

    corrupted = struct.pack("<I", 5) + truncated[4:]

    result = wa.parse_cue_chunk(corrupted)

    assert len(result) == 1
    assert result[0]["ID"] == 1


def test_parse_cue_chunk_too_small_returns_empty_list():
    result = wa.parse_cue_chunk(b"\x00\x00")
    assert result == []


# ---------------------------------------------------------------------------
# LIST/INFO chunk
# ---------------------------------------------------------------------------


def test_parse_list_info_chunk_extracts_fields():
    data = wavbuild.make_list_info_chunk({"INAM": "Forest Recording", "ICMT": "birds"})[8:]

    result = wa.parse_list_info_chunk(data)

    assert result["INAM"] == "Forest Recording"
    assert result["ICMT"] == "birds"


# ---------------------------------------------------------------------------
# LIST/adtl chunk (cue labels)
# ---------------------------------------------------------------------------


def test_parse_list_adtl_chunk_extracts_labels():
    data = wavbuild.make_list_adtl_chunk([(1, "Start"), (2, "Bird call")])[8:]

    result = wa.parse_list_adtl_chunk(data)

    assert result == [(1, "Start"), (2, "Bird call")]


# ---------------------------------------------------------------------------
# bext chunk
# ---------------------------------------------------------------------------


def test_parse_bext_chunk_extracts_fields():
    data = wavbuild.make_bext_chunk(
        description="Field test", originator="Tascam", coding_history="A=PCM"
    )[8:]

    result = wa.parse_bext_chunk(data)

    assert result["Description"] == "Field test"
    assert result["Originator"] == "Tascam"
    assert result["CodingHistory"] == "A=PCM"


def test_parse_bext_chunk_too_short_raises_value_error():
    with pytest.raises(ValueError, match="bext chunk too small"):
        wa.parse_bext_chunk(b"\x00" * 100)


# ---------------------------------------------------------------------------
# iXML chunk + embedded GPS
# ---------------------------------------------------------------------------


def test_parse_ixml_chunk_returns_raw_string():
    xml = "<BWFXML><LOCATION><GPS_LATITUDE>1.0</GPS_LATITUDE></LOCATION></BWFXML>"
    data = wavbuild.make_ixml_chunk(xml)[8:]

    assert wa.parse_ixml_chunk(data) == xml


def test_parse_gps_from_ixml_extracts_coordinates():
    xml = (
        "<BWFXML><LOCATION>"
        "<GPS_LATITUDE>52.37</GPS_LATITUDE>"
        "<GPS_LONGITUDE>4.9</GPS_LONGITUDE>"
        "<GPS_ALTITUDE>5.0</GPS_ALTITUDE>"
        "</LOCATION></BWFXML>"
    )

    result = wa.parse_gps_from_ixml(xml)

    assert result == {"latitude": 52.37, "longitude": 4.9, "altitude": 5.0}


def test_parse_gps_from_ixml_returns_none_for_invalid_xml():
    assert wa.parse_gps_from_ixml("not xml at all <<<") is None


def test_parse_gps_from_ixml_returns_none_when_no_location():
    assert wa.parse_gps_from_ixml("<BWFXML></BWFXML>") is None


# ---------------------------------------------------------------------------
# Unknown chunks
# ---------------------------------------------------------------------------


def test_wav_analyze_collects_unknown_chunks(write_wav):
    wav_bytes = wavbuild.build_wav(
        [
            wavbuild.make_fmt_chunk(),
            wavbuild.make_data_chunk(),
            wavbuild.make_unknown_chunk(b"JUNK", b"\x01\x02\x03"),
        ]
    )

    result = wa.wav_analyze(write_wav(wav_bytes))

    unknown = result["unknown_chunks"]
    assert len(unknown) == 1
    assert unknown[0]["id"] == "JUNK"
    assert unknown[0]["data"] == b"\x01\x02\x03"


# ---------------------------------------------------------------------------
# wav_analyze() end-to-end chunk coverage
# ---------------------------------------------------------------------------


def test_wav_analyze_full_chunk_coverage(write_wav):
    wav_bytes = wavbuild.build_wav(
        [
            wavbuild.make_fmt_chunk(sample_rate=48000),
            wavbuild.make_data_chunk(),
            wavbuild.make_cue_chunk([{"id": 1, "sample_offset": 1000}]),
            wavbuild.make_list_info_chunk({"INAM": "Test"}),
            wavbuild.make_list_adtl_chunk([(1, "Marker")]),
            wavbuild.make_bext_chunk(description="BWF test"),
            wavbuild.make_ixml_chunk(
                "<BWFXML><LOCATION><GPS_LATITUDE>1.0</GPS_LATITUDE>"
                "<GPS_LONGITUDE>2.0</GPS_LONGITUDE></LOCATION></BWFXML>"
            ),
            wavbuild.make_unknown_chunk(b"JUNK", b"xyz"),
        ]
    )

    result = wa.wav_analyze(write_wav(wav_bytes))

    assert result["fmt"]["Sample rate"] == 48000
    assert result["sample_rate"] == 48000
    assert result["cue_points"][0]["ID"] == 1
    assert result["cue_labels"] == {1: "Marker"}
    assert result["info"]["INAM"] == "Test"
    assert result["bext"]["Description"] == "BWF test"
    assert result["gps"] == {"latitude": 1.0, "longitude": 2.0, "altitude": None}
    assert result["unknown_chunks"][0]["id"] == "JUNK"
