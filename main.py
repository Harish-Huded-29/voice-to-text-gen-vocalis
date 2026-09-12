import asyncio
import collections
import json
import os
import queue
import re
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager

# Ensure UTF-8 console output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import sounddevice as sd
import torch
import uvicorn
import webrtcvad
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from transformers import AutoProcessor, SeamlessM4TForSpeechToText

# ---------------------------------------------------------------------------
# Paths & Audio Configuration
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SEAMLESS_DIR = os.path.join(BASE_DIR, "models", "seamless-m4t-medium")

SAMPLE_RATE = 16000           # 16 kHz required by WebRTC VAD and SeamlessM4T
FRAME_DURATION_MS = 30        # 30 ms per VAD frame
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000)  # 480 samples
FRAME_BYTES = FRAME_SAMPLES * 2                              # 960 bytes (16-bit int)

# VAD sensitivity: 2 (balanced noise suppression)
VAD_MODE = 2

PRE_SPEECH_FRAMES = 12        # ~360 ms pre-speech buffer
VOICE_TRIGGER_COUNT = 3       # 3 consecutive voiced frames (~90ms) to trigger genuine speech
SILENCE_TRIGGER_FRAMES = 20   # ~600 ms pause to finalize sentence
MIN_SENTENCE_DURATION_S = 0.45 # Minimum 0.45s speech length

# Energy Thresholds to filter background hum / breathing
FRAME_RMS_MIN = 0.012         # Minimum frame volume for speech eligibility
MIN_AUDIO_RMS = 0.012         # Minimum average sentence energy
MIN_AUDIO_PEAK = 0.035        # Minimum peak vocal energy to reject flat background hum

# Known silence/ambient noise dataset artifacts to ignore
HALLUCINATIONS = [
    r"it's\s+a\s+little\s+bit\s+of\s+a\s+stretch",
    r"the\s+first\s+thing\s+i\s+want\s+to\s+do",
    r"get\s+the\s+message\s+across\s+to\s+the\s+audience",
    r"the\s+second\s+half\s+of\s+the\s+game",
    r"thank\s+you\s+very\s+much",
    r"thank\s+you\s+so\s+much",
    r"thank\s+you",
    r"thanks\s+for\s+watching",
    r"thank\s+you\s+for\s+watching",
    r"please\s+subscribe",
    r"like\s+and\s+subscribe",
    r"subtitles\s+by",
    r"transcription\s+by",
    r"copyright",
    r"all\s+rights\s+reserved",
    r"you're\s+welcome",
    r"^\s*you[\.\!\?]?\s*$",
    r"^\s*bye[\.\!\?]?\s*$",
    r"^\s*the\s*$",
    r"^\s*[\.\,\?\!\s\-–—]+\s*$",
    r"\[music\]",
    r"\(music\)",
    r"\[applause\]",
    r"\(applause\)",
    r"\[silence\]",
]
HALLUCINATION_REGEX = re.compile("|".join(HALLUCINATIONS), re.IGNORECASE)

# ---------------------------------------------------------------------------
# Global State & Model Handles
# ---------------------------------------------------------------------------
processor: AutoProcessor = None
model: SeamlessM4TForSpeechToText = None
device: str = "cpu"

connected_clients = set()
event_loop: asyncio.AbstractEventLoop = None
transcription_queue = queue.Queue()
audio_stop_event = threading.Event()
is_capture_active = True
selected_device_id = None


def load_seamless_model():
    """Loads Meta SeamlessM4T Medium model from local directory."""
    global processor, model, device
    print(f"[*] Loading Meta SeamlessM4T Medium from: {SEAMLESS_DIR}")
    t0 = time.time()
    
    processor = AutoProcessor.from_pretrained(SEAMLESS_DIR)
    
    if torch.cuda.is_available():
        try:
            device = "cuda"
            model = SeamlessM4TForSpeechToText.from_pretrained(SEAMLESS_DIR, torch_dtype=torch.float16).to(device)
            print(f"[+] SeamlessM4T loaded on CUDA (float16) in {time.time()-t0:.2f}s!")
            return
        except Exception as cuda_err:
            print(f"[!] CUDA loading note: {cuda_err}. Falling back to CPU...")
    
    device = "cpu"
    model = SeamlessM4TForSpeechToText.from_pretrained(SEAMLESS_DIR)
    print(f"[+] SeamlessM4T loaded on CPU in {time.time()-t0:.2f}s!")


def broadcast_message(payload: dict):
    """Safely dispatches a JSON payload to all connected WebSocket clients."""
    if not connected_clients or event_loop is None:
        return
    for ws in list(connected_clients):
        try:
            asyncio.run_coroutine_threadsafe(ws.send_json(payload), event_loop)
        except Exception:
            pass


def is_speech_frame(vad, frame_bytes: bytes) -> bool:
    """True speech frame: satisfies WebRTC VAD and exceeds noise floor."""
    samples = np.frombuffer(frame_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    frame_rms = float(np.sqrt(np.mean(samples**2)))
    
    # Reject faint background hiss / breathing below noise floor
    if frame_rms < FRAME_RMS_MIN:
        return False
    
    try:
        return vad.is_speech(frame_bytes, SAMPLE_RATE)
    except Exception:
        return False


def host_mic_worker():
    """Continuously records microphone from system audio with zero latency."""
    def audio_callback(indata, frames, time_info, status):
        if not is_capture_active:
            return
        raw_bytes = bytes(indata)
        transcription_queue.put(raw_bytes)
        
        # Broadcast live audio volume level for frontend visualizer
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(samples**2)))
        level_pct = min(100, int(rms * 450))
        if level_pct > 2:
            broadcast_message({"type": "volume", "level": level_pct})

    while not audio_stop_event.is_set():
        try:
            dev = selected_device_id
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES,
                                   dtype='int16', channels=1, device=dev,
                                   callback=audio_callback):
                print(f"[+] Microphone active (Device: {dev or 'System Default'}). Ready to listen!")
                while not audio_stop_event.is_set():
                    time.sleep(0.5)
        except Exception as e:
            print(f"[!] Microphone initialization note: {e}. Retrying in 2s...")
            time.sleep(2)


def vad_processing_loop():
    """Consumes incoming 16kHz audio, performs VAD segmentation, and triggers Speech-to-English translation."""
    vad = webrtcvad.Vad(VAD_MODE)
    ring_buffer = collections.deque(maxlen=PRE_SPEECH_FRAMES)
    triggered = False
    voiced_frames = []
    silence_counter = 0
    buffered_bytes = bytearray()

    while not audio_stop_event.is_set():
        if not is_capture_active:
            while not transcription_queue.empty():
                try:
                    transcription_queue.get_nowait()
                except queue.Empty:
                    break
            buffered_bytes.clear()
            voiced_frames.clear()
            ring_buffer.clear()
            triggered = False
            silence_counter = 0
            time.sleep(0.05)
            continue

        try:
            chunk = transcription_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        buffered_bytes.extend(chunk)

        while len(buffered_bytes) >= FRAME_BYTES:
            frame = bytes(buffered_bytes[:FRAME_BYTES])
            del buffered_bytes[:FRAME_BYTES]

            is_speech = is_speech_frame(vad, frame)

            if not triggered:
                ring_buffer.append((frame, is_speech))
                num_voiced = sum(1 for _, speech in ring_buffer if speech)
                if num_voiced >= VOICE_TRIGGER_COUNT:
                    triggered = True
                    print("[VAD] 🎤 Voice detected, listening...")
                    broadcast_message({"type": "status", "state": "speaking"})
                    for f, _ in ring_buffer:
                        voiced_frames.append(f)
                    ring_buffer.clear()
                    silence_counter = 0
            else:
                voiced_frames.append(frame)
                if is_speech:
                    silence_counter = 0
                else:
                    silence_counter += 1

                if silence_counter >= SILENCE_TRIGGER_FRAMES:
                    triggered = False
                    broadcast_message({"type": "status", "state": "transcribing"})
                    
                    pcm_data = b"".join(voiced_frames)
                    voiced_frames.clear()
                    silence_counter = 0
                    ring_buffer.clear()

                    duration_s = len(pcm_data) / (SAMPLE_RATE * 2)
                    if duration_s >= MIN_SENTENCE_DURATION_S:
                        print(f"[VAD] ⚡ Pause detected ({duration_s:.2f}s audio). Running SeamlessM4T...")
                        process_seamless_translation(pcm_data)
                    
                    broadcast_message({
                        "type": "status",
                        "state": "listening" if is_capture_active else "paused"
                    })


def process_seamless_translation(pcm_bytes: bytes):
    """
    Directly translates Kannada, Hindi, Tamil, Telugu, Marathi, Spanish, etc.
    speech audio into fluent English text using Meta SeamlessM4T Medium.
    """
    try:
        audio_np = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        rms = np.sqrt(np.mean(audio_np**2))
        max_peak = np.max(np.abs(audio_np))
        
        # Discard background fan hum / low energy clicks
        if rms < MIN_AUDIO_RMS or max_peak < MIN_AUDIO_PEAK:
            return

        # Peak normalization for optimal acoustic clarity
        if max_peak > 0.01:
            audio_np = audio_np * (0.90 / max_peak)

        # Preprocess 16kHz audio for SeamlessM4T
        audio_inputs = processor(audio=audio_np, return_tensors="pt", sampling_rate=SAMPLE_RATE)
        if device == "cuda":
            audio_inputs = {k: v.to("cuda") for k, v in audio_inputs.items()}

        # Generate Speech-to-English translation
        with torch.no_grad():
            output_tokens = model.generate(
                **audio_inputs,
                tgt_lang="eng",
                max_new_tokens=80,
                repetition_penalty=1.2,
            )

        english_text = processor.decode(output_tokens[0].tolist(), skip_special_tokens=True).strip()

        # Reject empty text, single letters, or hallucinated dataset phrases
        if not english_text or len(english_text) < 3 or HALLUCINATION_REGEX.search(english_text):
            return

        payload = {
            "type": "transcript",
            "id": str(uuid.uuid4()),
            "text": english_text,
            "source_language": "multilingual",
            "source_language_name": "Indic / Global Speech",
            "language": "en",
            "language_prob": 1.0,
            "duration": round(len(audio_np) / SAMPLE_RATE, 2),
            "timestamp": time.time(),
        }
        
        broadcast_message(payload)
        print(f"[✨ Seamless English Output]: {payload['text']}\n")

    except Exception as err:
        print(f"[!] Seamless translation error: {err}", file=sys.stderr)


# ---------------------------------------------------------------------------
# FastAPI Web Application & WebSocket Server
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global event_loop
    event_loop = asyncio.get_running_loop()
    
    load_seamless_model()
    
    vad_thread = threading.Thread(target=vad_processing_loop, daemon=True)
    vad_thread.start()
    
    mic_thread = threading.Thread(target=host_mic_worker, daemon=True)
    mic_thread.start()
    
    yield
    
    audio_stop_event.set()


app = FastAPI(title="Meta SeamlessM4T Speech-to-English API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {
        "status": "online",
        "model_loaded": model is not None,
        "capture_active": is_capture_active,
        "clients_connected": len(connected_clients),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global is_capture_active, selected_device_id
    await websocket.accept()
    connected_clients.add(websocket)
    print(f"[+] WebSocket client connected. Total clients: {len(connected_clients)}")
    
    await websocket.send_json({
        "type": "status",
        "state": "listening" if is_capture_active else "paused",
        "capture_active": is_capture_active,
        "message": "Connected to Meta SeamlessM4T Speech-to-English pipeline",
    })

    try:
        while True:
            message = await websocket.receive()
            
            if "bytes" in message and message["bytes"]:
                if is_capture_active:
                    transcription_queue.put(message["bytes"])
            elif "text" in message and message["text"]:
                try:
                    msg = json.loads(message["text"])
                    action = msg.get("type")
                    
                    if action == "set_capture":
                        is_capture_active = bool(msg.get("active", True))
                        broadcast_message({
                            "type": "status",
                            "state": "listening" if is_capture_active else "paused",
                            "capture_active": is_capture_active,
                        })

                    elif action == "set_device":
                        selected_device_id = msg.get("device_id")

                except Exception as parse_err:
                    print(f"[!] Error parsing client message: {parse_err}")

    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        print(f"[-] WebSocket client disconnected. Remaining: {len(connected_clients)}")
    except Exception as e:
        connected_clients.discard(websocket)
        print(f"[!] WebSocket error: {e}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
