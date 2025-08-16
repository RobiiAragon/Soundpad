# USB Sound Mapper

Map USB device buttons (keyboards, mouse, HID gamepads) to play sounds on Windows.

Features:
- Select a HID device or use global keyboard/mouse hooks
- Map up to 10 buttons/keys to audio files (WAV/MP3/OGG, etc.)
- Runs in background with a system tray icon
- Saves your mappings to a config file in %APPDATA%

## Quick start - compiled version (.Exe)

1. Save the program.exe on a secure folder (is a portable program)

## Quick start - base project

1. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

2. Run the app:

```powershell
python -m src.app
```

## Notes
- For some HID devices, reading raw reports may require elevated permissions.
- If a device can't be opened via HID, use the "Global Keyboard" or "Global Mouse" options.
- Audio playback uses pygame.mixer.

MIDI support fue retirado en esta versión para simplificar.
