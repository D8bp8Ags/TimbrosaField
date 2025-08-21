"""WAV File Analyzer for Field Recording Applications.

This module provides comprehensive analysis of WAV audio files, including:
- Audio format information (PCM, float, etc.)
- Cue point extraction and timing analysis
- Broadcast Wave Format (BWF) metadata parsing
- LIST-INFO chunk processing for general metadata
- iXML chunk support for production metadata
- Metadata injection capabilities

The analyzer is designed specifically for field recording workflows where
detailed metadata and cue point information is crucial for organization
and post-production.

Basic usage:
    result = wav_analyze('recording.wav')
    print_analysis(result)

Adding metadata:
    metadata = {'INAM': 'Field Recording', 'ICMT': 'forest, birds, wind'}
    inject_info_chunk('input.wav', 'output.wav', metadata)
"""

import logging
import os
import struct
from typing import Any

# Configure logging
logging.basicConfig(
    level=getattr(
        logging,
        os.getenv("LOG_LEVEL", "DEBUG").upper(),
        logging.INFO,
    ),
    format="[%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# Supported audio formats in fmt-chunk
AUDIO_FORMATS = {
    0x0001: "PCM",
    0x0003: "IEEE float",
    0x0006: "A-law",
    0x0007: "Mu-law",
    0xFFFE: "Extensible",
}


def pad_to_even(data: bytes) -> bytes:
    """Add padding byte to data if length is odd.

    WAV file format requires even-byte alignment for chunks.

    Args:     data: Input bytes to potentially pad.

    Returns:     Padded bytes with even length.
    """
    return data + b"\x00" if len(data) % 2 else data


def create_info_chunk(metadata: dict[str, str | bytes]) -> bytes:
    """Create a LIST-INFO chunk from metadata dictionary.

    Constructs a properly formatted LIST-INFO chunk that can be injected
    into WAV files to store general metadata information.

    Args:
        metadata: Dictionary containing metadata key-value pairs.
                 Keys should be 4-character INFO identifiers (INAM, ICMT, etc.).
                 Values can be strings or bytes.

    Returns:
        Complete LIST-INFO chunk as bytes, ready for file injection.

    Usage:
        metadata = {'INAM': 'Recording Name', 'ICMT': 'forest, birds'}
        chunk = create_info_chunk(metadata)
    """
    subchunks = b""

    for key, value in metadata.items():
        # Convert string values to UTF-8 bytes
        if isinstance(value, str):
            value_bytes = value.encode("utf-8")
        else:
            value_bytes = value

        value_padded = pad_to_even(value_bytes)
        subchunk = (
            key.encode("ascii") + struct.pack("<I", len(value_padded)) + value_padded
        )
        subchunks += subchunk

    # Create complete LIST chunk with INFO type
    list_chunk = b"LIST" + struct.pack("<I", len(subchunks) + 4) + b"INFO" + subchunks
    return list_chunk


def inject_info_chunk(
    wav_path: str, output_path: str, metadata: dict[str, str | bytes]
) -> None:
    """Inject LIST-INFO chunk into existing WAV file.

    Adds metadata to a WAV file by appending a LIST-INFO chunk.
    Updates the RIFF size accordingly to maintain file validity.

    Args:
        wav_path: Path to input WAV file.
        output_path: Path for output WAV file with metadata.
        metadata: Dictionary of metadata to inject.

    Raises:
        ValueError: If input file is not a valid WAVE file.

    Usage:
        metadata = {
            'INAM': 'Forest Recording',
            'IART': 'Field Recorder',
            'ICMT': 'birds, wind, morning'
        }
        inject_info_chunk('input.wav', 'tagged.wav', metadata)
    """
    with open(wav_path, "rb") as f:
        wav_data = f.read()

    # Validate WAVE file format
    if not wav_data.startswith(b"RIFF") or b"WAVE" not in wav_data[:20]:
        raise ValueError("Input file is not a valid WAVE file")

    # Extract current RIFF size and create INFO chunk
    riff_size = struct.unpack("<I", wav_data[4:8])[0]
    info_chunk = create_info_chunk(metadata)

    # Calculate new RIFF size and construct new file
    new_riff_size = riff_size + len(info_chunk)
    new_data = b"".join(
        [b"RIFF", struct.pack("<I", new_riff_size), wav_data[8:], info_chunk]
    )

    with open(output_path, "wb") as f:
        f.write(new_data)


def read_chunks(file) -> list[tuple[str, int, bytes]]:
    """Read and parse all chunks from a WAV file.

    Iterates through a WAVE file and extracts all chunks with their identifiers, sizes,
    and data. Handles padding bytes correctly.

    Args:
    file:
    Open file object positioned at start of WAV file.

    Returns:
    List of tuples containing (chunk_id, chunk_size, chunk_data).

    Raises:
    ValueError: If file is not a valid WAVE file.
    """
    chunks = []

    # Read and validate RIFF header
    riff_header = file.read(12)
    if riff_header[:4] != b"RIFF" or riff_header[8:12] != b"WAVE":
        raise ValueError("Not a valid WAVE file")

    # Read all chunks
    while True:
        header = file.read(8)
        if len(header) < 8:
            break

        chunk_id, chunk_size = struct.unpack("<4sI", header)
        chunk_data = file.read(chunk_size)

        # Handle padding byte for odd-sized chunks
        if chunk_size % 2 == 1:
            file.read(1)

        chunks.append((chunk_id.decode("ascii"), chunk_size, chunk_data))

    return chunks


def parse_fmt_chunk(data: bytes) -> dict[str, int | str]:
    """Parse fmt chunk to extract audio format information.

    Extracts essential audio parameters from the format chunk, including sample rate,
    bit depth, channel count, and audio format type. Also handles extended format
    information when present.

    Args:     data: Raw fmt chunk data as bytes.

    Returns:     Dictionary containing parsed audio format information.

    Raises:     ValueError: If fmt chunk is too small or malformed.
    """
    if len(data) < 16:
        raise ValueError("fmt chunk too short (less than 16 bytes)")

    # Unpack basic format information
    fields = struct.unpack("<HHIIHH", data[:16])
    audio_format, num_channels, sample_rate, byte_rate, block_align, bits_per_sample = (
        fields
    )

    result = {
        "Audio format": audio_format,
        "Audio format name": AUDIO_FORMATS.get(
            audio_format, f"Unknown ({audio_format})"
        ),
        "Channels": num_channels,
        "Sample rate": sample_rate,
        "Byte rate": byte_rate,
        "Block align": block_align,
        "Bits per sample": bits_per_sample,
    }

    # Handle extended format information
    if len(data) > 16:
        if len(data) >= 18:
            cb_size = struct.unpack("<H", data[16:18])[0]
            result["Extra size"] = cb_size

            extra_data = data[18 : 18 + cb_size]

            if audio_format == 0xFFFE and cb_size >= 22:
                # WAVE_FORMAT_EXTENSIBLE format
                valid_bits, channel_mask, subformat = struct.unpack(
                    "<HI16s", extra_data[:22]
                )
                result.update(
                    {
                        "Valid bits per sample": valid_bits,
                        "Channel mask": channel_mask,
                        "Subformat GUID": subformat.hex(),
                    }
                )
            else:
                # Other non-PCM formats
                result["Extra data (hex)"] = extra_data.hex()

    return result


def parse_cue_chunk(data: bytes) -> list[dict[str, int]]:
    """Parse cue chunk to extract marker/cue point information.

    Extracts cue point data including IDs, positions, and sample offsets.
    Handles malformed chunks gracefully by reading as many complete
    cue points as possible.

    Args:
        data: Raw cue chunk data as bytes.

    Returns:
        List of dictionaries, each containing cue point information:
        - ID: Unique cue point identifier
        - Position: Position in playlist
        - Sample Offset: Position in samples from start of audio

    Usage:
        cue_points = parse_cue_chunk(cue_data)
        for cue in cue_points:
            logger.debug(f"Cue {cue['ID']} at sample {cue['Sample Offset']}")
    """
    if len(data) < 4:
        logging.warning("Cue chunk too small for cue point count")
        return []

    num_cue_points = struct.unpack("<I", data[:4])[0]
    logging.debug(f"Cue points in header: {num_cue_points}")

    cue_points = []
    expected_size = 4 + num_cue_points * 24

    if len(data) < expected_size:
        logging.warning(
            f"Cue chunk contains {len(data)} bytes, expected {expected_size}"
        )
        num_possible = (len(data) - 4) // 24
        logging.warning(f"Reading only first {num_possible} cue points")
    else:
        num_possible = num_cue_points

    # Extract cue point data
    for i in range(num_possible):
        offset = 4 + i * 24
        try:
            fields = struct.unpack("<IIIIII", data[offset : offset + 24])
            cue_points.append(
                {
                    "ID": fields[0],
                    "Position": fields[1],
                    "Chunk ID": fields[2],
                    "Chunk Start": fields[3],
                    "Block Start": fields[4],
                    "Sample Offset": fields[5],
                }
            )
        except struct.error:
            logging.warning(f"Cannot read cue point {i + 1} (insufficient bytes)")
            break

    return cue_points


def extract_valid_cue_points(
    cue_points: list[dict[str, int]], sample_rate: int
) -> list[dict[str, int | float]]:
    """Filter cue points with valid offsets and calculate timing.

    Filters out cue points with zero sample offset (typically invalid) and calculates
    the corresponding time in seconds for each valid point.

    Args:     cue_points: List of cue point dictionaries from parse_cue_chunk().
    sample_rate: Audio sample rate in Hz.

    Returns:     List of dictionaries containing:     - id: Cue point ID     -
    sample_offset: Position in samples     - time: Position in seconds
    """
    result = []

    for cp in cue_points:
        offset = cp.get("Sample Offset", 0)
        cid = cp.get("ID", 0)

        if offset > 0:
            result.append(
                {"id": cid, "sample_offset": offset, "time": offset / sample_rate}
            )

    return result


def parse_bext_chunk(data: bytes) -> dict[str, str | int]:
    """Parse Broadcast Wave Format (BWF) bext chunk.

    Extracts professional audio metadata from the bext chunk, including description,
    originator information, timing references, and coding history. This chunk is
    commonly used in professional broadcast and film audio.

    Args:     data: Raw bext chunk data as bytes.

    Returns:     Dictionary containing parsed BWF metadata.

    Raises:     ValueError: If bext chunk is too small (less than 602 bytes).
    """
    if len(data) < 602:
        raise ValueError("bext chunk too small: expected at least 602 bytes")

    # Unpack fixed-size fields
    fields = struct.unpack("<256s32s32s10s8sIIH64s190s", data[:602])

    description = fields[0].decode("utf-8", errors="ignore").strip("\x00")
    originator = fields[1].decode("utf-8", errors="ignore").strip("\x00")
    originator_ref = fields[2].decode("utf-8", errors="ignore").strip("\x00")
    origination_date = fields[3].decode("ascii", errors="ignore").strip("\x00")
    origination_time = fields[4].decode("ascii", errors="ignore").strip("\x00")
    time_ref_low = fields[5]
    time_ref_high = fields[6]
    version = fields[7]
    umid = fields[8].hex()

    # Extract optional coding history (after byte 602)
    coding_history = ""
    if len(data) > 602:
        coding_history = (
            data[602:].split(b"\x00", 1)[0].decode("utf-8", errors="ignore").strip()
        )

    return {
        "Description": description,
        "Originator": originator,
        "Originator Reference": originator_ref,
        "Origination Date": origination_date,
        "Origination Time": origination_time,
        "Time Reference Low": time_ref_low,
        "Time Reference High": time_ref_high,
        "Time Reference (samples)": (time_ref_high << 32) + time_ref_low,
        "Version": version,
        "UMID": umid,
        "CodingHistory": coding_history,
    }


def parse_list_info_chunk(data: bytes) -> dict[str, str]:
    """Parse LIST-INFO chunk for general metadata.

    Extracts common metadata fields like title (INAM), artist (IART), comments (ICMT),
    and other INFO identifiers from a LIST-INFO chunk.

    Args:     data: Raw LIST chunk data starting with 'INFO' identifier.

    Returns:     Dictionary mapping INFO identifiers to their string values.
    """
    info = {}
    pos = 4  # Skip 'INFO' identifier

    while pos + 8 <= len(data):
        subchunk_id = data[pos : pos + 4].decode("ascii", errors="ignore")
        subchunk_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        content = (
            data[pos + 8 : pos + 8 + subchunk_size]
            .decode("ascii", errors="ignore")
            .strip("\x00")
        )

        info[subchunk_id] = content
        pos += 8 + subchunk_size

        # Handle padding byte
        if subchunk_size % 2 == 1:
            pos += 1

    return info


def parse_list_adtl_chunk(data: bytes) -> list[tuple[int, str]]:
    """Parse LIST-adtl chunk for cue point labels.

    Extracts text labels associated with cue points from the associated data list (adtl)
    chunk. Each label is linked to a cue point by ID.

    Args:     data: Raw LIST chunk data starting with 'adtl' identifier.

    Returns:     List of tuples containing (cue_id, label_text) pairs.
    """
    pos = 4  # Skip 'adtl' identifier
    labels = []

    while pos + 8 <= len(data):
        subchunk_id = data[pos : pos + 4].decode("ascii", errors="ignore")
        subchunk_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        content = data[pos + 8 : pos + 8 + subchunk_size]

        if subchunk_id == "labl" and len(content) >= 4:
            cue_id = struct.unpack("<I", content[:4])[0]
            text = content[4:].decode("ascii", errors="ignore").strip("\x00")
            labels.append((cue_id, text))

        pos += 8 + subchunk_size

        # Handle padding byte
        if subchunk_size % 2 == 1:
            pos += 1

    return labels


def parse_ixml_chunk(data: bytes) -> str:
    """Parse iXML chunk for production metadata.

    Extracts XML-formatted production metadata commonly used in professional recording
    equipment and post-production workflows.

    Args:     data: Raw iXML chunk data as bytes.

    Returns:     XML content as string, or empty string if parsing fails.
    """
    try:
        xml = data.decode("utf-8", errors="ignore")
        return xml
    except Exception:
        return ""


def hex_dump(data: bytes, length: int = 64) -> str:
    """Create hexadecimal representation of binary data.

    Generates a space-separated hexadecimal dump of binary data, useful for debugging
    unknown chunk formats.

    Args:     data: Binary data to convert.     length: Maximum number of bytes to
    include (default: 64).

    Returns:     Space-separated hexadecimal string.

    Test with binary data:     hex_dump(b'\\x00\\x01\\x02\\x03') returns '00 01 02 03'
    hex_dump(b'Hello', length=3) returns '48 65 6C'
    """
    return " ".join(f"{b:02X}" for b in data[:length])


def wav_analyze(filename: str) -> dict[str, Any]:
    """Analyze WAV file and extract all metadata and structural information.

    Comprehensive analysis of a WAV file including audio format parameters,
    cue points, BWF metadata, INFO metadata, and production information.

    Args:
        filename: Path to WAV file to analyze.

    Returns:
        Dictionary containing all extracted information:
        - fmt: Audio format information
        - cue_points: List of cue/marker points
        - cue_labels: Text labels for cue points
        - bext: Broadcast Wave Format metadata
        - info: General INFO metadata
        - ixml: Production XML metadata
        - unknown_chunks: List of unrecognized chunks
        - sample_rate: Audio sample rate (for convenience)

    Usage:
        result = wav_analyze('field_recording.wav')
        sample_rate = result['fmt']['Sample rate']
        num_cues = len(result['cue_points'])
    """
    with open(filename, "rb") as f:
        chunks = read_chunks(f)

    result = {
        "fmt": None,
        "cue_points": [],
        "cue_labels": {},
        "bext": None,
        "info": None,
        "ixml": None,
        "unknown_chunks": [],
        "sample_rate": None,
    }

    # Process each chunk type
    for chunk_id, chunk_size, data in chunks:
        if chunk_id == "fmt ":
            fmt = parse_fmt_chunk(data)
            result["fmt"] = fmt
            result["sample_rate"] = fmt.get("Sample rate")

        elif chunk_id == "cue ":
            result["cue_points"] = parse_cue_chunk(data)

        elif chunk_id == "bext":
            result["bext"] = parse_bext_chunk(data)

        elif chunk_id == "LIST":
            list_type = data[:4].decode("ascii", errors="ignore")

            if list_type == "INFO":
                result["info"] = parse_list_info_chunk(data)
            elif list_type == "adtl":
                labels = parse_list_adtl_chunk(data)
                result["cue_labels"] = {cid: txt for cid, txt in labels}

        elif chunk_id == "iXML":
            result["ixml"] = parse_ixml_chunk(data)

        elif chunk_id == "data":
            continue  # Skip audio data

        else:
            result["unknown_chunks"].append(
                {"id": chunk_id, "size": chunk_size, "data": data}
            )

    return result


def print_analysis(result: dict[str, Any]) -> None:
    """Print formatted analysis results to console.

    Displays comprehensive analysis results in a readable format with appropriate icons
    and formatting for different types of metadata.

    Args:     result: Analysis result dictionary from wav_analyze().
    """

    def print_section(icon: str, title: str, data: dict[str, Any]) -> None:
        """Helper function to print a section with consistent formatting."""
        if data:
            logging.info(f"{icon} {title}:")
            for key, value in data.items():
                logging.info(f"   - {key}: {value}")

    def print_multiline_section(icon: str, title: str, content: str) -> None:
        """Helper function to print multiline content."""
        if content:
            logging.info(f"{icon} {title}:")
            for line in content.strip().splitlines():
                logging.info(f"   {line}")

    # Print standard metadata sections
    print_section("🎛️", "Audio Format", result["fmt"])
    print_section("📝", "BWF Metadata (bext)", result["bext"])
    print_section("📇", "INFO Metadata", result["info"])

    # Handle cue points with filtering and statistics
    if result["cue_points"]:
        filtered_cues = [
            cue for cue in result["cue_points"] if cue["Sample Offset"] != 0
        ]
        logging.info(f"📍 Cue Points: {len(filtered_cues)}")

        for i, cue in enumerate(filtered_cues, 1):
            logging.info(
                f"   Cue {i}: sample offset = {cue['Sample Offset']} (ID = {cue['ID']})"
            )

        skipped = len(result["cue_points"]) - len(filtered_cues)
        if skipped > 0:
            logging.warning(f"   ⚠️ {skipped} cue point(s) with offset 0 skipped")

    # Handle cue labels with filtering
    if result["cue_labels"]:
        non_empty_labels = {
            cid: txt for cid, txt in result["cue_labels"].items() if txt.strip()
        }

        if non_empty_labels:
            logging.info("🏷️  CUE Labels:")
            for cid, txt in non_empty_labels.items():
                logging.info(f"   Cue ID {cid}: '{txt}'")

        skipped = len(result["cue_labels"]) - len(non_empty_labels)
        if skipped > 0:
            logging.warning(f"   ⚠️ {skipped} empty label(s) skipped")

    # Handle iXML metadata
    print_multiline_section("📦", "iXML Metadata", result["ixml"])

    # Handle unknown chunks
    if result["unknown_chunks"]:
        logging.info(f"❔ Unknown Chunks ({len(result['unknown_chunks'])}):")
        for unk in result["unknown_chunks"]:
            hex_start = hex_dump(unk["data"])
            logging.info(f"   ID: {unk['id']}, size: {unk['size']}, data: {hex_start}")

    # Combined timing and labels
    sample_rate = result.get("sample_rate")
    if all([result["cue_points"], sample_rate, result["cue_labels"]]):
        logging.info("🕒 Timed Labels:")
        for cue in result["cue_points"]:
            label = result["cue_labels"].get(cue["ID"])
            if label:
                time_sec = cue["Sample Offset"] / sample_rate
                logging.info(f"   {label} @ {time_sec:.2f}s")


def main() -> None:
    """Main function to analyze all WAV files in current directory."""
    wav_files = [f for f in os.listdir(".") if f.lower().endswith(".wav")]

    if not wav_files:
        logging.warning("No .wav files found in current directory")
        return

    for wav_file in wav_files:
        logging.info(f"Analyzing file: {wav_file}")
        result = wav_analyze(wav_file)
        print_analysis(result)
        logging.info("-" * 50)


if __name__ == "__main__":
    main()
