"""
API routes and endpoints for the Clinical Trial Simulator.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Form, File, UploadFile
from fastapi.responses import JSONResponse, Response
from typing import List, Optional, Dict, Any
import logging
import uuid
from datetime import datetime

from .models import (
    TrialDesign, SimulationRequest, SimulationResult,
    AgentRequest, AgentResponse, PredictionRequest, PredictionResponse,
    TrialReport, HealthCheck, ErrorResponse
)
from .simulator import get_simulator
from .agent_router import AgentRouter  # Changed from .agents import AgentFactory
from .ml_service import get_ml_service
from .database import get_db
from .config import get_settings
from .speech_service import get_speech_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Create routers
api_router = APIRouter(prefix="/api", tags=["api"])
health_router = APIRouter(tags=["health"])


# Health and Status Endpoints
@health_router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    ml_service = get_ml_service()
    model_info = ml_service.get_model_info()
    
    return HealthCheck(
        status="healthy",
        version=settings.APP_VERSION,
        gpu_available=model_info.get("gpu_available", False),
        model_loaded=model_info.get("model_loaded", False)
    )


@api_router.get("/status", response_model=Dict[str, Any])
async def get_status():
    """Get detailed system status."""
    ml_service = get_ml_service()
    db = get_db()
    
    model_info = ml_service.get_model_info()
    stats = db.get_historical_stats()
    
    return {
        "status": "operational",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "ml_service": model_info,
        "database": {
            "total_trials": stats.get("total_trials", 0),
            "connected": True
        },
        "timestamp": datetime.now().isoformat()
    }


# Trial Simulation Endpoints
@api_router.post("/trials/simulate", response_model=SimulationResult)
async def simulate_trial(request: SimulationRequest):
    """
    Run clinical trial simulation.
    
    Args:
        request: Simulation parameters including trial design
        
    Returns:
        SimulationResult with complete simulation outcomes
    """
    try:
        logger.info(f"API Request: POST /api/trials/simulate - {request.trial_design.trial_name}")
        logger.debug(f"Request details: Phase={request.trial_design.phase}, Drug={request.trial_design.drug_name}, Patients={request.trial_design.target_enrollment}")
        
        simulator = get_simulator()
        
        # Run simulation
        result = simulator.simulate_trial(
            trial_design=request.trial_design,
            seed=request.random_seed
        )
        
        # Use ML prediction if requested
        if request.use_ml_prediction:
            logger.debug("ML prediction requested")
            ml_service = get_ml_service()
            if ml_service.model_loaded:
                prediction = ml_service.predict_trial_success(request.trial_design)
                result.success_probability = prediction.success_probability
                logger.debug(f"ML prediction: {prediction.success_probability:.3f}")
        
        # Save result to database
        db = get_db()
        result_dict = result.dict()
        simulation_id = db.save_simulation_result(result_dict)
        
        # Add simulation_id to result for response
        result.simulation_id = simulation_id
        
        logger.info(f"✓ Simulation successful: {simulation_id}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Simulation failed: {type(e).__name__}: {str(e)}")
        logger.exception("Simulation error details:")
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")


@api_router.post("/trials/batch-simulate", response_model=List[SimulationResult])
async def batch_simulate_trials(
    designs: List[TrialDesign],
    num_simulations: int = Query(default=1, ge=1, le=10)
):
    """
    Run batch simulations for multiple trial designs.
    
    Args:
        designs: List of trial designs
        num_simulations: Number of simulations per design
        
    Returns:
        List of simulation results
    """
    try:
        simulator = get_simulator()
        results = []
        
        for design in designs:
            for i in range(num_simulations):
                result = simulator.simulate_trial(
                    trial_design=design,
                    seed=i
                )
                results.append(result)
        
        return results
        
    except Exception as e:
        logger.error(f"Batch simulation error: {e}")
        raise HTTPException(status_code=500, detail=f"Batch simulation failed: {str(e)}")


# Trial History Endpoints
@api_router.get("/trials/history")
async def get_trial_history(
    phase: Optional[str] = None,
    therapeutic_area: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Get historical trial data with optional filtering.
    
    Args:
        phase: Filter by trial phase
        therapeutic_area: Filter by therapeutic area
        limit: Maximum number of results
        
    Returns:
        List of historical trials
    """
    try:
        db = get_db()
        
        filters = {}
        if phase:
            filters['phase'] = phase
        if therapeutic_area:
            filters['therapeutic_area'] = therapeutic_area
        
        trials_df = db.get_trials(filters=filters)
        trials_df = trials_df.head(limit)
        
        return JSONResponse(content=trials_df.to_dict(orient='records'))
        
    except Exception as e:
        logger.error(f"Error fetching trial history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/trials/stats")
async def get_trial_statistics():
    """Get aggregated statistics from historical trials."""
    try:
        db = get_db()
        stats = db.get_historical_stats()
        return stats
        
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/trials/similar/{therapeutic_area}/{phase}")
async def get_similar_trials(
    therapeutic_area: str,
    phase: str,
    limit: int = Query(default=5, ge=1, le=20)
):
    """Find similar historical trials."""
    try:
        db = get_db()
        similar_trials = db.get_similar_trials(
            therapeutic_area=therapeutic_area,
            phase=phase,
            limit=limit
        )
        
        return JSONResponse(content=similar_trials.to_dict(orient='records'))
        
    except Exception as e:
        logger.error(f"Error finding similar trials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# AI Agent Endpoints
@api_router.post("/agents/analyze", response_model=AgentResponse)
async def agent_analyze(request: AgentRequest):
    """
    Process analysis request through AI agents.
    
    Args:
        request: Agent request with query and type
        
    Returns:
        AgentResponse with analysis results
    """
    try:
        logger.info(f"API Request: POST /api/agents/analyze")
        logger.info(f"Agent Type: {request.agent_type} | Query: {request.query[:100]}{'...' if len(request.query) > 100 else ''}")
        logger.debug(f"Context provided: {bool(request.context)}")
        
        response = AgentRouter.process_request(request)
        
        logger.info(f"✓ Agent response: {len(response.response)} chars, confidence={response.confidence:.2f}")
        logger.debug(f"Sources: {response.sources}")
        
        return response
        
    except ValueError as e:
        logger.warning(f"⚠ Invalid agent request: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Agent processing failed: {type(e).__name__}: {str(e)}")
        logger.exception("Agent error details:")
        raise HTTPException(status_code=500, detail=f"Agent failed: {str(e)}")


@api_router.post("/agents/research", response_model=AgentResponse)
async def research_agent(query: str, context: Optional[Dict[str, Any]] = None):
    """Research agent endpoint for historical data analysis."""
    request = AgentRequest(
        query=query,
        context=context,
        agent_type="research"
    )
    return await agent_analyze(request)


@api_router.post("/agents/predict", response_model=AgentResponse)
async def prediction_agent(query: str, context: Optional[Dict[str, Any]] = None):
    """Prediction agent endpoint for trial outcome forecasting."""
    request = AgentRequest(
        query=query,
        context=context,
        agent_type="prediction"
    )
    return await agent_analyze(request)


@api_router.post("/agents/optimize", response_model=AgentResponse)
async def optimization_agent(query: str, context: Optional[Dict[str, Any]] = None):
    """Optimization agent endpoint for protocol improvements."""
    request = AgentRequest(
        query=query,
        context=context,
        agent_type="optimization"
    )
    return await agent_analyze(request)


@api_router.post("/agents/report", response_model=AgentResponse)
async def report_agent(query: str = Form(...), context: Optional[str] = Form(None)):
    """
    Report agent endpoint for comprehensive analysis.
    
    Args:
        query: Question or analysis request
        context: JSON string with simulation data (optional)
    """
    logger.info("=" * 80)
    logger.info("📥 REPORT AGENT REQUEST RECEIVED")
    logger.info(f"Query length: {len(query)} chars")
    logger.info(f"Query preview: {query[:200]}")
    logger.info(f"Context provided: {context is not None}")
    if context:
        logger.info(f"Context length: {len(context)} chars")
        logger.info(f"Context preview: {context[:500]}")
    
    # Parse context if it's a JSON string
    context_dict = None
    if context:
        try:
            import json
            logger.info("🔍 Parsing context JSON...")
            context_dict = json.loads(context)
            logger.info(f"✅ Context parsed successfully")
            logger.info(f"Context keys: {list(context_dict.keys())}")
            if 'simulation_id' in context_dict:
                logger.info(f"Simulation ID: {context_dict.get('simulation_id')}")
            if 'results' in context_dict:
                results = context_dict.get('results', {})
                logger.info(f"Results keys: {list(results.keys())}")
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse context JSON: {str(e)}")
            logger.warning("Using context as raw string")
            context_dict = {"raw_context": context}
    
    logger.info("🤖 Creating AgentRequest...")
    request = AgentRequest(
        query=query,
        context=context_dict,
        agent_type="report"
    )
    logger.info(f"✓ AgentRequest created: type={request.agent_type}")
    logger.info("🔄 Calling agent_analyze...")
    
    try:
        response = await agent_analyze(request)
        logger.info(f"✅ REPORT AGENT COMPLETED: {len(response.response)} chars")
        
        # Save analysis to CSV if simulation_id is provided in context
        if context_dict and 'simulation_id' in context_dict:
            simulation_id = context_dict['simulation_id']
            db = get_db()
            
            analysis_data = {
                'response': response.response,
                'confidence': response.confidence,
                'agent_type': response.agent_type,
                'sources': response.sources
            }
            
            saved = db.save_ai_analysis(simulation_id, analysis_data)
            if saved:
                logger.info(f"💾 AI analysis cached for simulation {simulation_id}")
            else:
                logger.warning(f"⚠ Failed to cache AI analysis for {simulation_id}")
        
        logger.info("=" * 80)
        return response
    except Exception as e:
        logger.error(f"❌ REPORT AGENT FAILED: {type(e).__name__}: {str(e)}")
        logger.error("=" * 80)
        raise


@api_router.get("/agents/status")
async def get_agent_status():
    """
    Get agent routing status and configuration.
    
    Shows:
    - Which agent system is active (Google ADK vs Fallback)
    - Google ADK availability and API configuration
    - Per-agent routing information
    """
    try:
        status = AgentRouter.get_status()
        return status
    except Exception as e:
        logger.error(f"Error getting agent status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ML Prediction Endpoints
@api_router.post("/predict/outcome", response_model=PredictionResponse)
async def predict_outcome(request: PredictionRequest):
    """
    Predict trial outcome using ML model.
    
    Args:
        request: Prediction request with trial design
        
    Returns:
        PredictionResponse with success probability
    """
    try:
        ml_service = get_ml_service()
        
        if not ml_service.model_loaded:
            logger.warning("ML model not loaded, loading now...")
            ml_service.load_model()
        
        prediction = ml_service.predict_trial_success(
            trial_design=request.trial_design,
            historical_context=str(request.historical_data) if request.historical_data else None
        )
        
        return prediction
        
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@api_router.post("/predict/batch", response_model=List[PredictionResponse])
async def batch_predict(trial_designs: List[TrialDesign]):
    """Batch prediction for multiple trial designs."""
    try:
        ml_service = get_ml_service()
        
        if not ml_service.model_loaded:
            ml_service.load_model()
        
        predictions = ml_service.batch_predict(trial_designs)
        
        return predictions
        
    except Exception as e:
        logger.error(f"Batch prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Report Generation Endpoints
@api_router.post("/reports/generate")
async def generate_report(
    trial_design: TrialDesign,
    simulation_result: Optional[SimulationResult] = None,
    include_predictions: bool = True
):
    """
    Generate comprehensive trial report.
    
    Args:
        trial_design: Trial design parameters
        simulation_result: Optional simulation results
        include_predictions: Whether to include ML predictions
        
    Returns:
        Comprehensive trial report
    """
    try:
        report_id = str(uuid.uuid4())
        
        # Build context for report agent
        context = {
            "trial_design": trial_design,
            "simulation_result": simulation_result
        }
        
        # Get report from agent
        request = AgentRequest(
            query="Generate comprehensive trial analysis report",
            context=context,
            agent_type="report"
        )
        
        report_response = AgentRouter.process_request(request)
        
        # Add predictions if requested
        predictions = None
        if include_predictions:
            ml_service = get_ml_service()
            if ml_service.model_loaded:
                predictions = ml_service.predict_trial_success(trial_design)
        
        report_data = {
            "report_id": report_id,
            "trial_name": trial_design.trial_name,
            "generated_at": datetime.now().isoformat(),
            "content": report_response.response,
            "predictions": predictions.dict() if predictions else None,
            "simulation_summary": simulation_result.dict() if simulation_result else None
        }
        
        return report_data
        
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Model Management Endpoints
@api_router.post("/model/load")
async def load_model(
    background_tasks: BackgroundTasks,
    model_name: Optional[str] = None
):
    """Load ML model (can take time, runs in background)."""
    try:
        ml_service = get_ml_service()
        
        if ml_service.model_loaded:
            return {"status": "already_loaded", "model_info": ml_service.get_model_info()}
        
        # Load model in background
        def load_model_task():
            success = ml_service.load_model(model_name)
            logger.info(f"Model loading {'succeeded' if success else 'failed'}")
        
        background_tasks.add_task(load_model_task)
        
        return {
            "status": "loading",
            "message": "Model loading in background",
            "model_name": model_name or settings.MODEL_NAME
        }
        
    except Exception as e:
        logger.error(f"Model loading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/model/info")
async def get_model_info():
    """Get information about the loaded ML model."""
    try:
        ml_service = get_ml_service()
        return ml_service.get_model_info()
        
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/model/unload")
async def unload_model():
    """Unload ML model to free GPU memory."""
    try:
        ml_service = get_ml_service()
        ml_service.unload_model()
        
        return {"status": "unloaded", "message": "Model unloaded successfully"}
        
    except Exception as e:
        logger.error(f"Model unloading error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Data Management Endpoints
@api_router.get("/data/drugs")
async def get_drugs(mechanism: Optional[str] = None):
    """Get drug/compound database."""
    try:
        db = get_db()
        
        filters = {}
        if mechanism:
            filters['mechanism'] = mechanism
        
        drugs_df = db.get_drugs(filters=filters)
        
        return JSONResponse(content=drugs_df.to_dict(orient='records'))
        
    except Exception as e:
        logger.error(f"Error fetching drugs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/data/patients")
async def get_patients(trial_id: Optional[str] = None):
    """Get patient demographics data."""
    try:
        db = get_db()
        patients_df = db.get_patients(trial_id=trial_id)
        
        return JSONResponse(content=patients_df.to_dict(orient='records'))
        
    except Exception as e:
        logger.error(f"Error fetching patients: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Chat session storage (in-memory for now)
# In production, use Redis or database
chat_sessions = {}

def get_chat_service(user_id: str, username: str, db) -> 'ChatService':
    """Get or create chat service for user."""
    from .chatbot import ChatService
    
    if user_id not in chat_sessions:
        chat_sessions[user_id] = ChatService(user_id=user_id, username=username, database=db)
        logger.info(f"Created new chat session for user: {username}")
    
    return chat_sessions[user_id]


# Chat Endpoints
@api_router.post("/chat/message")
async def send_chat_message(
    message: str = Form(...),
    user_id: str = Form(...),
    username: str = Form(...),
    language_mode: str = Form(default='auto'),
    force_language: Optional[str] = Form(default=None)
):
    """
    Send a message to the chatbot and get a response.
    Supports English, Hindi, Bengali, and other languages.
    
    Args:
        message: User's message
        user_id: User ID
        username: Username
        language_mode: 'auto' for auto-detection, or specific language code
        force_language: If not 'auto', force bot to respond in this language
    """
    try:
        logger.info(f"Chat message from {username}: {message[:50]}...")
        logger.info(f"Language mode: {language_mode}, Force language: {force_language}")
        
        # Get or create chat service instance (maintains session)
        db = get_db()
        chat_service = get_chat_service(user_id=user_id, username=username, db=db)
        
        # Set language if forced (not auto mode)
        if language_mode != 'auto' and force_language:
            chat_service.language = force_language
            chat_service.force_language = True  # Mark as forced language mode
            logger.info(f"Forcing language: {force_language}")
        else:
            chat_service.force_language = False  # Auto-detect mode
        
        # Process message
        result = await chat_service.process_message(message)
        
        # If in manual language mode, ensure response is in that language
        if language_mode != 'auto' and force_language:
            result['language'] = force_language
        
        logger.info(f"Chat response generated: {result['action_type']} in language: {result['language']}")
        
        return JSONResponse(content={
            'success': True,
            'response': result['response'],
            'language': result['language'],
            'action_type': result['action_type'],
            'action_data': result['action_data'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                'success': False,
                'error': str(e),
                'message': 'Failed to process chat message'
            }
        )


@api_router.get("/chat/history")
async def get_chat_history(user_id: str, limit: int = 50):
    """Get chat history for a user."""
    try:
        db = get_db()
        history = db.get_chat_history(user_id=user_id, limit=limit)
        
        return JSONResponse(content={
            'success': True,
            'history': history,
            'count': len(history)
        })
        
    except Exception as e:
        logger.error(f"Error fetching chat history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/chat/user-simulations")
async def get_user_simulations_for_chat(user_id: str):
    """Get user's simulations for chat context with trial information."""
    try:
        db = get_db()
        simulations = db.get_user_simulations(user_id=user_id)
        
        # Enrich simulations with trial information
        enriched_simulations = []
        for sim in simulations:
            trial_info = None
            if 'trial_id' in sim and sim['trial_id']:
                trial_info = db.get_trial_by_id(sim['trial_id'])
            
            enriched_sim = {**sim, 'trial_info': trial_info}
            enriched_simulations.append(enriched_sim)
        
        return JSONResponse(content={
            'success': True,
            'simulations': enriched_simulations,
            'count': len(enriched_simulations)
        })
        
    except Exception as e:
        logger.error(f"Error fetching user simulations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/simulation/{simulation_id}")
async def get_simulation_details(simulation_id: str):
    """Get detailed simulation results by ID."""
    try:
        db = get_db()
        simulation = db.get_simulation_by_id(simulation_id)
        
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Clean the simulation data - convert any remaining NaN/infinity to None
        import math
        cleaned_simulation = {}
        for key, value in simulation.items():
            if isinstance(value, float):
                if math.isnan(value) or math.isinf(value):
                    cleaned_simulation[key] = None
                else:
                    cleaned_simulation[key] = value
            else:
                cleaned_simulation[key] = value
        
        # Fetch trial information if trial_id exists
        trial_info = None
        if 'trial_id' in cleaned_simulation and cleaned_simulation['trial_id']:
            trial_info = db.get_trial_by_id(cleaned_simulation['trial_id'])
        
        return JSONResponse(content={
            'success': True,
            'simulation': cleaned_simulation,
            'trial_info': trial_info  # Include trial information
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching simulation details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/simulation/{simulation_id}/ai-analysis")
async def get_simulation_ai_analysis(simulation_id: str):
    """
    Get cached AI analysis for a simulation.
    
    Returns:
        Cached analysis if exists, otherwise null
    """
    try:
        db = get_db()
        analysis = db.get_ai_analysis(simulation_id)
        
        if analysis:
            logger.info(f"📊 Returning cached AI analysis for {simulation_id}")
            return JSONResponse(content={
                'success': True,
                'has_analysis': True,
                'analysis': {
                    'response': analysis.get('analysis_response', ''),
                    'confidence': float(analysis.get('confidence', 0.0)),
                    'agent_type': analysis.get('agent_type', 'unknown'),
                    'timestamp': analysis.get('timestamp', ''),
                    'sources': analysis.get('sources', [])
                }
            })
        else:
            return JSONResponse(content={
                'success': True,
                'has_analysis': False,
                'analysis': None
            })
    
    except Exception as e:
        logger.error(f"Error fetching AI analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/simulation/{simulation_id}/update")
async def update_simulation(simulation_id: str, update_data: dict):
    """Update simulation data."""
    try:
        db = get_db()
        
        # Verify simulation exists
        simulation = db.get_simulation_by_id(simulation_id)
        if not simulation:
            raise HTTPException(status_code=404, detail="Simulation not found")
        
        # Update each field individually
        updated_fields = []
        for field, value in update_data.items():
            try:
                success = db.update_simulation_data(simulation_id, field, value)
                if success:
                    updated_fields.append(field)
                    logger.info(f"Updated {simulation_id}: {field} = {value}")
            except Exception as field_error:
                logger.error(f"Error updating {field}: {str(field_error)}")
                # Continue with other fields
        
        if not updated_fields:
            raise HTTPException(status_code=500, detail="No fields were updated")
        
        return JSONResponse(content={
            'success': True,
            'message': f'Successfully updated {len(updated_fields)} fields',
            'updated_fields': updated_fields
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating simulation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Voice Input/Output Endpoints
@api_router.post("/chat/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    language: str = Form(default='en')
):
    """
    Transcribe audio to text only (no chatbot processing).
    
    Args:
        audio: Audio file (WebM/Opus format from browser)
        language: Language code ('en', 'hi', 'bn')
        
    Returns:
        JSON with transcribed text
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🎙️ TRANSCRIBE REQUEST RECEIVED")
        logger.info(f"   Language: {language}")
        logger.info(f"   Audio filename: {audio.filename}")
        
        # Get speech service
        speech_service = get_speech_service()
        
        if not speech_service.is_available():
            logger.error("❌ Speech service not available!")
            raise HTTPException(status_code=503, detail="Speech service not available")
        
        # Read audio content
        audio_content = await audio.read()
        logger.info(f"✓ Received audio: {len(audio_content)} bytes")
        
        if len(audio_content) == 0:
            logger.error("❌ Audio content is empty!")
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Transcribe audio to text
        logger.info(f"🎯 Transcribing audio (language: {language})...")
        transcribed_text, transcribe_error = speech_service.transcribe_audio(
            audio_content, 
            language
        )
        
        if transcribe_error:
            logger.error(f"❌ Transcription error: {transcribe_error}")
            raise HTTPException(status_code=400, detail=f"Transcription failed: {transcribe_error}")
        
        if not transcribed_text:
            logger.warning("⚠️ No speech detected in audio")
            raise HTTPException(status_code=400, detail="No speech detected in audio")
        
        logger.info(f"✅ Transcription successful: '{transcribed_text}'")
        logger.info("=" * 80)
        
        return JSONResponse(content={
            'success': True,
            'text': transcribed_text,
            'language': language
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Transcription error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/chat/voice-input")
async def voice_input(
    audio: UploadFile = File(...),
    language: str = Form(default='en'),
    user_id: str = Form(...),
    username: str = Form(...)
):
    """
    Process voice input: transcribe audio, get chatbot response, and synthesize speech.
    
    Args:
        audio: Audio file (WebM/Opus format from browser)
        language: Language code ('en', 'hi', 'bn')
        user_id: User ID for chat context
        username: Username for chat context
        
    Returns:
        JSON with transcribed text, chatbot response text, and audio URL
    """
    try:
        logger.info("=" * 80)
        logger.info(f"🎤 VOICE INPUT REQUEST RECEIVED")
        logger.info(f"   User: {username}")
        logger.info(f"   User ID: {user_id}")
        logger.info(f"   Language: {language}")
        logger.info(f"   Audio filename: {audio.filename}")
        logger.info(f"   Audio content type: {audio.content_type}")
        
        # Get speech service
        logger.info("📡 Getting speech service...")
        speech_service = get_speech_service()
        
        logger.info(f"   Speech service available: {speech_service.is_available()}")
        if not speech_service.is_available():
            logger.error("❌ Speech service not available!")
            raise HTTPException(status_code=503, detail="Speech service not available")
        
        # Read audio content
        logger.info("📥 Reading audio content...")
        audio_content = await audio.read()
        logger.info(f"✓ Received audio: {len(audio_content)} bytes")
        
        if len(audio_content) == 0:
            logger.error("❌ Audio content is empty!")
            raise HTTPException(status_code=400, detail="Audio file is empty")
        
        # Transcribe audio to text
        logger.info(f"🎯 Starting transcription (language: {language})...")
        transcribed_text, transcribe_error = speech_service.transcribe_audio(
            audio_content, 
            language
        )
        
        if transcribe_error:
            logger.error(f"❌ Transcription error: {transcribe_error}")
            raise HTTPException(status_code=400, detail=f"Transcription failed: {transcribe_error}")
        
        if not transcribed_text:
            logger.warning("⚠️ No speech detected in audio")
            raise HTTPException(status_code=400, detail="No speech detected in audio")
        
        logger.info(f"✓ Transcription successful: '{transcribed_text}'")
        logger.info(f"   Transcription length: {len(transcribed_text)} characters")
        
        # Get chatbot response using existing chat session
        logger.info("🤖 Processing through chatbot...")
        from .chatbot import ChatService
        db = get_db()
        
        # Get or create chat session (using same logic as chat message endpoint)
        if user_id not in chat_sessions:
            logger.info(f"   Creating new chat session for user {user_id}")
            chat_sessions[user_id] = ChatService(user_id, username, db)
        else:
            logger.info(f"   Using existing chat session for user {user_id}")
        
        chat_service = chat_sessions[user_id]
        
        # Update language if changed
        if chat_service.language != language:
            logger.info(f"   Updating language from {chat_service.language} to {language}")
            chat_service.language = language
        
        # Process the transcribed text through chatbot
        logger.info(f"   Sending to chatbot: '{transcribed_text}'")
        response = await chat_service.process_message(transcribed_text)
        response_text = response.get('message', 'Sorry, I could not process your request.')
        
        logger.info(f"✓ Chatbot response received: '{response_text[:100]}...'")
        logger.info(f"   Response length: {len(response_text)} characters")
        
        # Synthesize speech from response
        logger.info(f"🔊 Synthesizing speech (language: {language})...")
        audio_bytes, synthesis_error = speech_service.synthesize_speech(
            response_text,
            language
        )
        
        if synthesis_error:
            # Return text response even if TTS fails
            logger.warning(f"⚠️ TTS failed but returning text: {synthesis_error}")
            return JSONResponse(content={
                'success': True,
                'transcribed_text': transcribed_text,
                'response_text': response_text,
                'audio_available': False,
                'error': synthesis_error
            })
        
        logger.info(f"✓ Speech synthesis successful: {len(audio_bytes)} bytes")
        
        # Encode audio as base64 for transmission
        logger.info("📦 Encoding audio as base64...")
        import base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        logger.info(f"✓ Base64 encoding complete: {len(audio_base64)} characters")
        
        logger.info("✅ Voice processing complete - sending response")
        logger.info("=" * 80)
        
        return JSONResponse(content={
            'success': True,
            'transcribed_text': transcribed_text,
            'response_text': response_text,
            'audio_base64': audio_base64,
            'audio_available': True,
            'language': language
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ VOICE INPUT ERROR: {str(e)}")
        logger.exception("Full traceback:")
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/chat/text-to-speech")
async def text_to_speech(
    text: str = Form(...),
    language: str = Form(default='en')
):
    """
    Convert text to speech.
    
    Args:
        text: Text to convert to speech
        language: Language code ('en', 'hi', 'bn')
        
    Returns:
        Audio file (MP3 format)
    """
    try:
        logger.info(f"TTS request: {len(text)} chars, language={language}")
        
        # Get speech service
        speech_service = get_speech_service()
        if not speech_service.is_available():
            raise HTTPException(status_code=503, detail="Speech service not available")
        
        # Synthesize speech
        audio_bytes, error = speech_service.synthesize_speech(text, language)
        
        if error:
            raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {error}")
        
        # Return audio as MP3
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Include routers
def get_routers():
    """Get all routers for inclusion in main app."""
    return [health_router, api_router]
