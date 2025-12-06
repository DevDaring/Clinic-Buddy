"""
Agent Router: Intelligent routing between AWS Bedrock and Fallback agents.

This router provides automatic failover between:
1. Primary: AWS Bedrock agents (agents.py) - Uses Claude Sonnet 4.5
2. Fallback: Rule-based agents (fallback_agents.py) - Always available

Routing Logic:
- If AWS Bedrock available + credentials configured -> Use agents.py
- If Bedrock fails at runtime -> Automatically fallback to fallback_agents.py
- If Bedrock not available -> Use fallback_agents.py directly
"""

import logging
from typing import Dict, Any
from datetime import datetime

from .models import AgentRequest, AgentResponse
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Try to import AWS Bedrock agents
try:
    from . import agents as bedrock_agents
    BEDROCK_AGENTS_AVAILABLE = hasattr(bedrock_agents, 'AWS_BEDROCK_AVAILABLE') and bedrock_agents.AWS_BEDROCK_AVAILABLE
    logger.info(f"✓ AWS Bedrock agents module loaded (Bedrock available: {BEDROCK_AGENTS_AVAILABLE})")
except Exception as e:
    BEDROCK_AGENTS_AVAILABLE = False
    logger.warning(f"⚠ Could not load AWS Bedrock agents: {e}")
    bedrock_agents = None

# Import fallback agents
try:
    from . import fallback_agents
    FALLBACK_AGENTS_AVAILABLE = True
    logger.info("✓ Fallback agents module loaded")
except Exception as e:
    FALLBACK_AGENTS_AVAILABLE = False
    fallback_agents = None
    logger.error(f"❌ Could not load fallback agents: {e}")


class AgentRouter:
    """
    Intelligent router for agent requests.

    Provides seamless failover and detailed logging.
    """
    
    _use_adk = None
    _routing_decision_made = False
    
    @classmethod
    def _determine_routing_strategy(cls):
        """Determine which agent system to use."""
        if cls._routing_decision_made:
            return cls._use_adk
        
        # Check if AWS Bedrock is available and configured
        if BEDROCK_AGENTS_AVAILABLE and settings.AWS_ACCESS_KEY_ID:
            cls._use_adk = True
            logger.info("🤖 Agent Router: Using AWS Bedrock (Claude Sonnet 4.5)")
        else:
            cls._use_adk = False
            if not BEDROCK_AGENTS_AVAILABLE:
                logger.info("📋 Agent Router: AWS Bedrock not available, using fallback")
            elif not settings.AWS_ACCESS_KEY_ID:
                logger.info("📋 Agent Router: AWS_ACCESS_KEY_ID not set, using fallback")
        
        cls._routing_decision_made = True
        return cls._use_adk
    
    @classmethod
    def process_request(cls, request: AgentRequest) -> AgentResponse:
        """
        Process agent request with automatic routing and fallback.
        
        Flow:
        1. Determine routing strategy (ADK vs Fallback)
        2. Try primary route
        3. On error, fallback to secondary route
        4. If both fail, return error response
        
        Args:
            request: AgentRequest with query, agent_type, and context
            
        Returns:
            AgentResponse with results from either ADK or fallback agents
        """
        logger.info("=" * 80)
        logger.info("🔄 AGENT ROUTER: Processing request")
        logger.info(f"Agent type: {request.agent_type}")
        logger.info(f"Query length: {len(request.query)} chars")
        logger.info(f"Context provided: {request.context is not None}")
        if request.context:
            logger.info(f"Context keys: {list(request.context.keys())}")
        
        use_adk = cls._determine_routing_strategy()
        logger.info(f"Routing strategy: {'AWS Bedrock' if use_adk else 'Fallback'}")
        
        # Try AWS Bedrock first if available
        if use_adk and bedrock_agents:
            try:
                logger.info(f"→ Routing to AWS Bedrock: {request.agent_type}")
                logger.debug(f"Calling bedrock_agents.AgentFactory.process_request...")
                response = bedrock_agents.AgentFactory.process_request(request)
                logger.info(f"✅ Bedrock response received ({len(response.response)} chars)")
                logger.info(f"Confidence: {response.confidence:.2f}")
                logger.info("=" * 80)
                return response
            except Exception as e:
                logger.error(f"❌ AWS Bedrock processing failed: {type(e).__name__}: {str(e)}")
                logger.exception("Bedrock error details:")
                logger.info("↩ Falling back to rule-based agents")
                # Fall through to fallback
        
        # Use fallback agents
        if FALLBACK_AGENTS_AVAILABLE and fallback_agents:
            try:
                logger.info(f"→ Routing to fallback agents: {request.agent_type}")
                logger.debug(f"Calling fallback_agents.AgentFactory.process_request...")
                response = fallback_agents.AgentFactory.process_request(request)
                logger.info(f"✅ Fallback response received ({len(response.response)} chars)")
                logger.info(f"Confidence: {response.confidence:.2f}")
                logger.info("=" * 80)
                return response
            except Exception as e:
                logger.error(f"❌ Fallback agent processing failed: {type(e).__name__}: {str(e)}")
                logger.exception("Fallback error details:")
        
        # Both systems failed - return error
        logger.error("❌❌❌ BOTH AGENT SYSTEMS FAILED ❌❌❌")
        logger.info("=" * 80)
        return AgentResponse(
            agent_type=request.agent_type,
            response=f"⚠ Agent processing unavailable. Both AWS Bedrock and fallback systems failed. Please check logs and configuration.",
            confidence=0.0,
            sources=["Error Handler"],
            timestamp=datetime.now()
        )
    
    @classmethod
    def get_agent(cls, agent_type: str):
        """
        Get agent instance (for compatibility with existing code).
        
        Args:
            agent_type: Type of agent ('research', 'prediction', 'optimization', 'report')
            
        Returns:
            Agent instance from appropriate system
        """
        use_adk = cls._determine_routing_strategy()
        
        if use_adk and bedrock_agents:
            try:
                return bedrock_agents.AgentFactory.get_agent(agent_type)
            except Exception as e:
                logger.warning(f"Failed to get Bedrock agent: {e}")
        
        if FALLBACK_AGENTS_AVAILABLE and fallback_agents:
            return fallback_agents.AgentFactory.get_agent(agent_type)
        
        raise RuntimeError(f"No agent system available for type: {agent_type}")
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """
        Get comprehensive status of agent routing system.
        
        Returns:
            Dictionary with routing status, availability, and configuration
        """
        use_adk = cls._determine_routing_strategy()
        
        status = {
            "router_version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            # Flat keys for easy access
            "aws_bedrock_available": BEDROCK_AGENTS_AVAILABLE,
            "api_key_configured": bool(settings.AWS_ACCESS_KEY_ID),
            "active_system": "AWS Bedrock" if use_adk else "Fallback",
            "fallback_available": FALLBACK_AGENTS_AVAILABLE,
            # Nested structure for detailed info
            "routing": {
                "active_system": "AWS Bedrock" if use_adk else "Fallback",
                "primary_available": BEDROCK_AGENTS_AVAILABLE,
                "fallback_available": FALLBACK_AGENTS_AVAILABLE
            },
            "aws_bedrock": {
                "module_loaded": bedrock_agents is not None,
                "bedrock_available": BEDROCK_AGENTS_AVAILABLE,
                "api_key_configured": bool(settings.AWS_ACCESS_KEY_ID),
                "model": settings.AWS_SONNET_45 if BEDROCK_AGENTS_AVAILABLE else None
            },
            "fallback": {
                "module_loaded": fallback_agents is not None,
                "available": FALLBACK_AGENTS_AVAILABLE
            },
            "agents": {
                "research": "available",
                "prediction": "available",
                "optimization": "available",
                "report": "available"
            }
        }
        
        # Add per-agent routing info
        for agent_type in ["research", "prediction", "optimization", "report"]:
            try:
                agent = cls.get_agent(agent_type)
                status["agents"][agent_type] = {
                    "available": True,
                    "using_bedrock": use_adk,
                    "source": "AWS Bedrock" if use_adk else "Fallback"
                }
            except Exception as e:
                status["agents"][agent_type] = {
                    "available": False,
                    "error": str(e)
                }
        
        return status
    
    @classmethod
    def force_fallback_mode(cls):
        """Force router to use fallback mode (useful for testing)."""
        cls._use_adk = False
        cls._routing_decision_made = True
        logger.warning("⚠ Forced fallback mode activated")
    
    @classmethod
    def reset_routing_decision(cls):
        """Reset routing decision (re-evaluate on next request)."""
        cls._routing_decision_made = False
        logger.info("↻ Routing decision reset")


# Factory alias for backward compatibility
class AgentFactory:
    """Alias for AgentRouter to maintain backward compatibility."""
    
    @classmethod
    def process_request(cls, request: AgentRequest) -> AgentResponse:
        return AgentRouter.process_request(request)
    
    @classmethod
    def get_agent(cls, agent_type: str):
        return AgentRouter.get_agent(agent_type)
    
    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        return AgentRouter.get_status()


# Export main classes
__all__ = [
    'AgentRouter',
    'AgentFactory',  # Backward compatibility
    'BEDROCK_AGENTS_AVAILABLE',
    'FALLBACK_AGENTS_AVAILABLE'
]
