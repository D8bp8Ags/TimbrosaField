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
    from my_app.tags.definitions import tag_categories

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
    "🌍 Environment": [
        "forest", "field", "meadow", "heath",
        "mountain", "valley",
        "river", "stream", "lake", "pond", "waterfall",
        "sea", "beach", "dune", "marsh",
        "cave",
        "park", "square", "street", "station",
        "school", "playground", "store",
        "construction site",
    ],
    "🔊 Sound source": [
        "bird", "owl", "woodpecker", "duck", "swan",
        "dog", "cat", "cow", "sheep", "horse", "goat", "pig",
        "frog", "bat", "fox",
        "bee", "bumblebee", "cricket", "grasshopper", "mosquito", "fly", "wasp",
        "voices", "crowd", "footsteps",
        "traffic", "machinery", "construction work",
        "waves", "running water", "rustling leaves",
    ],
    "🌦️ Conditions": [
        "rain", "wind", "storm", "thunder",
        "snow", "ice", "fog",
    ],
    "🕒 Time": [
        "morning", "afternoon", "evening", "night",
    ],
    "🎚️ Sound character": [
        "quiet", "loud",
        "distant", "close",
        "busy", "sparse",
        "continuous", "intermittent",
        "immersive",
    ],
    "🎧 Recording": [
        "mono", "stereo",
        "clean", "noisy", "distorted",
    ],
    "🎭 Mood": [
        "calm", "tense", "dark", "eerie",
    ],
}