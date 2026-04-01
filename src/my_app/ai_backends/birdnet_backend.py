"""BirdNET backend for AI analysis.

LICENCE NOTICE
--------------
This module wraps the birdnetlib library and the BirdNET-Analyzer model
weights, both developed by Stefan Kahl / Cornell Lab of Ornithology.

  birdnetlib  — MIT licence (library wrapper)
  BirdNET model weights — Creative Commons Attribution-NonCommercial-
                          ShareAlike 4.0 International (CC BY-NC-SA 4.0)

The CC BY-NC-SA 4.0 licence does **not** permit commercial use.
Do not distribute or use this file as part of a commercial product without
verifying licence compliance or obtaining a separate commercial licence.

Reference: https://github.com/kahst/BirdNET-Analyzer
"""

from .base import AiBackend

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


class BirdnetBackend(AiBackend):
    """Wraps birdnetlib to detect bird species in a WAV file.

    Applies GPS location and recording date from WAV metadata when available
    to improve species filtering accuracy.
    """

    name = "BirdNET"
    color = (50, 200, 80, 45)
    text_color = "#40d060"

    def analyze(self, wav_path: str, metadata: dict) -> list[dict]:
        """Run BirdNET with GPS and date filters from WAV metadata.

        Args:
            wav_path: Absolute path to the WAV file.
            metadata: Dict as returned by ``wav_analyze()``.

        Returns:
            List of detection dicts (label, score, start_time, end_time,
            detail, tag, tag_key).
        """
        from birdnetlib import Recording  # noqa: PLC0415
        from birdnetlib.analyzer import Analyzer  # noqa: PLC0415

        analyzer = Analyzer()
        kwargs: dict = {"min_conf": 0.25}

        gps = metadata.get("gps") or {}
        lat = gps.get("latitude")
        lon = gps.get("longitude")
        if lat and lon:
            kwargs["lat"] = float(lat)
            kwargs["lon"] = float(lon)

        bext = metadata.get("bext") or {}
        date_str = bext.get("OriginationDate", "")
        if date_str and len(date_str) >= 10:
            try:
                from datetime import date as dt  # noqa: PLC0415
                d = dt.fromisoformat(date_str[:10])
                kwargs["week"] = min(max(round(d.timetuple().tm_yday / 7.25), 1), 48)
            except ValueError:
                pass

        recording = Recording(analyzer, wav_path, **kwargs)
        recording.analyze()

        results = []
        for det in recording.detections:
            sci = det["scientific_name"]
            dutch = DUTCH_NAMES.get(sci)
            tag = dutch or det["common_name"]
            detail = f"{dutch} ({sci})" if dutch else sci
            results.append({
                "label": det["common_name"],
                "score": det["confidence"],
                "start_time": det["start_time"],
                "end_time": det["end_time"],
                "detail": detail,
                "tag": tag,
                "tag_key": sci,
            })
        return results
