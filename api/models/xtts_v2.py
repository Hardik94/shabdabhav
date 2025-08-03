from TTS.api import TTS
import asyncio
from io import BytesIO
import soundfile as sf

class XTTSV2ModelWrapper:
    def __init__(self, model_name="tts_models/en/vctk/vits"):
        """
        model_name: Coqui TTS model name or local path
        """
        self.model_name = model_name
        self.model = None

    async def load(self):
        import torch
        # This loads the TTS model
        if self.model is None:
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
            self.model = TTS(self.model_name, progress_bar=False).to(device)
            # self.model = TTS(self.model_name, progress_bar=False, gpu=torch.cuda.is_available())

    async def generate_audio(self, text: str):
        if self.model is None:
            await self.load()

        wav = self.model.tts(text, speaker_wav="./api/data/parler_tts_out.wav")
        # wav is numpy array (float32)
        buffer = BytesIO()
        sf.write(buffer, wav, self.model.synthesizer.output_sample_rate, format="WAV")
        buffer.seek(0)
        return buffer
