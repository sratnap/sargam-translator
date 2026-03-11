"""
Sargam Translator v1 — Proof of Concept
----------------------------------------
Takes a clean audio file (solo voice or single instrument, up to ~1 min)
and prints the melody as sargam notation relative to a user-defined Sa.

Usage:
    python sargam_translator.py <audio_file> <sa_note>

Example:
    python sargam_translator.py my_recording.mp3 C#

Supported Sa notes: C, C#, D, D#, E, F, F#, G, G#, A, A#, B
Supported audio formats: MP3, WAV, M4A, AAC
"""

import sys
import numpy as np
import librosa


# ─────────────────────────────────────────────
# SECTION 1: SARGAM MAPPING TABLE
# ─────────────────────────────────────────────
#
# In Hindustani music, all notes are relative to Sa.
# We measure distance from Sa in semitones (half-steps).
# 0 semitones = Sa, 1 semitone above = Komal Re, etc.
#
# Notation convention used here:
#   Uppercase = Shuddha (natural)
#   Lowercase = Komal (flat)
#   Apostrophe = Tivra (sharp) — only Tivra Ma exists
#   Dot suffix in name = octave (handled separately below)

SEMITONES_TO_SARGAM = {
    0:  "S",   # Sa          — always natural, the anchor
    1:  "r",   # Komal Re    — flat 2nd
    2:  "R",   # Shuddha Re  — natural 2nd
    3:  "g",   # Komal Ga    — flat 3rd
    4:  "G",   # Shuddha Ga  — natural 3rd
    5:  "M",   # Shuddha Ma  — natural 4th
    6:  "M'",  # Tivra Ma    — sharp 4th (the only tivra swara)
    7:  "P",   # Pa          — always natural, the 5th
    8:  "d",   # Komal Dha   — flat 6th
    9:  "D",   # Shuddha Dha — natural 6th
    10: "n",   # Komal Ni    — flat 7th
    11: "N",   # Shuddha Ni  — natural 7th
}

# All 12 chromatic pitch names, used to find the Sa's position
# in the equal-tempered scale
CHROMATIC_SCALE = ["C", "C#", "D", "D#", "E", "F",
                   "F#", "G", "G#", "A", "A#", "B"]


# ─────────────────────────────────────────────
# SECTION 2: OCTAVE LABEL HELPER
# ─────────────────────────────────────────────
#
# In Hindustani music there are three octave registers:
#   Mandra saptak  = lower octave  (dot below the note)
#   Madhya saptak  = middle octave (no marking)
#   Taar saptak    = upper octave  (dot above the note)
#
# Since we can't easily type dots in a terminal, we use:
#   (l) = lower / mandra
#   (no suffix) = middle / madhya
#   (h) = higher / taar

def octave_suffix(octave_offset):
    """
    octave_offset: how many octaves away from the middle octave.
    Returns a string suffix to append to the sargam syllable.
    """
    if octave_offset == 0:
        return ""       # madhya saptak — no marking needed
    elif octave_offset > 0:
        return "." * octave_offset    # e.g., S. = taar Sa
    else:
        return "," * abs(octave_offset)  # e.g., S, = mandra Sa


# ─────────────────────────────────────────────
# SECTION 3: HZ → SARGAM CONVERSION
# ─────────────────────────────────────────────
#
# A musical pitch can be expressed in Hz (vibrations per second).
# Standard tuning: A4 = 440 Hz.
# librosa.hz_to_midi() converts Hz to a MIDI note number —
# a universal integer scale where C4 (middle C) = 60.
#
# Once we have a MIDI number, we find:
#   1. Which of the 12 chromatic pitches it is (pitch class)
#   2. How far that is from Sa in semitones
#   3. Which octave register it's in relative to middle Sa

def hz_to_sargam(hz, sa_midi):
    """
    Convert a frequency in Hz to a sargam syllable.

    hz      : detected pitch frequency (e.g., 261.6 for C4)
    sa_midi : MIDI note number of the user's chosen Sa
              (e.g., 60 for C4, 61 for C#4)

    Returns a sargam string like "S", "r", "G", "M'", "P.", "n,"
    or None if the frequency is too low/high to be valid.
    """
    if hz <= 0 or np.isnan(hz):
        return None  # silence or unvoiced — skip

    # Convert Hz to MIDI note number (can be a float, e.g., 60.3)
    midi = librosa.hz_to_midi(hz)

    # Round to nearest semitone — this is the "pitch snapping"
    # described in the PRD. Handles vibrato and slight intonation drift.
    midi_rounded = round(midi)

    # How many semitones is this note above the Sa (in any octave)?
    # We use modulo 12 to collapse all octaves into one 0–11 range.
    semitones_from_sa = (midi_rounded - sa_midi) % 12

    # Which octave is this note in, relative to Sa's octave?
    # Integer division tells us how many octaves up or down.
    octave_offset = (midi_rounded - sa_midi) // 12

    # Look up the sargam syllable
    syllable = SEMITONES_TO_SARGAM[semitones_from_sa]

    # Append octave marker
    syllable += octave_suffix(octave_offset)

    return syllable


# ─────────────────────────────────────────────
# SECTION 4: AUDIO LOADING & PITCH DETECTION
# ─────────────────────────────────────────────
#
# librosa.load() reads the audio file and converts it to a
# mono waveform (single channel) sampled at 22,050 Hz —
# standard for audio analysis.
#
# librosa.pyin() is the pYIN algorithm — the same math used
# in instrument tuner apps, adapted for melodic audio.
# It estimates the fundamental frequency (F0) at each moment
# in time, returning:
#   f0         : array of Hz values, one per time frame
#   voiced_flag: True/False — was a pitched note detected here?
#   voiced_prob: confidence score (0–1)

def detect_pitches(audio_path):
    """
    Load an audio file and run pYIN pitch detection on it.
    Returns (f0, voiced_flag, times) arrays.
    """
    print(f"\nLoading audio: {audio_path}")
    # sr=None preserves the original sample rate
    y, sr = librosa.load(audio_path, sr=None, mono=True)

    duration = librosa.get_duration(y=y, sr=sr)
    print(f"Duration: {duration:.1f} seconds | Sample rate: {sr} Hz")

    print("Running pYIN pitch detection...")

    # fmin / fmax define the expected pitch range.
    # C2 (~65 Hz) to C7 (~2093 Hz) covers all voice types and most instruments.
    f0, voiced_flag, voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr
    )

    # Time stamps for each detected frame
    times = librosa.times_like(f0, sr=sr)

    return f0, voiced_flag, times


# ─────────────────────────────────────────────
# SECTION 5A: PITCH SMOOTHING
# ─────────────────────────────────────────────
#
# Vocal pitch naturally wavers slightly around a target note.
# This means pYIN might detect: D d D D d D D — when the singer
# clearly intended just D the whole time.
#
# We fix this with a sliding window majority vote:
#   - Look at each note and its surrounding SMOOTH_WINDOW neighbors
#   - Replace it with whichever note appears most in that window
#   - This irons out brief flickers without destroying real note changes

SMOOTH_WINDOW = 9  # frames — runs shorter than this are treated as noise/transitions

def smooth_pitch_sequence(notes):
    """
    Smooth out brief noisy runs WITHOUT blurring across real note boundaries.

    The old majority-vote window was eating notes like N when they sat
    between two longer notes (D and S.) because the window would see
    mostly D and S. frames and vote N away.

    New approach: work at the RUN level, not the frame level.
    - Build a list of runs: [(note, length), ...]
    - Any run shorter than SMOOTH_WINDOW is probably a transition/noise
    - Replace it with whichever neighbor run is longer
    - Long runs (real notes) are never touched
    """
    if len(notes) < SMOOTH_WINDOW:
        return notes

    # Build runs: [[note, count], ...]
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

    # Iteratively remove short noisy runs by merging into dominant neighbor
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

    # Reconstruct flat list from runs
    smoothed = []
    for note, count in runs:
        smoothed.extend([note] * count)

    return smoothed



# ─────────────────────────────────────────────
#
# pYIN detects pitch many times per second (roughly 86 frames/sec).
# If you hold a single note for 1 second, you'll get ~86 identical
# entries for that note. We collapse consecutive duplicates so the
# output reads like actual sargam: "S R G M" not "S S S S R R R R..."
#
# We also apply a minimum duration filter — a note must appear for
# at least MIN_FRAMES consecutive frames to count. This filters out
# the brief glide/transition pitches between notes.

# ─────────────────────────────────────────────────────────────
# ADAPTIVE THRESHOLD — how it works
# ─────────────────────────────────────────────────────────────
#
# Instead of a fixed minimum duration, we use the MEDIAN run length
# as a reference for what a "real note" looks like in this recording.
# Any run shorter than 10% of the median is treated as a transition/noise.
#
# This means:
#   - A slow alap (long held notes) → median is large, threshold scales up
#   - A fast taan (short quick notes) → median is small, threshold scales down
#   - Real notes are never dropped, even if slightly shorter than average
#   - Only very brief flickers (< 10% of median) get filtered out

def collapse_repeated_notes(sargam_list):
    """
    1. Group consecutive identical syllables into (note, run_length) pairs
    2. Compute adaptive minimum threshold from the distribution of run lengths
    3. Filter out runs below the threshold
    4. Return one entry per surviving note
    """
    if not sargam_list:
        return []

    # Step 1: group consecutive identical notes into (note, count) pairs
    groups = []
    current = sargam_list[0]
    count = 1
    for note in sargam_list[1:]:
        if note == current:
            count += 1
        else:
            groups.append((current, count))
            current = note
            count = 1
    groups.append((current, count))

    # Step 2: compute adaptive threshold from run length distribution
    run_lengths = [count for _, count in groups]
    # Use median run length as the reference for "what a real note looks like"
    median_length = np.median(run_lengths)
    # A run must be at least 10% of the median to count as a real note.
    # This means genuine notes (even slightly short ones) are never dropped —
    # only very brief flickers that are tiny compared to the rest of the song.
    threshold = max(median_length * 0.10, 3)

    # Step 3: filter out short runs below threshold
    filtered = [note for note, count in groups if count >= threshold]

    return filtered


# ─────────────────────────────────────────────
# SECTION 6: MAIN FUNCTION — PUT IT ALL TOGETHER
# ─────────────────────────────────────────────

def translate_to_sargam(audio_path, sa_note):
    """
    Full pipeline: audio file → sargam string.

    audio_path : path to the audio file (str)
    sa_note    : the root pitch as a note name, e.g. "C#", "D", "A"
    """

    # --- Validate Sa input ---
    sa_note = sa_note.strip().upper().replace("b", "#")  # normalize input
    # Common enharmonic equivalents (e.g., Db = C#)
    enharmonic = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
    sa_note = enharmonic.get(sa_note, sa_note)

    if sa_note not in CHROMATIC_SCALE:
        print(f"Error: '{sa_note}' is not a valid note.")
        print(f"Choose from: {', '.join(CHROMATIC_SCALE)}")
        sys.exit(1)

    # Find Sa's index in the chromatic scale (0=C, 1=C#, ... 11=B)
    sa_index = CHROMATIC_SCALE.index(sa_note)

    # We use octave 3 as our reference middle octave for typical singing voices.
    # (Octave 4 was too high, pushing most vocal output into mandra saptak)
    # MIDI note for Sa in octave 3:
    sa_midi = 48 + sa_index  # C3=48, so C#3=49, D3=50, etc.

    print(f"\nSa set to: {sa_note} (MIDI {sa_midi})")

    # --- Detect pitches ---
    f0, voiced_flag, times = detect_pitches(audio_path)

    # --- Convert each detected pitch to sargam ---
    sargam_notes = []
    for hz, is_voiced in zip(f0, voiced_flag):
        if not is_voiced:
            continue  # skip unvoiced/silent frames
        syllable = hz_to_sargam(hz, sa_midi)
        if syllable is not None:
            sargam_notes.append(syllable)

    # --- Debug: show raw note groups BEFORE any smoothing or filtering ---
    print("\n" + "-" * 60)
    print("DEBUG — raw note groups (note : frames held)")
    print("-" * 60)
    raw_groups = []
    if sargam_notes:
        current = sargam_notes[0]
        count = 1
        for note in sargam_notes[1:]:
            if note == current:
                count += 1
            else:
                raw_groups.append((current, count))
                current = note
                count = 1
        raw_groups.append((current, count))
        for note, count in raw_groups:
            print(f"  {note:6s} : {count} frames (~{count/86*1000:.0f}ms)")
    print("-" * 60)

    # --- Smooth pitch sequence before collapsing ---
    # If a note rapidly alternates between two adjacent semitones
    # (e.g. D and d), replace each short flicker with the dominant
    # note in that local window. Window size = 9 frames (~100ms).
    sargam_notes = smooth_pitch_sequence(sargam_notes)

    # --- Collapse repeated notes ---
    sargam_notes = collapse_repeated_notes(sargam_notes)

    # --- Print the result ---
    print("\n" + "=" * 60)
    print("SARGAM OUTPUT")
    print("=" * 60)

    if not sargam_notes:
        print("No pitched notes detected. Try a cleaner recording.")
    else:
        # Print in rows of 16 notes for readability
        row_size = 16
        for i in range(0, len(sargam_notes), row_size):
            print("  ".join(sargam_notes[i:i + row_size]))

    print("=" * 60)
    print(f"Total notes detected: {len(sargam_notes)}")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python sargam_translator.py <audio_file> <sa_note>")
        print("Example: python sargam_translator.py recording.mp3 C#")
        sys.exit(1)

    audio_file = sys.argv[1]
    sa_input = sys.argv[2]

    translate_to_sargam(audio_file, sa_input)
