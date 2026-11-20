<div align="center">

# USB Sound Mapper

**Map buttons on any USB device — keyboard, mouse or HID gamepad — to play sounds on Windows.**

[![CI](https://github.com/RobiiAragon/Soundpad/actions/workflows/ci.yml/badge.svg)](https://github.com/RobiiAragon/Soundpad/actions/workflows/ci.yml) ![Python 3.10+](https://img.shields.io/badge/Python%203.10+-3776AB?style=flat-square&logo=python&logoColor=white) ![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white) ![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white) ![License MIT](https://img.shields.io/badge/License%20MIT-2ea44f?style=flat-square)

**English** · [Español](README.es.md)

</div>

---

A soundboard that lives in your system tray. Pick a device, press a button, assign an audio file. Born as a practice project for the *Audiovisual Production* course at UTT.

## Features

- 🎛️ Choose a specific HID device or use global keyboard / mouse hooks.
- 🔊 As many buttons as you want, each mapped to an audio file (WAV, MP3, OGG…). Key combos and multi-device combos (e.g. key + mouse button) work too.
- 🎚️ Master volume and a **Stop sounds** button (also in the tray menu).
- 🧷 Runs in the background with a tray icon.
- 💾 Mappings saved to `%APPDATA%\USB-Sound-Mapper\config.json` (crash logs go to `crash.log` in the same folder).

## Run

**Portable build:** download the `.exe` from [Releases](https://github.com/RobiiAragon/Soundpad/releases) and keep it in its own folder.

**From source:**

```powershell
git clone https://github.com/RobiiAragon/Soundpad.git
cd Soundpad
python -m pip install -r requirements.txt
python -m src.app
```

## Notes

- Some HID devices need elevated permissions to read raw reports. If a device can't be opened, use **Global Keyboard** or **Global Mouse**.
- Audio playback uses `pygame.mixer`. MIDI support was removed to keep things simple.

## Build the .exe

```powershell
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onefile --windowed --name Soundpad --paths . --collect-submodules src src/app.py
```

CI builds the same `.exe` on every push (download it from the run's artifacts) and attaches it to the release when a `v*` tag is pushed.

## Tests

```powershell
python -m pip install pytest
python -m pytest -q
```

## Project structure

```
src/
  app.py            entry point
  core/             devices, audio player, mappings, config
  gui/              main window and tray icon
```

## License

[MIT](LICENSE)

---

Made by **[Jesús Aragón](https://github.com/RobiiAragon)** · [Portfolio](https://robiiaragon.github.io/portfolio/)
