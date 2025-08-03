from fastapi import Request, HTTPException
from api.models.model_cache import ModelCacheLRU
import importlib
# router = APIRouter()

async def router_parler(text, model_id, description, model_cache, model_key, model_dir=None):
    if not model_id:
            model_id = "parler-tts/parler-tts-mini-v1"

    async def loader():
        return await parler_loader(model_id=model_id, model_dir=model_dir)

    try:
        model_wrapper, _ = await model_cache.get(model_key, loader)
        audio_buffer = await model_wrapper.generate_audio(prompt=text, description=description)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating Parler-TTS audio: {e}")
    return audio_buffer

async def parler_loader(model_id: str, model_dir: str = None):
    try:
        parler_module = importlib.import_module("parler_tts")
        torch = importlib.import_module("torch")
        transformers = importlib.import_module("transformers")
        soundfile = importlib.import_module("soundfile")
    except ImportError:
        raise HTTPException(
            status_code=500, 
            detail="Parler-TTS not installed. Please install with 'pip install .[parler-tts]'"
        )
    ParlerTTSModelWrapper = importlib.import_module("api.models.parler_tts").ParlerTTSModelWrapper
    
    wrapper = ParlerTTSModelWrapper(model_id=model_id, model_dir=model_dir)
    await wrapper.load()
    return wrapper, wrapper.tokenizer  # tokenizer only used internally by wrapper




