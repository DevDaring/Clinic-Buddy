"""
Database operations using CSV files for hackathon POC.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import uuid
from datetime import datetime, timedelta
import logging
import shutil

from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class CSVDatabase:
    """Simple CSV-based database for rapid prototyping."""
    
    def __init__(self):
        self.data_dir = Path(settings.DATA_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._initialize_csv_files()
    
    def _initialize_csv_files(self):
        """Initialize CSV files with sample data if they don't exist."""
        
        # Trials CSV
        trials_path = Path(settings.TRIALS_CSV)
        if not trials_path.exists():
            trials_data = self._generate_sample_trials()
            trials_data.to_csv(trials_path, index=False)
            logger.info(f"Created trials database: {trials_path}")
        
        # Drugs CSV
        drugs_path = Path(settings.DRUGS_CSV)
        if not drugs_path.exists():
            drugs_data = self._generate_sample_drugs()
            drugs_data.to_csv(drugs_path, index=False)
            logger.info(f"Created drugs database: {drugs_path}")
        
        # Patients CSV
        patients_path = Path(settings.PATIENTS_CSV)
        if not patients_path.exists():
            patients_data = self._generate_sample_patients()
            patients_data.to_csv(patients_path, index=False)
            logger.info(f"Created patients database: {patients_path}")
        
        # Outcomes CSV
        outcomes_path = Path(settings.OUTCOMES_CSV)
        if not outcomes_path.exists():
            outcomes_data = self._generate_sample_outcomes()
            outcomes_data.to_csv(outcomes_path, index=False)
            logger.info(f"Created outcomes database: {outcomes_path}")
    
    def _generate_sample_trials(self) -> pd.DataFrame:
        """Generate sample historical trial data."""
        np.random.seed(42)
        
        phases = ["Phase I", "Phase II", "Phase III", "Phase IV"]
        areas = ["Oncology", "Cardiology", "Neurology", "Immunology", "Endocrinology"]
        statuses = ["Completed", "Completed", "Completed", "Terminated"]
        
        trials = []
        for i in range(50):
            trial = {
                "trial_id": f"NCT{np.random.randint(10000000, 99999999)}",
                "trial_name": f"Study of Drug-{i+1} in {np.random.choice(areas)}",
                "phase": np.random.choice(phases),
                "therapeutic_area": np.random.choice(areas),
                "drug_name": f"Drug-{i+1}",
                "indication": f"Treatment condition {i+1}",
                "enrollment": np.random.randint(50, 500),
                "duration_days": np.random.randint(180, 1095),
                "status": np.random.choice(statuses),
                "success": np.random.choice([True, False], p=[0.65, 0.35]),
                "dropout_rate": round(np.random.uniform(0.05, 0.30), 2),
                "adverse_events": np.random.randint(0, 50),
                "cost_usd": np.random.randint(1000000, 10000000),
                "start_date": (datetime.now() - timedelta(days=np.random.randint(365, 1825))).strftime("%Y-%m-%d"),
                "completion_date": (datetime.now() - timedelta(days=np.random.randint(0, 365))).strftime("%Y-%m-%d")
            }
            trials.append(trial)
        
        return pd.DataFrame(trials)
    
    def _generate_sample_drugs(self) -> pd.DataFrame:
        """Generate sample drug/compound data."""
        np.random.seed(42)
        
        mechanisms = ["Kinase Inhibitor", "Antibody", "Small Molecule", "Checkpoint Inhibitor", "Enzyme Inhibitor"]
        
        drugs = []
        for i in range(30):
            drug = {
                "drug_id": f"DRUG-{1000+i}",
                "drug_name": f"Experimental-Drug-{i+1}",
                "mechanism": np.random.choice(mechanisms),
                "molecular_weight": round(np.random.uniform(200, 800), 1),
                "bioavailability": round(np.random.uniform(0.3, 0.95), 2),
                "half_life_hours": round(np.random.uniform(2, 48), 1),
                "target_indication": f"Disease condition {i+1}",
                "development_stage": np.random.choice(["Phase I", "Phase II", "Phase III"]),
                "manufacturer": f"Pharma Company {np.random.randint(1, 10)}"
            }
            drugs.append(drug)
        
        return pd.DataFrame(drugs)
    
    def _generate_sample_patients(self) -> pd.DataFrame:
        """Generate sample patient demographics data."""
        np.random.seed(42)
        
        genders = ["Male", "Female"]
        ethnicities = ["Caucasian", "African American", "Asian", "Hispanic", "Other"]
        
        patients = []
        for i in range(200):
            patient = {
                "patient_id": f"PAT-{10000+i}",
                "age": np.random.randint(18, 80),
                "gender": np.random.choice(genders),
                "ethnicity": np.random.choice(ethnicities),
                "weight_kg": round(np.random.uniform(50, 120), 1),
                "height_cm": round(np.random.uniform(150, 195), 1),
                "bmi": round(np.random.uniform(18, 35), 1),
                "comorbidities": np.random.choice(["None", "Hypertension", "Diabetes", "Multiple"], p=[0.4, 0.25, 0.25, 0.1]),
                "enrollment_date": (datetime.now() - timedelta(days=np.random.randint(0, 365))).strftime("%Y-%m-%d"),
                "trial_id": f"NCT{np.random.randint(10000000, 99999999)}"
            }
            patients.append(patient)
        
        return pd.DataFrame(patients)
    
    def _generate_sample_outcomes(self) -> pd.DataFrame:
        """Generate sample trial outcome data."""
        np.random.seed(42)
        
        outcomes = []
        for i in range(50):
            outcome = {
                "outcome_id": f"OUT-{1000+i}",
                "trial_id": f"NCT{np.random.randint(10000000, 99999999)}",
                "primary_endpoint_met": np.random.choice([True, False], p=[0.65, 0.35]),
                "efficacy_score": round(np.random.uniform(0.4, 0.95), 2),
                "safety_score": round(np.random.uniform(0.5, 0.98), 2),
                "overall_score": round(np.random.uniform(0.45, 0.92), 2),
                "dropout_count": np.random.randint(5, 50),
                "adverse_events_count": np.random.randint(0, 30),
                "serious_adverse_events": np.random.randint(0, 5),
                "completion_rate": round(np.random.uniform(0.70, 0.95), 2),
                "statistical_significance": np.random.choice([True, False], p=[0.7, 0.3])
            }
            outcomes.append(outcome)
        
        return pd.DataFrame(outcomes)
    
    # Query methods
    def get_trials(self, filters: Optional[Dict] = None) -> pd.DataFrame:
        """Get trials with optional filtering."""
        df = pd.read_csv(settings.TRIALS_CSV)
        
        if filters:
            for key, value in filters.items():
                if key in df.columns:
                    if isinstance(value, list):
                        df = df[df[key].isin(value)]
                    else:
                        df = df[df[key] == value]
        
        return df
    
    def get_trial_by_id(self, trial_id: str) -> Optional[Dict]:
        """Get a specific trial by ID."""
        df = pd.read_csv(settings.TRIALS_CSV)
        result = df[df['trial_id'] == trial_id]
        
        if not result.empty:
            return result.iloc[0].to_dict()
        return None
    
    def get_drugs(self, filters: Optional[Dict] = None) -> pd.DataFrame:
        """Get drugs with optional filtering."""
        df = pd.read_csv(settings.DRUGS_CSV)
        
        if filters:
            for key, value in filters.items():
                if key in df.columns:
                    df = df[df[key] == value]
        
        return df
    
    def get_patients(self, trial_id: Optional[str] = None) -> pd.DataFrame:
        """Get patients, optionally filtered by trial."""
        df = pd.read_csv(settings.PATIENTS_CSV)
        
        if trial_id:
            df = df[df['trial_id'] == trial_id]
        
        return df
    
    def get_outcomes(self, trial_id: Optional[str] = None) -> pd.DataFrame:
        """Get outcomes, optionally filtered by trial."""
        df = pd.read_csv(settings.OUTCOMES_CSV)
        
        if trial_id:
            df = df[df['trial_id'] == trial_id]
        
        return df
    
    def get_historical_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics from historical data."""
        trials_df = pd.read_csv(settings.TRIALS_CSV)
        outcomes_df = pd.read_csv(settings.OUTCOMES_CSV)
        
        stats = {
            "total_trials": len(trials_df),
            "success_rate": trials_df['success'].mean() if 'success' in trials_df.columns else 0.65,
            "avg_duration_days": trials_df['duration_days'].mean() if 'duration_days' in trials_df.columns else 365,
            "avg_enrollment": trials_df['enrollment'].mean() if 'enrollment' in trials_df.columns else 200,
            "avg_dropout_rate": trials_df['dropout_rate'].mean() if 'dropout_rate' in trials_df.columns else 0.15,
            "avg_cost": trials_df['cost_usd'].mean() if 'cost_usd' in trials_df.columns else 5000000,
            "phase_distribution": trials_df['phase'].value_counts().to_dict() if 'phase' in trials_df.columns else {},
            "area_distribution": trials_df['therapeutic_area'].value_counts().to_dict() if 'therapeutic_area' in trials_df.columns else {}
        }
        
        return stats
    
    def save_simulation_result(self, result: Dict[str, Any]) -> str:
        """Save a simulation result and return its ID."""
        result_id = str(uuid.uuid4())
        result['simulation_id'] = result_id
        result['created_at'] = datetime.now().isoformat()
        
        # Append to results file (create if doesn't exist)
        results_path = self.data_dir / "simulation_results.csv"
        
        # Flatten the result for CSV storage
        flat_result = {k: v for k, v in result.items() if not isinstance(v, (dict, list))}
        
        df = pd.DataFrame([flat_result])
        
        if results_path.exists():
            df.to_csv(results_path, mode='a', header=False, index=False)
        else:
            df.to_csv(results_path, index=False)
        
        return result_id
    
    def get_trial_by_id(self, trial_id: str) -> Optional[Dict]:
        """Get trial information by trial_id from trials.csv."""
        try:
            trials_path = Path(settings.TRIALS_CSV)
            if not trials_path.exists():
                logger.warning(f"Trials CSV not found: {trials_path}")
                return None
            
            df = pd.read_csv(trials_path)
            
            # Find trial by trial_id
            trial_row = df[df['trial_id'] == trial_id]
            
            if trial_row.empty:
                logger.warning(f"Trial not found: {trial_id}")
                return None
            
            # Convert to dict and replace NaN with None
            trial_dict = trial_row.iloc[0].to_dict()
            trial_dict = {k: (None if pd.isna(v) else v) for k, v in trial_dict.items()}
            
            return trial_dict
            
        except Exception as e:
            logger.error(f"Error getting trial by ID {trial_id}: {str(e)}")
            return None
    
    def get_similar_trials(self, therapeutic_area: str, phase: str, limit: int = 5) -> pd.DataFrame:
        """Find similar historical trials."""
        df = pd.read_csv(settings.TRIALS_CSV)
        
        # Filter by therapeutic area and phase
        similar = df[
            (df['therapeutic_area'] == therapeutic_area) &
            (df['phase'] == phase)
        ]
        
        return similar.head(limit)
    
    def get_user_simulations(self, user_id: str) -> List[Dict]:
        """Get all simulations created by a specific user."""
        try:
            results_path = Path(settings.SIMULATION_RESULTS_CSV)
            if not results_path.exists():
                return []
            
            df = pd.read_csv(results_path)
            
            # Filter by user_id if column exists
            if 'user_id' in df.columns:
                user_sims = df[df['user_id'] == user_id]
            else:
                # If no user_id column, return all (for backwards compatibility)
                user_sims = df
            
            # Replace NaN with None for JSON serialization
            user_sims = user_sims.replace({np.nan: None})
            
            # Convert to list of dicts
            return user_sims.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error getting user simulations: {str(e)}")
            return []
    
    def verify_simulation_owner(self, simulation_id: str, user_id: str) -> bool:
        """Verify that a user owns a simulation."""
        try:
            results_path = Path(settings.SIMULATION_RESULTS_CSV)
            if not results_path.exists():
                return False
            
            df = pd.read_csv(results_path)
            
            # Find the simulation
            sim = df[df['simulation_id'] == simulation_id]
            if sim.empty:
                return False
            
            # Check ownership if user_id column exists
            if 'user_id' in df.columns:
                return sim.iloc[0]['user_id'] == user_id
            
            # If no user_id column, allow access (backwards compatibility)
            return True
            
        except Exception as e:
            logger.error(f"Error verifying simulation owner: {str(e)}")
            return False
    
    def get_simulation_by_id(self, simulation_id: str) -> Optional[Dict]:
        """Get simulation data by ID."""
        try:
            results_path = Path(settings.SIMULATION_RESULTS_CSV)
            if not results_path.exists():
                logger.error(f"Simulation results file not found: {results_path}")
                return None
            
            df = pd.read_csv(results_path)
            sim = df[df['simulation_id'] == simulation_id]
            
            if sim.empty:
                logger.warning(f"Simulation not found: {simulation_id}")
                return None
            
            # Replace NaN with None for JSON serialization
            sim = sim.replace({np.nan: None})
            result = sim.iloc[0].to_dict()
            logger.info(f"Found simulation: {simulation_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting simulation: {str(e)}", exc_info=True)
            return None
    
    def update_simulation_data(self, simulation_id: str, field: str, new_value: Any) -> Tuple[bool, Optional[str]]:
        """
        Update a field in simulation data.
        Returns: (success, error_message)
        """
        import shutil
        
        try:
            results_path = Path(settings.SIMULATION_RESULTS_CSV)
            if not results_path.exists():
                error_msg = f"Simulation results file not found: {results_path}"
                logger.error(error_msg)
                return False, error_msg
            
            # Create backup before modification
            backup_path = results_path.with_suffix('.csv.bak')
            try:
                shutil.copy(results_path, backup_path)
                logger.debug(f"Created backup: {backup_path}")
            except Exception as backup_error:
                logger.warning(f"Could not create backup: {backup_error}")
            
            # Load CSV
            df = pd.read_csv(results_path)
            logger.info(f"Loaded simulation CSV with {len(df)} rows")
            
            # Find the simulation
            sim_idx = df[df['simulation_id'] == simulation_id].index
            if len(sim_idx) == 0:
                error_msg = f"Simulation {simulation_id} not found in CSV"
                logger.error(error_msg)
                logger.info(f"Available simulations: {df['simulation_id'].tolist()[:10]}")
                return False, error_msg
            
            # Check field exists
            idx = sim_idx[0]
            if field not in df.columns:
                error_msg = f"Field '{field}' not found in simulation data"
                logger.error(error_msg)
                logger.info(f"Available fields: {df.columns.tolist()}")
                return False, error_msg
            
            # Get old value for logging
            old_value = df.at[idx, field]
            logger.info(f"Updating {simulation_id}: {field} from {old_value} to {new_value}")
            
            # Convert new_value to appropriate type
            try:
                if df[field].dtype == 'int64':
                    new_value = int(new_value)
                elif df[field].dtype == 'float64':
                    new_value = float(new_value)
            except ValueError as ve:
                error_msg = f"Cannot convert '{new_value}' to {df[field].dtype}"
                logger.error(error_msg)
                return False, error_msg
            
            # Update the field
            df.at[idx, field] = new_value
            
            # Add updated_at timestamp if column exists
            if 'updated_at' in df.columns:
                df.at[idx, 'updated_at'] = datetime.now().isoformat()
            
            # Save back to CSV
            try:
                df.to_csv(results_path, index=False)
                logger.info(f"✅ Successfully updated {field} to {new_value} for {simulation_id}")
                logger.info(f"CSV saved to: {results_path}")
            except Exception as save_error:
                # Restore from backup
                if backup_path.exists():
                    shutil.copy(backup_path, results_path)
                    logger.warning(f"Restored from backup after save error: {save_error}")
                error_msg = f"Failed to save CSV: {str(save_error)}"
                return False, error_msg
            
            # Verify the update
            try:
                df_verify = pd.read_csv(results_path)
                verify_value = df_verify[df_verify['simulation_id'] == simulation_id].iloc[0][field]
                logger.info(f"Verification: {field} is now {verify_value} in CSV")
                
                # Remove backup after successful verification
                if backup_path.exists():
                    backup_path.unlink()
                    logger.debug("Backup removed after successful update")
                    
            except Exception as verify_error:
                logger.warning(f"Verification failed: {verify_error}")
            
            return True, None
            
        except Exception as e:
            error_msg = f"Unexpected error updating simulation: {str(e)}"
            logger.error(error_msg, exc_info=True)
            # Try to restore from backup
            if backup_path.exists():
                try:
                    shutil.copy(backup_path, results_path)
                    logger.info("Restored from backup after unexpected error")
                except:
                    pass
            return False, error_msg
    
    def save_chat_message(self, user_id: str, message: str, response: str, 
                          language: str, action_type: str, simulation_id: Optional[str] = None):
        """Save chat message to history."""
        try:
            chat_history_path = self.data_dir / "chat_history.csv"
            
            # Create new message
            new_message = {
                'chat_id': str(uuid.uuid4()),
                'user_id': user_id,
                'simulation_id': simulation_id or '',
                'timestamp': datetime.now().isoformat(),
                'message': message,
                'response': response,
                'language': language,
                'action_type': action_type
            }
            
            # Load or create DataFrame
            if chat_history_path.exists():
                df = pd.read_csv(chat_history_path)
                df = pd.concat([df, pd.DataFrame([new_message])], ignore_index=True)
            else:
                df = pd.DataFrame([new_message])
            
            # Save to CSV
            df.to_csv(chat_history_path, index=False)
            logger.info(f"Saved chat message for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error saving chat message: {str(e)}", exc_info=True)
    
    def get_chat_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get chat history for a user."""
        try:
            chat_history_path = self.data_dir / "chat_history.csv"
            
            if not chat_history_path.exists():
                return []
            
            df = pd.read_csv(chat_history_path)
            
            # Filter by user
            user_history = df[df['user_id'] == user_id]
            
            # Sort by timestamp descending and limit
            user_history = user_history.sort_values('timestamp', ascending=False).head(limit)
            
            # Reverse to show oldest first
            user_history = user_history.iloc[::-1]
            
            return user_history.to_dict('records')
            
        except Exception as e:
            logger.error(f"Error getting chat history: {str(e)}")
            return []
    
    def save_ai_analysis(self, simulation_id: str, analysis_data: Dict[str, Any]) -> bool:
        """
        Save AI analysis result to CSV for caching.
        
        Args:
            simulation_id: Simulation ID
            analysis_data: Dictionary with keys: response, confidence, agent_type, sources
            
        Returns:
            bool: True if saved successfully
        """
        try:
            ai_analysis_path = self.data_dir / "ai_analysis.csv"
            
            # Prepare data
            new_analysis = {
                'simulation_id': simulation_id,
                'analysis_response': analysis_data.get('response', ''),
                'confidence': analysis_data.get('confidence', 0.0),
                'agent_type': analysis_data.get('agent_type', 'unknown'),
                'timestamp': datetime.now().isoformat(),
                'sources': ','.join(analysis_data.get('sources', []))
            }
            
            # Load existing data
            if ai_analysis_path.exists():
                df = pd.read_csv(ai_analysis_path)
                
                # Remove old analysis for this simulation if exists
                df = df[df['simulation_id'] != simulation_id]
                
                # Add new analysis
                df = pd.concat([df, pd.DataFrame([new_analysis])], ignore_index=True)
            else:
                df = pd.DataFrame([new_analysis])
            
            # Save to CSV
            df.to_csv(ai_analysis_path, index=False)
            logger.info(f"✓ Saved AI analysis for simulation {simulation_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error saving AI analysis: {str(e)}", exc_info=True)
            return False
    
    def get_ai_analysis(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached AI analysis for a simulation.
        
        Args:
            simulation_id: Simulation ID
            
        Returns:
            Dictionary with analysis data or None if not found
        """
        try:
            ai_analysis_path = self.data_dir / "ai_analysis.csv"
            
            if not ai_analysis_path.exists():
                return None
            
            df = pd.read_csv(ai_analysis_path)
            
            # Find analysis for this simulation
            analysis = df[df['simulation_id'] == simulation_id]
            
            if analysis.empty:
                return None
            
            # Get the most recent (should be only one due to save logic)
            record = analysis.iloc[-1].to_dict()
            
            # Convert sources string back to list
            sources = record.get('sources', '')
            if sources:
                record['sources'] = sources.split(',')
            else:
                record['sources'] = []
            
            logger.info(f"✓ Found cached AI analysis for simulation {simulation_id}")
            return record
            
        except Exception as e:
            logger.error(f"Error getting AI analysis: {str(e)}")
            return None


# Singleton instance
db = CSVDatabase()


def get_db() -> CSVDatabase:
    """Get database instance."""
    return db

