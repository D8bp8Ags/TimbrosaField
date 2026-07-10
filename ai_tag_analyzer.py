#!/usr/bin/env python3
"""Standalone AI tag analyzer for WAV field recordings.

Tests two approaches:
  1. Claude API  — tag suggestions based on WAV metadata (no audio needed)
  2. BirdNET     — bird species detection from actual audio (pip install birdnetlib)

Usage:
    python ai_tag_analyzer.py                    # uses first WAV from config dir
    python ai_tag_analyzer.py example.wav    # specific filename in config dir
    python ai_tag_analyzer.py /full/path/to.wav  # absolute path

Requirements:
    pip install anthropic          # for Claude suggestions
    pip install birdnetlib         # for BirdNET detection (optional)
    export ANTHROPIC_API_KEY=...   # Claude API key
"""

import os
import sys

# Dutch names keyed by scientific name (BirdNET only provides English + scientific)
DUTCH_NAMES = {
    "Alopochen aegyptiaca": "Nijlgans",
    "Anas platyrhynchos": "Wilde Eend",
    "Anas crecca": "Wintertaling",
    "Anas acuta": "Pijlstaart",
    "Anas querquedula": "Zomertaling",
    "Anas clypeata": "Slobeend",
    "Anas penelope": "Smient",
    "Anas strepera": "Krakeend",
    "Aythya fuligula": "Kuifeend",
    "Aythya ferina": "Tafeleend",
    "Anser anser": "Grauwe Gans",
    "Anser albifrons": "Kolgans",
    "Anser brachyrhynchus": "Kleine Rietgans",
    "Branta canadensis": "Canadese Gans",
    "Branta leucopsis": "Brandgans",
    "Branta bernicla": "Rotgans",
    "Cygnus olor": "Knobbelzwaan",
    "Cygnus cygnus": "Wilde Zwaan",
    "Chroicocephalus ridibundus": "Kokmeeuw",
    "Larus argentatus": "Zilvermeeuw",
    "Larus michahellis": "Geelpootmeeuw",
    "Larus fuscus": "Kleine Mantelmeeuw",
    "Larus marinus": "Grote Mantelmeeuw",
    "Larus canus": "Stormmeeuw",
    "Hydrocoloeus minutus": "Dwergmeeuw",
    "Sterna hirundo": "Visdief",
    "Scolopax rusticola": "Houtsnip",
    "Gallinago gallinago": "Watersnip",
    "Vanellus vanellus": "Kievit",
    "Pluvialis apricaria": "Goudplevier",
    "Charadrius hiaticula": "Bontbekplevier",
    "Haematopus ostralegus": "Scholekster",
    "Tringa totanus": "Tureluur",
    "Tringa nebularia": "Groenpootruiter",
    "Actitis hypoleucos": "Oeverloper",
    "Numenius arquata": "Wulp",
    "Limosa limosa": "Grutto",
    "Ardea cinerea": "Blauwe Reiger",
    "Ardea alba": "Grote Zilverreiger",
    "Egretta garzetta": "Kleine Zilverreiger",
    "Nycticorax nycticorax": "Kwak",
    "Ciconia ciconia": "Ooievaar",
    "Phalacrocorax carbo": "Aalscholver",
    "Podiceps cristatus": "Fuut",
    "Fulica atra": "Meerkoet",
    "Gallinula chloropus": "Waterhoen",
    "Rallus aquaticus": "Waterral",
    "Alcedo atthis": "IJsvogel",
    "Columba palumbus": "Houtduif",
    "Columba livia": "Stadsduif",
    "Streptopelia decaocto": "Turkse Tortel",
    "Streptopelia turtur": "Tortelduif",
    "Cuculus canorus": "Koekoek",
    "Apus apus": "Gierzwaluw",
    "Hirundo rustica": "Boerenzwaluw",
    "Delichon urbicum": "Huiszwaluw",
    "Riparia riparia": "Oeverzwaluw",
    "Picus viridis": "Groene Specht",
    "Dendrocopos major": "Grote Bonte Specht",
    "Dendrocopos minor": "Kleine Bonte Specht",
    "Dryocopus martius": "Zwarte Specht",
    "Falco tinnunculus": "Torenvalk",
    "Falco subbuteo": "Boomvalk",
    "Falco peregrinus": "Slechtvalk",
    "Accipiter nisus": "Sperwer",
    "Accipiter gentilis": "Havik",
    "Buteo buteo": "Buizerd",
    "Pernis apivorus": "Wespendief",
    "Milvus milvus": "Rode Wouw",
    "Circus aeruginosus": "Bruine Kiekendief",
    "Haliaeetus albicilla": "Zeearend",
    "Corvus corax": "Raaf",
    "Corvus corone": "Zwarte Kraai",
    "Corvus monedula": "Kauw",
    "Corvus frugilegus": "Roek",
    "Pica pica": "Ekster",
    "Garrulus glandarius": "Vlaamse Gaai",
    "Parus major": "Koolmees",
    "Parus caeruleus": "Pimpelmees",
    "Cyanistes caeruleus": "Pimpelmees",
    "Periparus ater": "Zwarte Mees",
    "Lophophanes cristatus": "Kuifmees",
    "Poecile palustris": "Glanskop",
    "Poecile montanus": "Matkop",
    "Aegithalos caudatus": "Staartmees",
    "Sitta europaea": "Boomklever",
    "Certhia familiaris": "Boomkruiper",
    "Troglodytes troglodytes": "Winterkoning",
    "Erithacus rubecula": "Roodborst",
    "Luscinia megarhynchos": "Nachtegaal",
    "Phoenicurus ochruros": "Zwarte Roodstaart",
    "Phoenicurus phoenicurus": "Gekraagde Roodstaart",
    "Saxicola rubetra": "Paapje",
    "Saxicola torquatus": "Roodborsttapuit",
    "Turdus merula": "Merel",
    "Turdus philomelos": "Zanglijster",
    "Turdus iliacus": "Koperwiek",
    "Turdus pilaris": "Kramsvogel",
    "Turdus viscivorus": "Grote Lijster",
    "Muscicapa striata": "Grauwe Vliegenvanger",
    "Ficedula hypoleuca": "Bonte Vliegenvanger",
    "Sylvia atricapilla": "Zwartkop",
    "Sylvia communis": "Grasmus",
    "Sylvia borin": "Tuinfluiter",
    "Curruca curruca": "Braamsluiper",
    "Acrocephalus scirpaceus": "Kleine Karekiet",
    "Acrocephalus arundinaceus": "Grote Karekiet",
    "Acrocephalus palustris": "Bosrietzanger",
    "Locustella naevia": "Sprinkhaanzanger",
    "Phylloscopus collybita": "Tjiftjaf",
    "Phylloscopus trochilus": "Fitis",
    "Regulus regulus": "Goudhaan",
    "Regulus ignicapilla": "Vuurgoudhaan",
    "Fringilla coelebs": "Vink",
    "Fringilla montifringilla": "Keep",
    "Chloris chloris": "Groenling",
    "Carduelis carduelis": "Putter",
    "Spinus spinus": "Sijs",
    "Linaria cannabina": "Kneu",
    "Pyrrhula pyrrhula": "Goudvink",
    "Coccothraustes coccothraustes": "Appelvink",
    "Emberiza citrinella": "Geelgors",
    "Emberiza schoeniclus": "Rietgors",
    "Miliaria calandra": "Grauwe Gors",
    "Passer domesticus": "Huismus",
    "Passer montanus": "Ringmus",
    "Sturnus vulgaris": "Spreeuw",
    "Motacilla alba": "Witte Kwikstaart",
    "Motacilla flava": "Gele Kwikstaart",
    "Motacilla cinerea": "Grote Gele Kwikstaart",
    "Anthus pratensis": "Graspieper",
    "Anthus trivialis": "Boompieper",
    "Anthus spinoletta": "Waterpieper",
    "Lanius collurio": "Grauwe Klauwier",
    "Lanius excubitor": "Klapekster",
    "Oriolus oriolus": "Wielewaal",
    # Insects — BirdNET matches nearest acoustic pattern, exact species may differ
    "Neoconocephalus retusus": "Sprinkhaan (kegeldraagsprinkhaan-type)",
    "Orchelimum pulchellum": "Sprinkhaan (weidesprinkhaan-type)",
    "Orchelimum vulgare": "Sprinkhaan (weidesprinkhaan-type)",
    "Conocephalus brevipennis": "Sprinkhaan (kortveugelige sabelsprinkhaan-type)",
    "Conocephalus fasciatus": "Sprinkhaan (sabelsprinkhaan-type)",
    "Gryllus pennsylvanicus": "Veldkrekel-type",
    "Gryllus rubens": "Veldkrekel-type",
    "Acheta domesticus": "Huiskrekel",
    "Gryllotalpa gryllotalpa": "Veenmol",
}

# Add app modules to path so we can reuse load_user_config and wav_analyze
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "my_app"))

from user_config_manager import load_user_config
from wav_analyzer import wav_analyze


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_wav_dir():
    config = load_user_config()
    return config["paths"]["fieldrecording_dir"]


def _pick_wav_file(wav_dir):
    if not os.path.isdir(wav_dir):
        print(f"WAV directory not found: {wav_dir}")
        sys.exit(1)
    files = sorted(f for f in os.listdir(wav_dir) if f.lower().endswith(".wav"))
    if not files:
        print(f"No WAV files found in: {wav_dir}")
        sys.exit(1)
    return os.path.join(wav_dir, files[0])


def _build_context(wav_path, metadata):
    """Turn WAV metadata into a readable context string for Claude."""
    filename = os.path.basename(wav_path)
    bext = metadata.get("bext", {})
    info = metadata.get("info", {})
    gps  = metadata.get("gps") or {}
    fmt  = metadata.get("fmt", {})

    lines = [f"Filename : {filename}"]

    date = bext.get("OriginationDate", "")
    time = bext.get("OriginationTime", "")
    if date:
        lines.append(f"Date/Time: {date} {time}".strip())

    desc = bext.get("Description", "").strip()
    if desc:
        lines.append(f"Description: {desc}")

    tags = info.get("ICMT", "").strip()
    if tags:
        lines.append(f"Existing tags: {tags}")

    title = info.get("INAM", "").strip()
    if title and title != "Untitled Recording":
        lines.append(f"Title: {title}")

    location = gps.get("location_name", "").strip()
    lat = gps.get("latitude")
    lon = gps.get("longitude")
    if location:
        lines.append(f"Location: {location}")
    elif lat and lon:
        lines.append(f"GPS: {lat}, {lon}")

    sr = fmt.get("Sample rate")
    if sr:
        lines.append(f"Sample rate: {sr} Hz")

    dur = metadata.get("duration_seconds")
    if dur:
        lines.append(f"Duration: {int(dur)//60}m {int(dur)%60}s")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

def analyze_with_claude(wav_path, metadata):
    try:
        import anthropic
    except ImportError:
        print("[Claude] anthropic not installed — run: pip install anthropic")
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[Claude] ANTHROPIC_API_KEY not set")
        return None

    client = anthropic.Anthropic(api_key=api_key)
    context = _build_context(wav_path, metadata)

    prompt = (
        "You are a field recording archivist. Based on the metadata below, "
        "suggest 5-10 concise tags for archiving and searching this recording.\n\n"
        f"{context}\n\n"
        "Focus on: sound environment (forest, urban, water, etc.), "
        "time of day or season if inferable, animal sounds suggested by "
        "location or time, and recording conditions.\n\n"
        "Return only the tags as a comma-separated list, nothing else."
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


# ---------------------------------------------------------------------------
# BirdNET
# ---------------------------------------------------------------------------

def analyze_with_birdnet(wav_path, metadata):
    try:
        from birdnetlib import Recording
        from birdnetlib.analyzer import Analyzer
    except ImportError:
        print("[BirdNET] birdnetlib not installed — run: pip install birdnetlib")
        return None

    print("[BirdNET] Running analysis...")
    try:
        analyzer = Analyzer()

        # Use GPS + date from metadata to filter species list to local fauna
        kwargs = {"min_conf": 0.25}
        gps = metadata.get("gps") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        if lat and lon:
            kwargs["lat"] = float(lat)
            kwargs["lon"] = float(lon)
            print(f"[BirdNET] Location filter: {lat:.4f}, {lon:.4f}")

        bext = metadata.get("bext") or {}
        date_str = bext.get("OriginationDate", "")
        if date_str and len(date_str) >= 10:
            try:
                from datetime import date as dt  # noqa: PLC0415
                d = dt.fromisoformat(date_str[:10])
                week = min(max(round(d.timetuple().tm_yday / 7.25), 1), 48)
                kwargs["week"] = week
                print(f"[BirdNET] Date filter: {d} → week {week}")
            except ValueError:
                pass

        recording = Recording(analyzer, wav_path, **kwargs)
        recording.analyze()
        return recording.detections
    except Exception as exc:
        print(f"[BirdNET] Analysis failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# CLAP — soundscape / environment classification (disabled, replaced by AST)
# ---------------------------------------------------------------------------

CLAP_LABELS = [
    "birds singing",
    "wind",
    "rain",
    "running water, stream or river",
    "waves, sea or ocean",
    "insects, crickets or grasshoppers",
    "frogs",
    "traffic, cars or road noise",
    "human voices",
    "farm animals",
    "forest ambience",
    "open field or meadow",
    "urban environment",
    "silence",
    "aircraft",
]


def analyze_with_clap(wav_path):
    """Analyze wav_path with CLAP using a sliding window over predefined labels.

    Args:
        wav_path: Path to WAV file.

    Returns:
        List of (label, score, start_s, end_s) sorted by start time, or None on error.
    """
    try:
        import torch
        from transformers import ClapModel, ClapProcessor
    except ImportError:
        print("[CLAP] Missing: pip install transformers torch")
        return None

    print("[CLAP] Loading model (first run downloads ~900 MB)...")
    try:
        model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
        processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
    except Exception as exc:
        print(f"[CLAP] Model load failed: {exc}")
        return None

    try:
        import soundfile as sf
        import numpy as np

        audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        if sr != 48000:
            from math import gcd  # noqa: PLC0415
            from scipy.signal import resample_poly  # noqa: PLC0415
            g = gcd(sr, 48000)
            audio = resample_poly(audio, 48000 // g, sr // g)
            sr = 48000

        chunk_samples = sr * 10
        step_samples  = sr * 5
        results = []

        for start in range(0, len(audio), step_samples):
            chunk = audio[start:start + chunk_samples]
            if len(chunk) < sr * 2:
                break
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))

            inputs = processor(
                text=CLAP_LABELS,
                audios=[chunk],
                return_tensors="pt",
                padding=True,
                sampling_rate=sr,
            )
            with torch.no_grad():
                outputs = model(**inputs)

            scores = outputs.logits_per_audio[0].softmax(dim=0).numpy()
            start_s = start / sr
            end_s   = min((start + chunk_samples) / sr, len(audio) / sr)
            window_hits = [
                (label, float(score), start_s, end_s)
                for label, score in zip(CLAP_LABELS, scores)
                if score > 0.20
            ]
            results.extend(window_hits)

        return sorted(results, key=lambda x: x[2])

    except Exception as exc:
        print(f"[CLAP] Analysis failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# AST — Audio Spectrogram Transformer (AudioSet 527 labels, no input needed)
# ---------------------------------------------------------------------------

def analyze_with_ast(wav_path, top_n=5, min_conf=0.05, chunk_seconds=10):
    """Analyze wav_path with AST using a sliding window.

    Args:
        wav_path: Path to WAV file.
        top_n: Number of top labels to return per window.
        min_conf: Minimum confidence threshold (sigmoid score).
        chunk_seconds: Window size in seconds.

    Returns:
        List of (label, score, start_s, end_s) sorted by start time, or None on error.
    """
    try:
        import torch
        from transformers import AutoFeatureExtractor, ASTForAudioClassification
    except ImportError:
        print("[AST] Missing: pip install transformers torch")
        return None

    print("[AST] Loading model (first run downloads ~80 MB)...")
    try:
        model_id = "MIT/ast-finetuned-audioset-10-10-0.448"
        extractor = AutoFeatureExtractor.from_pretrained(model_id)
        model = ASTForAudioClassification.from_pretrained(model_id)
        model.eval()
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
        model = model.to(device)
        print(f"[AST] Using device: {device}")
    except Exception as exc:
        print(f"[AST] Model load failed: {exc}")
        return None

    try:
        import soundfile as sf
        import numpy as np

        audio, sr = sf.read(wav_path, dtype="float32", always_2d=False)
        if audio.ndim > 1:
            audio = audio.mean(axis=1)

        # AST expects 16 kHz
        target_sr = extractor.sampling_rate  # 16000
        if sr != target_sr:
            import librosa  # noqa: PLC0415
            print(f"[AST] Resampling {sr} Hz → {target_sr} Hz...")
            audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
            sr = target_sr

        chunk_samples = sr * chunk_seconds
        step_samples  = sr * (chunk_seconds // 2)  # 50% overlap
        results = []

        for start in range(0, len(audio), step_samples):
            chunk = audio[start:start + chunk_samples]
            if len(chunk) < sr * 2:  # skip chunks shorter than 2s
                break
            if len(chunk) < chunk_samples:
                chunk = np.pad(chunk, (0, chunk_samples - len(chunk)))

            inputs = extractor(
                chunk,
                sampling_rate=sr,
                return_tensors="pt",
            )
            inputs = {k: v.to(device) for k, v in inputs.items()}
            with torch.no_grad():
                logits = model(**inputs).logits[0]

            # AST is multi-label: use sigmoid (not softmax)
            scores = torch.sigmoid(logits).cpu().numpy()
            start_s = start / sr
            end_s   = min((start + chunk_samples) / sr, len(audio) / sr)

            top_indices = scores.argsort()[::-1][:top_n]
            for idx in top_indices:
                score = float(scores[idx])
                if score < min_conf:
                    continue
                label = model.config.id2label[idx]
                results.append((label, score, start_s, end_s))

        return sorted(results, key=lambda x: x[2])  # sort by start time

    except Exception as exc:
        print(f"[AST] Analysis failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# AST tree display helpers
# ---------------------------------------------------------------------------

def _load_audioset_ontology():
    """Return AudioSet ontology as list of dicts, downloading once to ~/.cache."""
    import json
    import urllib.request

    cache_path = os.path.join(os.path.expanduser("~"), ".cache", "audioset_ontology.json")
    if not os.path.exists(cache_path):
        print("[AST] Downloading AudioSet ontology (~500 KB, once)...")
        url = "https://raw.githubusercontent.com/audioset/ontology/master/ontology.json"
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        urllib.request.urlretrieve(url, cache_path)
    with open(cache_path) as f:
        return json.load(f)


def _build_name_hierarchy(ontology):
    """Return (name_to_parent, name_to_children) dicts keyed by label name."""
    id_to_name = {e["id"]: e["name"] for e in ontology}
    name_to_children = {}
    name_to_parent = {}
    for entry in ontology:
        name = entry["name"]
        name_to_children.setdefault(name, [])
        for child_id in entry.get("child_ids", []):
            child_name = id_to_name.get(child_id)
            if child_name:
                name_to_children[name].append(child_name)
                name_to_parent[child_name] = name
    return name_to_parent, name_to_children


def _print_ast_tree(ast_results):
    """Print AST results grouped by time window as a hierarchy tree."""
    try:
        ontology = _load_audioset_ontology()
        name_to_parent, _ = _build_name_hierarchy(ontology)
    except Exception as exc:
        print(f"  [tree] Could not load ontology ({exc}), falling back to flat list")
        name_to_parent = {}

    # Group by (start_s, end_s)
    from collections import defaultdict
    windows = defaultdict(dict)  # (start_s, end_s) -> {label: score}
    for label, score, start_s, end_s in ast_results:
        windows[(start_s, end_s)][label] = score

    for (start_s, end_s), labels in sorted(windows.items()):
        start_fmt = f"{int(start_s)//60}:{int(start_s)%60:02d}"
        end_fmt   = f"{int(end_s)//60}:{int(end_s)%60:02d}"
        print(f"\n  {start_fmt} – {end_fmt}  ({start_s:.0f}s – {end_s:.0f}s)")

        detected = set(labels)

        def _detected_ancestor(label):
            """Walk up the ontology tree; return first ancestor that is detected."""
            parent = name_to_parent.get(label)
            while parent:
                if parent in detected:
                    return parent
                parent = name_to_parent.get(parent)
            return None

        # Root labels: detected labels with no detected ancestor
        roots = [l for l in detected if _detected_ancestor(l) is None]
        roots.sort(key=lambda l: -labels[l])

        LABEL_COL = 40  # fixed column width for indent + label

        def _print_node(label, indent):
            score = labels[label]
            bar = "█" * int(score * 20)
            tree_prefix = "  " * indent + ("└── " if indent > 0 else "")
            label_str = tree_prefix + label
            print(f"  {label_str:<{LABEL_COL}s}  {score:.2f}  {bar}")
            # Direct detected children: ancestor resolves to this label
            children = [l for l in detected if _detected_ancestor(l) == label]
            for child in sorted(children, key=lambda l: -labels[l]):
                _print_node(child, indent + 1)

        for root in roots:
            _print_node(root, 0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    wav_dir = _get_wav_dir()
    print(f"WAV directory : {wav_dir}\n")

    # Resolve the target file
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        wav_path = arg if os.path.isabs(arg) else os.path.join(wav_dir, arg)
    else:
        wav_path = _pick_wav_file(wav_dir)
        print(f"No file specified — using first: {os.path.basename(wav_path)}\n")

    if not os.path.exists(wav_path):
        print(f"File not found: {wav_path}")
        sys.exit(1)

    # Read metadata
    print(f"File: {os.path.basename(wav_path)}")
    print("-" * 60)
    metadata = wav_analyze(wav_path)

    # Print current metadata summary
    bext = metadata.get("bext") or {}
    info = metadata.get("info") or {}
    gps  = metadata.get("gps") or {}
    print(f"Date/Time    : {bext.get('OriginationDate','?')} {bext.get('OriginationTime','')}")
    print(f"Location     : {gps.get('location_name') or gps.get('latitude') or 'unknown'}")
    print(f"Existing tags: {info.get('ICMT') or '(none)'}")
    print()

    # --- BirdNET (disabled) ---
    # detections = analyze_with_birdnet(wav_path, metadata)
    # ...

    # # --- AST ---
    # print()
    # print("=== AST — AudioSet soundscape classification (527 labels) ===")
    # ast_results = analyze_with_ast(wav_path)
    # if ast_results is None:
    #     pass  # error already printed
    # elif ast_results:
    #     _print_ast_tree(ast_results)
    # else:
    #     print("  No labels detected above threshold.")

    # # --- CLAP ---
    # print()
    # print("=== CLAP — soundscape classification (custom labels) ===")
    # clap_results = analyze_with_clap(wav_path)
    # if clap_results is None:
    #     pass  # error already printed
    # elif clap_results:
    #     for label, score, start_s, end_s in clap_results:
    #         start_fmt = f"{int(start_s)//60}:{int(start_s)%60:02d}"
    #         end_fmt   = f"{int(end_s)//60}:{int(end_s)%60:02d}"
    #         bar = "█" * int(score * 20)
    #         print(
    #             f"  {label:<40s}  {score:.2f}  "
    #             f"{start_fmt} – {end_fmt}  ({start_s:.0f}s – {end_s:.0f}s)  {bar}"
    #         )
    # else:
    #     print("  No labels above threshold.")


if __name__ == "__main__":
    main()