from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import torch
from io import BytesIO
import soundfile as sf

import os

DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"

class ParlerTTSModelWrapper:
    def __init__(self, model_id: str, model_dir: str = None):
        """
        model_id: HuggingFace model id e.g. "parler-tts/parler-tts-mini-v1"
        model_dir: If provided, load model files from this local directory for faster load
        """
        self.model_id = model_id
        self.model_dir = model_dir
        self.model = None
        self.tokenizer = None

    async def load(self):
        # Load model and tokenizer from local path or HuggingFace hub
        model_path = self.model_dir or self.model_id
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(model_path).to(DEVICE)
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)

    async def generate_audio(self, prompt: str, description: str):
        if self.model is None or self.tokenizer is None:
            await self.load()

        desc_tokens = self.tokenizer(description, return_tensors="pt")
        prompt_tokens = self.tokenizer(prompt, return_tensors="pt")
        input_ids = desc_tokens.input_ids.to(DEVICE)
        attention_mask = desc_tokens.attention_mask.to(DEVICE)
        prompt_ids = prompt_tokens.input_ids.to(DEVICE)

        with torch.no_grad():
            output = self.model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                prompt_input_ids=prompt_ids
            )
        audio = output.cpu().numpy().squeeze()

        buffer = BytesIO()
        sf.write(buffer, audio, self.model.config.sampling_rate, format="WAV")
        buffer.seek(0)
        return buffer
