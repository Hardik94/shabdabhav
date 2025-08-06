from piper import PiperVoice
import torch
from io import BytesIO
import soundfile as sf
import os
import numpy as np
from typing import AsyncGenerator

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

class PiperTTSModelWrapper:
    def __init__(self, model_path: str, local_cache_dir: str = None, voice: str = None):
        """
        model_path: Path to the .onnx model file for Piper
        local_cache_dir: Directory for on-disk audio cache (optional)
        voice: Piper voice name/variant, if supported by your model
        """
        self.model_path = model_path
        self.local_cache_dir = local_cache_dir
        self.voice = voice
        self.model = None

        if self.local_cache_dir and not os.path.exists(self.local_cache_dir):
            os.makedirs(self.local_cache_dir, exist_ok=True)

    def load(self):
        # Load Piper ONNX using memory mapping for efficiency
        # self.model = PiperVoice.load_onnx(self.model_path, use_memory_mapping=True, device=DEVICE)
        self.model = PiperVoice.load(self.model_path, self.model_path+".json", use_cuda=True) if DEVICE == "cuda" \
            else PiperVoice.load(self.model_path, self.model_path+".json")

        # You may set other model options here, such as voice

    def get_cache_path(self, text):
        """Return local cache filename (optional, improves speed for repeated requests)"""
        if not self.local_cache_dir:
            return None
        import hashlib
        hash_id = hashlib.sha1(text.encode('utf-8')).hexdigest()
        return os.path.join(self.local_cache_dir, f"{hash_id}.wav")
    
    def synthesize_to_buffer(self, text):
        audio_int16 = []
        sample_rate = None
        sample_width = None
        sample_channels = None

        # Collect all chunks
        for chunk in self.model.synthesize(text):
            if sample_rate is None:
                sample_rate = chunk.sample_rate
                sample_width = chunk.sample_width
                sample_channels = chunk.sample_channels
            audio_int16.append(chunk.audio_int16_bytes)

        if not audio_int16:
            raise RuntimeError("No audio generated.")

        # Concatenate all the raw bytes
        all_bytes = b"".join(audio_int16)

        # Convert bytes to numpy array
        audio_np = np.frombuffer(all_bytes, dtype=np.int16)

        # Reshape for channels if needed
        if sample_channels > 1:
            audio_np = audio_np.reshape(-1, sample_channels)

        # Write to in-memory WAV
        buffer = BytesIO()
        sf.write(buffer, audio_np, sample_rate, format="WAV", subtype="PCM_16")
        buffer.seek(0)
        return buffer


    async def generate_audio(self, text: str):
        cache_path = self.get_cache_path(text)
        if cache_path and os.path.isfile(cache_path):
            # Fast path: serve cached audio
            with open(cache_path, "rb") as f:
                return BytesIO(f.read())

        if self.model is None:
            self.load()

        return self.synthesize_to_buffer(text)

    async def pipersynth_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Stream Piper TTS output, chunk by chunk, formatted as WAV stream."""
        # We will collect PCM chunks, but stream as they come as raw PCM inside WAV container.

        # Pipe to a BytesIO buffer to write WAV header and data chunk by chunk
        buffer = BytesIO()

        # We need to write a valid WAV header at the start, and update sizes at the end
        # soundfile / wave support streaming only in "file" mode, so we'll buffer chunks and yield in batches.

        # Instead of yielding raw int16 bytes immediately (not WAV), 
        # we concatenate chunks and yield WAV data in single pass using a workaround below.

        # Because SoundFile does not support streaming write to BytesIO incrementally,
        # we collect chunks in memory first, then yield as one streaming response:
        # This approach loses streaming benefit but maintains WAV format.

        # Streaming true WAV requires custom wave chunk handling or streaming raw PCM (not WAV) chunks.

        # BUT, since you asked for streaming WAV, we must re-think strategy:

        # --- Approach #1 (simpler): stream raw PCM (int16) chunks + set content type accordingly ---
        # This is best client if expecting raw PCM stream or using custom player.

        # Yield raw PCM with application/octet-stream or audio/L16 content-type:
        for chunk in self.model.synthesize(text):
            # chunk.audio_int16_bytes is raw bytes of int16 PCM audio
            yield chunk.audio_int16_bytes
    