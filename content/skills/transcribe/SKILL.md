---
name: transcribe
description: "Transcribe video and audio files via Gemini API. Use when the user asks to transcribe a recording, generate a meeting summary, extract speech from video or audio, or convert speech to text. Supports mp4, mkv, webm, avi, mov, mp3, wav, ogg, m4a, flac."
---

# transcribe — video and audio transcription

Transcribes audio and video files via the Gemini 2.5 Flash API.

## Modes

### Generic (default)
Verbatim speech transcription with timecodes `[MM:SS]` and speaker identification.

Output files:
- `<name> - transcript.md` — verbatim speech with timecodes
- `<name> - summary.md` — short summary (with the `--with-summary` flag)

### UI analysis (`--analyze-ui`, video only)
Detailed video analysis with breakdown of on-screen interface, navigation, and actions, plus screenshots.

Output files:
- `<name> - summary.md` — short overview (topic, participants, decisions)
- `<name> - detailed.md` — step-by-step chronological analysis with screen content and screenshots
- `<name> - transcript.md` — verbatim speech with timecodes
- `screenshots/` — PNG frames of key moments

## Usage

```
/transcribe <FilePath> [--output-dir DIR] [--analyze-ui] [--with-summary] [--format md|txt]
```

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| `FilePath` | yes | — | Path to audio / video file |
| `--output-dir` | no | `<file_folder>/Transcript/<name>/` | Result directory |
| `--analyze-ui` | no | off | UI-analysis mode (video only) |
| `--with-summary` | no | off | Add a summary (for generic mode) |
| `--format` | no | `md` | Output format: `md` or `txt` |

## Supported formats

- **Video:** mp4, mkv, webm, avi, mov
- **Audio:** mp3, wav, ogg, m4a, flac, aac, wma

## Dependencies

- Python packages: `google-genai`, `python-dotenv`
- System: `ffmpeg`, `ffprobe` in PATH
- API key: environment variable `GEMINI_API_KEY`, or `<skill-dir>/.env` with `GEMINI_API_KEY=...` (the script also checks supported user-skill locations and then `cwd/.env`)

## Procedure

1. Determine `FilePath` and optional flags from the user's arguments.

2. Run the script:

```powershell
$env:PYTHONUNBUFFERED = "1"
python <skill-dir>/scripts/transcribe.py "<FilePath>" [--output-dir "<OutputDir>"] [--analyze-ui] [--with-summary] [--format md|txt]
```

**IMPORTANT:** `PYTHONUNBUFFERED=1` is mandatory; otherwise stdout is buffered and progress is not displayed.

On macOS / Linux use `PYTHONUNBUFFERED=1 python ...` instead.

3. The script runs long (5–15 minutes depending on length). Files > 1 hour are split automatically.

4. After completion, report the result paths to the user.

5. Read the summary (if any) or the start of the transcript and show it to the user.

## Cost

~$0.10 per 1 hour of recording (Gemini 2.5 Flash). Long files cost proportionally.

## Limitations

- Maximum ~1 hour per Gemini request (the script splits automatically)
- Cyrillic file names: the script automatically copies the file to a temp location with an ASCII name
- Screenshot quality depends on source video quality
- Timecode accuracy +/- a few seconds
- `--analyze-ui` with an audio file automatically falls back to generic + summary
