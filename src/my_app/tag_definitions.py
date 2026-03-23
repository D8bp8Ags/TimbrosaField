"""Tag Definitions Module for TimbrosaField Field Recording Application.

This module defines the comprehensive tag taxonomy used throughout the TimbrosaField
application for categorizing and organizing field recordings. The tag system is
designed to provide consistent, hierarchical metadata that enables effective
searching, filtering, and organization of audio recordings.

The tag categories are structured to cover all aspects of field recording scenarios:
- Location and environment types
- Wildlife and animal sounds
- Weather conditions and natural elements
- Temporal context (time of day)
- Technical audio characteristics
- Human activities and urban sounds

Each category uses emoji prefixes for visual identification in the user interface,
making it easier for users to quickly navigate and select appropriate tags.

The tags within each category are carefully curated to:
- Cover common field recording scenarios
- Use consistent terminology
- Avoid redundancy across categories
- Provide appropriate granularity for useful classification

Usage:
    from tag_definitions import tag_categories

    # Get all nature-related tags
    nature_tags = tag_categories["🌿 Nature"]

    # Get all available categories
    categories = list(tag_categories.keys())

    # Create flat list of all tags
    all_tags = []
    for category_tags in tag_categories.values():
        all_tags.extend(category_tags)

Example tag applications:
    Forest morning with birdsong: ["forest", "morning", "bird", "clear", "ambient"]
    Urban traffic recording: ["street", "traffic", "voices", "distant", "stereo"]
    Rainy evening atmosphere: ["rain", "evening", "wind", "ambient", "clear"]
"""

tag_categories = {
    # Location and environment tags for natural settings
    # Used to describe the primary location or environment where recording was made
    "🌿 Nature": [
        "stream",
        "mountain",
        "forest",
        "dune",
        "cave",
        "heath",
        "lake",
        "marsh",
        "nature reserve",
        "river",
        "beach",
        "valley",
        "field",
        "pond",
        "waterfall",
        "meadow",
        "sea",
    ],
    # Urban environments and human-influenced locations
    # Covers built environments, public spaces, and human activity areas
    "🏙️ Urban / Human": [
        "construction site",
        "park",
        "square",
        "school",
        "playground",
        "station",
        "street",
        "traffic",
        "store",
    ],
    # Animal sound sources for wildlife and domestic animals
    # Identifies specific animals whose sounds are prominent in the recording
    "🐦 Animals (wild & domestic)": [
        "hedgehog",
        "duck",
        "goat",
        "dog",
        "cat",
        "cow",
        "frog",
        "rabbit",
        "mouse",
        "horse",
        "sheep",
        "woodpecker",
        "owl",
        "pig",
        "bat",
        "bird",
        "fox",
        "swan",
    ],
    # Insects and small creatures often creating ambient soundscapes
    # Used for recordings where insect or small animal sounds are significant
    "🦗 Insects & Small animals": [
        "bee",
        "bumblebee",
        "cricket",
        "mosquito",
        "caterpillar",
        "snail",
        "grasshopper",
        "butterfly",
        "fly",
        "worm",
        "wasp",
    ],
    # Weather conditions and natural elements present during recording
    # Describes environmental conditions affecting the soundscape
    "🌧️ Weather & Elements": [
        "dew",
        "ice",
        "fog",
        "thunderstorm",
        "rain",
        "snow",
        "storm",
        "wind",
        "sun",
    ],
    # Temporal context indicating when the recording was made
    # Helps categorize recordings by time period for lighting and activity correlation
    "⏰ Time of day": ["evening", "afternoon", "night", "morning", "sunset", "sunrise"],
    # Activity types and sound characteristics in the recording
    # Describes the nature of activities or sound types present
    "🛠️ Sound type / Activity": [
        "construction noise",
        "nearby",
        "crowd",
        "machines",
        "voices",
        "silence",
        "distant",
        "traffic",
        "footsteps",
    ],
    # Technical aspects and quality characteristics of the recording
    # Used to describe audio quality, recording technique, and technical properties
    "🎧 Recording quality": [
        "ambient",
        "close",
        "clear",
        "mono",
        "noise",
        "stereo",
        "distant",
        "distortion",
    ],
}
