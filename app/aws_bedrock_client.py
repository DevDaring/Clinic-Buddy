"""
AWS Bedrock Client for Claude Sonnet 4.5 Model.
Handles all text generation using AWS Bedrock API.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

logger = logging.getLogger(__name__)

# Check if boto3 is available
BOTO3_AVAILABLE = False
boto3 = None  # type: ignore
ClientError = Exception  # Fallback for type checking

try:
    import boto3 as _boto3  # type: ignore
    from botocore.exceptions import ClientError as _ClientError
    boto3 = _boto3
    ClientError = _ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    logger.warning("boto3 library not available. AWS Bedrock features will be limited.")


class AWSBedrockClient:
    """Client for AWS Bedrock API - Claude Sonnet 4.5"""
    
    def __init__(self):
        """Initialize AWS Bedrock client with credentials from environment."""
        self.client: Any = None
        self.models: Dict[str, str] = {}
        self._initialized = False
        
        if not BOTO3_AVAILABLE or boto3 is None:
            logger.error("boto3 library not available. Install with: pip install boto3")
            return
        
        try:
            self.client = boto3.client(
                "bedrock-runtime",
                region_name=os.getenv("AWS_REGION", "us-east-1"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "")
            )
            
            # Model IDs for Sonnet models
            AWS_SONNET_45 = os.getenv("AWS_SONNET_45", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
            
            self.models = {
                "claude-4.5-sonnet": AWS_SONNET_45
            }
            
            self._initialized = True
            logger.info(f"✅ AWS Bedrock client initialized successfully")
            logger.info(f"   Region: {os.getenv('AWS_REGION', 'us-east-1')}")
            logger.info(f"   Model: {AWS_SONNET_45}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AWS Bedrock client: {e}")
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        """Check if AWS Bedrock client is available and initialized."""
        return BOTO3_AVAILABLE and self._initialized and self.client is not None
    
    def generate(
        self, 
        prompt: str, 
        model_name: str = "claude-4.5-sonnet",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generate response from AWS Bedrock Claude Sonnet.
        
        Args:
            prompt: Input prompt
            model_name: Model identifier (default: claude-4.5-sonnet)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            system_instruction: Optional system instruction for the model
            
        Returns:
            Generated text response
        """
        if not self.is_available:
            raise RuntimeError("AWS Bedrock client not available or not initialized")
        
        model_id = self.models.get(model_name)
        if not model_id:
            raise ValueError(f"Unknown model: {model_name}. Available: {list(self.models.keys())}")
        
        try:
            # Build request body
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}]
                    }
                ]
            }
            
            # Add system instruction if provided
            if system_instruction:
                body["system"] = system_instruction
            
            logger.debug(f"Calling AWS Bedrock with model: {model_id}")
            
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            result = json.loads(response["body"].read())
            generated_text = result["content"][0]["text"].strip()
            
            logger.info(f"✅ AWS Bedrock response received: {len(generated_text)} chars")
            return generated_text
            
        except ClientError as e:
            error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', 'Unknown') if hasattr(e, 'response') else 'Unknown'
            error_message = getattr(e, 'response', {}).get('Error', {}).get('Message', str(e)) if hasattr(e, 'response') else str(e)
            logger.error(f"AWS Bedrock API error ({error_code}): {error_message}")
            raise Exception(f"AWS Bedrock API error: {error_message}")
        except Exception as e:
            logger.error(f"AWS Bedrock text generation error: {e}")
            raise Exception(f"Error generating text via AWS Bedrock: {str(e)}")
    
    def generate_with_history(
        self,
        messages: list,
        model_name: str = "claude-4.5-sonnet",
        max_tokens: int = 2048,
        temperature: float = 0.7,
        system_instruction: Optional[str] = None
    ) -> str:
        """
        Generate response with conversation history.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model_name: Model identifier
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_instruction: Optional system instruction
            
        Returns:
            Generated text response
        """
        if not self.is_available:
            raise RuntimeError("AWS Bedrock client not available or not initialized")
        
        model_id = self.models.get(model_name)
        if not model_id:
            raise ValueError(f"Unknown model: {model_name}")
        
        try:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages
            }
            
            if system_instruction:
                body["system"] = system_instruction
            
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json"
            )
            
            result = json.loads(response["body"].read())
            return result["content"][0]["text"].strip()
            
        except Exception as e:
            logger.error(f"AWS Bedrock generation with history error: {e}")
            raise Exception(f"Error generating text: {str(e)}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the AWS Bedrock configuration."""
        return {
            "provider": "AWS Bedrock",
            "available": self.is_available,
            "boto3_available": BOTO3_AVAILABLE,
            "initialized": self._initialized,
            "region": os.getenv("AWS_REGION", "us-east-1"),
            "models": self.models,
            "credentials_configured": bool(os.getenv("AWS_ACCESS_KEY_ID"))
        }


# Singleton instance
_bedrock_client = None


def get_bedrock_client() -> AWSBedrockClient:
    """Get singleton AWS Bedrock client instance."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = AWSBedrockClient()
    return _bedrock_client
