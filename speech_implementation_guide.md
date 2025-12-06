Here’s a clean, **credentials-first** plan that works on **Windows 10 (local FastAPI)** and **Linux (Cloud Run)** for **STT (hi/en/bn)** + **TTS**.

# 1) requirements.txt (pin stable libs)

```
fastapi==0.115.4
uvicorn[standard]==0.32.0
python-multipart==0.0.9
python-dotenv==1.0.1
google-cloud-speech==2.27.0
google-cloud-texttospeech==2.16.5
```

*(Optional for audio conversions if you ever re-encode client audio: `ffmpeg` system pkg.)*

---

# 2) What to store in `.env` (do **not** copy private key here)

**Only store non-secret pointers & config:**

```
GOOGLE_APPLICATION_CREDENTIALS=./secrets/speech_key.json
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=global
DEFAULT_LANG=en-IN
```

* Keep the real **`speech_key.json`** on disk at `./secrets/speech_key.json` (git-ignored).
* Never paste private key fields into `.env`.

**Windows 10 tip:** you can also set the env var once:

```powershell
setx GOOGLE_APPLICATION_CREDENTIALS "C:\path\to\secrets\speech_key.json"
```

---

# 3) Local Windows 10 (FastAPI) — how the app uses creds

* Your code should rely on **Application Default Credentials (ADC)** via the env var:
* Minimal “critical” snippet to bootstrap and verify:

```python
# critical snippet: credential bootstrap
import os
from dotenv import load_dotenv
load_dotenv()  # loads GOOGLE_APPLICATION_CREDENTIALS, etc.

# Verify ADC works (no manual json loading needed)
import google.auth
creds, project = google.auth.default()
assert creds is not None, "ADC not found. Set GOOGLE_APPLICATION_CREDENTIALS."
print("ADC OK for project:", project)

# STT / TTS clients pick up ADC automatically
from google.cloud import speech_v2 as speech
from google.cloud import texttospeech

speech_client = speech.SpeechClient()          # uses ADC
tts_client    = texttospeech.TextToSpeechClient()  # uses ADC
```

* **STT config for WebM/Opus** (sent from the browser):

```python
# critical snippet: STT config (Google Speech-to-Text v2)
config = {
  "auto_decoding_config": {},                 # let API detect WEBM/OPUS
  "language_codes": [lang_code],              # e.g., "en-IN", "hi-IN", "bn-IN"
  "features": {"enable_automatic_punctuation": True}
}
# For one-shot audio bytes: create_recognizer + recognize
```

* **TTS config** (same language as the chatbot reply):

```python
# critical snippet: TTS config
from google.cloud import texttospeech

synthesis_input = texttospeech.SynthesisInput(text=reply_text)
voice = texttospeech.VoiceSelectionParams(language_code=lang_code)  # "en-IN"/"hi-IN"/"bn-IN"
audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
# tts_client.synthesize_speech(synthesis_input, voice, audio_config)
```

---

# 4) Cloud Run (Linux) — credentials the right way

**Use Secret Manager (recommended):**

1. Save `speech_key.json` as a **Secret** (e.g., `speech-sa-key`).
2. When deploying Cloud Run, **mount the secret as a file** and point the env var to that path.

**Deployment sketch (one-time idea):**

* In Cloud Run UI:

  * Variables & secrets → Mount secret `speech-sa-key` at `/var/secrets/speech_key.json`
  * Add env var `GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/speech_key.json`
* Or CLI equivalent:

```bash
gcloud run deploy your-service \
  --set-secrets=GOOGLE_APPLICATION_CREDENTIALS=speech-sa-key:latest:/var/secrets/speech_key.json \
  --set-env-vars=GOOGLE_APPLICATION_CREDENTIALS=/var/secrets/speech_key.json \
  --region=your-region --source=.
```

*Result:* The **same code** as local (ADC) works unchanged on Cloud Run.

---

# 5) Language routing (shared for STT & TTS)

```python
# critical snippet: language selection
SUPPORTED = {"en-IN":"en-IN", "hi-IN":"hi-IN", "bn-IN":"bn-IN"}
lang_code = SUPPORTED.get(user_selected or os.getenv("DEFAULT_LANG","en-IN"), "en-IN")
```

* If user doesn’t select, fall back to `DEFAULT_LANG` from `.env`.
* For code-mix, you can send multiple language codes to STT (primary first).

---

# 6) Putting it together (flow summary)

1. **UI** records mic as **WebM/Opus** → POST to `/stt`.
2. **Backend** (FastAPI) reads bytes and calls **Google STT v2** using **ADC**.
3. Feed transcribed text → your chatbot → get reply.
4. Call **Google TTS** with the **same language** → return **MP3** (or OGG) to the UI to play.
5. Works **identically** on Windows & Cloud Run because both use **ADC** from `GOOGLE_APPLICATION_CREDENTIALS`.

---

# 7) Security & ops notes

* **Never** commit `speech_key.json`.
* Scope is handled by the clients; the service account needs **Speech-to-Text User** and **Text-to-Speech User** (and **Secret Manager Secret Accessor** for Cloud Run if using secrets).
* Rotate secrets periodically; re-deploy to pick up the new secret version.

If you want, I can add minimal FastAPI endpoints (upload + synth) as short snippets next; but with the above, your Copilot changes should align to **ADC-first** auth on both platforms.
