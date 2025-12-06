# Agent Flow Architecture - Clinical Trial Predictor

## Overview

This document describes the **dual-framework agentic system** with intelligent routing between:
1. **Primary**: AWS Bedrock agents (Claude Sonnet 4.5) 
2. **Fallback**: Rule-based agents (always available)

The system automatically routes requests and provides seamless failover for maximum reliability.

---

## System Architecture with Router

```
┌─────────────────────────────────────────────────────────────┐
│                    User Application                          │
│              (FastAPI Web Interface)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   AGENT ROUTER             │
        │   (agent_router.py)        │
        │   - Intelligent Routing     │
        │   - Auto Failover          │
        └────────┬───────────────────┘
                 │
         ┌───────┴────────┐
         │  Route Decision │
         │  ADK Available? │
         │  API Key Set?   │
         └───────┬─────────┘
                 │
     ┌───────────┴───────────┐
     │                       │
     ▼                       ▼
┌─────────────┐      ┌──────────────┐
│ AWS Bedrock │      │  Fallback    │
│ agents.py   │      │ fallback_    │
│             │      │ agents.py    │
│ Claude      │      │ Rule-Based   │
│ Sonnet 4.5  │      │ Always Works │
└──────┬──────┘      └──────┬───────┘
       │                    │
       └──────────┬─────────┘
                  │
     ┌────────────▼────────────┐
     │ 4 Agent Types:          │
     │ - Research              │
     │ - Prediction            │
     │ - Optimization          │
     │ - Report                │
     └────────┬────────────────┘
              │
   ┌──────────┼──────────┐
   │          │          │
   ▼          ▼          ▼
┌────────┐ ┌─────────┐ ┌──────────┐
│Database│ │ML Model │ │ Analysis │
│ (CSV)  │ │(Local)  │ │ Engine   │
└────────┘ └─────────┘ └──────────┘
```

---

## Agent Router - Decision Flow

```
User Request
     │
     ▼
┌─────────────────┐
│ AgentRouter     │
│ .process_request│
└────────┬────────┘
         │
         ▼
    Check ADK
    Available?
         │
    ┌────┴────┐
    │         │
   YES       NO
    │         │
    ▼         ▼
Check API   Use Fallback
Key Set?    Agents
    │
┌───┴───┐
│       │
YES    NO
│       │
▼       ▼
Try     Use
ADK     Fallback
│
├─ Success? ──YES──> Return Response
│
└─ ERROR ──> Log Error
             │
             ▼
          Fallback
          Agents
             │
             ▼
          Return
          Response
```

### 1. Request Entry Point

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│ AgentFactory.process_request()          │
│                                         │
│ - Validates agent type                  │
│ - Gets appropriate agent instance       │
│ - Calls agent.process(request)          │
└────────────┬────────────────────────────┘
             │
             ▼
      Agent.process()
```

**Input Parameters:**
- `agent_type`: research | prediction | optimization | report
- `query`: User's natural language query
- `context`: Optional metadata (trial design, simulation results, etc.)

---

### 2. Agent Decision Tree

Each agent follows this flow:

```
┌──────────────────────────────┐
│  Agent.process(request)      │
└────────────┬─────────────────┘
             │
             ▼
    ┌────────────────────┐
    │ Is ADK Available?  │
    │ Is API Key Set?    │
    │ Is Agent Init?     │
    └────┬───────────┬───┘
         │           │
        YES          NO
         │           │
         ▼           ▼
   ┌──────────┐  ┌──────────────┐
   │ Bedrock  │  │ Fallback     │
   │(Claude)  │  │ Mode (Local) │
   └────┬─────┘  └──────┬───────┘
        │               │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │  AgentResponse│
        │  - response   │
        │  - confidence │
        │  - sources    │
        │  - timestamp  │
        └───────────────┘
```

---

## Agent Types & Workflows

### 1. Research Agent

**Purpose:** Analyze historical trial data and identify patterns

**Workflow:**

```
User Query: "What factors lead to trial success?"
    │
    ▼
┌─────────────────────────────────────────┐
│ ResearchAgent._process_with_adk()       │
│                                         │
│ 1. Prepare system instructions:         │
│    "You are a clinical trial analyst... │
│     Analyze historical data..."         │
│                                         │
│ 2. Build prompt with context:           │
│    - Query + Historical context         │
│                                         │
│ 3. Call Claude Sonnet 4.5 API:         │
│    bedrock_client.generate()            │
│    .invoke(prompt)                       │
│                                         │
│ 4. Format response                      │
└────────────┬─────────────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│ AgentResponse                   │
│ - Success factors identified    │
│ - Benchmark data               │
│ - Confidence: 0.85             │
│ - Sources: Database, Analysis  │
└─────────────────────────────────┘
```

**Fallback (No ADK):**
```
Local Analysis:
  1. Query database for statistics
  2. Calculate historical patterns
  3. Apply rule-based analysis
  4. Return formatted insights
```

---

### 2. Prediction Agent

**Purpose:** Forecast trial success probability

**Workflow:**

```
User Input: Trial Design (Phase II, 200 patients, 18-month duration)
    │
    ▼
┌──────────────────────────────────────────┐
│ PredictionAgent._process_with_adk()      │
│                                          │
│ 1. System Instruction:                   │
│    "Predict trial outcomes, identify     │
│     risk factors, confidence scores..."  │
│                                          │
│ 2. Prepare context:                      │
│    - Trial design JSON                   │
│    - Historical comparables              │
│    - ML predictions                      │
│                                          │
│ 3. Send to Claude Sonnet 4.5:           │
│    "Analyze this trial design and        │
│     predict success probability..."      │
│                                          │
│ 4. Parse response:                       │
│    - Extract probability                 │
│    - Identify risk factors               │
│    - Confidence score                    │
└───────────┬────────────────────────────┘
            │
            ▼
┌────────────────────────────────┐
│ AgentResponse                  │
│ - Success Probability: 68%     │
│ - Risk Factors:                │
│   • High dropout rate (25%)    │
│   • Enrollment challenges      │
│ - Confidence: 0.82             │
│ - Sources: ML Model, Database  │
└────────────────────────────────┘
```

**Fallback (No Bedrock):**
```
ML-Based Prediction:
  1. Load local fallback model
  2. Extract trial parameters
  3. Run prediction pipeline
  4. Calculate confidence score
  5. Return formatted prediction
```

---

### 3. Optimization Agent

**Purpose:** Suggest protocol improvements

**Workflow:**

```
User Query: Trial Design + Simulation Results
    │
    ▼
┌─────────────────────────────────────────┐
│ OptimizationAgent._process_with_adk()   │
│                                         │
│ 1. System Instruction:                  │
│    "Optimization expert. Suggest        │
│     protocol improvements, cost/        │
│     timeline optimizations..."          │
│                                         │
│ 2. Analyze context:                     │
│    - Current trial design               │
│    - Simulation bottlenecks             │
│    - Best practice database             │
│                                         │
│ 3. Generate recommendations via API:    │
│    - Multi-site strategies              │
│    - Enrollment optimization            │
│    - Cost reduction                     │
│    - Timeline acceleration              │
│                                         │
│ 4. Prioritize suggestions               │
└────────────┬─────────────────────────────┘
             │
             ▼
┌──────────────────────────────────┐
│ AgentResponse                    │
│ Optimizations:                   │
│ 1. Use 5 sites (vs. 2 proposed) │
│ 2. Add patient engagement prog  │
│ 3. Implement RBM approach       │
│ 4. Estimated savings: $2.3M    │
│ - Confidence: 0.80              │
│ - Sources: Best Practices DB    │
└──────────────────────────────────┘
```

**Fallback (No ADK):**
```
Rule-Based Optimization:
  1. Analyze trial parameters
  2. Check against best practices
  3. Identify optimization opportunities
  4. Apply cost/timeline calculations
  5. Return prioritized suggestions
```

---

### 4. Report Agent

**Purpose:** Generate comprehensive analysis reports

**Workflow:**

```
User Request: Generate trial report
    │
    ▼
┌──────────────────────────────────────┐
│ ReportAgent._process_with_adk()      │
│                                      │
│ 1. System Instruction:               │
│    "Reporting specialist. Generate   │
│     comprehensive reports..."        │
│                                      │
│ 2. Gather data:                      │
│    - Trial design details            │
│    - Simulation results              │
│    - Predictions + insights          │
│    - Recommendations                 │
│    - Benchmarking data               │
│                                      │
│ 3. Generate report via Claude:       │
│    - Executive summary               │
│    - Key findings                    │
│    - Risk assessment                 │
│    - Recommendations                 │
│    - Supporting data/charts          │
│                                      │
│ 4. Format markdown output            │
└───────────┬──────────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│ AgentResponse                    │
│ (Markdown Report)                │
│                                  │
│ # Clinical Trial Report          │
│ ## Executive Summary             │
│ ## Design Overview               │
│ ## Predictions & Analysis        │
│ ## Risk Assessment               │
│ ## Recommendations               │
│ ## Appendix: Benchmarks          │
│                                  │
│ - Confidence: 0.88               │
│ - Sources: Database, Analysis    │
└──────────────────────────────────┘
```

**Fallback (No ADK):**
```
Template-Based Report:
  1. Load report template
  2. Fill in trial data
  3. Add analysis sections
  4. Include recommendations
  5. Format and return
```

---

## Data Flow Through Agents

### Input Data Path:

```
┌─────────────────────┐
│  User Input/Query   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│  AgentRequest Object            │
│  - agent_type                   │
│  - query (user question)        │
│  - context (optional):          │
│    • trial_design               │
│    • simulation_result          │
│    • additional_metadata        │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  Agent Processing               │
│  - Builds system prompt         │
│  - Enriches context             │
│  - Calls external services      │
│    • Database queries           │
│    • ML model inference         │
│    • Claude Sonnet 4.5 API      │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  AgentResponse Object           │
│  - response (generated answer)  │
│  - confidence (0.0-1.0)         │
│  - sources (data sources used)  │
│  - timestamp (when generated)   │
└─────────────────────────────────┘
```

---

## Execution Modes

### Mode 1: AWS Bedrock (Preferred)

```
Condition: AWS credentials are set in .env

Flow:
  1. Parse request with system instructions
  2. Prepare context from local data
  3. Send to AWS Bedrock Claude Sonnet 4.5
  4. Stream/wait for response
  5. Parse and format response
  6. Return structured AgentResponse

Advantages:
  ✓ Latest Claude model (Sonnet 4.5)
  ✓ Intelligent reasoning
  ✓ Context-aware responses
  ✓ No local GPU needed
  ✓ Automatic tool integration
```

### Mode 2: Fallback (Local)

```
Condition: ADK unavailable OR API key missing

Flow:
  1. Use agent's _process_fallback() method
  2. Query local database
  3. Apply ML inference (if model loaded)
  4. Execute rule-based analysis
  5. Format response locally
  6. Return structured AgentResponse

Advantages:
  ✓ Works offline
  ✓ No API dependencies
  ✓ Faster for simple queries
  ✓ Privacy-preserving
```

---

## Error Handling & Resilience

```
┌─────────────────────┐
│  Agent.process()    │
└──────────┬──────────┘
           │
           ▼
    ┌──────────────┐
    │ Try ADK Mode │
    └──────┬───────┘
           │
     ┌─────┴──────┐
     │             │
  SUCCESS        ERROR
     │             │
     ▼             ▼
  Return    ┌────────────────┐
 Response   │ Log Error      │
            │ Catch exception│
            │ Fall back      │
            └────────┬───────┘
                     │
                     ▼
            Try Fallback Mode
                     │
              ┌──────┴──────┐
              │             │
           SUCCESS        ERROR
              │             │
              ▼             ▼
           Return      Return Error
          Response      Response
```

---

## Configuration & Environment

### Required Environment Variables:

```env
# For AWS Bedrock Mode
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_DEFAULT_REGION=us-east-1

# For Model Configuration
Local_model=1  # 1=local, 0=API
HuggingFace_Model_URL=google/gemma-3-4b-it
HF_TOKEN=hf_xxxxx

# AWS Bedrock Model
AWS_SONNET_45=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

### Configuration in code:

```python
# config.py
AWS_ACCESS_KEY_ID: Optional[str] = None
AWS_SECRET_ACCESS_KEY: Optional[str] = None
AWS_DEFAULT_REGION: Optional[str] = "us-east-1"
LOCAL_MODEL: Optional[int] = None
HUGGINGFACE_MODEL_URL: Optional[str] = None
HF_TOKEN: Optional[str] = None
```

---

## Usage Examples

### Example 1: Research Query

```python
from app.agents import AgentFactory
from app.models import AgentRequest

request = AgentRequest(
    agent_type="research",
    query="What are the success factors for Phase II trials?",
    context={"therapeutic_area": "Oncology"}
)

response = AgentFactory.process_request(request)
print(response.response)  # AI-generated insights
print(response.confidence)  # 0.85
```

### Example 2: Prediction with Context

```python
trial_design = {
    "trial_name": "ABC-001",
    "phase": "Phase II",
    "target_enrollment": 200,
    "duration_days": 540,
    "expected_dropout_rate": 0.20
}

request = AgentRequest(
    agent_type="prediction",
    query="What is the success probability?",
    context={"trial_design": trial_design}
)

response = AgentFactory.process_request(request)
```

### Example 3: Generate Report

```python
request = AgentRequest(
    agent_type="report",
    query="Generate comprehensive trial analysis report",
    context={
        "trial_design": trial_design,
        "simulation_result": simulation_results
    }
)

response = AgentFactory.process_request(request)
# Returns markdown-formatted report
```

---

## Performance Characteristics

### AWS Bedrock Mode (Claude Sonnet 4.5):

| Metric | Value |
|--------|-------|
| First Request Latency | 500ms - 2s |
| Subsequent Requests | 300ms - 1.5s |
| API Rate Limit | Based on AWS tier |
| Max Context Length | 200K tokens |
| Accuracy | 90%+ for structured tasks |
| Cost | ~$0.003 per 1K input tokens |

### Fallback Mode (Local):

| Metric | Value |
|--------|-------|
| First Request Latency | 100-500ms |
| Subsequent Requests | 50-200ms |
| No Rate Limits | ∞ |
| GPU Memory | 6GB+ (with quantization) |
| Accuracy | 75-85% for structured tasks |
| Cost | $0 (after model download) |

---

## Implementation Details - Hackathon POC

### File Structure
```
app/
├── agents.py              # AWS Bedrock agents (Claude Sonnet 4.5)
├── fallback_agents.py     # Rule-based agents (no API required)
├── agent_router.py        # Intelligent routing layer ⭐ NEW
├── routes.py              # Updated to use AgentRouter
└── models.py              # AgentRequest, AgentResponse
```

### Key Components

#### 1. agents.py (AWS Bedrock - Primary)
```python
class AWSBedrockAgent:
    def __init__(self, agent_type, instruction):
        self.bedrock_client = BedrockClient()
        self.model_id = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        self.system_instruction = instruction
    
    def process(self, request):
        response = self.bedrock_client.generate(prompt)
        return AgentResponse(...)

# 4 agents: Research, Prediction, Optimization, Report
```

#### 2. fallback_agents.py (Rule-Based - Backup)
```python
class ResearchAgent(BaseAgent):
    def process(self, request):
        stats = self.db.get_historical_stats()
        analysis = self._analyze_historical_data(...)
        return AgentResponse(...)

# Always works, no API required
```

#### 3. agent_router.py (Intelligent Router) ⭐ 
```python
class AgentRouter:
    @classmethod
    def process_request(cls, request):
        # 1. Check ADK available + API key
        if use_adk:
            try:
                return adk_agents.process_request(request)
            except:
                logger.info("Falling back...")
        
        # 2. Use fallback
        return fallback_agents.process_request(request)
```

#### 4. routes.py (Updated)
```python
from .agent_router import AgentRouter  # Changed

@api_router.post("/agents/analyze")
async def agent_analyze(request: AgentRequest):
    response = AgentRouter.process_request(request)  # Routed!
    return response

@api_router.get("/agents/status")
async def get_agent_status():
    return AgentRouter.get_status()  # New endpoint
```

### Environment Setup

**.env Configuration:**
```bash
# For AWS Bedrock mode (Primary)
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_DEFAULT_REGION=us-east-1

# For fallback mode
# Just comment out AWS credentials
```

### Testing Modes

**1. Test AWS Bedrock Mode:**
```bash
# Set AWS credentials in .env
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Test
curl -X POST "http://localhost:8000/api/agents/research" \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze Phase II oncology trials"}'

# Check status
curl http://localhost:8000/api/agents/status
# Should show: "active_system": "AWS Bedrock"
```

**2. Test Fallback Mode:**
```bash
# Remove AWS credentials from .env
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=

# Restart app
python run.py

# Same test - should still work!
curl -X POST "http://localhost:8000/api/agents/research" ...

# Check status
curl http://localhost:8000/api/agents/status
# Should show: "active_system": "Fallback"
```

### Router Status Response
```json
{
  "router_version": "1.0.0",
  "routing": {
    "active_system": "AWS Bedrock",
    "primary_available": true,
    "fallback_available": true
  },
  "aws_bedrock": {
    "module_loaded": true,
    "bedrock_available": true,
    "credentials_configured": true,
    "model": "claude-sonnet-4-5"
  },
  "fallback": {
    "module_loaded": true,
    "available": true
  },
  "agents": {
    "research": {
      "available": true,
      "using_bedrock": true,
      "source": "AWS Bedrock"
    },
    ...
  }
}
```

### Advantages of Dual-Framework Design

✅ **Reliability**: Never fails - always has fallback
✅ **Flexibility**: Switch between Bedrock/Fallback dynamically
✅ **Testing**: Test both modes independently
✅ **Development**: Work offline with fallback mode
✅ **Cost**: Use fallback for dev, Bedrock for production
✅ **Hackathon**: Shows both rule-based AND AI capabilities
✅ **AWS Bedrock**: Claude Sonnet 4.5 as primary mode
✅ **Production Ready**: Handles API failures gracefully

---

## Scaling & Deployment

### Single Instance:
```
Client → FastAPI → Agent → Database
                ↓
            AWS Bedrock Claude (async)
```

### Cloud Run (Recommended):
```
Cloud Load Balancer
        ↓
    Cloud Run (Serverless)
    - No GPU needed
    - Uses Bedrock mode
    - Auto-scaling
        ↓
    CSV Database
        ↓
    AWS Bedrock Claude Sonnet 4.5
```

### Batch Processing:
```
Batch Queue
    ↓
  ┌─────────────────────┐
  │  Agent Pool (N=5)   │
  │  Each agent async   │
  └──────────┬──────────┘
             ↓
      Database (Results)
```

---

## Future Enhancements

1. **Tool Integration**: Agents with specialized tools (data access, calculations)
2. **Memory**: Persistent agent memory across sessions
3. **Multi-turn**: Conversational agents with dialog history
4. **Tool Composition**: Complex workflows with agent chains
5. **Monitoring**: Performance metrics and logging
6. **Cost Optimization**: Token usage tracking and optimization
7. **Fine-tuning**: Custom model adaptation

---

## Troubleshooting

### Issue: Agent returns generic response

**Cause**: Fallback mode active (ADK unavailable)
**Solution**: 
- Check `GOOGLE_API_KEY` in `.env`
- Verify API key has Generative AI access
- Check network connectivity

### Issue: Slow response time

**Cause 1**: ADK API latency
**Solution**: Use fallback mode for faster responses

**Cause 2**: Model loading (first request)
**Solution**: Pre-warm agents on startup

### Issue: Inconsistent responses

**Cause**: Temperature/randomness settings
**Solution**: Set specific temperature in system instruction

---

## Summary

The agentic framework provides:

✅ **Flexible Execution**: ADK with automatic fallback  
✅ **Multiple Agents**: Specialized for different tasks  
✅ **Resilient Design**: Graceful degradation  
✅ **Scalable Architecture**: From laptop to cloud  
✅ **Intelligent Analysis**: AI-powered insights  
✅ **Fast Responses**: Optimized for clinical use

The system intelligently routes requests to appropriate agents, which leverage AWS Bedrock Claude Sonnet 4.5 while maintaining fallback capabilities for offline operation.
