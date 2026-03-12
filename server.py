"""
Sargam Translator — FastAPI Server v2
--------------------------------------
Runs the sargam translation logic as a local web server.
Returns note timestamps for synchronized playback in the UI.

To start:
    python -m uvicorn server:app --reload

Then open index.html in your browser.
"""

import tempfile
import os
import numpy as np
import librosa
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Sargam mapping ──────────────────────────────────────────────────

SEMITONES_TO_SARGAM = {
    0:  "S",
    1:  "r",
    2:  "R",
    3:  "g",
    4:  "G",
    5:  "M",
    6:  "M'",
    7:  "P",
    8:  "d",
    9:  "D",
    10: "n",
    11: "N",
}

CHROMATIC_SCALE = ["C", "C#", "D", "D#", "E", "F",
                   "F#", "G", "G#", "A", "A#", "B"]

def octave_suffix(octave_offset):
    if octave_offset == 0:
        return ""
    elif octave_offset > 0:
        return "." * octave_offset
    else:
        return "," * abs(octave_offset)

def hz_to_sargam(hz, sa_midi):
    if hz <= 0 or np.isnan(hz):
        return None
    midi = librosa.hz_to_midi(hz)
    midi_rounded = round(midi)
    semitones_from_sa = (midi_rounded - sa_midi) % 12
    octave_offset = (midi_rounded - sa_midi) // 12
    syllable = SEMITONES_TO_SARGAM[semitones_from_sa]
    syllable += octave_suffix(octave_offset)
    return syllable

# ── Smoothing ───────────────────────────────────────────────────────

SMOOTH_WINDOW = 9

def smooth_pitch_sequence(notes):
    if len(notes) < SMOOTH_WINDOW:
        return notes
    runs = []
    current = notes[0]
    count = 1
    for note in notes[1:]:
        if note == current:
            count += 1
        else:
            runs.append([current, count])
            current = note
            count = 1
    runs.append([current, count])
    changed = True
    while changed:
        changed = False
        for i in range(1, len(runs) - 1):
            note, count = runs[i]
            if count < SMOOTH_WINDOW:
                prev_count = runs[i - 1][1]
                next_count = runs[i + 1][1]
                dominant = runs[i-1][0] if prev_count >= next_count else runs[i+1][0]
                if dominant != note:
                    runs[i][0] = dominant
                    changed = True
                    break
    smoothed = []
    for note, count in runs:
        smoothed.extend([note] * count)
    return smoothed

# ── Collapse with timestamps ────────────────────────────────────────

def collapse_with_timestamps(syllables, timestamps):
    """
    Collapse consecutive identical syllables, keeping the timestamp
    of the first frame of each note group. Filters out very short
    runs (transitions/noise) using a local windowed median threshold.
    """
    if not syllables:
        return [], []

    # Build groups: (note, count, start_timestamp)
    groups = []
    current = syllables[0]
    current_time = timestamps[0]
    count = 1
    for i in range(1, len(syllables)):
        if syllables[i] == current:
            count += 1
        else:
            groups.append((current, count, current_time))
            current = syllables[i]
            current_time = timestamps[i]
            count = 1
    groups.append((current, count, current_time))

    if len(groups) == 1:
        return [groups[0][0]], [groups[0][2]]

    LOCAL_WINDOW = 8
    half = LOCAL_WINDOW // 2
    run_lengths = [c for _, c, _ in groups]

    filtered_notes = []
    filtered_times = []

    for i, (note, count, t) in enumerate(groups):
        lo = max(0, i - half)
        hi = min(len(groups), i + half + 1)
        local_lengths = run_lengths[lo:hi]
        local_median = np.median(local_lengths)
        threshold = max(local_median * 0.10, 3)
        if count >= threshold:
            filtered_notes.append(note)
            filtered_times.append(t)

    return filtered_notes, filtered_times

# ── API endpoint ────────────────────────────────────────────────────

@app.post("/translate")
async def translate(file: UploadFile = File(...), sa: str = Form(...)):
    # Validate Sa
    sa = sa.strip().upper()
    enharmonic = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
    sa = enharmonic.get(sa, sa)
    if sa not in CHROMATIC_SCALE:
        return {"error": f"Invalid Sa: {sa}. Choose from {', '.join(CHROMATIC_SCALE)}"}

    sa_index = CHROMATIC_SCALE.index(sa)
    sa_midi = 48 + sa_index
    print(f"DEBUG SERVER: sa={sa}, sa_midi={sa_midi}, file={file.filename}")

    suffix = os.path.splitext(file.filename)[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=None, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        f0, voiced_flag, voiced_prob = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr
        )

        frame_times = librosa.times_like(f0, sr=sr)
        CONFIDENCE_THRESHOLD = 0.2

        # Convert frames to (syllable, timestamp) pairs
        syllables = []
        timestamps = []
        for hz, is_voiced, confidence, t in zip(f0, voiced_flag, voiced_prob, frame_times):
            if not is_voiced:
                continue
            if confidence < CONFIDENCE_THRESHOLD:
                continue
            syllable = hz_to_sargam(hz, sa_midi)
            if syllable is not None:
                syllables.append(syllable)
                timestamps.append(float(t))

        # Smooth then collapse, preserving timestamps
        syllables = smooth_pitch_sequence(syllables)
        # Re-align timestamps after smoothing (syllables list may have changed)
        # We rebuild timestamps to match the smoothed syllables by
        # keeping only timestamps at positions that survived smoothing.
        # Since smooth_pitch_sequence preserves length, timestamps stay aligned.
        syllables, timestamps = collapse_with_timestamps(syllables, timestamps)

        # Build response
        notes_with_times = [
            {"note": n, "time": round(t, 3)}
            for n, t in zip(syllables, timestamps)
        ]

        return {
            "sargam": notes_with_times,
            "duration": round(duration, 1),
            "total_notes": len(notes_with_times),
            "sa": sa,
        }

    except Exception as e:
        import traceback
        return {"error": str(e), "detail": traceback.format_exc()}

    finally:
        os.unlink(tmp_path)
