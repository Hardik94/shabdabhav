import asyncio
from collections import OrderedDict
import torch
import gc

class ModelCacheLRU:
    def __init__(self, max_size=2):
        self.max_size = max_size
        self.cache = OrderedDict()  # Dict[str, Any], key=model_key, val=(model_obj, tokenizer_obj)
        self.lock = asyncio.Lock()

    async def get(self, model_key: str, loader_func):
        """
        Get the model/tokenizer from cache or load using loader_func.
        - model_key: Unique string key for model (e.g. "parler:parler-tts-mini-v1")
        - loader_func: Callable that returns (model, tokenizer)
        """

        async with self.lock:
            if model_key in self.cache:
                # Move to end to mark recently used
                self.cache.move_to_end(model_key)
                return self.cache[model_key]

            # Load model/tokenizer
            model, tokenizer = await loader_func()

            # Evict if over capacity
            if len(self.cache) >= self.max_size:
                await self._evict()

            self.cache[model_key] = (model, tokenizer)
            return model, tokenizer

    async def _evict(self):
        # Remove least-recently used (first) model
        model_key, (model, _) = self.cache.popitem(last=False)
        try:
            # Try to free GPU/CPU memory
            del model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Run garbage collector to free
            gc.collect()
        except Exception:
            pass

