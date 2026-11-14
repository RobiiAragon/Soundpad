<div align="center">

# USB Sound Mapper

**Map buttons on any USB device — keyboard, mouse or HID gamepad — to play sounds on Windows.**

![Python 3.10+](https://img.shields.io/badge/Python%203.10+-3776AB?style=flat-square&logo=python&logoColor=white) ![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white) ![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white) ![License MIT](https://img.shields.io/badge/License%20MIT-2ea44f?style=flat-square)

**English** · [Español](README.es.md)

</div>

---

A soundboard that lives in your system tray. Pick a device, press a button, assign an audio file. Born as a practice project for the *Audiovisual Production* course at UTT.

## Features

- 🎛️ Choose a specific HID device or use global keyboard / mouse hooks.
- 🔊 Up to 10 buttons mapped to audio files (WAV, MP3, OGG…).
- 🧷 Runs in the background with a tray icon.
- 💾 Mappings saved to a config file in `%APPDATA%`.

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
