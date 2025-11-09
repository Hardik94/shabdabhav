from pathlib import Path
from typing import Optional, Dict, Any
from io import BytesIO
import tempfile


async def transcribe_with_hf_whisper(audio_bytes: bytes, model_id: str, language: Optional[str] = None) -> Dict[str, Any]:
    """
    Transcribe using Hugging Face Transformers Whisper (e.g., openai/whisper-small).
    Optional dependency inside QUIC container:
      pip install transformers torch soundfile
    """
    try:
        import soundfile as sf
        from transformers import WhisperProcessor, WhisperForConditionalGeneration
        import torch
    except Exception as exc:
        raise FileNotFoundError(
            "HF Whisper runtime not installed. Install: 'pip install transformers torch soundfile'"
        ) from exc

    # Load model and processor from hub (cached in HF_HOME or ~/.cache)
    processor = WhisperProcessor.from_pretrained(model_id)
    model = WhisperForConditionalGeneration.from_pretrained(model_id)
    model.eval()

    # Read audio from bytes
    # Whisper expects 16kHz mono log-mel; the processor handles conversion
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        audio, sr = sf.read(tmp_path)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass

    # Prepare features
    inputs = processor(audio, sampling_rate=sr, return_tensors="pt")
    forced_decoder_ids = None
    if language:
        try:
            forced_decoder_ids = processor.get_decoder_prompt_ids(language=language, task="transcribe")
        except Exception:
            forced_decoder_ids = None

    with torch.no_grad():
        pred_ids = model.generate(
            inputs.input_features,
            forced_decoder_ids=forced_decoder_ids,
        )
    text = processor.batch_decode(pred_ids, skip_special_tokens=True)[0].strip()
    return {"text": text, "language": language}


