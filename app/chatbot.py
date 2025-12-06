"""
Multilingual Chat Service for Clinical Trial Simulator
Supports conversation, simulation updates, and data translation
Text generation powered by AWS Bedrock (Claude Sonnet 4.5)
Voice services use Google Cloud Speech APIs
"""

import os
import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

# AWS Bedrock for text generation
from .aws_bedrock_client import get_bedrock_client, BOTO3_AVAILABLE
from .config import get_settings
from .database import CSVDatabase

logger = logging.getLogger(__name__)
settings = get_settings()

# Field name aliases for natural language to CSV column mapping
FIELD_ALIASES = {
    # Patients enrolled
    'patient': 'patients_enrolled',
    'patients': 'patients_enrolled',
    'patient count': 'patients_enrolled',
    'patient number': 'patients_enrolled',
    'patient enrolled': 'patients_enrolled',  # Added singular form
    'patients enrolled': 'patients_enrolled',
    'enrollment': 'patients_enrolled',
    'enrolled': 'patients_enrolled',
    'number of patients': 'patients_enrolled',
    
    # Patients completed
    'completed': 'patients_completed',
    'patients completed': 'patients_completed',
    'completion': 'patients_completed',
    'finished': 'patients_completed',
    
    # Dropout rate
    'dropout': 'dropout_rate',
    'dropout rate': 'dropout_rate',
    'dropouts': 'dropout_rate',
    'attrition': 'dropout_rate',
    'attrition rate': 'dropout_rate',
    
    # Cost
    'cost': 'estimated_cost',
    'estimated cost': 'estimated_cost',
    'budget': 'estimated_cost',
    'expense': 'estimated_cost',
    'price': 'estimated_cost',
    
    # Duration
    'duration': 'actual_duration_days',
    'days': 'actual_duration_days',
    'timeline': 'actual_duration_days',
    'trial duration': 'actual_duration_days',
    'study duration': 'actual_duration_days',
    
    # Success probability
    'success': 'success_probability',
    'success rate': 'success_probability',
    'success probability': 'success_probability',
    'probability': 'success_probability',
}


class ChatService:
    """
    Multilingual chatbot service powered by AWS Bedrock (Claude Sonnet 4.5).
    Supports English, Hindi, Bengali, and other languages.
    Text generation uses AWS Bedrock, voice services use Google Cloud.
    """
    
    def __init__(self, user_id: str, username: str, database: CSVDatabase):
        self.user_id = user_id
        self.username = username
        self.db = database
        self.context = []
        self.language = None
        self.force_language = False  # Track if language is manually forced
        self.pending_action = None
        self.conversation_history = []
        self.current_simulation_id = None  # Track current simulation being discussed
        
        # Initialize AWS Bedrock client for text generation
        self.bedrock_client = get_bedrock_client()
        
        # Check if AWS Bedrock is available
        if not self.bedrock_client.is_available:
            error_msg = "AWS Bedrock client not available. Please check AWS credentials in .env file (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION)."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info(f"✅ Chat service initialized with AWS Bedrock for user: {self.username}")
    
    def _call_bedrock_api(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """
        Call AWS Bedrock API for text generation using Claude Sonnet 4.5.
        Returns the response text.
        """
        try:
            logger.info(f"Calling AWS Bedrock API for user {self.username}")
            response = self.bedrock_client.generate(
                prompt=prompt,
                model_name="claude-4.5-sonnet",
                max_tokens=2048,
                temperature=settings.TEMPERATURE,
                system_instruction=system_instruction
            )
            logger.info(f"✅ AWS Bedrock response received: {len(response)} chars")
            return response
        except Exception as e:
            logger.error(f"❌ AWS Bedrock API call failed: {str(e)[:200]}")
            raise Exception(f"AWS Bedrock API failed: {str(e)}")
    
    def _get_system_prompt(self, user_simulations: List[Dict]) -> str:
        """Generate system prompt with user's simulation context."""
        
        # Language name mapping for forced language responses
        language_names = {
            'en': 'English',
            'hi': 'हिंदी (Hindi)',
            'bn': 'বাংলা (Bengali)',
            'es': 'Español (Spanish)',
            'fr': 'Français (French)',
            'de': 'Deutsch (German)',
            'zh': '中文 (Chinese)',
            'ja': '日本語 (Japanese)',
            'ko': '한국어 (Korean)'
        }
        
        sim_list = "\n".join([
            f"- ID: {sim['simulation_id']}, "
            f"Patients Enrolled: {sim.get('patients_enrolled', 'N/A')}, "
            f"Patients Completed: {sim.get('patients_completed', 'N/A')}, "
            f"Success Probability: {sim.get('success_probability', 'N/A')}, "
            f"Cost: ${sim.get('estimated_cost', 'N/A')}"
            for sim in user_simulations
        ])
        
        # Add current simulation context if available
        current_context = ""
        if self.current_simulation_id:
            current_context = f"\n\n**CURRENT SIMULATION IN DISCUSSION:** {self.current_simulation_id}\n(User is currently asking about this simulation. Use it as default when they say 'this simulation', 'it', or don't specify which one.)"
        
        # Check if language is forced (manually selected by user)
        language_instruction = "ALWAYS respond in the SAME LANGUAGE the user uses"
        if self.language and hasattr(self, 'force_language') and self.force_language:
            lang_name = language_names.get(self.language, self.language)
            language_instruction = f"⚠️ CRITICAL: User has MANUALLY selected {lang_name} language. You MUST respond ONLY in {lang_name}, regardless of what language the user's input is in. This is a forced language mode."
        
        return f"""You are a multilingual AI assistant for a Clinical Trial Simulation platform.

**User Information:**
- Username: {self.username}
- User ID: {self.user_id}
- Language: {self.language or 'Auto-detect from user message'}

**User's Simulations:**
{sim_list if sim_list else "No simulations yet"}{current_context}

**Your Capabilities:**
1. Answer questions about clinical trials and simulations
2. Help users view their simulation data
3. Assist with updating INPUT parameters (patient count, drug dosage, trial duration, etc.)
4. Translate simulation descriptions and data to different languages
5. Explain simulation results and statistics

**Important Rules:**
1. {language_instruction}
2. For data updates, show: Field name, Current value, New value
3. ALWAYS ask for confirmation before making any changes
4. Users can ONLY update INPUT fields, NOT output/results
5. After confirming update, trigger re-simulation automatically
6. Be helpful, friendly, and professional
7. If unsure, ask clarifying questions
8. Use simple, clean formatting - avoid excessive asterisks and markdown
9. Be concise and direct in responses

**Formatting Guidelines:**
- Use bullet points with simple dashes (-)
- Avoid bold (**) and italic (*) unless absolutely necessary
- Use emojis sparingly (only for status indicators like ✓, ❌, 📝)
- Keep responses clean and readable

**Update Format:**
When user wants to update, respond with:
```
📝 Update Request:
- Simulation ID: [ID]
- Field: [field_name]
- Current Value: [old_value]
- New Value: [new_value]

Reply with 'YES' or 'CONFIRM' to proceed, or 'NO' or 'CANCEL' to abort.
```

**Translation Format:**
When translating, show original and translated side-by-side.

Remember: Be conversational, helpful, and use clean formatting!"""
    
    async def process_message(self, message: str) -> Dict[str, Any]:
        """
        Process user message and generate response.
        
        Returns:
            {
                'response': str,
                'language': str,
                'action_type': str,  # 'chat', 'update_request', 'confirmation', 'translation'
                'action_data': dict or None
            }
        """
        try:
            logger.info("="*70)
            logger.info(f"🔵 PROCESSING MESSAGE from {self.username}")
            logger.info(f"   Message: {message[:100]}...")
            logger.info(f"   ChatService instance ID: {id(self)}")
            logger.info(f"   Pending action exists: {self.pending_action is not None}")
            if self.pending_action:
                logger.info(f"   Pending action type: {self.pending_action.get('type')}")
                logger.info(f"   Pending action details: {self.pending_action}")
            logger.info("="*70)
            
            # Detect language if first message
            if not self.language:
                self.language = self._detect_language(message)
                logger.info(f"Detected language: {self.language}")
            
            # Extract and track simulation ID mentioned in message
            sim_id_in_message = self._extract_simulation_id(message)
            if sim_id_in_message:
                self.current_simulation_id = sim_id_in_message
                logger.info(f"Tracking simulation: {sim_id_in_message}")
            
            # Check if this is a confirmation response
            logger.info(f"🔍 Checking confirmation: pending_action={self.pending_action is not None}, is_confirmation={self._is_confirmation(message)}")
            if self.pending_action and self._is_confirmation(message):
                logger.info("✅ CONFIRMATION DETECTED - Calling _handle_confirmation()")
                return await self._handle_confirmation(message)
            
            # Check for update intent
            logger.info(f"🔍 Checking update intent...")
            update_intent = self._parse_update_intent(message)
            if update_intent:
                logger.info(f"✅ UPDATE INTENT DETECTED: {update_intent}")
                return await self._handle_update_request(update_intent)
            
            # Check for translation request
            translation_intent = self._parse_translation_intent(message)
            if translation_intent:
                return await self._handle_translation_request(translation_intent)
            
            # Regular conversation
            return await self._handle_chat(message)
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {
                'response': f"Sorry, I encountered an error: {str(e)}",
                'language': self.language or 'en',
                'action_type': 'error',
                'action_data': None
            }
    
    def _extract_simulation_id(self, message: str) -> Optional[str]:
        """Extract simulation ID from message if mentioned."""
        # Get user's simulations
        user_sims = self.db.get_user_simulations(self.user_id)
        
        # Check if any simulation ID is mentioned in the message
        for sim in user_sims:
            sim_id = sim['simulation_id']
            if sim_id.lower() in message.lower():
                return sim_id
        
        return None
    
    def _normalize_field_name(self, field_name: str) -> Tuple[Optional[str], List[str]]:
        """
        Normalize field name using aliases dictionary.
        Returns: (normalized_field, suggestions) where suggestions are similar fields if no exact match.
        """
        field_lower = field_name.lower().strip()
        
        # Direct match in aliases
        if field_lower in FIELD_ALIASES:
            normalized = FIELD_ALIASES[field_lower]
            logger.debug(f"Field normalized: '{field_name}' → '{normalized}'")
            return normalized, []
        
        # Check if it's already a valid CSV column name
        sample_sim = self.db.get_user_simulations(self.user_id)
        if sample_sim:
            valid_fields = list(sample_sim[0].keys())
            if field_lower in [f.lower() for f in valid_fields]:
                # Find the actual field name (preserve case)
                for f in valid_fields:
                    if f.lower() == field_lower:
                        logger.debug(f"Field already valid: '{field_name}' → '{f}'")
                        return f, []
        
        # No match found - find similar suggestions
        suggestions = []
        for alias, real_field in FIELD_ALIASES.items():
            if field_lower in alias or alias in field_lower:
                if real_field not in suggestions:
                    suggestions.append(real_field)
        
        logger.warning(f"Field '{field_name}' not recognized. Suggestions: {suggestions}")
        return None, suggestions[:3]  # Return top 3 suggestions
    
    def _detect_language(self, message: str) -> str:
        """Detect language from message using simple heuristics."""
        
        # Simple detection based on character sets
        if any('\u0900' <= char <= '\u097F' for char in message):
            return 'hi'  # Hindi (Devanagari script)
        elif any('\u0980' <= char <= '\u09FF' for char in message):
            return 'bn'  # Bengali
        else:
            return 'en'  # Default to English
    
    def _is_confirmation(self, message: str) -> bool:
        """Check if message is a confirmation (yes/no) - accepts many variations."""
        msg_lower = message.lower().strip()
        
        # Positive confirmations - English (expanded)
        yes_keywords = [
            'yes', 'y', 'yeah', 'yup', 'yep', 'sure', 'ok', 'okay', 
            'confirm', 'proceed', 'go ahead', 'do it', 'affirmative',
            'correct', 'right', 'true', 'accept', 'agree', 'approved'
        ]
        
        # Negative confirmations - English (expanded)
        no_keywords = [
            'no', 'n', 'nah', 'nope', 'never', 'cancel', 'abort', 
            'stop', 'dont', "don't", 'negative', 'reject', 'decline',
            'wrong', 'false', 'disagree', 'denied'
        ]
        
        # Hindi confirmations
        yes_keywords_hindi = ['हां', 'हाँ', 'जी', 'ठीक है', 'हां करें', 'सही', 'हाँ जी']
        no_keywords_hindi = ['नहीं', 'रद्द करें', 'नही', 'मत करो', 'नहीं जी']
        
        # Bengali confirmations
        yes_keywords_bengali = ['হ্যাঁ', 'ঠিক আছে', 'করুন', 'হ্যাঁ করুন', 'সঠিক']
        no_keywords_bengali = ['না', 'বাতিল', 'নাহ', 'করবেন না', 'না করুন']
        
        # Check all keywords
        if msg_lower in yes_keywords + yes_keywords_hindi + yes_keywords_bengali:
            logger.debug(f"Confirmation detected: '{message}' → YES")
            return True
        if msg_lower in no_keywords + no_keywords_hindi + no_keywords_bengali:
            logger.debug(f"Confirmation detected: '{message}' → NO")
            return True
        
        logger.debug(f"Not a confirmation: '{message}'")
        return False
    
    def _parse_ai_confirmation_request(self, ai_response: str) -> Optional[Dict]:
        """
        Parse AI's response to detect if it's showing a confirmation request.
        Extract simulation_id, field, current_value, new_value from the AI's message.
        
        Returns: pending_action dict if confirmation request detected, None otherwise
        """
        import re
        
        # Pattern: "📝 Update Request:" followed by field details
        if '📝 Update Request:' in ai_response or 'Update Request:' in ai_response:
            logger.info("🔍 Detected '📝 Update Request:' in AI response")
            
            # Extract simulation ID
            sim_match = re.search(r'Simulation ID:\s*([a-z0-9_-]+)', ai_response, re.IGNORECASE)
            if not sim_match:
                logger.warning("Could not extract simulation_id from AI confirmation")
                return None
            simulation_id = sim_match.group(1)
            
            # Extract field name
            field_match = re.search(r'Field:\s*([^\n]+)', ai_response, re.IGNORECASE)
            if not field_match:
                logger.warning("Could not extract field from AI confirmation")
                return None
            field_text = field_match.group(1).strip()
            
            # Normalize field name
            field_normalized, _ = self._normalize_field_name(field_text)
            if not field_normalized:
                logger.warning(f"Could not normalize field: {field_text}")
                return None
            
            # Extract current value
            current_match = re.search(r'Current Value:\s*([^\n]+)', ai_response, re.IGNORECASE)
            current_value = current_match.group(1).strip() if current_match else 'N/A'
            
            # Extract new value
            new_match = re.search(r'New Value:\s*([^\n]+)', ai_response, re.IGNORECASE)
            if not new_match:
                logger.warning("Could not extract new value from AI confirmation")
                return None
            new_value = new_match.group(1).strip()
            
            logger.info(f"✅ Parsed AI confirmation request:")
            logger.info(f"   Simulation: {simulation_id}")
            logger.info(f"   Field: {field_normalized}")
            logger.info(f"   Current: {current_value}")
            logger.info(f"   New: {new_value}")
            
            return {
                'type': 'update',
                'simulation_id': simulation_id,
                'field': field_normalized,
                'current_value': current_value,
                'new_value': new_value,
                'timestamp': datetime.now().isoformat()
            }
        
        return None
    
    def _parse_update_intent(self, message: str) -> Optional[Dict]:
        """Parse message for update intent using enhanced patterns and keywords."""
        
        msg_lower = message.lower()
        logger.debug(f"Parsing update intent from: '{message}'")
        
        # Pattern 1: "set it to X" or "change it to X" (context-based, no field specified)
        context_patterns = [
            r'(?:set|change|make|update)\s+(?:it|that|this)\s+(?:to|as)\s+([\d.]+)',
            r'(?:i\s+want|make\s+it)\s+([\d.]+)',
            r'(?:should\s+be|must\s+be)\s+([\d.]+)',
        ]
        
        for pattern in context_patterns:
            match = re.search(pattern, msg_lower)
            if match:
                logger.info(f"Context-based update detected: value={match.group(1)}")
                return {
                    'simulation_id': self.current_simulation_id,
                    'field': 'patients_enrolled',  # Default assumption
                    'new_value': match.group(1),
                    'original_message': message,
                    'needs_field_inference': True
                }
        
        # Keywords for updates in multiple languages
        update_keywords = [
            'update', 'change', 'modify', 'set', 'edit', 'alter', 'adjust',
            'make', 'want', 'should be', 'must be',
            'अपडेट', 'बदलें', 'परिवर्तन', 'सेट',
            'আপডেট', 'পরিবর্তন', 'সেট', 'সম্পাদনা'
        ]
        
        has_update_keyword = any(keyword in msg_lower for keyword in update_keywords)
        
        # Try to extract simulation ID from message
        sim_id_pattern = r'(?:simulation[:\s]+|sim[:\s]+|id[:\s]+|for\s+)([a-z0-9_-]+(?:_[a-z0-9_-]+)*)'
        sim_match = re.search(sim_id_pattern, message, re.IGNORECASE)
        simulation_id = sim_match.group(1) if sim_match else None
        
        # Try to extract field and value with comprehensive patterns
        field_name = None
        new_value = None
        
        # Pattern 2: "X patients" or "X patient count"
        patient_patterns = [
            r'(\d+)\s+patients?(?:\s+enrolled)?',
            r'(\d+)\s+(?:patient\s+)?(?:count|number)',
            r'enrollment\s+(?:of\s+)?(\d+)',
            r'enroll\s+(\d+)',
        ]
        for pattern in patient_patterns:
            match = re.search(pattern, msg_lower)
            if match and has_update_keyword:
                field_name = 'patients_enrolled'
                new_value = match.group(1)
                logger.info(f"Patient pattern matched: {pattern} → {new_value}")
                break
        
        # Pattern 3: "field to/= value" or "field: value" or "field for simulation to value"
        if not field_name:
            # Remove action words and polite phrases first
            msg_clean = msg_lower
            action_words = r'\b(?:can\s+you\s+)?(?:please\s+)?(?:update|change|modify|set|edit|alter|adjust|make|want)\b\s+'
            msg_clean = re.sub(action_words, '', msg_clean)
            
            field_value_patterns = [
                r'([a-z_\s]+?)\s+for\s+[a-z0-9_]+\s+to\s+([\d.]+)',  # "patient enrolled for sim_123 to 500"
                r'([a-z_\s]+?)\s+(?:to|as)\s+([\d.]+)',  # "patients to 500" or "patient count to 500"
                r'([a-z_\s]+?)\s*[:=]\s*([\d.]+)',  # "patients: 500" or "patients=500"
                r'([a-z_\s]+?)\s+should\s+be\s+([\d.]+)',  # "patients should be 500"
                r'([a-z_\s]+?)\s+(?:is|are)\s+([\d.]+)',  # "patients is 500"
            ]
            
            for pattern in field_value_patterns:
                match = re.search(pattern, msg_clean)
                if match:
                    field_name = match.group(1).strip()
                    new_value = match.group(2)
                    logger.info(f"Field-value pattern matched: {field_name}={new_value}")
                    break
        
        # Pattern 4: Specific field patterns
        if not field_name:
            specific_patterns = {
                r'dropout\s+(?:rate\s+)?(?:to|of|is)\s+([\d.]+)': 'dropout_rate',
                r'cost\s+(?:to|of|is)\s+([\d.]+)': 'estimated_cost',
                r'duration\s+(?:to|of|is)\s+(\d+)': 'actual_duration_days',
                r'success\s+(?:rate|probability)\s+(?:to|of|is)\s+([\d.]+)': 'success_probability',
            }
            
            for pattern, field in specific_patterns.items():
                match = re.search(pattern, msg_lower)
                if match:
                    field_name = field
                    new_value = match.group(1)
                    logger.info(f"Specific pattern matched: {field}={new_value}")
                    break
        
        if field_name and new_value:
            # Normalize field name using aliases
            normalized_field, suggestions = self._normalize_field_name(field_name)
            
            if normalized_field:
                logger.info(f"Update intent parsed: field={normalized_field}, value={new_value}")
                return {
                    'simulation_id': simulation_id or self.current_simulation_id,
                    'field': normalized_field,
                    'new_value': new_value,
                    'original_message': message
                }
            else:
                # Field not recognized
                logger.warning(f"Field '{field_name}' not recognized. Suggestions: {suggestions}")
                return {
                    'simulation_id': simulation_id or self.current_simulation_id,
                    'field': field_name,  # Keep original for error message
                    'new_value': new_value,
                    'original_message': message,
                    'invalid_field': True,
                    'suggestions': suggestions
                }
        
        logger.debug("No update intent found")
        return None
    
    def _parse_translation_intent(self, message: str) -> Optional[Dict]:
        """Parse message for translation request."""
        
        msg_lower = message.lower()
        
        # Translation keywords
        translate_keywords = [
            'translate', 'translation', 'convert to',
            'अनुवाद', 'में बदलें',
            'অনুবাদ', 'রূপান্তর'
        ]
        
        if not any(keyword in msg_lower for keyword in translate_keywords):
            return None
        
        # Extract target language
        language_map = {
            'hindi': 'hi', 'हिंदी': 'hi', 'हिन्दी': 'hi',
            'bengali': 'bn', 'bangla': 'bn', 'বাংলা': 'bn',
            'english': 'en', 'अंग्रेजी': 'en', 'ইংরেজি': 'en'
        }
        
        target_language = None
        for lang_name, lang_code in language_map.items():
            if lang_name in msg_lower:
                target_language = lang_code
                break
        
        return {
            'target_language': target_language,
            'original_message': message
        }
    
    async def _handle_chat(self, message: str) -> Dict[str, Any]:
        """Handle regular chat conversation."""
        
        try:
            # Get user's simulations for context
            user_simulations = self.db.get_user_simulations(self.user_id)
            
            # Build conversation context
            system_prompt = self._get_system_prompt(user_simulations)
            
            # Add conversation history
            chat_history = self.conversation_history[-5:]  # Last 5 messages for context
            
            # Create prompt with history
            full_prompt = f"{system_prompt}\n\n**Conversation History:**\n"
            for msg in chat_history:
                full_prompt += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"
            full_prompt += f"**Current User Message:**\n{message}\n\n**Your Response:**"
            
            # Generate response with AWS Bedrock (Claude Sonnet 4.5)
            logger.info(f"Calling AWS Bedrock API for user {self.username}")
            assistant_response = self._call_bedrock_api(full_prompt)
            logger.info(f"AWS Bedrock response received: {len(assistant_response)} chars")
            
            # Store in conversation history
            self.conversation_history.append({
                'user': message,
                'assistant': assistant_response,
                'timestamp': datetime.now().isoformat()
            })
            
            # Save to database
            self.db.save_chat_message(
                user_id=self.user_id,
                message=message,
                response=assistant_response,
                language=self.language,
                action_type='chat'
            )
            
            logger.info(f"Chat response generated for {self.username}")
            
            # Check if AI generated a confirmation request
            # Parse the response to see if it's asking for confirmation
            parsed_pending = self._parse_ai_confirmation_request(assistant_response)
            if parsed_pending:
                logger.info("🟡 AI GENERATED CONFIRMATION REQUEST - Creating pending_action")
                logger.info(f"   Extracted: {parsed_pending}")
                self.pending_action = parsed_pending
                return {
                    'response': assistant_response,
                    'language': self.language,
                    'action_type': 'update_request',  # Change action type to indicate confirmation needed
                    'action_data': parsed_pending
                }
            
            return {
                'response': assistant_response,
                'language': self.language,
                'action_type': 'chat',
                'action_data': None
            }
            
        except Exception as e:
            logger.error(f"Error in _handle_chat: {str(e)}", exc_info=True)
            return {
                'response': f"I encountered an error: {str(e)}. Please make sure your AWS credentials are configured correctly.",
                'language': self.language or 'en',
                'action_type': 'error',
                'action_data': None
            }
    
    def _validate_update(self, simulation_id: str, field: str, new_value: str) -> Tuple[bool, Optional[str]]:
        """
        Validate update request before asking for confirmation.
        Returns: (is_valid, error_message)
        """
        logger.debug(f"Validating update: sim={simulation_id}, field={field}, value={new_value}")
        
        # Check if simulation exists
        simulation = self.db.get_simulation_by_id(simulation_id)
        if not simulation:
            logger.warning(f"Simulation '{simulation_id}' not found")
            return False, f"Simulation '{simulation_id}' not found. Use 'show my simulations' to see available simulations."
        
        # Check ownership
        if not self.db.verify_simulation_owner(simulation_id, self.user_id):
            logger.warning(f"User {self.user_id} doesn't own simulation {simulation_id}")
            return False, f"You don't have permission to update this simulation."
        
        # Check if field exists
        if field not in simulation:
            logger.warning(f"Field '{field}' not found in simulation")
            # Suggest similar fields
            available_fields = [f for f in simulation.keys() if not f.startswith('_')]
            suggestions = [f for f in available_fields if field.lower() in f.lower() or f.lower() in field.lower()]
            if suggestions:
                return False, f"Field '{field}' not found. Did you mean: {', '.join(suggestions[:3])}?"
            return False, f"Field '{field}' not found. Available fields: {', '.join(available_fields[:5])}"
        
        # Validate value based on field type and constraints
        try:
            if field == 'patients_enrolled':
                val = int(new_value)
                if val <= 0:
                    return False, "Number of patients must be positive (greater than 0)."
                if val > 10000:
                    return False, "Number of patients seems too high (maximum 10,000)."
            
            elif field == 'patients_completed':
                val = int(new_value)
                enrolled = simulation.get('patients_enrolled', 0)
                if val < 0:
                    return False, "Number of completed patients cannot be negative."
                if val > enrolled:
                    return False, f"Completed patients ({val}) cannot exceed enrolled patients ({enrolled})."
            
            elif field == 'dropout_rate':
                val = float(new_value)
                if val < 0 or val > 1:
                    return False, "Dropout rate must be between 0 and 1 (e.g., 0.15 for 15%)."
            
            elif field == 'estimated_cost':
                val = float(new_value)
                if val < 0:
                    return False, "Cost cannot be negative."
            
            elif field == 'actual_duration_days':
                val = int(new_value)
                if val <= 0:
                    return False, "Duration must be positive (at least 1 day)."
                if val > 3650:  # ~10 years
                    return False, "Duration seems too long (maximum 3650 days / 10 years)."
            
            elif field == 'success_probability':
                val = float(new_value)
                if val < 0 or val > 1:
                    return False, "Success probability must be between 0 and 1 (e.g., 0.75 for 75%)."
            
            # Add more field validations as needed
            
        except ValueError as e:
            logger.warning(f"Value conversion error: {e}")
            return False, f"Invalid value '{new_value}' for field '{field}'. Expected a number."
        
        logger.info(f"Validation passed for {field}={new_value}")
        return True, None
    
    async def _handle_update_request(self, intent: Dict) -> Dict[str, Any]:
        """Handle simulation update request with validation."""
        
        simulation_id = intent['simulation_id']
        field = intent['field']
        new_value = intent['new_value']
        
        logger.info(f"Update request: sim={simulation_id}, field={field}, value={new_value}")
        
        # Check if field was marked as invalid during parsing
        if intent.get('invalid_field'):
            suggestions = intent.get('suggestions', [])
            if suggestions:
                return {
                    'response': f"❌ Field '{field}' not recognized.\n\nDid you mean one of these?\n" + 
                               "\n".join([f"- {s}" for s in suggestions]),
                    'language': self.language,
                    'action_type': 'error',
                    'action_data': None
                }
            return {
                'response': f"❌ Field '{field}' not recognized. Please check the field name and try again.",
                'language': self.language,
                'action_type': 'error',
                'action_data': None
            }
        
        # If no simulation ID, try to use current simulation or ask user to specify
        if not simulation_id:
            if self.current_simulation_id:
                simulation_id = self.current_simulation_id
                logger.info(f"Using current simulation context: {simulation_id}")
            else:
                # Check if user has only one simulation
                user_sims = self.db.get_user_simulations(self.user_id)
                if len(user_sims) == 1:
                    simulation_id = user_sims[0]['simulation_id']
                    logger.info(f"Using user's only simulation: {simulation_id}")
                else:
                    sim_list = "\n".join([f"- {s['simulation_id']}" for s in user_sims])
                    return {
                        'response': f"Please specify which simulation to update:\n{sim_list}",
                        'language': self.language,
                        'action_type': 'clarification',
                        'action_data': None
                    }
        
        # Validate the update request
        is_valid, error_message = self._validate_update(simulation_id, field, new_value)
        if not is_valid:
            logger.warning(f"Validation failed: {error_message}")
            return {
                'response': f"❌ {error_message}",
                'language': self.language,
                'action_type': 'error',
                'action_data': None
            }
        
        # Get current simulation data (already validated to exist)
        simulation = self.db.get_simulation_by_id(simulation_id)
        current_value = simulation.get(field, 'N/A')
        
        # Store pending action
        self.pending_action = {
            'type': 'update',
            'simulation_id': simulation_id,
            'field': field,
            'current_value': current_value,
            'new_value': new_value,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("🟢 PENDING ACTION CREATED:")
        logger.info(f"   Type: {self.pending_action['type']}")
        logger.info(f"   Simulation: {simulation_id}")
        logger.info(f"   Field: {field}")
        logger.info(f"   Current: {current_value}")
        logger.info(f"   New: {new_value}")
        logger.info(f"   ChatService ID: {id(self)}")
        logger.info("="*70)
        
        # Generate confirmation message in user's language
        confirmation_msg = self._generate_confirmation_message(
            simulation_id, field, current_value, new_value
        )
        
        logger.info(f"Update request pending confirmation for {self.username}")
        
        return {
            'response': confirmation_msg,
            'language': self.language,
            'action_type': 'update_request',
            'action_data': self.pending_action
        }
    
    def _generate_confirmation_message(self, sim_id: str, field: str, old_val: Any, new_val: Any) -> str:
        """Generate confirmation message in appropriate language."""
        
        if self.language == 'hi':
            return f"""📝 अपडेट अनुरोध:
- सिमुलेशन ID: {sim_id}
- फ़ील्ड: {field}
- वर्तमान मान: {old_val}
- नया मान: {new_val}

जारी रखने के लिए 'हां' या 'YES' का जवाब दें, या रद्द करने के लिए 'नहीं' या 'NO' का जवाब दें।"""
        
        elif self.language == 'bn':
            return f"""📝 আপডেট অনুরোধ:
- সিমুলেশন ID: {sim_id}
- ফিল্ড: {field}
- বর্তমান মান: {old_val}
- নতুন মান: {new_val}

এগিয়ে যেতে 'হ্যাঁ' বা 'YES' উত্তর দিন, অথবা বাতিল করতে 'না' বা 'NO' উত্তর দিন।"""
        
        else:  # English
            return f"""📝 Update Request Detected:
- Simulation ID: {sim_id}
- Field: {field}
- Current Value: {old_val}
- New Value: {new_val}

Reply with 'YES' or 'CONFIRM' to proceed, or 'NO' or 'CANCEL' to abort."""
    
    async def _handle_confirmation(self, message: str) -> Dict[str, Any]:
        """Handle user confirmation for pending action."""
        
        msg_lower = message.lower().strip()
        
        # Check if confirmed
        yes_keywords = ['yes', 'confirm', 'ok', 'y', 'हां', 'हाँ', 'जी', 'হ্যাঁ', 'ঠিক']
        no_keywords = ['no', 'cancel', 'n', 'नहीं', 'না']
        
        is_confirmed = any(keyword in msg_lower for keyword in yes_keywords)
        is_cancelled = any(keyword in msg_lower for keyword in no_keywords)
        
        if not (is_confirmed or is_cancelled):
            return {
                'response': "Please reply with YES to confirm or NO to cancel.",
                'language': self.language,
                'action_type': 'clarification',
                'action_data': None
            }
        
        if is_cancelled:
            self.pending_action = None
            return {
                'response': "❌ Update cancelled.",
                'language': self.language,
                'action_type': 'cancelled',
                'action_data': None
            }
        
        # Execute the update
        if self.pending_action['type'] == 'update':
            return await self._execute_update()
        
        return {
            'response': "No pending action to confirm.",
            'language': self.language,
            'action_type': 'error',
            'action_data': None
        }
    
    async def _execute_update(self) -> Dict[str, Any]:
        """Execute the pending update."""
        
        try:
            action = self.pending_action
            simulation_id = action['simulation_id']
            field = action['field']
            old_value = action['current_value']
            new_value = action['new_value']
            
            # Update the simulation data
            success, error_message = self.db.update_simulation_data(
                simulation_id=simulation_id,
                field=field,
                new_value=new_value
            )
            
            if not success:
                logger.error(f"Database update failed: {error_message}")
                return {
                    'response': f"❌ Failed to update {field}.\n\n{error_message}",
                    'language': self.language,
                    'action_type': 'error',
                    'action_data': None
                }
            
            # Save to chat history
            self.db.save_chat_message(
                user_id=self.user_id,
                message=f"Confirmed update: {field} = {new_value}",
                response=f"Updated {field} from {old_value} to {new_value}",
                language=self.language or 'en',
                action_type='update_executed',
                simulation_id=simulation_id
            )
            
            # Clear pending action
            self.pending_action = None
            
            # Generate success message with old and new values
            success_msg = self._generate_success_message(simulation_id, field, old_value, new_value)
            
            logger.info(f"Update executed successfully: {simulation_id} - {field}: {old_value} → {new_value}")
            
            return {
                'response': success_msg,
                'language': self.language,
                'action_type': 'update_executed',
                'action_data': {
                    'simulation_id': simulation_id,
                    'field': field,
                    'old_value': old_value,
                    'new_value': new_value,
                    'resimulation_required': True
                }
            }
            
        except Exception as e:
            logger.error(f"Error executing update: {str(e)}", exc_info=True)
            return {
                'response': f"❌ Error: {str(e)}",
                'language': self.language,
                'action_type': 'error',
                'action_data': None
            }
    
    def _generate_success_message(self, sim_id: str, field: str, old_val: Any, new_val: Any) -> str:
        """Generate success message in appropriate language."""
        
        if self.language == 'hi':
            return f"""✅ सफलतापूर्वक अपडेट किया गया!

- सिमुलेशन ID: {sim_id}
- फ़ील्ड: {field}
- पुराना मान: {old_val}
- नया मान: {new_val}

🔄 सिमुलेशन को फिर से प्रोसेस किया जा रहा है...
परिणाम कुछ मिनटों में तैयार हो जाएंगे।"""
        
        elif self.language == 'bn':
            return f"""✅ সফলভাবে আপডেট করা হয়েছে!

- সিমুলেশন ID: {sim_id}
- ফিল্ড: {field}
- পুরাতন মান: {old_val}
- নতুন মান: {new_val}

🔄 সিমুলেশন পুনরায় প্রক্রিয়া করা হচ্ছে...
ফলাফল কয়েক মিনিটের মধ্যে প্রস্তুত হবে।"""
        
        else:  # English
            return f"""✅ Successfully Updated!

- Simulation ID: {sim_id}
- Field: {field}
- Previous Value: {old_val}
- New Value: {new_val}

🔄 Re-processing simulation...
Results will be ready in a few minutes."""
    
    async def _handle_translation_request(self, intent: Dict) -> Dict[str, Any]:
        """Handle translation request."""
        
        target_language = intent['target_language']
        
        if not target_language:
            return {
                'response': "Please specify target language (English, Hindi, or Bengali).",
                'language': self.language,
                'action_type': 'clarification',
                'action_data': None
            }
        
        # Use AWS Bedrock to translate
        prompt = f"""Translate the following to {target_language}:
{intent['original_message']}

Provide translation only, no explanations."""
        
        translation = self._call_bedrock_api(prompt)
        
        return {
            'response': f"Translation:\n{translation}",
            'language': target_language,
            'action_type': 'translation',
            'action_data': {'translation': translation}
        }
    
    def get_conversation_history(self) -> List[Dict]:
        """Get current conversation history."""
        return self.conversation_history
    
    def clear_pending_action(self):
        """Clear any pending action (timeout or user request)."""
        self.pending_action = None
