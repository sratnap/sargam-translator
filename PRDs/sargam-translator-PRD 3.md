# Product Requirements Document: Sargam Translator App

**Version:** 1.0 (Draft)
**Author:** [Your Name]
**Date:** March 2026
**Status:** In Progress

---

## 1. Overview

### 1.1 Product Summary
The Sargam Translator is a mobile application that takes an audio recording of a song (vocal or instrumental) and automatically transcribes it into sargam notation (Sa Re Ga Ma Pa Dha Ni) relative to a user-specified root pitch (Sa). The output is displayed as aligned, readable sargam text with rudimentary taal (beat) markers, synchronized to audio playback.

### 1.2 The Problem
Hindustani classical musicians often learn and teach songs through sargam notation — the Indian equivalent of solfège. Translating a recording into sargam by ear is a skilled, time-consuming task that very few musicians can do fluently. There is currently no tool that automates this process in a way that is meaningful to Indian classical musicians, forcing teachers to do this manually every time.

### 1.3 The Solution
An app that:
1. Accepts an uploaded audio file (v1) or live recording (v2)
2. Detects pitch with tuner-grade precision using algorithms like pYIN
3. Maps detected pitches to sargam syllables relative to the user's chosen Sa
4. Displays the transcription as plain text sargam with beat markers, scrolling in sync with playback

---

## 2. Goals & Non-Goals

### Goals (v1)
- Accurately detect melody pitches from an uploaded audio file
- Distinguish komal (flat) and tivra (sharp) swaras (e.g., komal Re, tivra Ma)
- Map pitches to sargam relative to a user-defined Sa (in any of the 12 standard pitches: C, C#, D, D#, E, F, F#, G, G#, A, A#, B)
- Display output as plain-text sargam (e.g., `S R G M P D N Ṡ`)
- Target Indian classical musicians and students (with basic knowledge of sargam) as the primary audience

### Non-Goals (v1 — defer to future versions)
- Live audio recording within the app *(v2)*
- YouTube / streaming link import *(v2)*
- Beat / taal markers and alignment *(v2)*
- Synchronized scrolling playback *(v2)*
- Silence, pause, and breath handling *(v2)*
- Raag identification or filtering
- Western sheet music / staff notation output
- Gamak, meend, or microtonal ornament transcription
- Publishing or sharing features

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
- **v1 Target:** Mobile (iOS and Android)
- **v1 Fallback:** Web browser (if mobile build is complex to start)
- **Future:** Desktop app

### 4.2 Audio Input (v1)
- Upload a pre-recorded audio file from device storage
- Supported formats: MP3, WAV, M4A, AAC
- File length: up to ~1 minutes for v1

### 4.3 Audio Input (v2+)
- Live recording within the app
- YouTube / URL import

---

## 5. Core Features (v1)

### 5.1 Sa Selection (Root Pitch Input)
- User selects the song's reference Sa before processing, from all 12 chromatic pitches (C through B)
- UI: a simple picker/dropdown — e.g., "The song's reference Sa is: [C#]"
- This is the reference point for all sargam mapping

### 5.2 Pitch Detection Engine
- Use **pYIN algorithm** (probabilistic YIN) for monophonic pitch detection — the same mathematics used in professional instrument tuners unless you know a better, more reliable algorithm
- Extract the fundamental frequency (Hz) of the melody over time
- For polyphonic/mixed recordings (e.g., voice + tanpura + tabla), apply **melody separation** preprocessing (e.g., using Spleeter or Demucs) to isolate the lead melody before pitch detection (v2)

### 5.3 Pitch-to-Sargam Mapping
Map detected Hz values to the 12-note chromatic scale, then to sargam syllables relative to chosen Sa:

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
| 8                 | Komal Dha         | d            |
| 9                 | Shuddha Dha       | D            |
| 10                | Komal Ni          | n            |
| 11                | Shuddha Ni        | N            |

- Uppercase = shuddha (natural), lowercase = komal (flat), apostrophe = tivra (sharp)
- Octave indicators: dot below = mandra saptak, dot above = taar saptak (e.g., Ṡ for taar Sa)

### 5.4 Sargam Output Display
- Display as **plain text** sargam, e.g.:  
  `S R G M P D N Ṡ`
- Notes are arranged left-to-right in time order
- Komal/tivra swaras clearly distinguished (lowercase / apostrophe notation)
- Octave indicators shown where relevant (dot below = mandra, dot above = taar)

---

## 6. User Flow (v1)

```
App Launch
    │
    ▼
Home Screen
    │
    ├── [Upload Audio File]
    │       │
    │       ▼
    │   Select Sa (root pitch picker)
    │       │
    │       ▼
    │   Processing Screen ("Detecting pitches...")
    │       │
    │       ▼
    │   Transcription Result Screen
    │       ├── Plain-text sargam output
    │       └── [Copy text] / [Export as text] (stretch goal)
    │
    └── [Settings]
            └── Default Sa, notation style preferences
```

---

## 7. Technical Architecture (Proposed)

### 7.1 Tech Stack Options

| Layer | Option A (Python backend) | Option B (on-device) |
|---|---|---|
| Pitch Detection | Python + librosa / pYIN | On-device ML model |
| Source Separation | Spleeter or Demucs (Python) | Not feasible v1 |
| Backend | FastAPI (Python REST API) | N/A |
| Mobile Frontend | React Native or Flutter | React Native or Flutter |
| Audio Playback | React Native Sound / Expo AV | Same |

**Recommendation for v1:** Python backend (FastAPI) hosted in the cloud, with a React Native or Flutter mobile frontend. This keeps the heavy audio processing server-side where Python's audio libraries are mature and well-supported.

### 7.2 Key Python Libraries
- `librosa` — audio analysis, beat tracking, tempo detection
- `parselmouth` / `pyin` — precise pitch detection (pYIN algorithm)
- `spleeter` or `demucs` — melody/vocal separation from mixed audio
- `numpy`, `scipy` — signal processing utilities
- `fastapi` — lightweight Python API server

---

## 8. Notation & Musical Assumptions

- **Tuning reference:** A4 = 440 Hz (standard; could be made configurable later for artists using different tuning)
- **Octave handling:** Track which saptak (octave register) each note falls in — mandra, madhya, or taar
- **Pitch snapping:** Snap detected Hz to nearest semitone (chromatic pitch), with a configurable tolerance window (e.g., ±25 cents) to handle vibrato and gamak

---

## 9. Out of Scope for v1 (Future Roadmap)

| Feature | Target Version |
|---|---|
| Live in-app recording | v2 |
| YouTube / URL import | v2 |
| Beat / taal markers and alignment | v2 |
| Synchronized scrolling playback | v2 |
| Silence / pause / breath handling | v2 |
| Raag identification | v3 |
| Taal selection & precise alignment | v2 |
| Western staff notation export | v3 |
| Gamak / ornament transcription | v3+ |
| Multi-user / sharing features | v3 |
| Android/iOS app store publishing | Post-v1 |

---

## 10. Open Questions & v2+ considerations

1. **Source separation quality:** For recordings with heavy accompaniment (tabla, harmonium), how accurate does melody isolation need to be before the app is useful? Will v1 work acceptably on cleaner recordings (solo voice, single instrument) only?
2. **Notation style:** Are there other sargam notation conventions used by your students that differ from the uppercase/lowercase system above? (e.g., some teachers use S r R g G M m P d D n N)
3. **Export format:** Is plain text copy-paste sufficient for v1, or is a formatted PDF export important early on?
4. **Hosting:** Will the Python backend be self-hosted, or do you want to use a managed cloud service (e.g., Render, Railway, AWS)?

---

## 11. Success Metrics (v1)

- Pitch detection accuracy ≥ 85% on clean monophonic recordings (single voice or instrument, minimal accompaniment)
- Komal/tivra distinction correct ≥ 90% of the time
- End-to-end processing time under 60 seconds for a 3-minute song
- A musician can use the output to teach a song with minimal manual correction

---

*This PRD is a living document and should be updated as decisions are made and requirements evolve.*
