# shabdabhav
A opensource API Server for the STT &amp; TTS models

### Configure and Run Application in your environment
`pip install astral-uv`

```
uv venv --python 3.11
uv sync
```

### Run in Development environment
`uv run fastapi dev`

### Run in Production Environment
`uv run fastapi start`

### Build and Run docker image from scratch
```
docker build -t tts-astraluv-server .
docker run -p 8000:8000 --restart always -v ./data:/app/api/data tts-astraluv-server
```

## Documents of API
```
http://localhost:8000/docs
```

### Available Models 

| Model | TTS | STT |
|--|--|--|
| parler-tts/parler-tts-mini-v1 | ✅	|   |
| parler-tts/parler-tts-large-v1 | ✅ |   |
| parler-tts/parler-tts-mini-v1.1 | ✅ |   |
| piper | ✅ |   |

### Available Voice For Piper Model 
(https://huggingface.co/rhasspy/piper-voices):

--> en/en_US/libritts_r/medium
```
curl --location 'localhost:8000/v1/models/download?name=piper' \
--header 'Content-Type: application/json' \
--data '{
    "voice": "en/en_US/libritts_r/medium/*"
}'
```
