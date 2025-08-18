# TimbrosaField

TimbrosaField is a powerful and user-friendly tool for analyzing, visualizing, and tagging field recordings and other audio files. The application is built with Python and PyQt and supports advanced features such as waveform visualization, dynamic downsampling, metadata management, and channel display.

---

## Features

- **Support for WAV files:** Load and analyze mono and stereo audio files.
- **Waveform visualization:** Dynamic downsampling for smooth and fast rendering.
- **Metadata and tags:** Manage extensive metadata and custom tags for each recording.
- **Configuration storage:** Settings and tag data are saved in a JSON configuration file.

---

## Installation

1. Make sure you have Python 3.8+ installed.  
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Start the application:

```bash
python main.py
```
4. Ableton Live Export (optional): Create your own default_template.als in Ableton Live 12.2.1 (or a compatible newer version) and place it in the project root. The Ableton export generator relies on this template.
---

## Usage

- Open a WAV file via the menu.  
- View the waveform and use markers to annotate interesting segments.  
- Edit metadata and tags.  
- Save your configuration so your tags and settings are retained upon reopening.

---

## Project structure

```
TimbrosaField/
├── src/                # application source code
│   └── my_app/         # main package
├── .gitignore          # rules to exclude files from Git
├── LICENSE             # GPL‑3.0 license text
└── README.md           # project documentation (this file)
```

---

## Contribution

Contributions are welcome! Fork the project, create a feature branch, and submit a pull request.

---

## License

This project is licensed under the **GNU GENERAL PUBLIC LICENSE v3.0**.

```
GNU GENERAL PUBLIC LICENSE
Version 3, 29 June 2007

Copyright (C) <year> <author name>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
```

---


## Background

Recently, I bought a Tascam Portacapture X6 and was curious how I could integrate these recordings into my Ableton projects. Unfortunately, Ableton does not read tags from WAV files, and manually renaming files with tags took too much time. While waiting for my cheese plate, I started analyzing the WAV files — and before I knew it, this project was born.

My goal is to do field recordings, tag them through this app (with metadata stored inside the audio file), and then generate an Ableton template so I can easily browse by genre or tags within Ableton.

If you end up using this tool and/or have suggestions for new features, I’d love to hear from you!



## Join the Community

Have ideas, suggestions, or questions? Join the **TimbrosaField Discord server** to share feedback, get help, or connect with others using the tool.

👉 [Join here](https://discord.gg/d6ntrW3HHc)


## Contact

For questions or feedback, please open an [issue](https://github.com/D8bp8Ags/TimbrosaField/issues).

---

*Happy recording & analyzing!* 🎧
