"""Programmatic builder for small, synthetic WAV byte streams used in tests.

Deliberately independent from ``wav_analyzer.py`` (the module under test) so
that parser tests are not silently validated against their own chunk-writing
logic. Only ``struct.pack`` and plain byte concatenation are used here.

No personal field recordings or other real user data are used anywhere in
this module or its output — every fixture is synthesized from literal bytes.
"""

from __future__ import annotations

import struct

RIFF_HEADER_SIZE = 12
CHUNK_HEADER_SIZE = 8


def pad_to_even(data: bytes) -> bytes:
    """Right-pad ``data`` with one zero byte if its length is odd."""
    return data + b"\x00" if len(data) % 2 else data


def make_chunk(chunk_id: bytes, data: bytes, *, declare_odd_size: bool = False) -> bytes:
    """Build a single RIFF chunk: 4-byte id, 4-byte size (LE), data, pad byte.

    Args:
        chunk_id: Exactly 4 ASCII bytes (e.g. ``b"fmt "``).
        data: Raw chunk payload (unpadded).
        declare_odd_size: If True, the size field declares ``len(data)``
            even when that is odd (spec-correct: size reflects real data
            length, padding is a file-alignment artifact only). If False and
            ``len(data)`` is odd, the padding byte is still added on disk but
            the declared size still matches ``len(data)`` (this is what the
            WAV/RIFF spec requires either way; the flag exists only to make
            the "declared size vs. on-disk size" distinction explicit and
            testable).
    """
    assert len(chunk_id) == 4
    size = len(data)
    return chunk_id + struct.pack("<I", size) + pad_to_even(data)


def make_fmt_chunk(
    *,
    audio_format: int = 1,
    num_channels: int = 2,
    sample_rate: int = 44100,
    bits_per_sample: int = 16,
) -> bytes:
    """Build a minimal 16-byte PCM ``fmt `` chunk payload (no extension)."""
    block_align = num_channels * (bits_per_sample // 8)
    byte_rate = sample_rate * block_align
    payload = struct.pack(
        "<HHIIHH",
        audio_format,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )
    return make_chunk(b"fmt ", payload)


def make_data_chunk(sample_bytes: bytes = b"\x00\x00" * 8) -> bytes:
    """Build a ``data`` chunk with arbitrary/silent PCM sample bytes."""
    return make_chunk(b"data", sample_bytes)


def make_cue_chunk(cue_points: list[dict[str, int]]) -> bytes:
    """Build a ``cue `` chunk from a list of cue point field dicts.

    Each dict may supply ``id``, ``position``, ``chunk_id`` (as raw 4 bytes,
    defaults to ``b"data"``), ``chunk_start``, ``block_start``,
    ``sample_offset``. Missing fields default to 0 (or ``b"data"``).
    """
    payload = struct.pack("<I", len(cue_points))
    for cp in cue_points:
        chunk_id_bytes = cp.get("chunk_id", b"data")
        payload += struct.pack(
            "<IIIIII",
            cp.get("id", 0),
            cp.get("position", 0),
            struct.unpack("<I", chunk_id_bytes)[0],
            cp.get("chunk_start", 0),
            cp.get("block_start", 0),
            cp.get("sample_offset", 0),
        )
    return make_chunk(b"cue ", payload)


def make_list_info_chunk(fields: dict[str, str]) -> bytes:
    """Build a ``LIST`` chunk of type ``INFO`` from INFO-id -> text fields."""
    payload = b"INFO"
    for key, value in fields.items():
        assert len(key) == 4
        value_bytes = pad_to_even(value.encode("ascii") + b"\x00")
        payload += key.encode("ascii") + struct.pack("<I", len(value_bytes)) + value_bytes
    return make_chunk(b"LIST", payload)


def make_list_adtl_chunk(labels: list[tuple[int, str]]) -> bytes:
    """Build a ``LIST`` chunk of type ``adtl`` containing ``labl`` subchunks.

    Args:
        labels: List of (cue_id, label_text) pairs.
    """
    payload = b"adtl"
    for cue_id, text in labels:
        content = struct.pack("<I", cue_id) + text.encode("ascii") + b"\x00"
        content = pad_to_even(content)
        payload += b"labl" + struct.pack("<I", len(content)) + content
    return make_chunk(b"LIST", payload)


def make_bext_chunk(
    *,
    description: str = "",
    originator: str = "",
    originator_ref: str = "",
    origination_date: str = "",
    origination_time: str = "",
    time_ref_low: int = 0,
    time_ref_high: int = 0,
    version: int = 1,
    umid: bytes = b"\x00" * 64,
    coding_history: str = "",
) -> bytes:
    """Build a minimal 602-byte-fixed-part ``bext`` chunk."""
    fixed = struct.pack(
        "<256s32s32s10s8sIIH64s190s",
        description.encode("utf-8")[:256].ljust(256, b"\x00"),
        originator.encode("utf-8")[:32].ljust(32, b"\x00"),
        originator_ref.encode("utf-8")[:32].ljust(32, b"\x00"),
        origination_date.encode("ascii")[:10].ljust(10, b"\x00"),
        origination_time.encode("ascii")[:8].ljust(8, b"\x00"),
        time_ref_low,
        time_ref_high,
        version,
        umid[:64].ljust(64, b"\x00"),
        b"\x00" * 190,  # reserved
    )
    payload = fixed + coding_history.encode("utf-8")
    return make_chunk(b"bext", payload)


def make_ixml_chunk(xml_content: str) -> bytes:
    """Build an ``iXML`` chunk from a raw XML string (no auto-formatting)."""
    return make_chunk(b"iXML", xml_content.encode("utf-8"))


def make_unknown_chunk(chunk_id: bytes = b"JUNK", data: bytes = b"\x01\x02\x03") -> bytes:
    """Build a chunk with an id the parser does not specifically recognize."""
    return make_chunk(chunk_id, data)


def build_wav(chunks: list[bytes]) -> bytes:
    """Assemble a full RIFF/WAVE file from an ordered list of pre-built chunks."""
    body = b"WAVE" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def make_minimal_wav(
    *,
    sample_rate: int = 44100,
    num_channels: int = 2,
    bits_per_sample: int = 16,
    extra_chunks: list[bytes] | None = None,
) -> bytes:
    """Build the smallest valid WAV: RIFF/WAVE header, fmt, data, plus extras."""
    chunks = [
        make_fmt_chunk(
            sample_rate=sample_rate,
            num_channels=num_channels,
            bits_per_sample=bits_per_sample,
        ),
        make_data_chunk(),
    ]
    if extra_chunks:
        chunks.extend(extra_chunks)
    return build_wav(chunks)
