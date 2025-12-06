"""
Clinical trial simulation engine with statistical modeling.
"""

import numpy as np
import uuid
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, date
import logging

from .models import (
    TrialDesign, Patient, PatientDemographics, Gender,
    AdverseEvent, AdverseEventSeverity, TrialOutcome,
    SimulationResult
)
from .config import get_settings
from .database import get_db

logger = logging.getLogger(__name__)
settings = get_settings()


class ClinicalTrialSimulator:
    """Simulates clinical trial execution and outcomes."""
    
    def __init__(self):
        self.db = get_db()
        self.rng = np.random.default_rng()
    
    def simulate_trial(
        self,
        trial_design: TrialDesign,
        seed: int = None
    ) -> SimulationResult:
        """
        Run a complete clinical trial simulation.
        
        Args:
            trial_design: Trial design parameters
            seed: Random seed for reproducibility
            
        Returns:
            SimulationResult with complete trial outcomes
        """
        logger.info("="*80)
        logger.info(f"Starting Clinical Trial Simulation")
        logger.info(f"Trial Name: {trial_design.trial_name}")
        logger.info(f"Phase: {trial_design.phase}")
        logger.info(f"Drug: {trial_design.drug_name}")
        logger.info(f"Target Patients: {trial_design.target_enrollment}")
        logger.info(f"Duration: {trial_design.duration_days} days")
        logger.info(f"Random Seed: {seed if seed else 'None (random)'}")
        logger.info("="*80)
        
        try:
            if seed is not None:
                self.rng = np.random.default_rng(seed)
            
            # Generate readable simulation ID from trial name
            # Convert trial name to lowercase, remove special chars, replace spaces with underscore
            trial_slug = re.sub(r'[^a-z0-9]+', '_', trial_design.trial_name.lower()).strip('_')
            # Keep only first 3-4 words to avoid too long IDs
            trial_slug_parts = trial_slug.split('_')[:4]
            trial_slug = '_'.join(trial_slug_parts)
            # Add 4-digit random number
            random_num = self.rng.integers(1000, 9999)
            simulation_id = f"{trial_slug}_{random_num}"
            logger.debug(f"Generated simulation ID: {simulation_id}")
            
            # Step 1: Generate patient cohort
            logger.info(f"Step 1/5: Generating patient cohort ({trial_design.target_enrollment} patients)...")
            patients = self._generate_patient_cohort(trial_design, simulation_id)
            logger.info(f"✓ Generated {len(patients)} patients")
            
            # Step 2: Simulate trial execution
            logger.info(f"Step 2/5: Simulating trial execution over {trial_design.duration_days} days...")
            completed_patients, dropout_patients = self._simulate_execution(
                patients, trial_design
            )
            logger.info(f"✓ Completed: {len(completed_patients)}, Dropouts: {len(dropout_patients)}")
            
            # Step 3: Generate adverse events
            logger.info(f"Step 3/5: Generating adverse events...")
            adverse_events = self._generate_adverse_events(
                completed_patients + dropout_patients,
                trial_design
            )
            logger.info(f"✓ Generated {len(adverse_events)} adverse events")
            
            # Step 4: Calculate outcomes
            logger.info(f"Step 4/5: Calculating trial outcomes...")
            outcome = self._calculate_outcomes(
                trial_design,
                completed_patients,
                dropout_patients,
                adverse_events
            )
            logger.info(f"✓ Primary endpoint met: {outcome.primary_endpoint_met}")
            
            # Step 5: Estimate costs
            logger.info(f"Step 5/5: Estimating costs...")
            estimated_cost = self._estimate_costs(trial_design, len(patients))
            logger.info(f"✓ Estimated cost: ${estimated_cost:,.2f}")
            
            # Step 6: Calculate success probability using ML
            success_prob = self._calculate_success_probability(trial_design, outcome)
            logger.debug(f"Success probability calculated: {success_prob:.3f}")
            
            # Calculate actual duration with realistic variability
            actual_duration = int(trial_design.duration_days * self.rng.uniform(0.9, 1.15))
            completion_date = date.today() + timedelta(days=actual_duration)
            
            # Build result
            result = SimulationResult(
                simulation_id=simulation_id,
                trial_id=trial_design.trial_id,  # Include trial_id from design
                trial_design=trial_design,
                patients_enrolled=len(patients),
                patients_completed=len(completed_patients),
                dropout_rate=len(dropout_patients) / len(patients),
                outcome=outcome,
                actual_duration_days=actual_duration,
                completion_date=completion_date,
                estimated_cost=estimated_cost,
                success_probability=success_prob,
                confidence_interval=(
                    max(0, success_prob - 0.15),
                    min(1, success_prob + 0.15)
                )
            )
            
            logger.info("="*80)
            logger.info(f"✓ Simulation Complete: {simulation_id}")
            logger.info(f"  Enrolled: {len(patients)} | Completed: {len(completed_patients)} | Dropouts: {len(dropout_patients)}")
            logger.info(f"  Success Probability: {success_prob:.1%}")
            logger.info(f"  Primary Endpoint: {'✓ MET' if outcome.primary_endpoint_met else '✗ NOT MET'}")
            logger.info(f"  Cost: ${estimated_cost:,.0f} | Duration: {actual_duration} days")
            logger.info("="*80)
            
            return result
            
        except Exception as e:
            logger.error("="*80)
            logger.error(f"❌ SIMULATION FAILED: {trial_design.trial_name}")
            logger.error(f"Error Type: {type(e).__name__}")
            logger.error(f"Error Message: {str(e)}")
            logger.exception("Full traceback:")
            logger.error("="*80)
            raise
    
    def _generate_patient_cohort(self, trial_design: TrialDesign, simulation_id: str) -> List[Patient]:
        """Generate synthetic patient cohort."""
        patients = []
        
        for i in range(trial_design.target_enrollment):
            # Generate demographics within inclusion criteria
            age = int(self.rng.integers(
                trial_design.inclusion_criteria.min_age,
                trial_design.inclusion_criteria.max_age + 1
            ))
            
            # Use Python's random.choice to avoid numpy type issues with enums
            import random
            gender = random.choice([Gender.MALE, Gender.FEMALE])
            
            # Generate realistic physical measurements
            if gender == Gender.MALE:
                weight = self.rng.normal(80, 15)
                height = self.rng.normal(175, 8)
            else:
                weight = self.rng.normal(65, 12)
                height = self.rng.normal(163, 7)
            
            weight = max(30, min(150, weight))
            height = max(140, min(200, height))
            
            # Generate comorbidities
            num_comorbidities = self.rng.poisson(0.5)
            comorbidities = []
            if num_comorbidities > 0:
                possible = ["Hypertension", "Diabetes Type 2", "Hyperlipidemia", "Asthma"]
                comorbidities = self.rng.choice(
                    possible,
                    size=min(num_comorbidities, len(possible)),
                    replace=False
                ).tolist()
            
            demographics = PatientDemographics(
                age=age,
                gender=gender,
                ethnicity=random.choice([
                    "Caucasian", "African American", "Asian", "Hispanic", "Other"
                ]),
                weight_kg=round(weight, 1),
                height_cm=round(height, 1),
                comorbidities=comorbidities
            )
            
            # Assign to treatment arm
            treatment_arm = random.choice(
                trial_design.treatment_arms + 
                ([trial_design.control_arm] if trial_design.control_arm else [])
            )
            
            patient = Patient(
                patient_id=f"PAT-{simulation_id[:8]}-{i:04d}",
                demographics=demographics,
                enrollment_date=date.today(),
                treatment_arm=treatment_arm
            )
            
            patients.append(patient)
        
        return patients
    
    def _simulate_execution(
        self,
        patients: List[Patient],
        trial_design: TrialDesign
    ) -> Tuple[List[Patient], List[Patient]]:
        """Simulate trial execution with dropouts."""
        completed = []
        dropouts = []
        
        # Base dropout probability
        base_dropout_rate = trial_design.expected_dropout_rate
        
        for patient in patients:
            # Calculate patient-specific dropout risk
            dropout_risk = base_dropout_rate
            
            # Age factor
            if patient.demographics.age > 65:
                dropout_risk *= 1.3
            elif patient.demographics.age < 25:
                dropout_risk *= 1.2
            
            # Comorbidity factor
            if len(patient.demographics.comorbidities) > 2:
                dropout_risk *= 1.4
            elif len(patient.demographics.comorbidities) > 0:
                dropout_risk *= 1.2
            
            # Determine if patient drops out
            if self.rng.random() < dropout_risk:
                # Random dropout day
                dropout_day = int(self.rng.integers(30, trial_design.duration_days))
                patient.dropout_date = patient.enrollment_date + timedelta(days=dropout_day)
                dropouts.append(patient)
            else:
                completed.append(patient)
        
        return completed, dropouts
    
    def _generate_adverse_events(
        self,
        patients: List[Patient],
        trial_design: TrialDesign
    ) -> List[AdverseEvent]:
        """Generate realistic adverse events."""
        adverse_events = []
        
        # Base AE rate depends on phase and therapeutic area
        phase_multipliers = {
            "Phase I": 0.4,
            "Phase II": 0.3,
            "Phase III": 0.25,
            "Phase IV": 0.2
        }
        
        area_multipliers = {
            "Oncology": 1.5,
            "Cardiology": 1.2,
            "Neurology": 1.1,
            "Infectious Disease": 1.0,
            "Immunology": 1.3,
            "Endocrinology": 0.9,
            "Gastroenterology": 1.0,
            "Respiratory": 1.1
        }
        
        base_ae_rate = 0.3  # 30% of patients experience at least one AE
        base_ae_rate *= phase_multipliers.get(trial_design.phase.value, 1.0)
        base_ae_rate *= area_multipliers.get(trial_design.therapeutic_area, 1.0)
        
        # Common adverse events by type
        ae_types = [
            "Nausea", "Fatigue", "Headache", "Diarrhea", "Rash",
            "Decreased Appetite", "Dizziness", "Insomnia",
            "Constipation", "Vomiting", "Fever", "Cough"
        ]
        
        for patient in patients:
            # Control arm typically has lower AE rate
            patient_ae_rate = base_ae_rate
            if trial_design.control_arm and patient.treatment_arm == trial_design.control_arm:
                patient_ae_rate *= 0.7
            
            # Number of AEs for this patient
            if self.rng.random() < patient_ae_rate:
                num_aes = self.rng.poisson(1.5) + 1
                
                for _ in range(num_aes):
                    # Severity distribution: Mild (60%), Moderate (30%), Severe (9%), Life-threatening (1%)
                    import random
                    severity_values = [
                        AdverseEventSeverity.MILD,
                        AdverseEventSeverity.MODERATE,
                        AdverseEventSeverity.SEVERE,
                        AdverseEventSeverity.LIFE_THREATENING
                    ]
                    severity = random.choices(
                        severity_values,
                        weights=[0.60, 0.30, 0.09, 0.01],
                        k=1
                    )[0]
                    
                    ae = AdverseEvent(
                        event_type=random.choice(ae_types),
                        severity=severity,
                        patient_id=patient.patient_id,
                        occurrence_day=int(self.rng.integers(1, trial_design.duration_days)),
                        resolved=self.rng.random() > 0.2  # 80% resolution rate
                    )
                    adverse_events.append(ae)
        
        return adverse_events
    
    def _calculate_outcomes(
        self,
        trial_design: TrialDesign,
        completed_patients: List[Patient],
        dropout_patients: List[Patient],
        adverse_events: List[AdverseEvent]
    ) -> TrialOutcome:
        """Calculate trial outcomes and success metrics."""
        
        total_patients = len(completed_patients) + len(dropout_patients)
        
        # Calculate safety score
        severe_aes = [ae for ae in adverse_events if ae.severity in [
            AdverseEventSeverity.SEVERE,
            AdverseEventSeverity.LIFE_THREATENING
        ]]
        
        safety_score = 1.0 - (len(severe_aes) / max(total_patients, 1)) * 0.5
        safety_score = max(0.3, min(1.0, safety_score))
        
        # Calculate efficacy score (influenced by expected success rate)
        base_efficacy = trial_design.expected_success_rate
        
        # Adjust based on completion rate
        completion_rate = len(completed_patients) / max(total_patients, 1)
        efficacy_adjustment = (completion_rate - 0.5) * 0.3
        
        efficacy_score = base_efficacy + efficacy_adjustment + self.rng.normal(0, 0.1)
        efficacy_score = max(0.2, min(1.0, efficacy_score))
        
        # Overall score combines efficacy and safety
        overall_score = (efficacy_score * 0.7) + (safety_score * 0.3)
        
        # Primary endpoint met if overall score is high enough
        primary_endpoint_met = overall_score >= settings.SUCCESS_THRESHOLD
        
        # Success determined by multiple factors
        success = (
            primary_endpoint_met and
            safety_score >= 0.6 and
            completion_rate >= 0.65
        )
        
        return TrialOutcome(
            success=success,
            primary_endpoint_met=primary_endpoint_met,
            dropout_count=len(dropout_patients),
            adverse_events=adverse_events,
            efficacy_score=round(efficacy_score, 3),
            safety_score=round(safety_score, 3),
            overall_score=round(overall_score, 3)
        )
    
    def _estimate_costs(self, trial_design: TrialDesign, num_patients: int) -> float:
        """Estimate total trial costs in USD."""
        
        # Base costs per phase
        phase_base_costs = {
            "Phase I": 1_500_000,
            "Phase II": 7_000_000,
            "Phase III": 20_000_000,
            "Phase IV": 10_000_000
        }
        
        base_cost = phase_base_costs.get(trial_design.phase.value, 5_000_000)
        
        # Per-patient costs
        per_patient_cost = 15_000
        
        # Duration-based costs (site maintenance, monitoring)
        monthly_overhead = 50_000
        months = trial_design.duration_days / 30
        
        # Therapeutic area multipliers
        area_multipliers = {
            "Oncology": 1.5,
            "Cardiology": 1.3,
            "Neurology": 1.4,
            "Infectious Disease": 1.1,
            "Immunology": 1.3,
            "Endocrinology": 1.0,
            "Gastroenterology": 1.1,
            "Respiratory": 1.2
        }
        
        multiplier = area_multipliers.get(trial_design.therapeutic_area, 1.0)
        
        total_cost = (
            base_cost +
            (per_patient_cost * num_patients) +
            (monthly_overhead * months)
        ) * multiplier
        
        return round(total_cost, 2)
    
    def _calculate_success_probability(
        self,
        trial_design: TrialDesign,
        outcome: TrialOutcome
    ) -> float:
        """Calculate success probability using historical data and ML predictions."""
        
        # Get historical success rates for similar trials
        historical_stats = self.db.get_historical_stats()
        base_success_rate = historical_stats.get("success_rate", 0.65)
        
        # Adjust based on phase
        phase_success_rates = {
            "Phase I": 0.70,
            "Phase II": 0.50,
            "Phase III": 0.60,
            "Phase IV": 0.75
        }
        phase_rate = phase_success_rates.get(trial_design.phase.value, base_success_rate)
        
        # Combine with simulated outcomes
        probability = (
            phase_rate * 0.4 +
            outcome.overall_score * 0.6
        )
        
        return round(probability, 3)


# Singleton instance
simulator = ClinicalTrialSimulator()


def get_simulator() -> ClinicalTrialSimulator:
    """Get simulator instance."""
    return simulator
