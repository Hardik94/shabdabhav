from piper import PiperVoice
import torch
from io import BytesIO
import soundfile as sf
import os

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
        self.model = PiperVoice.load_onnx(self.model_path, use_memory_mapping=True, device=DEVICE)
        # You may set other model options here, such as voice

    def get_cache_path(self, text):
        """Return local cache filename (optional, improves speed for repeated requests)"""
        if not self.local_cache_dir:
            return None
        import hashlib
        hash_id = hashlib.sha1(text.encode('utf-8')).hexdigest()
        return os.path.join(self.local_cache_dir, f"{hash_id}.wav")

    async def generate_audio(self, text: str):
        cache_path = self.get_cache_path(text)
        if cache_path and os.path.isfile(cache_path):
            # Fast path: serve cached audio
            with open(cache_path, "rb") as f:
                return BytesIO(f.read())

        if self.model is None:
            self.load()

        # Piper's synthesize returns PCM float32 audio
        audio = self.model.synthesize(text)
        buffer = BytesIO()
        sf.write(buffer, audio, self.model.sample_rate, format="WAV")
        buffer.seek(0)

        # Cache generated file for next time
        if cache_path:
            with open(cache_path, "wb") as f:
                f.write(buffer.getvalue())
            buffer.seek(0)

        return buffer
