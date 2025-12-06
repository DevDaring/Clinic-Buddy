Great — I read your project files (README.md and Agent_Flow.md) and I’ll give you a step-by-step, copy-pasteable guide to deploy your app to **Google Cloud Run** from VS Code, using your GCP project `silicon-guru-472717-q9` and your account `koushik_phd21@iiitkalyani.ac.in`. I’ll show two safe options (recommended production approach with a service account + Cloud Build / Container image, and a simpler source deploy). Where relevant I refer to your README/agent docs.  

---

# Quick summary (what we’ll do)

1. Prepare local environment and test `python run.py` locally. 
2. Create a deploy service account with required roles (so Cloud Run can call Speech/TTS/Gemini).
3. Create *secrets* for Gemini API key (and optionally other keys) in Secret Manager.
4. Build a container image with Cloud Build (or use `--source` deploy). 
5. Deploy to Cloud Run with the service account, secrets, and environment variables.
6. Test the service and view logs.

---

# Prerequisites (on your laptop / VS Code)

Make sure you have:

* `gcloud` SDK installed and up-to-date.
* Docker CLI (optional if you use local Docker builds).
* You have your project id: `silicon-guru-472717-q9`.
* Your local repo contains the `Dockerfile`, `cloudbuild.yaml`, `.env` sample and `run.py` as in README. 

If `gcloud` not installed: [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)

---

# 0) Quick local test (before deploying)

In VS Code terminal, run:

```bash
# create a virtual env and install
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell

pip install -r requirements.txt
# ensure you have env vars in .env (or export GEMINI_API_KEY etc.)
python run.py
```

Open `http://localhost:8000` and `http://localhost:8000/api/docs` to confirm the app runs locally. README lists these endpoints. 

---

# 1) Initialize gcloud & set project

Run these commands from VS Code terminal:

```bash
gcloud auth login
gcloud config set project silicon-guru-472717-q9
gcloud auth list         # confirm your account koushik_phd21@iiitkalyani.ac.in is active
```

---

# 2) Enable required Google APIs

Enable Cloud Run, Cloud Build, Secret Manager, Speech & TTS, and IAM APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com \
    speech.googleapis.com texttospeech.googleapis.com iam.googleapis.com
```

(README mentions Cloud Run, Cloud Build and Speech/TTS usage.) 

---

# 3) Create a Cloud Run service account (recommended)

Create a dedicated service account `ct-run-sa` that the Cloud Run service will run as. This avoids storing JSON keys and allows the Cloud Run runtime to use Application Default Credentials.

```bash
PROJECT=silicon-guru-472717-q9
SA_NAME=ct-run-sa

gcloud iam service-accounts create $SA_NAME \
  --display-name="Cloud Run runtime service account for clinical-trial-app"

SA_EMAIL=${SA_NAME}@${PROJECT}.iam.gserviceaccount.com
echo "Service account created: $SA_EMAIL"
```

Grant it the minimum roles it needs:

```bash
# Roles: Cloud Run Invoker/Run Admin not required on SA itself. We give it API access and logging access.
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/cloudspeech.client"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/texttospeech.admin"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/logging.logWriter"
```

> Why this approach? If your code uses Google client libs, on Cloud Run the libraries will use the runtime service account automatically (ADC) — so you don't need to ship `speech_key.json`. This is more secure. Your README explains service account usage for the speech key; using the runtime SA is a best practice. 

---

# 4) Create secrets in Secret Manager (Gemini API key etc.)

Store sensitive keys in Secret Manager and map them into Cloud Run on deploy.

Example: create secret for Gemini API key:

1. On your laptop create a file `secrets/gemini_key.txt` containing your Gemini key (or just have the key value ready).

2. Create the secret:

```bash
gcloud secrets create gemini-api-key --replication-policy="automatic"
gcloud secrets versions add gemini-api-key --data-file="secrets/gemini_key.txt"
```

If you need to store other keys (like `GOOGLE_API_KEY`) do the same:

```bash
gcloud secrets create google-api-key --replication-policy="automatic"
gcloud secrets versions add google-api-key --data-file="secrets/google_api_key.txt"
```

*(Alternative: if you must use a JSON service account key file for some reason, you can create a secret and reference it — but prefer runtime SA + Secret Manager env var approach.)* 

---

# 5A) Build & push container using Cloud Build (recommended)

Your repo already includes `Dockerfile` and `cloudbuild.yaml` (README lists them). We'll use Cloud Build to build and push an image to Google Container Registry (or Artifact Registry).

From repo root:

```bash
gcloud builds submit --project=$PROJECT --config=cloudbuild.yaml .
# or build + push manually
IMAGE=gcr.io/${PROJECT}/clinical-trial-app:latest
gcloud builds submit --tag $IMAGE .
```

This will build the Docker image and push to `gcr.io/...`. (cloudbuild.yaml in your repo is used by README instructions). 

---

# 5B) (Alternative) Deploy directly from source (Cloud Run build from source)

If you prefer Cloud Run to build the container directly from your source:

```bash
gcloud run deploy clinical-trial-app \
  --source . \
  --region us-central1 \
  --platform managed \
  --project=$PROJECT \
  --allow-unauthenticated
```

But I prefer building with Cloud Build (option 5A) because it gives you image artifacts and more control. README mentions both Docker and Cloud Build deployment steps. 

---

# 6) Deploy the image to Cloud Run (with secrets & service account)

Use the image built earlier and deploy:

```bash
PROJECT=silicon-guru-472717-q9
IMAGE=gcr.io/${PROJECT}/clinical-trial-app:latest
SERVICE=clinical-trial-app
REGION=us-central1
SA_EMAIL=ct-run-sa@${PROJECT}.iam.gserviceaccount.com

gcloud run deploy $SERVICE \
  --image $IMAGE \
  --region $REGION \
  --platform managed \
  --project $PROJECT \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=300s \
  --service-account=$SA_EMAIL \
  --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_API_KEY=google-api-key:latest" \
  --set-env-vars="APP_ENV=production,APP_PORT=8000"
```

Notes:

* `--set-secrets` maps Secret Manager secrets into environment variables inside your container. The format is `ENV_NAME=SECRET_NAME:version`. Your app should read `GEMINI_API_KEY` from env (your README uses this env var). 
* `--service-account` makes the Cloud Run instance run as the SA you created; the Google client libs inside the container will use ADC to access Speech/TTS without needing to ship `speech_key.json`. This avoids a credentials file. (If your code *requires* a file path `GOOGLE_APPLICATION_CREDENTIALS`, you can adapt the code to use ADC or read the secret file from Secret Manager at startup.) 

---

# 7) If your app *requires* a file path for `GOOGLE_APPLICATION_CREDENTIALS`

Two options:

**A — Prefered**: modify code to use default credentials (most Google libraries support ADC — no code change if you don't set `GOOGLE_APPLICATION_CREDENTIALS` and run under Cloud Run service account).
**B — If you must use a JSON key file**: create a secret named `speech-sa-key` containing the JSON and mount it as an environment variable or write it to FS at startup (less secure). Example:

```bash
# create secret from JSON key
gcloud secrets create speech-sa-key --data-file="secrets/speech_key.json"

# deploy and map to env var
gcloud run deploy $SERVICE ... --set-secrets="SPEECH_SA_JSON=speech-sa-key:latest"
```

Then in your app entrypoint (run.py) write `os.environ['GOOGLE_APPLICATION_CREDENTIALS']='/tmp/speech_key.json'` and dump the `SPEECH_SA_JSON` content into `/tmp/speech_key.json` at startup. But again: avoid if possible — use runtime SA and ADC. 

---

# 8) Verify deployment and test endpoints

After deploy, CLI will show a public URL. Test:

```bash
# check revision and URL
gcloud run services describe $SERVICE --region=$REGION --format="value(status.url)"
# suppose URL is: https://clinical-trial-app-...run.app
curl https://<YOUR_SERVICE_URL>/api/docs
# or open in browser
```

Check logs:

```bash
gcloud run services logs read $SERVICE --region=$REGION --limit 100
```

---

# 9) Troubleshooting tips (common gotchas)

* If app fails to start: inspect container logs (`gcloud run services logs read ...`) to see missing env var or missing secret. 
* If Gemini API calls fail: ensure `GEMINI_API_KEY` secret value is correct and that your code reads `GEMINI_API_KEY` env var (README expects that). 
* If Speech/TTS calls fail with permission errors: ensure the Cloud Run runtime SA (`ct-run-sa@...`) has `roles/cloudspeech.client` and `roles/texttospeech.admin` (or appropriate roles) and you deployed with `--service-account`.
* If audio processing expects a filesystem path for `speech_key.json`, either adjust the code to use ADC or use the secret-write-at-startup workaround described above. 

---

# 10) Optional: Continuous deploy (Cloud Build trigger)

If you want to CI/CD on git push to `main`, set up a Cloud Build trigger that uses `cloudbuild.yaml` in your repo (README references cloudbuild.yaml). This automates `gcloud builds submit` and re-deploy. 

---

# Quick checklist (copy & paste)

1. `gcloud auth login && gcloud config set project silicon-guru-472717-q9`
2. `gcloud services enable run.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com speech.googleapis.com texttospeech.googleapis.com`
3. Create runtime SA and grant roles (see commands above).
4. Put GEMINI API key into Secret Manager.
5. `gcloud builds submit --tag gcr.io/silicon-guru-472717-q9/clinical-trial-app:latest`
6. `gcloud run deploy clinical-trial-app --image gcr.io/silicon-guru-472717-q9/clinical-trial-app:latest --region=us-central1 --service-account=ct-run-sa@silicon-guru-472717-q9.iam.gserviceaccount.com --set-secrets="GEMINI_API_KEY=gemini-api-key:latest,GOOGLE_API_KEY=google-api-key:latest" --allow-unauthenticated --memory=2Gi --cpu=2`
7. `gcloud run services describe clinical-trial-app --region=us-central1 --format="value(status.url)"` then open URL.

---

# References from your repo

* README (deployment notes, env var names, endpoints, docker/cloudbuild info). 
* Agent_Flow (agent routing and ADK vs fallback — useful to confirm GEMINI usage on Cloud Run). 

---

