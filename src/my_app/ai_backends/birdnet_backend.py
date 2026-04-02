"""Official BirdNET backend for AI analysis.

LICENCE NOTICE
--------------
This module targets the official ``birdnet`` Python package published by the
BirdNET team / Cornell Lab of Ornithology ecosystem.

Reference: https://birdnet.cornell.edu/
Docs:      https://birdnet-team.github.io/birdnet/
"""

from __future__ import annotations

from datetime import date as dt_date

from .base import AiBackend

_MODEL_VERSION = "2.4"


# ---------------------------------------------------------------------------
# Dutch common names keyed by scientific name.
# This mapping is original work and is NOT subject to the BirdNET licence.
# ---------------------------------------------------------------------------

DUTCH_NAMES: dict[str, str] = {
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
}


def _rows_from_predictions(predictions) -> list[dict]:
    """Convert various dataframe-like outputs to ``list[dict]``."""
    if predictions is None:
        return []

    if hasattr(predictions, "to_structured_array"):
        structured = predictions.to_structured_array()
        if getattr(structured, "dtype", None) is not None and structured.dtype.names:
            return [
                {name: row[name] for name in structured.dtype.names}
                for row in structured
            ]

    if hasattr(predictions, "to_dataframe"):
        frame = predictions.to_dataframe()
        if hasattr(frame, "to_dict"):
            return frame.to_dict(orient="records")

    if isinstance(predictions, list):
        return [row for row in predictions if isinstance(row, dict)]

    if hasattr(predictions, "to_dicts"):
        return list(predictions.to_dicts())

    if hasattr(predictions, "iter_rows"):
        try:
            return list(predictions.iter_rows(named=True))
        except TypeError:
            pass

    if hasattr(predictions, "iterrows"):
        return [dict(row) for _, row in predictions.iterrows()]

    if hasattr(predictions, "to_dict"):
        try:
            records = predictions.to_dict(orient="records")
            if isinstance(records, list):
                return records
        except TypeError:
            pass

        as_dict = predictions.to_dict()
        if isinstance(as_dict, dict):
            keys = list(as_dict.keys())
            if keys and all(isinstance(as_dict[k], dict) for k in keys):
                row_ids = sorted({
                    row_id for value in as_dict.values()
                    for row_id in value.keys()
                })
                return [
                    {
                        key: as_dict[key].get(row_id)
                        for key in keys
                    }
                    for row_id in row_ids
                ]

    raise RuntimeError("BirdNET returned an unsupported predictions object")


def _to_seconds(value) -> float:
    """Convert BirdNET time values to seconds."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if ":" not in text:
        try:
            return float(text)
        except ValueError:
            return 0.0

    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
    except ValueError:
        return 0.0
    return 0.0


def _get_week(metadata: dict) -> int | None:
    """Extract ISO-like BirdNET week number from WAV metadata."""
    bext = metadata.get("bext") or {}
    date_str = bext.get("OriginationDate", "")
    if not date_str or len(date_str) < 10:
        return None
    try:
        recorded = dt_date.fromisoformat(date_str[:10])
    except ValueError:
        return None
    return min(max(round(recorded.timetuple().tm_yday / 7.25), 1), 48)


def _split_species(row: dict) -> tuple[str, str]:
    """Return ``(scientific_name, common_name)`` from a BirdNET row."""
    scientific = str(row.get("scientific_name") or "").strip()
    common = str(row.get("common_name") or "").strip()

    if scientific or common:
        return scientific, common

    label = (
        row.get("species_name")
        or row.get("label")
        or row.get("species")
        or ""
    )
    text = str(label).strip()
    if not text:
        return "", ""

    if "_" in text:
        scientific, common = text.split("_", 1)
        return scientific.strip(), common.strip()
    return "", text


class BirdnetBackend(AiBackend):
    """Wrap the official BirdNET Python package for species detection."""

    name = "BirdNET"
    color = (50, 200, 80, 45)
    text_color = "#40d060"

    def __init__(self) -> None:
        self._model = None
        self._geo_model = None

    def _load_model(self):
        """Load and cache the official acoustic model."""
        if self._model is None:
            import birdnet  # noqa: PLC0415

            self._model = birdnet.load("acoustic", _MODEL_VERSION, "tf")
        return self._model

    def _load_geo_model(self):
        """Load and cache the official geo prior model when available."""
        if self._geo_model is None:
            import birdnet  # noqa: PLC0415

            self._geo_model = birdnet.load("geo", _MODEL_VERSION, "tf")
        return self._geo_model

    def _species_filter(self, metadata: dict) -> list[str] | None:
        """Build an optional BirdNET species filter from geo metadata."""
        gps = metadata.get("gps") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        week = _get_week(metadata)
        if lat is None or lon is None or week is None:
            return None

        try:
            predictions = self._load_geo_model().predict(float(lat), float(lon), week=week)
        except Exception:
            return None

        species = []
        for row in _rows_from_predictions(predictions):
            scientific, common = _split_species(row)
            if scientific and common:
                species.append(f"{scientific}_{common}")
            elif common:
                species.append(common)
        return species or None

    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:
        """Run BirdNET using the official Python package."""
        model = self._load_model()
        species_filter = self._species_filter(metadata)

        try:
            if species_filter:
                predictions = model.predict(wav_path, custom_species_list=species_filter)
            else:
                predictions = model.predict(wav_path)
        except TypeError:
            # Fallback for versions that expose the file API but not species
            # filtering yet.
            predictions = model.predict(wav_path)

        results = []
        for row in _rows_from_predictions(predictions):
            scientific, common = _split_species(row)
            dutch = DUTCH_NAMES.get(scientific)
            label = common or scientific or str(row.get("label") or "Unknown")
            tag = dutch or label
            detail = f"{dutch} ({scientific})" if dutch and scientific else scientific
            score = row.get("confidence")
            if score is None:
                score = row.get("score", 0.0)

            start = row.get("start_time", row.get("start"))
            end = row.get("end_time", row.get("end"))

            results.append({
                "label": label,
                "score": float(score),
                "start_time": _to_seconds(start),
                "end_time": _to_seconds(end),
                "detail": detail,
                "tag": tag,
                "tag_key": scientific or label,
            })

        return results
