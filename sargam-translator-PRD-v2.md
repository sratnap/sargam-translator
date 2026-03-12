# Product Requirements Document: Sargam Translator App

**Version:** 2.0 (Draft)
**Author:** Sohum Ratnaparkhi
**Date:** March 2026
**Status:** In Progress

---

## 1. Overview

### 1.1 Product Summary
The Sargam Translator is a web application (targeting mobile in future versions) that takes an audio recording of a song (vocal or instrumental) and automatically transcribes it into sargam notation (Sa Re Ga Ma Pa Dha Ni) relative to a user-specified root pitch (Sa). In v2, the output is displayed with synchronized scrolling playback — each note highlights in real time as the audio plays — and live in-browser recording is supported.

### 1.2 The Problem
Hindustani classical musicians often learn and teach songs through sargam notation — the Indian equivalent of solfège. Translating a recording into sargam by ear is a skilled, time-consuming task that very few musicians can do fluently. There is currently no tool that automates this process in a way that is meaningful to Indian classical musicians, forcing teachers to do this manually every time.

### 1.3 The Solution
An app that:
1. Accepts an uploaded audio file or live in-browser recording (v2)
2. Detects pitch with tuner-grade precision using the pYIN algorithm
3. Maps detected pitches to sargam syllables relative to the user's chosen Sa
4. Displays the transcription with each note highlighting in sync with audio playback (v2)

---

## 2. Goals & Non-Goals

### Goals (v1) ✅ Complete
- Accurately detect melody pitches from an uploaded audio file
- Distinguish komal (flat) and tivra (sharp) swaras (e.g., komal Re, tivra Ma)
- Map pitches to sargam relative to a user-defined Sa (all 12 chromatic pitches)
- Display output as plain-text sargam (e.g., `S R G M P D N Ṡ`)
- Colour-code note types (Sa/Pa in gold, komal in blue, tivra in amber)
- Target Indian classical musicians and students (with basic knowledge of sargam)

### Goals (v2)
- **Synchronized scrolling playback** — each sargam note highlights as the audio plays
- **Audio playback in browser** — user can play the uploaded recording directly in the UI
- **Live in-browser recording** — user can record directly in the app instead of uploading
- **Note timestamps** — server returns timestamp for each note, enabling sync playback
- **Silence / pause handling** — gaps between notes represented visually during playback

### Non-Goals (v2 — defer to future versions)
- YouTube / streaming link import *(v3)*
- Beat / taal markers with explicit notation *(v3)*
- Lyrics parsing and note-to-lyric alignment *(v3+)*
- Raag identification or filtering *(v3)*
- Western sheet music / staff notation output *(v3)*
- Gamak, meend, or microtonal ornament transcription *(v3+)*
- Source separation for heavy accompaniment (tabla, harmonium) *(v3)*
- Publishing or sharing features *(v3)*

---

## 3. Target Users

### Primary
Indian classical musicians (Hindustani tradition) — vocalists and instrumentalists — who teach or learn songs and rely on sargam as a learning and communication tool.

### Secondary
General musicians who want a pitch-transcription tool and are open to sargam notation as the output format.

### User Persona
**Meera, 34, Hindustani vocalist and teacher**
Meera teaches 12 students and regularly introduces new bandishes and film songs to her classes. Every time she introduces a song, she must manually transcribe it to sargam — a process that takes 30–60 minutes per song. She is not a developer but is comfortable with technology and uses her phone for most tasks.

---

## 4. Platform & Technical Scope

### 4.1 Platform
- **v1 & v2:** Web browser (local, running on user's computer)
- **v3 Target:** Mobile (iOS and Android)
- **Future:** Desktop app, hosted cloud version

### 4.2 Audio Input (v1) ✅ Complete
- Upload a pre-recorded audio file from device storage
- Supported formats: MP3, WAV, M4A, AAC
- File length: up to ~1 minute

### 4.3 Audio Input (v2)
- Live recording directly in the browser (via Web Audio API / MediaRecorder)
- Uploaded file OR live recording — user chooses

### 4.4 Audio Input (v3+)
- YouTube / URL import

---

## 5. Core Features

### 5.1 Sa Selection ✅ v1 Complete
- User selects the song's reference Sa before processing, from all 12 chromatic pitches
- UI: button grid — e.g., "The song's reference Sa is: [C#]"

### 5.2 Pitch Detection Engine ✅ v1 Complete
- pYIN algorithm for monophonic pitch detection
- Confidence filtering (threshold 0.2) to remove unvoiced/silent frames
- Adaptive local-windowed threshold to handle mixed slow/fast passages
- Run-level smoothing to handle vocal wobble without destroying note boundaries

### 5.3 Pitch-to-Sargam Mapping ✅ v1 Complete
Map detected Hz values to the 12-note chromatic scale relative to chosen Sa:

| Semitones from Sa | Sargam Name       | Abbreviation |
|-------------------|-------------------|--------------|
| 0                 | Sa                | S            |
| 1                 | Komal Re          | r            |
| 2                 | Shuddha Re        | R            |
| 3                 | Komal Ga          | g            |
| 4                 | Shuddha Ga        | G            |
| 5                 | Shuddha Ma        | M            |
| 6                 | Tivra Ma          | M'           |
| 7                 | Pa                | P            |
| 8                 | Komal Dha         — d            |
| 9                 | Shuddha Dha       | D            |
| 10                | Komal Ni          | n            |
| 11                | Shuddha Ni        | N            |

- Uppercase = shuddha (natural), lowercase = komal (flat), apostrophe = tivra (sharp)
- Octave indicators: `.` suffix = taar saptak, `,` suffix = mandra saptak

### 5.4 Sargam Output Display ✅ v1 Complete
- Plain text sargam, colour-coded by note type
- Sa and Pa: gold and bold (achala swaras)
- Komal notes: soft blue
- Tivra Ma: warm amber
- Copy-to-clipboard button

### 5.5 Note Timestamps (v2)
- Server returns each note with its start timestamp (in seconds) alongside the syllable
- Example response: `[{"note": "S", "time": 0.0}, {"note": "R", "time": 0.8}, ...]`
- Timestamps used by the frontend to drive synchronized highlighting

### 5.6 Synchronized Scrolling Playback (v2)
- After translation, user can play the original audio in the browser
- As audio plays, the current note is highlighted (gold outline / background pulse)
- Previously played notes dim slightly, upcoming notes remain at normal brightness
- Tapping/clicking a note in the output seeks the audio to that note's timestamp
- No explicit beat markers — the musician's ear provides rhythmic context

### 5.7 Live In-Browser Recording (v2)
- Microphone button in the UI
- Press to start recording, press again to stop
- Recorded audio is sent directly to the server for processing (same pipeline as upload)
- No need to save a file first — seamless record → translate flow

---

## 6. User Flow (v2)

```
App Launch
    │
    ▼
Home Screen
    │
    ├── [Upload Audio File] OR [Record Live 🎙]
    │       │
    │       ▼
    │   Select Sa (root pitch picker)
    │       │
    │       ▼
    │   Processing Screen ("Detecting pitches...")
    │       │
    │       ▼
    │   Transcription Result Screen
    │       ├── Audio playback bar (play/pause/seek)
    │       ├── Sargam output — notes highlight in sync with playback
    │       ├── [Copy text]
    │       └── [Re-translate with different Sa]
    │
    └── [Settings]
            └── Default Sa, notation style preferences
```

---

## 7. Technical Architecture

### 7.1 Tech Stack (v1 & v2)

| Layer | Implementation |
|---|---|
| Pitch Detection | Python + librosa (pYIN) |
| Backend | FastAPI (Python) |
| Frontend | Single HTML file (vanilla JS) |
| Audio Playback | HTML5 Audio API |
| Live Recording | Web Audio API / MediaRecorder |
| Hosting | Local (user's machine) for v1/v2 |

### 7.2 Key Changes for v2
- `server.py`: return note timestamps alongside syllables; return audio file for browser playback
- `index.html`: add HTML5 audio player; add playback sync loop; add live recording UI

### 7.3 Key Python Libraries
- `librosa` — pitch detection, audio analysis
- `numpy`, `scipy` — signal processing
- `fastapi` — API server
- `python-multipart` — file upload handling

---

## 8. Notation & Musical Assumptions

- **Tuning reference:** A4 = 440 Hz (standard)
- **Octave handling:** Mandra `,`, madhya (unmarked), taar `.`
- **Pitch snapping:** Nearest semitone, handles vibrato and gamak
- **Repeated notes:** Consecutive identical notes collapsed to one entry
- **Silence handling (v2):** Gaps between notes represented as pauses in playback highlighting

---

## 9. Roadmap

| Feature | Version |
|---|---|
| Core pitch detection + sargam output | v1 ✅ |
| Colour-coded web UI | v1 ✅ |
| Synchronized scrolling playback | v2 |
| Live in-browser recording | v2 |
| Audio playback in browser | v2 |
| YouTube / URL import | v3 |
| Lyrics parsing + note alignment | v3+ |
| Source separation (tabla/harmonium) | v3 |
| Raag identification | v3 |
| Taal markers + explicit rhythm notation | v3 |
| Western staff notation export | v3 |
| Gamak / ornament transcription | v3+ |
| Mobile app (iOS/Android) | v3 |
| Cloud hosting | v3 |

---

## 10. Open Questions

1. **Timestamp precision:** pYIN timestamps are frame-based (~11ms resolution). Is this precise enough for smooth note highlighting, or do we need interpolation?
2. **Live recording quality:** Browser microphone recordings may be lower quality than uploaded files. How much does this affect pYIN accuracy?
3. **Audio return format:** Should the server return the audio as a base64 blob or a streaming URL for playback?
4. **Hosting:** When moving to v3 mobile, will the Python backend be self-hosted or on a managed cloud service (Render, Railway, AWS)?

---

## 11. Success Metrics

### v1 ✅
- Pitch detection accuracy ≥ 85% on clean monophonic recordings
- Komal/tivra distinction correct ≥ 90% of the time
- All 12 swaras correctly identified in testing

### v2
- Note highlighting stays within 100ms of actual audio position during playback
- Live recording produces output of comparable quality to file upload
- End-to-end flow (record → translate → play back with sync) works in one sitting without errors

---

*This PRD is a living document and should be updated as decisions are made and requirements evolve.*
