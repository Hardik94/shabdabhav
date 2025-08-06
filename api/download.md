### To Download the parler-tts model
```
curl --location --request POST 'localhost:8000/models/download?name=parler-tts%2Fparler-tts-mini-v1'
```

### To Download the piper-tts voices, please select path from below mentioned repositories
https://huggingface.co/rhasspy/piper-voices
```
curl --location 'localhost:8000/models/download?name=piper' \
--header 'Content-Type: application/json' \
--data '{
    "voice": "en/en_US/amy/low/*"
}'
```
