<div align="center">

# USB Sound Mapper

**Asigna botones de cualquier dispositivo USB — teclado, mouse o control HID — para reproducir sonidos en Windows.**

![Python 3.10+](https://img.shields.io/badge/Python%203.10+-3776AB?style=flat-square&logo=python&logoColor=white) ![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?style=flat-square&logo=qt&logoColor=white) ![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white) ![License MIT](https://img.shields.io/badge/License%20MIT-2ea44f?style=flat-square)

[English](README.md) · **Español**

</div>

---

Una botonera de sonidos que vive en la bandeja del sistema. Eliges un dispositivo, presionas un botón y le asignas un audio. Nació como práctica de la materia *Producción Audiovisual* en la UTT.

## Funciones

- 🎛️ Elige un dispositivo HID específico o usa los hooks globales de teclado y mouse.
- 🔊 Hasta 10 botones con archivos de audio (WAV, MP3, OGG…).
- 🧷 Corre en segundo plano con ícono en la bandeja.
- 💾 Guarda tus asignaciones en `%APPDATA%`.

## Cómo usarlo

**Versión portable:** descarga el `.exe` de [Releases](https://github.com/RobiiAragon/Soundpad/releases) y déjalo en su propia carpeta.

**Desde el código:**

```powershell
git clone https://github.com/RobiiAragon/Soundpad.git
cd Soundpad
python -m pip install -r requirements.txt
python -m src.app
```

## Notas

- Algunos dispositivos HID piden permisos de administrador para leer sus reportes. Si uno no abre, usa **Global Keyboard** o **Global Mouse**.
- El audio usa `pygame.mixer`. Quité el soporte MIDI para simplificar.

## Estructura

```
src/
  app.py            punto de entrada
  core/             dispositivos, reproductor, asignaciones, configuración
  gui/              ventana principal e ícono de bandeja
```

## Licencia

[MIT](LICENSE)

---

Hecho por **[Jesús Aragón](https://github.com/RobiiAragon)** · [Portafolio](https://robiiaragon.github.io/portfolio/)
