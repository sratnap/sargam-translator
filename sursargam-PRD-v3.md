# Product Requirements Document: SurSargam

**Version:** 3.1 (Current)
**Author:** Sohum Ratnaparkhi
**Last Updated:** April 2026
**Status:** v3 Live on Render — v3.1 In Development

---

## 1. Overview

### 1.1 Product Summary
SurSargam is a web application that takes any audio recording — a voice memo, live microphone input, or eventually a YouTube link — and automatically transcribes the melody into Hindustani sargam notation (Sa Re Ga Ma Pa Dha Ni) relative to a user-specified Sa (root pitch). The output is colour-coded, plays back in sync with the audio, and can be manually corrected, exported as video, or copied as text.

### 1.2 The Problem
Hindustani musicians and teachers transcribe songs to sargam notation by ear — a process that takes 30–60 minutes per song. Students need this notation to learn songs, and teachers need it to teach efficiently. There is no tool that does this automatically for Indian classical music.

### 1.3 The Vision
SurSargam is not just a transcription tool — it is a music learning platform that teaches users to hear music in sargam the way a trained Hindustani musician does. The long-term goal is to break the barrier of needing to be "inherently talented" at music, and to show that anyone can develop this skill with the right tools. The target audience is the younger Indian diaspora generation who grew up with Bollywood and classical music but never formally learned.

### 1.4 The Solution (Current)
A fast, accurate, beautiful tool that:
1. Takes audio input (file upload or live microphone recording)
2. Detects pitch frame by frame using pYIN
3. Maps pitches to sargam syllables relative to the user's Sa
4. Displays output with synchronized playback highlighting
5. Allows manual correction of any note
6. Exports the result as a shareable video or copied text

### 1.5 Target Users
- **Primary:** Younger Indian diaspora — people who grew up with Hindustani/Bollywood music but never formally learned sargam
- **Secondary:** Hindustani vocalists, instrumentalists, and teachers who need to transcribe songs faster
- **Tertiary:** Students learning songs by ear, anyone who wants pitch transcription from audio

---

## 2. Version History & Status

### v1 ✅ Complete (master branch)
- Pitch detection from clean uploaded audio files
- All 12 swaras with komal/tivra/shuddha distinction
- Octave handling (mandra `,`, madhya unmarked, taar `.`)
- Colour-coded web UI (dark theme, gold accents)
- Sa selector (all 12 chromatic pitches)
- Plain text sargam output with Copy button

### v2 ✅ Complete
- Note timestamps returned from server alongside syllables
- Synchronized scrolling playback — notes highlight in real time as audio plays
- Click any note to jump to that moment in the audio
- Live in-browser microphone recording
- HTML5 audio player with progress bar

### v2.1 ✅ Complete
- Export Video button — records synchronized playback as a .webm video file
- Canvas-based rendering of notes + audio combined into downloadable video
- Shareable via WhatsApp, iMessage, etc.

### v2.2 ✅ Complete
- **iMessage-style note editor** — long press any note opens a contextual overlay with blur backdrop, lifted note clone, and note picker
- **Edit Mode toggle** — single tap opens editor for rapid bulk corrections
- **Delete note** — remove a note entirely from the sequence
- **Insert note** — insert a new note after any existing note, immediately opens editor on it
- **Undo / Redo** — full history stack, Ctrl+Z / Ctrl+Y
- **Reset** — restore original translation with confirmation prompt
- **Keyboard shortcuts** — Space (play/pause), ←/→ (prev/next note), E (edit mode), Esc (close)
- **Shortcuts modal** — ? button shows all keyboard shortcuts
- Corrected notes marked with a small gold dot underneath

### v2.3 ✅ Complete
- **Renamed to SurSargam** — tagline "sur to sargam", version line updated, exported video filename updated
- **Devanagari toggle** — Sa/सा toggle in toolbar switches all note display between Roman and Devanagari scripts. Keyboard shortcut: D
- **Line editor** — ☰ Lines button opens the full sargam as editable text lines of 8 notes each, numbered. Edit freely, apply validates all tokens, supports both scripts. Keyboard shortcut: L
- Shortcuts modal updated with new shortcuts (L, D)

### v3 ✅ Live (current deployed version)
- **Cloud deployment on Render** — app accessible from any device via public URL
- **FastAPI serves frontend** — index.html served via FileResponse, no separate static hosting needed
- **Password protection** — `/auth` endpoint checks against `APP_PASSWORD` environment variable. Browser caches auth in sessionStorage. No password required locally if env var not set
- **Relative API URLs** — frontend uses `/translate` not `http://localhost:8000/translate`
- **iOS audio playback fix** — audio src deferred until first user tap (Web Audio API iOS requirement)
- **iOS recording fix** — MediaRecorder uses `audio/mp4` on iOS Safari instead of `audio/wav`
- **Sa pitch preview** — long press any Sa button (300ms) plays a harmonium-like tone at that pitch using Web Audio API oscillators. Release to stop. Desktop only (iOS AudioContext limitation)
- **End-note cutoff fix** — 0.5s silence padding added to audio before pYIN processing, preventing final notes from being clipped
- **Cold start warning** — "First translation may take up to 30 seconds" shown below translate button, disappears after first successful translation
- **Better error messages** — server errors now say "please wait 30 seconds and try again" instead of referencing uvicorn
- **Memory optimisation** — librosa lazy-imported inside translate endpoint only, audio loaded at fixed 22050 Hz sample rate, temp file deleted immediately after audio loaded into memory

### v3.1 — In Development
- YouTube import (yt-dlp) without Demucs — run pYIN directly on mixed audio as first pass
- HPSS (harmonic-percussive source separation) as lightweight vocal isolation before pYIN
- Lyrics sync — user pastes lyrics, app aligns syllables to note timestamps

### v4+ — Future
- See Section 6

---

## 3. Technical Architecture (Current)

### 3.1 Stack

| Layer | Implementation |
|---|---|
| Pitch Detection | Python + librosa (pYIN algorithm) |
| Backend | FastAPI (Python) |
| Frontend | Single HTML file, vanilla JS |
| Audio Format Handling | librosa handles mp3/wav/m4a/aac natively |
| Hosting | Render (free tier, auto-deploy from GitHub v3 branch) |
| Password Auth | Environment variable APP_PASSWORD on Render |

### 3.2 Running Locally
```
cd C:\Users\sohum\OneDrive\Sargam
python -m uvicorn server:app --reload
```
Then open `http://localhost:8000` in browser. No password required locally (APP_PASSWORD not set).

### 3.3 Deployment
- GitHub repo: `sratnap/sargam-translator` (private)
- Render watches `v3` branch — every push auto-deploys
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
- Environment variable: `APP_PASSWORD` set in Render dashboard

### 3.4 Key Algorithm Parameters

| Parameter | Value | Purpose |
|---|---|---|
| Pitch algorithm | pYIN | Best accuracy for monophonic vocal pitch |
| Sample rate | 22050 Hz | Standard for pitch detection, half memory of 44100 |
| fmin | C2 | Lower bound for pitch detection |
| fmax | C7 | Upper bound for pitch detection |
| Confidence threshold | 0.2 | Filter unvoiced/silent frames |
| SMOOTH_WINDOW | 9 | Run-level smoothing to remove brief flickers |
| LOCAL_WINDOW | 8 | Local median threshold for note collapse |
| Octave reference | MIDI 48 (C3) | Tuned for typical singing voice range |
| End padding | 0.5s silence | Prevents pYIN from cutting off final notes |

### 3.5 Sargam Mapping

| Semitones from Sa | Note | Symbol | Colour | Devanagari |
|---|---|---|---|---|
| 0 | Sa | S | Gold (bold) | सा |
| 1 | Komal Re | r | Blue | रे॒ |
| 2 | Shuddha Re | R | Cream | रे |
| 3 | Komal Ga | g | Blue | ग॒ |
| 4 | Shuddha Ga | G | Cream | ग |
| 5 | Shuddha Ma | M | Cream | म |
| 6 | Tivra Ma | M' | Amber | म॑ |
| 7 | Pa | P | Gold (bold) | प |
| 8 | Komal Dha | d | Blue | ध॒ |
| 9 | Shuddha Dha | D | Cream | ध |
| 10 | Komal Ni | n | Blue | नि॒ |
| 11 | Shuddha Ni | N | Cream | नि |

Octave suffixes: `.` = taar saptak, `,` = mandra saptak, none = madhya saptak

### 3.6 API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | GET | Serves index.html |
| `/auth` | POST | Password check — body: `{password: string}` → `{ok: bool}` |
| `/translate` | POST | Translate audio → sargam. Form data: `file`, `sa` |

### 3.7 API Response Format
```json
{
  "sargam": [{"note": "S", "time": 1.207}, ...],
  "duration": 9.3,
  "total_notes": 15,
  "sa": "D"
}
```

### 3.8 GitHub Repository
- **URL:** https://github.com/sratnap/sargam-translator (private)
- **Branches:** master (v1), v2, v2.1, v2.2, v2.3, v3 (live/active)
- **Active branch:** v3 — Render watches this branch

---

## 4. Design System

| Token | Value | Usage |
|---|---|---|
| --bg | #0e0c0a | Page background |
| --surface | #1a1713 | Card background |
| --border | #2e2a24 | Borders, dividers |
| --gold | #c9a84c | Sa, Pa, active note, buttons |
| --gold-dim | #7a6330 | Hover states, labels |
| --cream | #f0e6d0 | Primary text, shuddha notes |
| --muted | #7a7060 | Secondary text |
| --error | #c0574a | Delete button, error states |
| --blue | #8fbcda | Komal notes |
| --amber | #c48a6a | Tivra Ma |

**Fonts:** Playfair Display (sargam output, headers) + DM Mono (UI, labels)

---

## 5. v3.1 Requirements

### 5.1 Overview
v3.1 adds YouTube import as the primary new feature, using HPSS for lightweight vocal separation before pYIN. Demucs (full neural source separation) is deferred until a paid Render tier is justified by usage.

### 5.2 YouTube Import
- User pastes a YouTube URL into a new input field
- Server downloads audio via **yt-dlp**
- HPSS (librosa built-in) separates harmonic content from percussive (removes tabla/drums)
- pYIN runs on harmonic component
- Audio deleted from server after processing
- Show step progress: "Downloading..." → "Separating..." → "Detecting pitches..."
- For personal/educational use only

### 5.3 Lyrics Sync
- User pastes lyrics manually into a text area
- App aligns lyric syllables to note timestamps
- Display sargam with lyrics underneath each note group
- Only ship if alignment accuracy is acceptable on Hindi/Urdu songs
- Melismatic singing (one syllable across many notes) handled by showing syllable at first note of phrase

### 5.4 v3.1 Tech Stack Additions

| Addition | Library | Purpose |
|---|---|---|
| YouTube download | yt-dlp | Audio import from YouTube |
| Harmonic separation | librosa HPSS (built-in) | Lightweight vocal isolation |
| Lyrics alignment | Manual paste + timestamp matching | Syllable-to-note alignment |

---

## 6. Future Versions (v4+)

| Feature | Version | Notes |
|---|---|---|
| "Learn this song" mode | v4 | Karaoke-style guided singing with sargam |
| Ear training features | v4 | Interval recognition, note guessing games |
| Demucs source separation | v4 | Requires paid Render tier (~$7/month) |
| Raag identification | v4 | Identify raag from translated sargam |
| Mobile app (iOS/Android) | v4 | Native app, resolves iOS Web Audio limitations |
| User accounts + history | v4 | Save translations, track progress |
| Shareable link | v4 | Unique URL per translation, 7-day expiry |
| Beat / taal markers | v4 | librosa beat tracker, `\|` at beat boundaries |
| Specific taal recognition | v4 | Teentaal, Keherwa etc. |
| Individual track selection | v4 | Choose vocals/tabla/harmonium stem |
| Custom domain | v4 | sursargam.com or sursargam.app |
| PDF export of notation | v4 | Printable sargam sheet |
| Spotify / streaming import | v4+ | Beyond YouTube |
| Gamak / meend transcription | v4+ | Ornament detection |
| Music learning game | v5+ | Cozy low-poly 3D world, separate product |

---

## 7. Full Feature Roadmap

| Feature | Version | Status |
|---|---|---|
| Pitch detection + sargam output | v1 | ✅ |
| Colour-coded web UI | v1 | ✅ |
| Sa selector | v1 | ✅ |
| Synchronized playback | v2 | ✅ |
| Live recording | v2 | ✅ |
| Export video | v2.1 | ✅ |
| Note editor (long press / edit mode) | v2.2 | ✅ |
| Delete / insert notes | v2.2 | ✅ |
| Undo / redo | v2.2 | ✅ |
| Keyboard shortcuts | v2.2 | ✅ |
| Rename to SurSargam | v2.3 | ✅ |
| Devanagari toggle | v2.3 | ✅ |
| Line editor | v2.3 | ✅ |
| Cloud deployment (Render) | v3 | ✅ |
| Invite-only password protection | v3 | ✅ |
| iOS audio playback fix | v3 | ✅ |
| iOS recording fix (mp4) | v3 | ✅ |
| Sa pitch preview (desktop) | v3 | ✅ |
| End-note cutoff fix | v3 | ✅ |
| Memory optimisation (lazy librosa) | v3 | ✅ |
| YouTube import (HPSS) | v3.1 | In development |
| Lyrics sync | v3.1 | In development |
| "Learn this song" mode | v4 | Planned |
| Demucs source separation | v4 | Planned |
| Mobile app | v4 | Planned |
| Raag identification | v4 | Planned |
| User accounts | v4 | Planned |
| Music learning game | v5+ | Concept stage |

---

## 8. Known Limitations

1. **Sa pitch preview iOS** — Web Audio API AudioContext does not initialise from touch events on iOS Safari. Desktop only for now. Resolved in v4 native app.
2. **Mixed audio accuracy** — pYIN struggles with recordings that have prominent instrument accompaniment (tabla, harmonium, tanpura). HPSS in v3.1 will partially address this; full resolution requires Demucs (v4).
3. **Free tier memory** — Render free tier is 512MB. Librosa uses ~300MB on first translation. Occasional OOM crashes possible under simultaneous load. Upgrade to paid tier when usage justifies it.
4. **Free tier cold start** — App sleeps after 15 minutes of inactivity. First request after sleep takes 30-60 seconds. UI warns users.
5. **Melismatic singing** — One syllable held across many notes is a fundamental challenge for lyrics alignment. Handled manually for now.

---

## 9. Open Questions

1. **HPSS accuracy on mixed recordings** — needs testing on real Bollywood songs before shipping YouTube import
2. **Lyrics alignment accuracy** — do not ship if accuracy on Hindi/Urdu is below acceptable threshold
3. **Render upgrade timing** — upgrade to $7/month paid tier when usage is consistent enough to justify
4. **yt-dlp compliance** — ensure app is used for personal/educational purposes only, add disclaimer in UI

---

## 10. Product Philosophy

SurSargam is built on the belief that anyone can learn to hear music in sargam — not just trained musicians. The transcription engine is the foundation, but the real product is the learning experience built on top of it. Every feature decision should be evaluated against this question: does this help a user develop their own musical ear, or does it just give them an answer?

The app targets the younger Indian diaspora specifically — people who feel a connection to Hindustani music but have never had access to the right tools or teachers. SurSargam should feel like having a knowledgeable, patient musical friend, not a cold utility.

---

*This is a living document. Update before starting each new version.*
