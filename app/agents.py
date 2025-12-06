"""AWS Bedrock agents using Claude Sonnet 4.5 for clinical trial analysis."""
import logging
from datetime import datetime

# AWS Bedrock client for text generation
from .aws_bedrock_client import get_bedrock_client, BOTO3_AVAILABLE

from .models import AgentRequest, AgentResponse
from .config import get_settings
from .database import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

# Check if AWS Bedrock is available (for router to check)
_bedrock_client = get_bedrock_client()
AWS_BEDROCK_AVAILABLE = BOTO3_AVAILABLE and _bedrock_client.is_available
logger.info(f"AWS Bedrock agents available: {AWS_BEDROCK_AVAILABLE}")

class AWSBedrockAgent:
    """Base agent class using AWS Bedrock (Claude Sonnet 4.5) for text generation."""
    
    def __init__(self, agent_type: str, instruction: str):
        self.agent_type = agent_type
        self.instruction = instruction
        self.db = get_db()
        self.bedrock_client = get_bedrock_client()
        
        if not self.bedrock_client.is_available:
            logger.warning(f"AWS Bedrock client not available for {agent_type} agent")
    
    def process(self, request: AgentRequest) -> AgentResponse:
        if not self.bedrock_client.is_available:
            raise RuntimeError(f"AWS Bedrock agent not initialized. boto3 available: {BOTO3_AVAILABLE}, credentials configured: {bool(settings.AWS_ACCESS_KEY_ID)}")
        
        # Build prompt with context data
        prompt = request.query
        
        # Include context data (simulation results, trial info, etc.) in the prompt
        if request.context:
            context = request.context
            prompt += "\n\n--- SIMULATION DATA ---\n"
            
            # Add simulation ID if available
            if context.get('simulation_id'):
                prompt += f"Simulation ID: {context['simulation_id']}\n"
            
            # Add trial info if available and not None
            trial_info = context.get('trial_info')
            if trial_info and isinstance(trial_info, dict):
                prompt += f"\nTrial Information:\n"
                for key, value in trial_info.items():
                    if value is not None:
                        prompt += f"  - {key}: {value}\n"
            
            # Add results if available and not None
            results = context.get('results')
            if results and isinstance(results, dict):
                prompt += f"\nSimulation Results:\n"
                for key, value in results.items():
                    if value is not None:
                        if isinstance(value, float):
                            prompt += f"  - {key}: {value:.4f}\n"
                        else:
                            prompt += f"  - {key}: {value}\n"
            
            # Add any other context data (skip None values)
            for key, value in context.items():
                if key not in ['simulation_id', 'trial_info', 'results'] and value is not None:
                    if isinstance(value, dict):
                        prompt += f"\n{key}:\n"
                        for k, v in value.items():
                            if v is not None:
                                prompt += f"  - {k}: {v}\n"
                    else:
                        prompt += f"\n{key}: {value}\n"
            
            # Add benchmark comparison
            try:
                stats = self.db.get_historical_stats()
                if stats:
                    prompt += f"\n--- BENCHMARK DATA ---\n"
                    prompt += f"Historical Success Rate: {stats.get('success_rate', 0)*100:.1f}%\n"
                    prompt += f"Average Completion Rate: {stats.get('avg_completion_rate', 0)*100:.1f}%\n"
                    prompt += f"Average Dropout Rate: {stats.get('avg_dropout_rate', 0)*100:.1f}%\n"
            except Exception as e:
                logger.warning(f"Could not get historical stats: {e}")
        
        logger.info(f"Sending prompt to AWS Bedrock ({len(prompt)} chars)")
        logger.debug(f"Prompt preview: {prompt[:500]}...")
        
        response = self.bedrock_client.generate(
            prompt=prompt,
            model_name="claude-4.5-sonnet",
            max_tokens=1024,
            temperature=0.7,
            system_instruction=self.instruction
        )
        
        return AgentResponse(
            agent_type=self.agent_type, 
            response=response, 
            confidence=0.92, 
            sources=["AWS Bedrock - Claude Sonnet 4.5"], 
            timestamp=datetime.now()
        )

class ResearchAgent(AWSBedrockAgent):
    def __init__(self):
        super().__init__(
            "research", 
            "You are a clinical trial research analyst. Provide concise, data-driven insights. CRITICAL: Keep ALL responses to exactly 4-5 sentences maximum. Be direct and actionable."
        )

class PredictionAgent(AWSBedrockAgent):
    def __init__(self):
        super().__init__(
            "prediction", 
            "You are a trial prediction specialist. Provide probability estimates with brief justification. CRITICAL: Keep ALL responses to exactly 4-5 sentences maximum. Focus on key factors only."
        )

class OptimizationAgent(AWSBedrockAgent):
    def __init__(self):
        super().__init__(
            "optimization", 
            "You are a trial optimization expert. Suggest top 2-3 improvements only. CRITICAL: Keep ALL responses to exactly 4-5 sentences maximum. Prioritize highest-impact changes."
        )

class ReportAgent(AWSBedrockAgent):
    def __init__(self):
        super().__init__(
            "report", 
            "You are a trial reporting specialist. Provide executive summary-style insights. CRITICAL: Keep ALL responses to exactly 4-5 sentences maximum. Highlight most important findings only."
        )

class AgentFactory:
    _agents = None
    @classmethod
    def _init(cls):
        if cls._agents is None:
            cls._agents = {'research': ResearchAgent(), 'prediction': PredictionAgent(), 'optimization': OptimizationAgent(), 'report': ReportAgent()}
    @classmethod
    def get_agent(cls, agent_type):
        cls._init()
        return cls._agents.get(agent_type)
    @classmethod
    def process_request(cls, request):
        agent = cls.get_agent(request.agent_type)
        if not agent:
            raise ValueError(f"Unknown agent: {request.agent_type}")
        return agent.process(request)
