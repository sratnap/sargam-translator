"""
Sargam Translator — FastAPI Server
------------------------------------
Runs the sargam translation logic as a local web server.
The webpage (index.html) talks to this server.

To start the server, run in Command Prompt:
    uvicorn server:app --reload

Then open index.html in your browser.
"""

import tempfile
import os
import numpy as np
import librosa
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow the HTML page to talk to this server
# (browsers block cross-origin requests by default)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Sargam mapping (same as sargam_translator.py) ──────────────────

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

SMOOTH_WINDOW = 9   # keeps short real notes intact while smoothing brief flickers

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

def collapse_repeated_notes(sargam_list):
    """
    Filter out transition noise while preserving both slow and fast notes.

    The old approach used a single global median threshold — this worked
    for uniform-paced recordings but ate short notes in fast passages when
    the median was dominated by long slow-section notes.

    New approach: LOCAL windowed threshold.
    - Divide the note groups into overlapping windows of LOCAL_WINDOW size
    - Compute a separate median threshold for each window
    - Each note is judged against its LOCAL context, not the global average
    - This means fast passages get a low threshold (keeps short notes)
      and slow passages get a higher threshold (filters wobble noise)
    """
    if not sargam_list:
        return []

    # Build groups of consecutive identical notes
    groups = []
    current = sargam_list[0]
    count = 1
    for note in sargam_list[1:]:
        if note == current:
            count += 1
        else:
            groups.append([current, count])
            current = note
            count = 1
    groups.append([current, count])

    if len(groups) == 1:
        return [groups[0][0]]

    # LOCAL_WINDOW: how many surrounding notes to consider when setting
    # the threshold for a given note. 8 means "look at the 4 notes before
    # and 4 notes after me to judge what counts as short in this passage."
    LOCAL_WINDOW = 8
    half = LOCAL_WINDOW // 2

    run_lengths = [c for _, c in groups]
    filtered = []

    for i, (note, count) in enumerate(groups):
        # Get the local window of run lengths around this note
        lo = max(0, i - half)
        hi = min(len(groups), i + half + 1)
        local_lengths = run_lengths[lo:hi]

        # Local threshold = 10% of local median, minimum 3 frames
        local_median = np.median(local_lengths)
        threshold = max(local_median * 0.10, 3)

        if count >= threshold:
            filtered.append(note)

    return filtered

# ── API endpoint ────────────────────────────────────────────────────

@app.post("/translate")
async def translate(file: UploadFile = File(...), sa: str = Form(...)):
    """
    Receives an audio file and a Sa note from the webpage.
    Returns the sargam transcription as JSON.
    """

    # Validate Sa
    sa = sa.strip().upper()
    enharmonic = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
    sa = enharmonic.get(sa, sa)
    if sa not in CHROMATIC_SCALE:
        return {"error": f"Invalid Sa: {sa}. Choose from {', '.join(CHROMATIC_SCALE)}"}

    sa_index = CHROMATIC_SCALE.index(sa)
    sa_midi = 48 + sa_index

    # Save uploaded file to a temporary location so librosa can read it
    suffix = os.path.splitext(file.filename)[1]  # e.g. ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Load and detect pitches
        y, sr = librosa.load(tmp_path, sr=None, mono=True)
        duration = librosa.get_duration(y=y, sr=sr)

        f0, voiced_flag, voiced_prob = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr
        )

        # Confidence filtering — pYIN gives each frame a voiced probability
        # (0.0 to 1.0). We use a low threshold of 0.2 here — just enough to
        # cut completely unvoiced frames (silence, breath) without accidentally
        # dropping real notes. The smoothing and collapse steps handle the rest.
        CONFIDENCE_THRESHOLD = 0.2

        # Convert to sargam
        sargam_notes = []
        for hz, is_voiced, confidence in zip(f0, voiced_flag, voiced_prob):
            if not is_voiced:
                continue
            if confidence < CONFIDENCE_THRESHOLD:
                continue  # skip low-confidence frames (transitions, breath noise)
            syllable = hz_to_sargam(hz, sa_midi)
            if syllable is not None:
                sargam_notes.append(syllable)

        sargam_notes = smooth_pitch_sequence(sargam_notes)
        sargam_notes = collapse_repeated_notes(sargam_notes)

        return {
            "sargam": sargam_notes,         # list of note strings
            "duration": round(duration, 1),
            "total_notes": len(sargam_notes),
            "sa": sa,
        }

    except Exception as e:
        return {"error": str(e)}

    finally:
        os.unlink(tmp_path)  # clean up the temp file
