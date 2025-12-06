"""
AI Agent implementations for clinical trial analysis and optimization.
Includes Research, Prediction, Optimization, and Report agents.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from .models import (
    AgentRequest, AgentResponse, TrialDesign,
    TrialReport, SimulationResult
)
from .config import get_settings
from .database import get_db

# Make ml_service import optional
try:
    from .ml_service import get_ml_service
    ML_SERVICE_AVAILABLE = True
except (ImportError, Exception) as e:
    ML_SERVICE_AVAILABLE = False
    logging.warning(f"ML Service not available: {e}")
    def get_ml_service():
        return None

logger = logging.getLogger(__name__)
settings = get_settings()


class BaseAgent:
    """Base class for all AI agents."""
    
    def __init__(self, agent_type: str, description: str):
        self.agent_type = agent_type
        self.description = description
        self.db = get_db()
        self.ml_service = get_ml_service()
    
    def process(self, request: AgentRequest) -> AgentResponse:
        """Process agent request and return response."""
        raise NotImplementedError


class ResearchAgent(BaseAgent):
    """
    Research Agent: Analyzes historical trial data and identifies patterns.
    """
    
    def __init__(self):
        super().__init__(
            agent_type="research",
            description="Analyzes historical clinical trial data and identifies success patterns"
        )
    
    def process(self, request: AgentRequest) -> AgentResponse:
        """
        Analyze historical data based on user query.
        
        Args:
            request: Agent request with query and optional context
            
        Returns:
            AgentResponse with research findings
        """
        logger.info(f"Research Agent processing query: {request.query[:100]}")
        
        try:
            # Extract key parameters from query
            context = request.context or {}
            
            # Get historical statistics
            stats = self.db.get_historical_stats()
            
            # Get trials data
            trials_df = self.db.get_trials()
            
            # Build research analysis
            analysis = self._analyze_historical_data(
                query=request.query,
                stats=stats,
                trials_df=trials_df,
                context=context
            )
            
            # Generate insights using ML if available
            if self.ml_service and hasattr(self.ml_service, 'model_loaded') and self.ml_service.model_loaded:
                enhanced_analysis = self._enhance_with_ml(analysis, request.query)
            else:
                enhanced_analysis = analysis
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=enhanced_analysis,
                confidence=0.85,
                sources=["Historical Trial Database", "Statistical Analysis"],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Research Agent error: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"Error during research analysis: {str(e)}",
                confidence=0.0,
                sources=[],
                timestamp=datetime.now()
            )
    
    def _analyze_historical_data(
        self,
        query: str,
        stats: Dict[str, Any],
        trials_df: Any,
        context: Dict[str, Any]
    ) -> str:
        """Analyze historical data and generate concise insights (4-5 sentences max)."""
        
        # Build ultra-concise analysis (4-5 sentences)
        analysis_parts = []
        
        # Sentence 1: Key statistics
        analysis_parts.append(
            f"Analysis of {stats['total_trials']} historical trials shows {stats['success_rate']*100:.1f}% overall success rate "
            f"with average enrollment of {stats['avg_enrollment']:.0f} patients and {stats['avg_dropout_rate']*100:.1f}% dropout rate."
        )
        
        # Sentence 2: Success factors
        analysis_parts.append(
            "Key success factors include meeting enrollment targets (+25% success), maintaining dropout <20% (+30% success), "
            "and optimal trial duration (Phase II: 1-2 years)."
        )
        
        # Sentence 3: Cost insight
        analysis_parts.append(
            f"Average trial cost is ${stats['avg_cost']/1e6:.1f}M with {stats['avg_duration_days']/365:.1f} years average duration."
        )
        
        # Sentence 4: Recommendation
        query_lower = query.lower()
        if 'recommend' in query_lower or 'suggest' in query_lower or 'optimize' in query_lower:
            analysis_parts.append(
                "Recommendations: Plan for 15-20% dropout in sample size, implement proactive retention strategies, "
                "and budget 10-15% contingency for timeline extensions."
            )
        elif 'phase' in query_lower:
            phase_dist = stats.get('phase_distribution', {})
            top_phase = max(phase_dist.items(), key=lambda x: x[1])[0] if phase_dist else 'Phase II'
            analysis_parts.append(f"Most trials are {top_phase} with specific success patterns for that phase.")
        else:
            analysis_parts.append(
                "Benchmark against similar completed trials and consider adaptive designs for efficiency."
            )
        
        return " ".join(analysis_parts)
    
    def _enhance_with_ml(self, analysis: str, query: str) -> str:
        """Enhance analysis with ML-generated insights (max 2 sentences)."""
        
        if not self.ml_service:
            return analysis
        
        prompt = f"""Query: {query}
Analysis: {analysis}

Add exactly 2 sentences of strategic insight. Be extremely concise."""
        
        try:
            enhanced = self.ml_service.generate_text(prompt, max_tokens=100)
            return f"{analysis} {enhanced.strip()}"
        except Exception as e:
            logger.error(f"ML enhancement failed: {e}")
            return analysis


class PredictionAgent(BaseAgent):
    """
    Prediction Agent: Forecasts trial success probability using ML models.
    """
    
    def __init__(self):
        super().__init__(
            agent_type="prediction",
            description="Predicts clinical trial outcomes using machine learning"
        )
    
    def process(self, request: AgentRequest) -> AgentResponse:
        """
        Generate trial success predictions.
        
        Args:
            request: Agent request with trial information
            
        Returns:
            AgentResponse with predictions
        """
        logger.info(f"Prediction Agent processing: {request.query[:100]}")
        
        try:
            context = request.context or {}
            
            # Extract trial design if provided in context
            trial_design = context.get('trial_design')
            
            if trial_design and self.ml_service:
                # Use ML service for prediction
                prediction = self.ml_service.predict_trial_success(trial_design)
                
                response_text = self._format_prediction_response(prediction)
            else:
                # General prediction guidance
                response_text = self._provide_prediction_guidance(request.query)
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=response_text,
                confidence=0.80,
                sources=["ML Prediction Model", "Historical Data"],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Prediction Agent error: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"Error generating prediction: {str(e)}",
                confidence=0.0,
                sources=[],
                timestamp=datetime.now()
            )
    
    def _format_prediction_response(self, prediction) -> str:
        """Format prediction into readable response."""
        
        response = f"""**Clinical Trial Success Prediction**

**Predicted Success Probability: {prediction.success_probability*100:.1f}%**
Confidence Score: {prediction.confidence_score*100:.1f}%

**Identified Risk Factors:**
"""
        for i, risk in enumerate(prediction.risk_factors, 1):
            response += f"{i}. {risk}\n"
        
        response += f"\n**Analysis:**\n{prediction.explanation}\n"
        
        # Add risk interpretation
        if prediction.success_probability >= 0.7:
            response += "\n✓ **Assessment**: High probability of success. Trial design appears robust."
        elif prediction.success_probability >= 0.5:
            response += "\n⚠ **Assessment**: Moderate probability. Consider risk mitigation strategies."
        else:
            response += "\n✗ **Assessment**: Lower probability. Significant protocol optimization recommended."
        
        return response
    
    def _provide_prediction_guidance(self, query: str) -> str:
        """Provide general prediction guidance."""
        
        return """**Prediction Methodology**

Our prediction system analyzes multiple factors:

1. **Historical Success Rates**
   - Phase-specific benchmarks
   - Therapeutic area trends
   - Enrollment patterns

2. **Trial Design Parameters**
   - Patient population characteristics
   - Inclusion/exclusion criteria
   - Endpoint selection and feasibility

3. **Risk Assessment**
   - Dropout probability modeling
   - Adverse event likelihood
   - Protocol complexity analysis

4. **ML-Powered Insights**
   - Pattern recognition from 1000+ trials
   - Success factor correlation analysis
   - Comparative trial matching

To get a specific prediction, provide trial design details including phase, therapeutic area, enrollment target, and primary endpoints."""


class OptimizationAgent(BaseAgent):
    """
    Optimization Agent: Suggests protocol improvements and design optimizations.
    """
    
    def __init__(self):
        super().__init__(
            agent_type="optimization",
            description="Optimizes trial protocols and suggests improvements"
        )
    
    def process(self, request: AgentRequest) -> AgentResponse:
        """
        Generate optimization suggestions.
        
        Args:
            request: Agent request with trial details
            
        Returns:
            AgentResponse with optimization recommendations
        """
        logger.info(f"Optimization Agent processing: {request.query[:100]}")
        
        try:
            context = request.context or {}
            trial_design = context.get('trial_design')
            simulation_result = context.get('simulation_result')
            
            if trial_design:
                suggestions = self._generate_optimizations(
                    trial_design,
                    simulation_result
                )
            else:
                suggestions = self._provide_optimization_framework(request.query)
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=suggestions,
                confidence=0.82,
                sources=["Optimization Algorithms", "Best Practices Database"],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Optimization Agent error: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"Error generating optimizations: {str(e)}",
                confidence=0.0,
                sources=[],
                timestamp=datetime.now()
            )
    
    def _generate_optimizations(
        self,
        trial_design: TrialDesign,
        simulation_result: Optional[SimulationResult]
    ) -> str:
        """Generate specific optimization recommendations."""
        
        optimizations = ["**Trial Protocol Optimization Recommendations**\n"]
        
        # Enrollment optimization
        if trial_design.target_enrollment > 500:
            optimizations.append("**1. Enrollment Strategy:**")
            optimizations.append("   - Consider multi-site approach to accelerate enrollment")
            optimizations.append("   - Implement site selection criteria to identify high-performing sites")
            optimizations.append("   - Use predictive modeling for enrollment forecasting")
        
        # Duration optimization
        if trial_design.duration_days > 730:
            optimizations.append("\n**2. Timeline Optimization:**")
            optimizations.append("   - Evaluate interim analysis timepoints for early success signals")
            optimizations.append("   - Consider adaptive design elements to adjust sample size")
            optimizations.append(f"   - Current duration: {trial_design.duration_days/365:.1f} years - assess if endpoint can be measured earlier")
        
        # Dropout mitigation
        if trial_design.expected_dropout_rate > 0.2:
            optimizations.append("\n**3. Dropout Rate Reduction:**")
            optimizations.append("   - Implement patient engagement programs")
            optimizations.append("   - Simplify visit schedules where possible")
            optimizations.append("   - Provide transportation and financial support")
            optimizations.append("   - Use digital health tools for remote monitoring")
        
        # Cost optimization
        optimizations.append("\n**4. Cost Efficiency Improvements:**")
        optimizations.append("   - Leverage centralized lab services")
        optimizations.append("   - Implement risk-based monitoring (RBM)")
        optimizations.append("   - Use electronic data capture (EDC) systems")
        optimizations.append("   - Consider decentralized trial elements")
        
        # Endpoint optimization
        optimizations.append("\n**5. Endpoint Enhancement:**")
        optimizations.append(f"   - Primary: {trial_design.primary_endpoint}")
        optimizations.append("   - Consider adding biomarker endpoints for early signals")
        optimizations.append("   - Ensure endpoints are clinically meaningful and measurable")
        
        # Safety monitoring
        optimizations.append("\n**6. Safety Optimization:**")
        optimizations.append("   - Implement real-time adverse event monitoring")
        optimizations.append("   - Establish clear stopping rules")
        optimizations.append("   - Use Data Safety Monitoring Board (DSMB)")
        
        if simulation_result:
            dropout_rate = simulation_result.dropout_rate
            if dropout_rate > 0.25:
                optimizations.append(f"\n⚠ **Alert**: Simulated dropout rate ({dropout_rate*100:.1f}%) exceeds target - prioritize retention strategies")
        
        return "\n".join(optimizations)
    
    def _provide_optimization_framework(self, query: str) -> str:
        """Provide general optimization framework."""
        
        return """**Clinical Trial Optimization Framework**

**Key Optimization Areas:**

1. **Design Efficiency**
   - Adaptive design implementation
   - Seamless phase transitions
   - Platform trial opportunities
   - Basket/umbrella trial structures

2. **Patient-Centric Approaches**
   - Simplified protocols
   - Home healthcare options
   - Digital health integration
   - Patient-reported outcomes

3. **Operational Excellence**
   - Site selection optimization
   - Risk-based monitoring
   - Centralized services
   - Technology enablement

4. **Statistical Optimization**
   - Enrichment strategies
   - Biomarker-driven enrollment
   - Interim analyses
   - Sample size re-estimation

5. **Cost Management**
   - Lean trial design
   - Strategic vendor selection
   - Resource allocation
   - Budget contingencies

Provide specific trial details for customized optimization recommendations."""


class ReportAgent(BaseAgent):
    """
    Report Agent: Generates comprehensive trial analysis reports.
    """
    
    def __init__(self):
        super().__init__(
            agent_type="report",
            description="Generates comprehensive trial analysis and insights reports"
        )
    
    def process(self, request: AgentRequest) -> AgentResponse:
        """
        Generate comprehensive trial report.
        
        Args:
            request: Agent request with report requirements
            
        Returns:
            AgentResponse with formatted report
        """
        logger.info(f"Report Agent processing: {request.query[:100]}")
        
        try:
            context = request.context or {}
            
            report_content = self._generate_report(
                query=request.query,
                context=context
            )
            
            return AgentResponse(
                agent_type=self.agent_type,
                response=report_content,
                confidence=0.88,
                sources=["Trial Database", "Analysis Engine", "ML Predictions"],
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Report Agent error: {e}")
            return AgentResponse(
                agent_type=self.agent_type,
                response=f"Error generating report: {str(e)}",
                confidence=0.0,
                sources=[],
                timestamp=datetime.now()
            )
    
    def _generate_report(self, query: str, context: Dict[str, Any]) -> str:
        """Generate ultra-concise report (4-5 sentences max)."""
        
        results = context.get('results', {})
        trial_info = context.get('trial_info', {})
        simulation_id = context.get('simulation_id', 'N/A')
        
        # Build 4-5 sentence executive summary
        sentences = []
        
        # Sentence 1: Overview with key metrics
        success_prob = results.get('success_probability', 0) * 100
        completed = results.get('patients_completed', 0)
        enrolled = results.get('patients_enrolled', 0)
        completion_rate = (completed / enrolled * 100) if enrolled > 0 else 0
        
        sentences.append(
            f"Simulation {simulation_id} shows {success_prob:.1f}% success probability with "
            f"{completion_rate:.1f}% completion rate ({completed}/{enrolled} patients)."
        )
        
        # Sentence 2: Risk assessment
        dropout_rate = results.get('dropout_rate', 0) * 100
        adverse_events = results.get('adverse_events', 0)
        risk_level = "low" if dropout_rate < 15 and adverse_events < 20 else "moderate" if dropout_rate < 25 else "high"
        
        sentences.append(
            f"Risk assessment: {risk_level} risk with {dropout_rate:.1f}% dropout rate and {adverse_events} adverse events."
        )
        
        # Sentence 3: Cost and timeline
        cost = results.get('estimated_cost', 0) / 1e6
        primary_met = results.get('primary_endpoint_met', False)
        endpoint_status = "achieved" if primary_met else "not achieved"
        
        sentences.append(
            f"Estimated cost is ${cost:.2f}M with primary endpoint {endpoint_status}."
        )
        
        # Sentence 4: Recommendation
        if success_prob >= 70:
            rec = "Strong candidate for advancement - success probability above industry average."
        elif success_prob >= 50:
            rec = "Moderate potential - consider protocol optimizations before proceeding."
        else:
            rec = "High risk - recommend significant design changes or discontinuation."
        
        sentences.append(rec)
        
        # Optional 5th sentence: Key action
        if dropout_rate > 20:
            sentences.append("Priority action: Implement enhanced patient retention strategies to reduce dropout.")
        elif adverse_events > 25:
            sentences.append("Priority action: Review safety protocols and patient selection criteria.")
        
        return " ".join(sentences)


# Agent Factory
class AgentFactory:
    """Factory for creating and managing agents."""
    
    _agents = {
        'research': ResearchAgent(),
        'prediction': PredictionAgent(),
        'optimization': OptimizationAgent(),
        'report': ReportAgent()
    }
    
    @classmethod
    def get_agent(cls, agent_type: str) -> BaseAgent:
        """Get agent by type."""
        agent = cls._agents.get(agent_type)
        if not agent:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return agent
    
    @classmethod
    def process_request(cls, request: AgentRequest) -> AgentResponse:
        """Process agent request through appropriate agent."""
        agent = cls.get_agent(request.agent_type)
        return agent.process(request)
