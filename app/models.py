"""
Pydantic models and schemas for request/response validation.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from enum import Enum


class TrialPhase(str, Enum):
    PHASE_I = "Phase I"
    PHASE_II = "Phase II"
    PHASE_III = "Phase III"
    PHASE_IV = "Phase IV"


class TrialStatus(str, Enum):
    PLANNING = "Planning"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    TERMINATED = "Terminated"
    SUSPENDED = "Suspended"


class Gender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"


class AdverseEventSeverity(str, Enum):
    MILD = "Mild"
    MODERATE = "Moderate"
    SEVERE = "Severe"
    LIFE_THREATENING = "Life-threatening"


# Patient Models
class PatientDemographics(BaseModel):
    age: int = Field(ge=18, le=100, description="Patient age")
    gender: Gender
    ethnicity: Optional[str] = None
    weight_kg: float = Field(ge=30, le=300)
    height_cm: float = Field(ge=100, le=250)
    comorbidities: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "age": 45,
                "gender": "Female",
                "ethnicity": "Caucasian",
                "weight_kg": 70.5,
                "height_cm": 165,
                "comorbidities": ["Hypertension", "Diabetes Type 2"]
            }
        }


class Patient(BaseModel):
    patient_id: str
    demographics: PatientDemographics
    enrollment_date: date
    dropout_date: Optional[date] = None
    treatment_arm: str
    
    
# Trial Design Models
class InclusionCriteria(BaseModel):
    min_age: int = 18
    max_age: int = 75
    required_biomarkers: List[str] = Field(default_factory=list)
    excluded_conditions: List[str] = Field(default_factory=list)


class TrialDesign(BaseModel):
    trial_id: Optional[str] = None  # NCT ID or similar identifier
    trial_name: str = Field(min_length=3, max_length=200)
    phase: TrialPhase
    therapeutic_area: str
    drug_name: str
    indication: str
    
    # Patient criteria
    target_enrollment: int = Field(ge=10, le=10000)
    inclusion_criteria: InclusionCriteria
    
    # Trial parameters
    duration_days: int = Field(ge=30, le=3650)
    primary_endpoint: str
    secondary_endpoints: List[str] = Field(default_factory=list)
    
    # Arms
    treatment_arms: List[str] = Field(min_length=1)
    control_arm: Optional[str] = "Placebo"
    
    # Estimated parameters
    expected_dropout_rate: float = Field(ge=0, le=1, default=0.15)
    expected_success_rate: float = Field(ge=0, le=1, default=0.7)
    
    class Config:
        json_schema_extra = {
            "example": {
                "trial_name": "Phase II Trial of Drug X in Advanced Cancer",
                "phase": "Phase II",
                "therapeutic_area": "Oncology",
                "drug_name": "DrugX-101",
                "indication": "Advanced Non-Small Cell Lung Cancer",
                "target_enrollment": 200,
                "inclusion_criteria": {
                    "min_age": 18,
                    "max_age": 75,
                    "required_biomarkers": ["PD-L1 positive"],
                    "excluded_conditions": ["Active infection", "Pregnancy"]
                },
                "duration_days": 730,
                "primary_endpoint": "Progression-Free Survival",
                "secondary_endpoints": ["Overall Survival", "Quality of Life"],
                "treatment_arms": ["DrugX 100mg", "DrugX 200mg"],
                "control_arm": "Standard of Care"
            }
        }


# Simulation Models
class AdverseEvent(BaseModel):
    event_type: str
    severity: AdverseEventSeverity
    patient_id: str
    occurrence_day: int
    resolved: bool = False


class TrialOutcome(BaseModel):
    success: bool
    primary_endpoint_met: bool
    dropout_count: int
    adverse_events: List[AdverseEvent]
    efficacy_score: float = Field(ge=0, le=1)
    safety_score: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)


class SimulationRequest(BaseModel):
    trial_design: TrialDesign
    num_simulations: int = Field(ge=1, le=100, default=10)
    random_seed: Optional[int] = None
    use_ml_prediction: bool = True


class SimulationResult(BaseModel):
    simulation_id: str
    trial_id: Optional[str] = None  # Link to trials.csv
    trial_design: TrialDesign
    patients_enrolled: int
    patients_completed: int
    dropout_rate: float
    
    # Outcomes
    outcome: TrialOutcome
    
    # Timeline
    actual_duration_days: int
    completion_date: Optional[date] = None
    
    # Costs (in USD)
    estimated_cost: float
    
    # Predictions
    success_probability: float = Field(ge=0, le=1)
    confidence_interval: tuple = Field(default=(0.0, 1.0))
    
    # Agent insights
    research_insights: Optional[str] = None
    optimization_suggestions: Optional[List[str]] = None


# Agent Models
class AgentRequest(BaseModel):
    query: str = Field(min_length=10, max_length=5000)
    context: Optional[Dict[str, Any]] = None
    agent_type: str = Field(default="research")
    
    @validator('agent_type')
    def validate_agent_type(cls, v):
        valid_types = ['research', 'prediction', 'optimization', 'report']
        if v not in valid_types:
            raise ValueError(f'agent_type must be one of {valid_types}')
        return v


class AgentResponse(BaseModel):
    agent_type: str
    response: str
    confidence: float = Field(ge=0, le=1, default=0.8)
    sources: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


# Prediction Models
class PredictionRequest(BaseModel):
    trial_design: TrialDesign
    historical_data: Optional[Dict[str, Any]] = None
    prediction_type: str = "success_probability"


class PredictionResponse(BaseModel):
    success_probability: float = Field(ge=0, le=1)
    risk_factors: List[str]
    confidence_score: float = Field(ge=0, le=1)
    explanation: str
    comparable_trials: List[str] = Field(default_factory=list)


# Report Models
class TrialReport(BaseModel):
    report_id: str
    trial_name: str
    generated_at: datetime = Field(default_factory=datetime.now)
    
    # Executive Summary
    executive_summary: str
    
    # Key Findings
    success_probability: float
    risk_assessment: str
    cost_analysis: str
    timeline_projection: str
    
    # Detailed Sections
    patient_analysis: str
    efficacy_analysis: str
    safety_analysis: str
    competitive_landscape: str
    
    # Recommendations
    recommendations: List[str]
    optimization_opportunities: List[str]
    
    # Supporting Data
    charts_data: Optional[Dict[str, Any]] = None


# API Response Models
class HealthCheck(BaseModel):
    status: str = "healthy"
    version: str
    gpu_available: bool
    model_loaded: bool


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
