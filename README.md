# Audio dB Tweaker

A simple Windows-friendly desktop app (built with Python + Tkinter) for adjusting the volume of audio files with instant preview before and after the change.

## Features

- **Upload any audio file** — supports mp3, wav, ogg, flac, m4a, aac, wma, aiff, and more
- **Adjust volume in 1 dB steps** — increase or decrease gain precisely, with a live dB readout and a one-click reset to 0 dB
- **Preview before you commit** — play the original audio or the modified version at any time, and stop playback whenever you like
- **Export the result** — save the adjusted audio as WAV, MP3, OGG, or FLAC
- **Native look on Windows** — built with `ttk`, using Windows' own visual style engine for the real Windows feel

## How it works

1. Click **Browse...** and select an audio file.
2. Use the **+ 1 dB** / **− 1 dB** buttons to raise or lower the volume, or **Reset to 0 dB** to start over.
3. Click **Play Original** or **Play Modified** to preview the audio. Click **Stop** at any time. (playback runs through `ffplay`)
4. Once you're happy with the result, click **Save Modified Audio As...** and choose a format and destination.

The app doesn't overwrite your original file — it only saves a new file when you explicitly export it. Additionally the number of chosen dBs will be displayed at the end of the file Ex: `Audio_+5db`.

## Dependencies

### Python packages

```
pip install pydub
```

If you're on **Python 3.13 or newer**, also install this: (Python removed the built-in `audioop` module that `pydub` depends on):

```
pip install audioop-lts
```

### FFmpeg (required, installed separately)

This app relies on FFmpeg to decode/encode audio formats and to play previews (via `ffplay`, which ships with FFmpeg). It is **not** bundled with the app — you need it installed on your system and available on your PATH.

- **Windows:** Download `ffmpeg-release-essentials.zip` from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), unzip it, and add its `bin` folder to your system PATH.
- **macOS:** `brew install ffmpeg`
- **Linux:** `sudo apt install ffmpeg`

If FFmpeg isn't detected on startup, the app will show a popup with these instructions.

## Running the app

```
Audio dB Tweaker.exe
```
## Building
Make sure `icon.ico` and `audio_db_tweaker.py` are in the same folder as build.bat, then simply run it. If all goes right, you'll find the compiled `.exe` app in the `dist` folder.
## License

Licensed under the BSD 3-Clause License — see [LICENSE](LICENSE) for more details. You're free to use, modify, and redistribute this code, including in modified form, as long as credit is retained and my name isn't used to imply endorsement of derivative versions.
