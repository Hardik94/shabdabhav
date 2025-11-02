

## To Download the TTS models

### To Download piper Voice 

```
curl --location 'localhost:8000/v1/models/download?name=piper' \
--header 'Content-Type: application/json' \
--data '{
    "voice": "en/en_US/libritts_r/medium/*"
}'
```

| Languagage | ISO code | voice | tone | Action |
|---|---|---|---|---|
| English | en/en_US | amy | `low`, `medium` | `en/en_US/amy/low/*`, `en/en_US/amy/medium/*` |
| English | en/en_US | arctic | `medium` | `en/en_US/arctic/medium/*` |
| English | en/en_US | bryce | `medium` | `en/en_US/bryce/medium/*` |
| English | en/en_US | danny | `low` | `en/en_US/danny/low/*` |
| English | en/en_US | hfc_female | `medium` | `en/en_US/hfc_female/medium/*` |
| English | en/en_US | hfc_male | `medium` | `en/en_US/hfc_male/medium/*` |
| English | en/en_US | joe | `medium` | `en/en_US/joe/medium/*` |
| English | en/en_US | john | `medium` | `en/en_US/john/medium/*` |
| English | en/en_US | kathleen | `low` | `en/en_US/kathleen/low/*` |
| English | en/en_US | kristin | `medium` | `en/en_US/kristin/medium/*` |
| English | en/en_US | kushal | `medium` | `en/en_US/kushal/medium/*` |
| English | en/en_US | l2arctic | `medium` | `en/en_US/l2arctic/medium/*` |
| English | en/en_US | lessac | `low`, `medium`, `High` | `en/en_US/lessac/low/*`, `en/en_US/lessac/medium/*`, `en/en_US/lessac/high/*` |
| English | en/en_US | libritts | `high` | `en/en_US/libritts/high/*` |
| English | en/en_US | libritts_r | `medium` | `en/en_US/libritts_r/medium/*` |
| English | en/en_US | ljspeech | `medium`, `high` | `en/en_US/ljspeech/high/*`, `en/en_US/ljspeech/medium/*` |
| English | en/en_US | norman | `medium` | `en/en_US/norman/medium/*` |
| English | en/en_US | reza_ibrahim | `medium` | `en/en_US/reza_ibrahim/medium/*` |
| English | en/en_US | ryan | `low`, `medium`, `high` | `en/en_US/ryan/low/*`, `en/en_US/amy/medium/*`, `en/en_US/ryan/high/*` | 
| English | en/en_US | sam | `medium` | `en/en_US/sam/medium/*` |
| English | en/en_GB | alan | `low`, `medium` | `en/en_GB/alan/low/*`, `en/en_GB/alan/medium/*` |
| English | en/en_GB | alba | `medium` | `en/en_GB/alba/medium/*` |
| English | en/en_GB | aru | `medium` | `en/en_GB/aru/medium/*` |
| English | en/en_GB | cori | `high`, `medium` | `en/en_GB/cori/high/*`, `en/en_GB/cori/medium/*` |
| English | en/en_GB | jenny_dioco | `medium` | `en/en_GB/jenny_dioco/medium/*` |
| English | en/en_GB | northern_english_male | `medium` | `en/en_GB/northern_english_male/medium/*` |
| English | en/en_GB | semaine | `medium` | `en/en_GB/semaine/medium/*` |
| English | en/en_GB | southern_english_female | `low` | `en/en_GB/southern_english_female/low/*` |
| English | en/en_GB | vctk | `medium` | `en/en_GB/vctk/medium/*` |


### To Download parler model

```
curl --location 'localhost:8000/v1/models/download?name=parler-tts/parler-tts-mini-v1' \
--header 'Content-Type: application/json' \
--data '{}'
```

| Model | version |
|---|---|
| parler-tts | parler-tts-mini-v1 |
| parler-tts | parler-tts-large-v1 |
| parler-tts | parler-tts-mini-v1.1 |


