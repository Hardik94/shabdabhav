from fastapi import HTTPException
import importlib

async def router_piper(text, model_id, model_cache, model_key, model_dir="/home/workspace/shabdabhav/api/data/piper-tts"):
    """
    Like router_parler, but for Piper-TTS.
    """
    if not model_id:
        model_id = "en/en_US/amy/medium/en_US-amy-medium.onnx"  # Update as needed

    async def loader():
        return await piper_loader(model_id=model_id, model_dir=model_dir)

    try:
        model_wrapper, _ = await model_cache.get(model_key, loader)
        # Piper does not use description parameter (can ignore or repurpose)
        audio_buffer = await model_wrapper.generate_audio(text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Piper-TTS audio: {e}")

    return audio_buffer

async def piper_loader(model_id: str, model_dir: str = None):
    try:
        piper_module = importlib.import_module("piper")
        soundfile = importlib.import_module("soundfile")
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="Piper-TTS not installed. Please install with 'pip install piper-tts soundfile'"
        )
    # Import your Piper wrapper
    PiperTTSModelWrapper = importlib.import_module("api.models.piper_tts").PiperTTSModelWrapper

    # For Piper, model_id is the ONNX file path, and model_dir may be used to find it
    model_path = model_id
    if model_dir is not None:
        import os
        model_path = os.path.join(model_dir, model_id)
        print(model_path)

    wrapper = PiperTTSModelWrapper(model_path=model_path)
    # LAZY LOAD: don't load in constructor – let generate_audio/load() do it
    # (if your wrapper auto-loads, call wrapper.load() here if needed)
    return wrapper, None  # Second value, for consistency; not used


