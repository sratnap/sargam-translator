"""
SurSargam — FastAPI Server v3.1
--------------------------------
Serves the full app (index.html + translation API) from a single process.

Security:
  - APP_PASSWORD environment variable gates access.
  - /auth exchanges the password for a signed, expiring token.
  - /translate REQUIRES a valid token — the endpoint does no work without one.
  - Uploads are size-capped before any audio decoding happens.

Local development:
    python -m uvicorn server:app --reload
    Then open http://localhost:8000

    If APP_PASSWORD is not set, auth is disabled entirely (open access).
    To test the locked-down behaviour locally:
        set APP_PASSWORD=testpass
        python -m uvicorn server:app --reload

Production (Render):
    Set APP_PASSWORD in the Render dashboard.
    Start command: uvicorn server:app --host 0.0.0.0 --port $PORT
"""

import tempfile
import os
import time
import hmac
import hashlib
import numpy as np
import librosa
from fastapi import FastAPI, UploadFile, File, Form, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ────────────────────────────────────────────────────────────
# APP_PASSWORD is set as an environment variable on Render.
# If it is empty (typical local dev), auth is disabled and everything is open.

APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

# Tokens are signed with a secret derived from the password, so rotating
# APP_PASSWORD automatically invalidates every token already issued.
_SECRET = hashlib.sha256(("sursargam::" + APP_PASSWORD).encode()).digest()

TOKEN_LIFETIME_SECONDS = 7 * 24 * 60 * 60  # 7 days


def make_token():
    """Create a token of the form '<expiry>.<signature>'."""
    expiry = str(int(time.time()) + TOKEN_LIFETIME_SECONDS)
    signature = hmac.new(_SECRET, expiry.encode(), hashlib.sha256).hexdigest()
    return f"{expiry}.{signature}"


def token_is_valid(token):
    """Verify a token's signature and expiry. Returns True/False, never raises."""
    if not token or "." not in token:
        return False
    expiry, signature = token.rsplit(".", 1)
    expected = hmac.new(_SECRET, expiry.encode(), hashlib.sha256).hexdigest()
    # compare_digest avoids leaking information through timing
    if not hmac.compare_digest(signature, expected):
        return False
    try:
        return int(expiry) > int(time.time())
    except ValueError:
        return False


def auth_required():
    """Auth is only enforced when a password has actually been configured."""
    return bool(APP_PASSWORD)


# ── Rate limiting ───────────────────────────────────────────────────
# Two separate guards, both in-memory (no database, no extra dependency):
#
#   1. Hourly cap  — how many translations one user may run per hour.
#   2. Queue depth — how many translations may be waiting at any moment.
#
# The queue guard matters because librosa runs synchronously and blocks the
# whole event loop while it works. A deep queue makes the entire site
# unresponsive, not just slow, so it is better to turn people away quickly
# with a clear message than to let requests pile up and time out.
#
# NOTE: this state lives in memory, so it resets whenever Render restarts or
# spins the instance down. That is fine for protecting against accidents and
# casual overuse. It is not a defence against a determined attacker.

RATE_LIMIT_PER_HOUR = 20   # translations per user per hour
MAX_QUEUE_DEPTH = 3        # translations queued or running at once

_request_log = {}          # key -> list of unix timestamps
_in_flight = 0             # translations currently queued or running


def _rate_key(request):
    """Identify the caller: by token if we have one, otherwise by IP."""
    token = request.headers.get("x-auth-token", "")
    if token:
        # The signature is the unique part; it is already a hash, so this
        # is a stable per-session identifier without storing the token.
        return "t:" + token.rsplit(".", 1)[-1][:16]
    client = request.client.host if request.client else "unknown"
    return "ip:" + client


def _check_and_record_rate(key):
    """
    Returns None if the request is allowed, or seconds-until-retry if not.
    Prunes timestamps older than an hour as it goes.
    """
    now = time.time()
    cutoff = now - 3600

    stamps = [t for t in _request_log.get(key, []) if t > cutoff]

    if len(stamps) >= RATE_LIMIT_PER_HOUR:
        _request_log[key] = stamps
        retry_after = int(stamps[0] + 3600 - now) + 1
        return max(retry_after, 1)

    stamps.append(now)
    _request_log[key] = stamps

    # Opportunistic cleanup so the dict cannot grow without bound
    if len(_request_log) > 500:
        for k in [k for k, v in _request_log.items() if not any(t > cutoff for t in v)]:
            del _request_log[k]

    return None


# ── Middleware ──────────────────────────────────────────────────────
# Runs BEFORE FastAPI parses the request body, so a rejected request never
# causes the server to buffer an upload. The in-handler auth check below is
# kept as a second layer.

PROTECTED_PATHS = {"/translate"}


@app.middleware("http")
async def guard_translate(request: Request, call_next):
    global _in_flight

    if request.url.path not in PROTECTED_PATHS:
        return await call_next(request)

    # ── 1. Auth ──
    if auth_required():
        token = request.headers.get("x-auth-token", "")
        if not token_is_valid(token):
            return JSONResponse(
                {"error": "Not authorised. Please refresh the page and sign in again."},
                status_code=401,
            )

    # ── 2. Queue depth ──
    if _in_flight >= MAX_QUEUE_DEPTH:
        return JSONResponse(
            {"error": "The server is busy with other translations right now. "
                      "Please wait a moment and try again."},
            status_code=429,
            headers={"Retry-After": "30"},
        )

    # ── 3. Hourly cap ──
    key = _rate_key(request)
    retry_after = _check_and_record_rate(key)
    if retry_after is not None:
        minutes = max(1, retry_after // 60)
        return JSONResponse(
            {"error": f"You've reached the limit of {RATE_LIMIT_PER_HOUR} translations "
                      f"per hour. Please try again in about {minutes} minute"
                      f"{'s' if minutes != 1 else ''}."},
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    _in_flight += 1
    try:
        return await call_next(request)
    finally:
        _in_flight -= 1


@app.post("/auth")
async def auth(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    entered = body.get("password", "")

    if not auth_required():
        # No password configured — open access, but still hand back a token
        # so the frontend can use one code path everywhere.
        return JSONResponse({"ok": True, "token": make_token()})

    if hmac.compare_digest(entered, APP_PASSWORD):
        return JSONResponse({"ok": True, "token": make_token()})

    return JSONResponse({"ok": False}, status_code=401)


# ── Serve frontend ──────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "index.html")
    return FileResponse(index_path, media_type="text/html")


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


# ── Upload limits ───────────────────────────────────────────────────
# Checked before any decoding, so an oversized file can never reach librosa.

MAX_UPLOAD_BYTES = 20 * 1024 * 1024   # 20 MB
MAX_DURATION_SECONDS = 300            # 5 minutes


# ── Translation endpoint ────────────────────────────────────────────

@app.post("/translate")
async def translate(
    file: UploadFile = File(...),
    sa: str = Form(...),
    x_auth_token: str = Header(default=""),
):
    # ── Gate 1: token. Nothing below this runs without a valid token. ──
    if auth_required() and not token_is_valid(x_auth_token):
        return JSONResponse(
            {"error": "Not authorised. Please refresh the page and sign in again."},
            status_code=401,
        )

    # ── Gate 2: validate Sa before touching the file ──
    sa = sa.strip().upper()
    enharmonic = {"DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"}
    sa = enharmonic.get(sa, sa)
    if sa not in CHROMATIC_SCALE:
        return {"error": f"Invalid Sa: {sa}. Choose from {', '.join(CHROMATIC_SCALE)}"}

    sa_index = CHROMATIC_SCALE.index(sa)
    sa_midi = 48 + sa_index

    # ── Gate 3: size cap, checked on the raw bytes before decoding ──
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES // (1024 * 1024)
        return {"error": f"File is too large. Please keep uploads under {mb} MB."}

    suffix = os.path.splitext(file.filename)[1] or ".wav"

    # Log the file TYPE, never the filename — filenames often contain
    # personal detail (names, lesson titles) and we have no need for them.
    print(f"SurSargam: sa={sa}, sa_midi={sa_midi}, "
          f"type={suffix}, bytes={len(contents)}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        y, sr = librosa.load(tmp_path, sr=None, mono=True)

        # ── Gate 4: duration cap, now that we know the real length ──
        raw_duration = librosa.get_duration(y=y, sr=sr)
        if raw_duration > MAX_DURATION_SECONDS:
            mins = MAX_DURATION_SECONDS // 60
            return {"error": f"Audio is too long. Please keep it under {mins} minutes."}

        # Pad with 0.5s silence at end — prevents pYIN from cutting off final notes
        silence = np.zeros(int(sr * 0.5))
        y = np.concatenate([y, silence])
        duration = raw_duration

        f0, voiced_flag, voiced_prob = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr
        )

        frame_times = librosa.times_like(f0, sr=sr)
        CONFIDENCE_THRESHOLD = 0.2

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

        syllables = smooth_pitch_sequence(syllables)
        syllables, timestamps = collapse_with_timestamps(syllables, timestamps)

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
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
