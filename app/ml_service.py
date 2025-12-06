"""
GPU-accelerated ML model inference service.
Supports both local Gemma model and AWS Bedrock (Claude Sonnet 4.5) API for clinical trial predictions.
Text generation via AWS Bedrock, local models via HuggingFace.
"""

import torch
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        pipeline,
        BitsAndBytesConfig
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logging.warning("Transformers library not available. Local ML features will be limited.")

# AWS Bedrock client for text generation
from .aws_bedrock_client import get_bedrock_client, BOTO3_AVAILABLE

from .config import get_settings
from .models import TrialDesign, PredictionResponse

logger = logging.getLogger(__name__)
settings = get_settings()


class MLModelService:
    """
    Machine learning model service for clinical trial predictions.
    Supports both local Gemma model (GPU-accelerated) and AWS Bedrock API (Claude Sonnet 4.5).
    Uses LOCAL_MODEL=1 for local Gemma, LOCAL_MODEL=0 for AWS Bedrock API.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.use_local_model = self.settings.LOCAL_MODEL == 1
        
        if self.use_local_model:
            self.device = self._get_device()
            logger.info(f"ML Service initialized for LOCAL MODEL. Device: {self.device}")
            logger.info(f"Model URL: {self.settings.HUGGINGFACE_MODEL_URL}")
        else:
            self.device = None
            self._init_bedrock_api()
            logger.info("ML Service initialized for AWS Bedrock API (Claude Sonnet 4.5)")
        
        self.model = None
        self.tokenizer = None
        self.pipeline = None
        self.model_loaded = False
        self.bedrock_client = None
    
    def _init_bedrock_api(self):
        """Initialize AWS Bedrock API client."""
        self.bedrock_client = get_bedrock_client()
        
        if not BOTO3_AVAILABLE:
            logger.error("boto3 library not available. Install with: pip install boto3")
            return
        
        if not self.bedrock_client.is_available:
            logger.error("AWS Bedrock client not available. Check AWS credentials in .env file.")
            return
        
        logger.info("AWS Bedrock API configured successfully")
    
    def _get_device(self) -> str:
        """Determine the best available device (GPU/CPU)."""
        if torch.cuda.is_available():
            device = "cuda"
            logger.info(f"CUDA available. GPU: {torch.cuda.get_device_name(0)}")
            logger.info(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
        else:
            device = "cpu"
            logger.warning("CUDA not available. Using CPU (this will be slower)")
        
        return device
    
    def load_model(self, model_name: Optional[str] = None) -> bool:
        """
        Load the ML model for inference from HuggingFace.
        For local model: loads model from HuggingFace URL in config
        For AWS Bedrock API: no model loading needed
        
        Args:
            model_name: Model identifier (overrides config URL)
            
        Returns:
            True if model loaded successfully or AWS Bedrock API ready
        """
        if not self.use_local_model:
            # AWS Bedrock API doesn't need model loading
            if self.bedrock_client and self.bedrock_client.is_available:
                logger.info("Using AWS Bedrock API - no local model loading needed")
                self.model_loaded = True
                return True
            else:
                logger.error("AWS Bedrock API not available or not configured")
                return False
        
        # Local model loading
        if not TRANSFORMERS_AVAILABLE:
            logger.error("Transformers library not available")
            return False
        
        if self.model_loaded:
            logger.info("Model already loaded")
            return True
        
        try:
            # Use provided model_name or get from config
            model_url = model_name or self.settings.HUGGINGFACE_MODEL_URL or "google/gemma-2b-it"
            logger.info(f"Loading model from HuggingFace: {model_url}")
            
            # Check if HF_TOKEN is configured for gated models
            if self.settings.HF_TOKEN:
                logger.info("Using HuggingFace token for authentication (gated model)")
            else:
                logger.warning("No HF_TOKEN configured - will use public models only")
            
            # Configure quantization for efficient GPU usage
            quantization_config = None
            if self.device == "cuda":
                try:
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16,
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_quant_type="nf4"
                    )
                except Exception as e:
                    logger.warning(f"Could not configure quantization: {e}")
            
            # Load tokenizer from HuggingFace
            logger.info(f"Downloading tokenizer from: {model_url}")
            self.tokenizer = AutoTokenizer.from_pretrained(
                model_url,
                trust_remote_code=True,
                token=self.settings.HF_TOKEN
            )
            logger.info("Tokenizer downloaded successfully")
            
            # Load model from HuggingFace
            logger.info(f"Downloading model from: {model_url}")
            self.model = AutoModelForCausalLM.from_pretrained(
                model_url,
                quantization_config=quantization_config,
                device_map="auto" if self.device == "cuda" else None,
                trust_remote_code=True,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                token=self.settings.HF_TOKEN
            )
            logger.info("Model downloaded successfully")
            
            if self.device == "cpu":
                self.model = self.model.to(self.device)
            
            # Create text generation pipeline
            logger.info("Creating text generation pipeline")
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device == "cuda" else -1,
                max_new_tokens=512,
                temperature=self.settings.TEMPERATURE,
                top_p=self.settings.TOP_P,
                do_sample=True
            )
            
            self.model_loaded = True
            logger.info(f"Model {model_url} loaded and ready for inference")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model from HuggingFace: {e}")
            return False
    
    def generate_text(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: Optional[float] = None
    ) -> str:
        """
        Generate text using the loaded model or Gemini API.
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Generated text
        """
        if not self.use_local_model:
            return self._generate_text_bedrock(prompt, max_tokens, temperature)
        
        # Local model generation
        if not self.model_loaded:
            logger.warning("Model not loaded, attempting to load...")
            if not self.load_model():
                return "Error: Model not available"
        
        try:
            temp = temperature if temperature is not None else self.settings.TEMPERATURE
            
            result = self.pipeline(
                prompt,
                max_new_tokens=max_tokens,
                temperature=temp,
                top_p=self.settings.TOP_P,
                do_sample=True,
                return_full_text=False
            )
            
            generated_text = result[0]['generated_text']
            return generated_text.strip()
            
        except Exception as e:
            logger.error(f"Local model text generation error: {e}")
            return f"Error generating text: {str(e)}"
    
    def _generate_text_bedrock(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: Optional[float] = None
    ) -> str:
        """Generate text using AWS Bedrock API (Claude Sonnet 4.5)."""
        if not self.bedrock_client or not self.bedrock_client.is_available:
            logger.error("AWS Bedrock client not available")
            return "Error: AWS Bedrock API not available"
        
        try:
            temp = temperature if temperature is not None else self.settings.TEMPERATURE
            
            response = self.bedrock_client.generate(
                prompt=prompt,
                model_name="claude-4.5-sonnet",
                max_tokens=max_tokens,
                temperature=temp
            )
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"AWS Bedrock API text generation error: {e}")
            return f"Error generating text via AWS Bedrock: {str(e)}"
    
    def predict_trial_success(
        self,
        trial_design: TrialDesign,
        historical_context: Optional[str] = None
    ) -> PredictionResponse:
        """
        Predict trial success probability using ML model (local or Gemini API).
        
        Args:
            trial_design: Trial design parameters
            historical_context: Optional historical trial data context
            
        Returns:
            PredictionResponse with success probability and insights
        """
        
        # Build comprehensive prompt
        prompt = self._build_prediction_prompt(trial_design, historical_context)
        
        # Generate prediction
        if self.model_loaded:
            response_text = self.generate_text(prompt, max_tokens=400)
        else:
            # Fallback to heuristic-based prediction
            response_text = self._heuristic_prediction(trial_design)
        
        # Parse response and extract metrics
        prediction = self._parse_prediction_response(response_text, trial_design)
        
        return prediction
    
    def _build_prediction_prompt(
        self,
        trial_design: TrialDesign,
        historical_context: Optional[str]
    ) -> str:
        """Build a comprehensive prompt for trial success prediction."""
        
        prompt = f"""You are an expert clinical trial analyst. Analyze the following trial design and predict its success probability.

Trial Information:
- Name: {trial_design.trial_name}
- Phase: {trial_design.phase.value}
- Therapeutic Area: {trial_design.therapeutic_area}
- Drug: {trial_design.drug_name}
- Indication: {trial_design.indication}
- Target Enrollment: {trial_design.target_enrollment} patients
- Duration: {trial_design.duration_days} days ({trial_design.duration_days/365:.1f} years)
- Primary Endpoint: {trial_design.primary_endpoint}
- Treatment Arms: {', '.join(trial_design.treatment_arms)}

Patient Criteria:
- Age Range: {trial_design.inclusion_criteria.min_age}-{trial_design.inclusion_criteria.max_age} years
- Required Biomarkers: {', '.join(trial_design.inclusion_criteria.required_biomarkers) if trial_design.inclusion_criteria.required_biomarkers else 'None'}

Expected Parameters:
- Dropout Rate: {trial_design.expected_dropout_rate*100:.1f}%
- Success Rate: {trial_design.expected_success_rate*100:.1f}%

"""
        
        if historical_context:
            prompt += f"\nHistorical Context:\n{historical_context}\n"
        
        prompt += """
Based on this information, provide:
1. Success probability (0-100%)
2. Top 3-5 risk factors
3. Brief explanation of your assessment
4. Confidence level (0-100%)

Format your response as:
SUCCESS_PROBABILITY: [number]%
CONFIDENCE: [number]%
RISK_FACTORS: [factor1], [factor2], [factor3]
EXPLANATION: [your analysis]
"""
        
        return prompt
    
    def _heuristic_prediction(self, trial_design: TrialDesign) -> str:
        """Fallback heuristic-based prediction when ML model is unavailable."""
        
        # Phase-based success rates
        phase_rates = {
            "Phase I": 70,
            "Phase II": 50,
            "Phase III": 60,
            "Phase IV": 75
        }
        
        base_success = phase_rates.get(trial_design.phase.value, 60)
        
        # Adjust based on parameters
        if trial_design.target_enrollment < 100:
            base_success -= 5
        elif trial_design.target_enrollment > 500:
            base_success += 5
        
        if trial_design.expected_dropout_rate > 0.25:
            base_success -= 10
        
        # Risk factors
        risk_factors = []
        if trial_design.expected_dropout_rate > 0.2:
            risk_factors.append("High expected dropout rate")
        if trial_design.duration_days > 730:
            risk_factors.append("Long trial duration")
        if trial_design.target_enrollment > 1000:
            risk_factors.append("Large enrollment target")
        if trial_design.therapeutic_area == "Oncology":
            risk_factors.append("Complex therapeutic area")
        
        confidence = 75
        
        return f"""SUCCESS_PROBABILITY: {base_success}%
CONFIDENCE: {confidence}%
RISK_FACTORS: {', '.join(risk_factors) if risk_factors else 'Standard trial risks'}
EXPLANATION: This {trial_design.phase.value} trial in {trial_design.therapeutic_area} has a moderate success probability based on historical data. The trial design appears feasible with {trial_design.target_enrollment} patients over {trial_design.duration_days/365:.1f} years."""
    
    def _parse_prediction_response(
        self,
        response_text: str,
        trial_design: TrialDesign
    ) -> PredictionResponse:
        """Parse the model's response into a structured prediction."""
        
        # Extract success probability
        success_prob = 0.65  # default
        try:
            if "SUCCESS_PROBABILITY:" in response_text:
                prob_str = response_text.split("SUCCESS_PROBABILITY:")[1].split()[0]
                success_prob = float(prob_str.strip('%')) / 100
        except Exception:
            pass
        
        # Extract confidence
        confidence = 0.75  # default
        try:
            if "CONFIDENCE:" in response_text:
                conf_str = response_text.split("CONFIDENCE:")[1].split()[0]
                confidence = float(conf_str.strip('%')) / 100
        except Exception:
            pass
        
        # Extract risk factors
        risk_factors = []
        try:
            if "RISK_FACTORS:" in response_text:
                risk_section = response_text.split("RISK_FACTORS:")[1].split("EXPLANATION:")[0]
                risk_factors = [r.strip() for r in risk_section.split(',') if r.strip()]
        except Exception:
            risk_factors = ["Standard trial risks"]
        
        # Extract explanation
        explanation = "Prediction based on trial parameters and historical data"
        try:
            if "EXPLANATION:" in response_text:
                explanation = response_text.split("EXPLANATION:")[1].strip()
        except Exception:
            pass
        
        return PredictionResponse(
            success_probability=min(1.0, max(0.0, success_prob)),
            risk_factors=risk_factors[:5],  # Top 5 risks
            confidence_score=min(1.0, max(0.0, confidence)),
            explanation=explanation,
            comparable_trials=[]
        )
    
    def batch_predict(
        self,
        trial_designs: List[TrialDesign]
    ) -> List[PredictionResponse]:
        """
        Batch prediction for multiple trials (GPU-optimized).
        
        Args:
            trial_designs: List of trial designs
            
        Returns:
            List of predictions
        """
        predictions = []
        
        for trial_design in trial_designs:
            prediction = self.predict_trial_success(trial_design)
            predictions.append(prediction)
        
        return predictions
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the active model (local or AWS Bedrock API)."""
        info = {
            "device": self.device,
            "model_loaded": self.model_loaded,
            "using_local_model": self.use_local_model,
            "using_bedrock_api": not self.use_local_model,
            "gpu_available": torch.cuda.is_available() if self.use_local_model else False,
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "bedrock_available": BOTO3_AVAILABLE
        }
        
        if self.use_local_model and torch.cuda.is_available():
            info.update({
                "gpu_name": torch.cuda.get_device_name(0),
                "gpu_memory_allocated_gb": torch.cuda.memory_allocated(0) / 1e9,
                "gpu_memory_reserved_gb": torch.cuda.memory_reserved(0) / 1e9,
                "gpu_count": torch.cuda.device_count()
            })
        
        if not self.use_local_model:
            info.update({
                "aws_bedrock_configured": self.bedrock_client.is_available if self.bedrock_client else False,
                "model_info": "Using AWS Bedrock (Claude Sonnet 4.5)"
            })
        
        return info
    
    def unload_model(self):
        """Unload model to free GPU memory."""
        if self.model is not None:
            del self.model
            del self.tokenizer
            del self.pipeline
            
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            self.model = None
            self.tokenizer = None
            self.pipeline = None
            self.model_loaded = False
            
            logger.info("Model unloaded successfully")


# Singleton instance
ml_service = MLModelService()


def get_ml_service() -> MLModelService:
    """Get ML service instance."""
    return ml_service
