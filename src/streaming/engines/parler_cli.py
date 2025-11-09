from pathlib import Path
from io import BytesIO


async def synthesize_with_parler(text: str, model: str, description: str | None = None) -> bytes:
    """
    Optional Parler-TTS inference. Requires extra deps inside the QUIC container:
      pip install parler-tts transformers soundfile torch

    Expects the model snapshot to be available under data/models/<model>/
    """
    try:
        import torch  # noqa: F401
        import soundfile as sf
        from transformers import AutoTokenizer
        from parler_tts import ParlerTTSForConditionalGeneration
    except Exception as exc:
        raise FileNotFoundError(
            "Parler-TTS runtime not installed. Install: 'pip install parler-tts transformers soundfile torch'"
        ) from exc

    # Resolve local model directory
    from src.common.config import models_root

    local_dir = models_root() / model
    if not local_dir.exists():
        raise FileNotFoundError(f"Parler model not found at {local_dir}")

    # Minimal inference per upstream examples
    tok = AutoTokenizer.from_pretrained(str(local_dir))
    net = ParlerTTSForConditionalGeneration.from_pretrained(str(local_dir))

    if not description:
        description = "A clear, neutral voice"

    inputs = tok(text, return_tensors="pt")
    desc = tok(description, return_tensors="pt")
    with torch.no_grad():
        audio = net.generate(**inputs, description=desc.input_ids)
    audio = audio.squeeze().cpu().numpy()

    buf = BytesIO()
    sf.write(buf, audio, 22050, format="WAV")
    buf.seek(0)
    return buf.read()


