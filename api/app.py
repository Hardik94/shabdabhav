from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from models.model_cache import ModelCacheLRU
from models.parler_tts import ParlerTTSModelWrapper
from models.xtts_v2 import XTTSV2ModelWrapper
import asyncio

app = FastAPI()

MAX_MODELS_IN_MEMORY = 2  # max models to cache in RAM at once
model_cache = ModelCacheLRU(max_size=MAX_MODELS_IN_MEMORY)


async def parler_loader(model_id: str, model_dir: str = None):
    wrapper = ParlerTTSModelWrapper(model_id=model_id, model_dir=model_dir)
    await wrapper.load()
    return wrapper, wrapper.tokenizer  # tokenizer only used internally by wrapper


async def xtts_loader(model_name: str):
    wrapper = XTTSV2ModelWrapper(model_name=model_name)
    await wrapper.load()
    return wrapper, None  # no tokenizer for XTTS


@app.post("/tts")
async def tts_endpoint(request: Request):
    """
    JSON payload expects:
    {
        "text": "...",
        "model_type": "parler" or "xtts",
        "model_id": "parler-tts/parler-tts-mini-v1" or "tts_models/en/vctk/vits",
        "description": "A female speaker with warm tone." (optional, Parler only)
        "model_dir": "./models_cache/parler-tts-mini-v1" (optional; local path for Parler)
    }
    """
    body = await request.json()
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Missing required field: text")
    model_type = body.get("model_type", "parler")
    model_id = body.get("model_id")
    description = body.get("description", "A clear expressive female voice.")
    model_dir = body.get("model_dir", None)

    model_key = f"{model_type}:{model_id or 'default'}:{model_dir or 'none'}"

    if model_type == "parler":
        if not model_id:
            model_id = "parler-tts/parler-tts-mini-v1"

        async def loader():
            return await parler_loader(model_id=model_id, model_dir=model_dir)

        try:
            model_wrapper, _ = await model_cache.get(model_key, loader)
            audio_buffer = await model_wrapper.generate_audio(prompt=text, description=description)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating Parler-TTS audio: {e}")

    elif model_type == "xtts":
        if not model_id:
            model_id = "tts_models/en/vctk/vits"

        async def loader():
            return await xtts_loader(model_id)

        try:
            model_wrapper, _ = await model_cache.get(model_key, loader)
            audio_buffer = await model_wrapper.generate_audio(text=text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error generating XTTS audio: {e}")

    else:
        raise HTTPException(status_code=400, detail=f"Unknown model_type: {model_type}")

    async def streamer():
        yield audio_buffer.read()

    return StreamingResponse(streamer(), media_type="audio/wav")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models_in_memory": list(model_cache.cache.keys()),
        "num_models": len(model_cache.cache)
    }
