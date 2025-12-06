# GCP Deployment Guide - Clinical Trial Predictor POC
## GPU: NVIDIA T4 16GB VRAM on Google Cloud Compute Engine
## Region: europe-west1 | Project ID: silicon-guru-472717-q9

---

## 📋 Prerequisites

1. **GCP Project** - Active GCP project with billing enabled
2. **gcloud CLI** - Installed and configured on local machine
3. **Docker** - Installed locally (for testing Dockerfile)
4. **APIs Enabled**:
   ```bash
   gcloud services enable \
     compute.googleapis.com \
     cloudbuild.googleapis.com \
     container.googleapis.com \
     cloudresourcemanager.googleapis.com
   ```

---

## 🚀 Quick Deployment (Option 1: Using Cloud Build)

### Step 1: Set GCP Project
```bash
gcloud config set project silicon-guru-472717-q9
```

### Step 2: Prepare .env File
Before deploying, update your `.env` file with production values:
```
Local_model=1
HuggingFace_Model_URL=google/gemma-3-4b-it
HF_TOKEN=hf_your_token_here
GEMINI_API_KEY=your_gemini_key
GOOGLE_API_KEY=your_google_api_key
PORT=8000
```

### Step 3: Run Cloud Build
```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_ZONE=us-central1-a,_MACHINE_TYPE=g2-standard-4 \
  --timeout=70m
```

### Step 4: Monitor Build
```bash
# View build logs
gcloud builds log BUILD_ID --stream

# List recent builds
gcloud builds list --limit=10
```

---

## 🖥️ Manual Deployment (Option 2: Direct VM Setup)

### Step 1: Create GCP VM with T4 GPU
```bash
gcloud compute instances create clinical-trial-poc \
  --project=silicon-guru-472717-q9 \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --zone=europe-west1-b \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-ssd \
  --scopes=https://www.googleapis.com/auth/cloud-platform
```

### Step 2: SSH into VM
```bash
gcloud compute ssh clinical-trial-poc --zone=europe-west1-b --project=silicon-guru-472717-q9
```

### Step 3: Install Docker & NVIDIA Runtime
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install NVIDIA Docker runtime
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-docker2
sudo systemctl restart docker

# Verify GPU access
docker run --rm --runtime=nvidia nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 nvidia-smi
```

### Step 4: Clone and Setup Application
```bash
# Clone repository (or upload your code)
cd ~
git clone YOUR_REPO_URL
cd Cloud_Run_Hack

# Create .env file with production values
cat > .env << 'EOF'
Local_model=1
HuggingFace_Model_URL=google/gemma-3-4b-it
HF_TOKEN=hf_your_token_here
GEMINI_API_KEY=your_gemini_key
GOOGLE_API_KEY=your_google_api_key
PORT=8000
EOF

# Make .env secure
chmod 600 .env
```

### Step 5: Build and Run Docker Image
```bash
# Build image
docker build -t clinical-trial-predictor:latest .

# Run container with GPU support
docker run \
  --gpus all \
  --runtime=nvidia \
  -p 8000:8000 \
  --env-file .env \
  --name clinical-trial-poc \
  -d \
  clinical-trial-predictor:latest
```

### Step 6: Verify Deployment
```bash
# Check container logs
docker logs -f clinical-trial-poc

# Test API endpoint
curl http://localhost:8000/health

# Check GPU usage
nvidia-smi
```

---

## 📊 Performance Tuning for L4 GPU

### Torch Configuration
Add to `app/config.py`:
```python
import torch

# Force CUDA
torch.cuda.set_device(0)
print(f"GPU: {torch.cuda.get_device_name(0)}")
print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

# Enable TF32 for faster computation
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
```

### Model Quantization (Already in setup)
- **bitsandbytes**: 4-bit quantization for Gemma models
- **device_map**: "auto" to utilize full GPU VRAM (16GB T4)
- **Effective model size**: ~7-8GB (quantized)

### Memory Monitoring
```bash
# Inside container
watch nvidia-smi

# Local machine
gcloud compute ssh clinical-trial-poc --zone=us-central1-a -- nvidia-smi -l 2
```

---

## 🔧 Advanced Deployment Options

### Option A: Docker Compose (for local testing)
```yaml
# docker-compose.yml
version: '3.8'
services:
  clinical-trial:
    build: .
    container_name: clinical-trial-poc
    ports:
      - "8000:8000"
    env_file: .env
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
    volumes:
      - ./data:/app/data
      - ./models:/app/models
    restart: on-failure
```

Run with:
```bash
docker-compose up -d
```

### Option B: Kubernetes on GKE
```bash
# Create GKE cluster with GPU support
gcloud container clusters create clinical-trial-cluster \
  --project=silicon-guru-472717-q9 \
  --zone=europe-west1-b \
  --machine-type=n1-standard-8 \
  --num-nodes=1 \
  --addons=HorizontalPodAutoscaling,HttpLoadBalancing \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=3
```

### Option C: Vertex AI (Managed Platform)
- Container image: `gcr.io/YOUR_PROJECT/clinical-trial-predictor:latest`
- Machine type: `n1-standard-8` with L4 GPU
- Framework: Custom training

---

## 🔒 Security Best Practices

### 1. Protect .env File
```bash
# Never commit .env to Git
echo ".env" >> .gitignore

# Set restrictive permissions
chmod 600 .env

# Use Google Secret Manager for production
gcloud secrets create env-file --data-file=.env
```

### 2. IAM Permissions
```bash
# Create service account for VM
gcloud iam service-accounts create clinical-trial-sa
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member=serviceAccount:clinical-trial-sa@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/container.developer
```

### 3. Network Security
```bash
# Create firewall rule (restrict to your IP)
gcloud compute firewall-rules create allow-clinical-trial \
  --allow=tcp:8000 \
  --source-ranges=YOUR_IP/32
```

---

## 📈 Monitoring & Logging

### View Application Logs
```bash
# Direct container logs
docker logs clinical-trial-poc

# Google Cloud Logging
gcloud logging read "resource.type=compute.googleapis.com AND resource.labels.instance_id=INSTANCE_ID" \
  --limit 50 \
  --format json
```

### Set Up Monitoring
```bash
# Create monitoring alert for GPU memory
gcloud monitoring policies create \
  --display-name="Clinical Trial GPU Memory" \
  --condition-display-name="GPU Memory > 90%" \
  --metric-type=custom.googleapis.com/gpu_memory_usage
```

---

## 🛑 Stopping & Cleanup

### Stop Container
```bash
docker stop clinical-trial-poc
docker rm clinical-trial-poc
```

### Stop VM
```bash
gcloud compute instances stop clinical-trial-poc --zone=europe-west1-b --project=silicon-guru-472717-q9
```

### Delete Resources
```bash
# Delete VM
gcloud compute instances delete clinical-trial-poc --zone=europe-west1-b --project=silicon-guru-472717-q9 --quiet

# Delete Docker image from GCR
gcloud container images delete gcr.io/silicon-guru-472717-q9/clinical-trial-predictor:latest
```

---

## 📞 Troubleshooting

### GPU Not Detected
```bash
# Check NVIDIA driver
nvidia-smi

# Check Docker GPU support
docker run --rm --runtime=nvidia nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 nvidia-smi

# Restart Docker daemon
sudo systemctl restart docker
```

### Out of Memory Error
```python
# Add to config.py
torch.cuda.empty_cache()

# Or reduce model size with quantization
load_in_4bit=True  # Already configured in ml_service.py
```

### Slow Build Time
- Use `machine_type: N1_HIGHCPU_8` in Cloud Build (already configured)
- Cache Docker layers: `-t gcr.io/$PROJECT_ID/clinical-trial-predictor:latest .`
- Pre-build base image: `gcr.io/cloud-builders/docker` caches steps

### Application Not Responding
```bash
# Check application health
curl -v http://localhost:8000/health

# Check logs for errors
docker logs clinical-trial-poc --tail=100

# Restart container
docker restart clinical-trial-poc
```

---

## 💡 POC Optimization Tips

1. **Model Caching**: Models downloaded on first start (~2-3 minutes), then cached
2. **VRAM Usage**: 24GB L4 supports 7-8GB quantized Gemma + 16GB for inference
3. **Batch Processing**: Can handle multiple concurrent requests (adjust in FastAPI)
4. **Fallback Mode**: If Gemini API fails, local model serves requests
5. **Cost Optimization**: 
   - Use `preemptible-vm` for dev/test: `--preemptible`
   - Stop VM when not in use
   - Budget alert: `gcloud billing budgets create`

---

## 📝 Commands Summary

```bash
# Set project
gcloud config set project silicon-guru-472717-q9

# Create VM with T4 GPU in europe-west1
gcloud compute instances create clinical-trial-poc \
  --project=silicon-guru-472717-q9 \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --zone=europe-west1-b \
  --boot-disk-size=100GB \
  --boot-disk-type=pd-ssd

# SSH to VM
gcloud compute ssh clinical-trial-poc --zone=europe-west1-b --project=silicon-guru-472717-q9

# Build & push with Cloud Build
gcloud builds submit --config=cloudbuild.yaml --timeout=70m

# Run container
docker run --gpus all --runtime=nvidia -p 8000:8000 --env-file .env -d clinical-trial-predictor:latest

# Monitor GPU
nvidia-smi -l 2
```

---

## 🎯 Next Steps

1. ✅ Set up GCP project and enable APIs
2. ✅ Update `.env` with production values
3. ✅ Choose deployment option (Cloud Build or Manual)
4. ✅ Deploy and test
5. ✅ Set up monitoring and alerts
6. ✅ Document API endpoints for frontend/integration

For more info: [Google Cloud GPU Documentation](https://cloud.google.com/compute/docs/gpus)
