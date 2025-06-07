"""
Question understanding component for analyzing and classifying questions about code.
"""

import re
import logging
from enum import Enum, auto
from typing import Dict, Set, List, Tuple, Optional

# Import spaCy for NLP processing
import spacy


class QuestionIntent(Enum):
    """Enumeration of possible question intents"""
    PURPOSE = auto()             # What does X do?
    IMPLEMENTATION = auto()      # How is X implemented?
    PARAMETER_USAGE = auto()     # How does method X use parameter Y?
    METHOD_LISTING = auto()      # What methods does class X have?
    CODE_WALKTHROUGH = auto()    # Explain/walk me through this code
    USAGE_EXAMPLE = auto()       # How do I use X?
    ERROR_HANDLING = auto()      # How does X handle errors?
    DESIGN_PATTERN = auto()      # What design pattern does X use?
    DEPENDENCY = auto()          # What dependencies does X have?
    STATISTICS = auto()          # How many functions are there in total?
    UNKNOWN = auto()             # Default fallback
    INVALID = auto()             # For nonsensical questions


class EntityType(Enum):
    """Types of code entities that can be referenced in questions"""
    CLASS = auto()
    FUNCTION = auto()
    METHOD = auto()
    MODULE = auto()
    PARAMETER = auto()
    VARIABLE = auto()
    FILE = auto()
    UNKNOWN = auto()


class QuestionAnalysis:
    """Container for question analysis results"""
    
    def __init__(self):
        self.intent = QuestionIntent.UNKNOWN
        self.entities = {}  # name -> EntityType
        self.is_valid = True
        self.invalid_reason = ""
        self.confidence = 0.0
        self.is_followup = False
        self.normalized_question = ""
    
    def to_dict(self):
        """Convert analysis to dict for logging"""
        return {
            "intent": self.intent.name,
            "entities": {name: entity_type.name for name, entity_type in self.entities.items()},
            "is_valid": self.is_valid,
            "invalid_reason": self.invalid_reason,
            "confidence": self.confidence,
            "is_followup": self.is_followup,
            "normalized_question": self.normalized_question
        }


class QuestionUnderstanding:
    """
    System for analyzing and understanding code-related questions using spaCy.
    
    Provides intent classification, entity extraction, and validation
    to improve question understanding using NLP techniques.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize spaCy NLP pipeline
        try:
            # Try to load the spaCy model
            self.nlp = spacy.load("en_core_web_sm")
            self.logger.info("Loaded spaCy model successfully")
        except IOError:
            # If model isn't downloaded, download it
            self.logger.warning("SpaCy model not found, trying to create a blank model")
            self.nlp = spacy.blank("en")
        
        # Define intent patterns - these will complement spaCy's capabilities
        self.intent_patterns = {
            # Purpose questions
            r'what (does|is) (the )?(class|function|method|module) ([\w_]+)( do| for)?\??': QuestionIntent.PURPOSE,
            r'what (does|is) (\w+)( do| for)?\??': QuestionIntent.PURPOSE,
            r'(what is|explain) the purpose of ([\w_]+)\??': QuestionIntent.PURPOSE,
            r'what is ([\w_]+) used for\??': QuestionIntent.PURPOSE,
            
            # Implementation questions
            r'how (does|is) (the )?(class|function|method|module|service|component) ([\w_]+) (work|implemented)\??': QuestionIntent.IMPLEMENTATION,
            r'how (does|is) ([\w_]+) (work|implemented)\??': QuestionIntent.IMPLEMENTATION,
            r'(explain|show) (me )?how ([\w_]+) (works|is implemented)\??': QuestionIntent.IMPLEMENTATION,
            
            # Parameter usage questions
            r'how (does|is) (the )?(parameter|argument) ([\w_]+) used in ([\w_]+)\??': QuestionIntent.PARAMETER_USAGE,
            r'how does ([\w_]+) use (the )?(parameter|argument) ([\w_]+)\??': QuestionIntent.PARAMETER_USAGE,
            r'what (does|is) ([\w_]+) do with (the )?(parameter|argument) ([\w_]+)\??': QuestionIntent.PARAMETER_USAGE,
            
            # Method listing questions
            r'what (methods|functions) (does|do) (the )?(class|module) ([\w_]+) have\??': QuestionIntent.METHOD_LISTING,
            r'list (all )?(the )?(methods|functions) (in|of) ([\w_]+)\??': QuestionIntent.METHOD_LISTING,
            r'what (are|is) the (methods|functions) (in|of) ([\w_]+)\??': QuestionIntent.METHOD_LISTING,
            
            # Statistics questions
            r'how many (functions|methods|classes|modules|files) (are there|exist)( in total| overall)?\??': QuestionIntent.STATISTICS,
            r'count (the )?(number of|all) (functions|methods|classes|modules|files)\??': QuestionIntent.STATISTICS,
            r'what is the (total|overall) (count|number) of (functions|methods|classes|modules|files)\??': QuestionIntent.STATISTICS,
        }
        
        # Intent classification keywords - for spaCy-based classification
        self.intent_keywords = {
            QuestionIntent.PURPOSE: [
                "purpose", "point", "what", "do", "does", "goal", "designed", "why", "role", "aim", "function"
            ],
            QuestionIntent.IMPLEMENTATION: [
                "how", "implement", "built", "created", "structure", "work", "algorithm", "mechanism", "approach"
            ],
            QuestionIntent.PARAMETER_USAGE: [
                "parameter", "argument", "input", "how", "use", "passed", "uses", "param", "arg"
            ],
            QuestionIntent.METHOD_LISTING: [
                "methods", "functions", "list", "what methods", "available methods", "what functions", "has methods"
            ],
            QuestionIntent.CODE_WALKTHROUGH: [
                "explain", "walk through", "step by step", "describe", "detail", "walkthrough"
            ],
            QuestionIntent.USAGE_EXAMPLE: [
                "example", "how to use", "sample", "usage", "how do I", "show me", "demonstrate"
            ],
            QuestionIntent.ERROR_HANDLING: [
                "error", "exception", "handle", "failure", "when it fails", "catch", "try except"
            ],
            QuestionIntent.DESIGN_PATTERN: [
                "pattern", "design", "architecture", "structure", "paradigm", "model", "mvc", "mvvm"
            ],
            QuestionIntent.DEPENDENCY: [
                "dependency", "depend", "require", "library", "module", "import", "package", "needs"
            ],
            QuestionIntent.STATISTICS: [
                "how many", "count", "number", "total", "statistics", "quantity", "sum", "overall", "amount"
            ],
        }
        
        # Add entity patterns to spaCy pipeline
        self._add_code_entity_patterns()
        
        # Common nonsense or filler words to detect invalid questions
        self.nonsense_words = {
            "blah", "foo", "bar", "baz", "qux", "asdf", "jkl", "xyz", "abc", 
            "lorem", "ipsum", "dolor", "amet", "consectetur", "adipiscing", "elit"
        }
        
        # Code-related terms that valid questions might contain
        self.code_terms = {
            "code", "function", "method", "class", "variable", "parameter", 
            "module", "library", "api", "interface", "implementation", "algorithm",
            "data", "structure", "object", "instance", "property", "attribute",
            "component", "service", "model", "view", "controller", "exception",
            "error", "bug", "debug", "test", "file", "import", "export", "return"
        }
    
    def _add_code_entity_patterns(self):
        """Add code entity patterns to spaCy's pipeline for custom entity recognition"""
        # Define entity patterns for code elements
        patterns = [
            {"label": "CODE_CLASS", "pattern": [{"SHAPE": "Xxxx"}, {"LOWER": "class", "OP": "?"}]},
            {"label": "CODE_FUNCTION", "pattern": [{"SHAPE": "xxxx"}, {"TEXT": "(", "OP": "?"}]},
            {"label": "CODE_METHOD", "pattern": [{"TEXT": "."}, {"SHAPE": "xxxx"}, {"TEXT": "(", "OP": "?"}]},
            {"label": "CODE_PARAMETER", "pattern": [{"LOWER": "parameter"}, {"SHAPE": "xxxx"}]},
            {"label": "CODE_MODULE", "pattern": [{"LOWER": "module"}, {"SHAPE": "xxxx"}]},
        ]
        
        # Add entity recognition patterns if entity_ruler is available
        if not self.nlp.has_pipe("entity_ruler"):
            ruler = self.nlp.add_pipe("entity_ruler")
            ruler.add_patterns(patterns)
    
    def analyze_question(self, question: str) -> QuestionAnalysis:
        """
        Analyze a question to understand intent and extract entities using spaCy.
        
        Args:
            question: The question text to analyze
            
        Returns:
            QuestionAnalysis object containing the analysis results
        """
        result = QuestionAnalysis()
        result.original_question = question
        
        # Normalize the question text
        normalized = question.strip()
        if not normalized.endswith('?'):
            normalized += '?'
        
        result.normalized_question = normalized
        
        # Process with spaCy
        doc = self.nlp(normalized)
        
        # Check if the question is valid
        is_valid, invalid_reason = self._validate_question(doc)
        if not is_valid:
            result.is_valid = False
            result.invalid_reason = invalid_reason
            result.intent = QuestionIntent.INVALID
            result.confidence = 1.0  # High confidence that it's invalid
            return result
        
        # Detect intent using NLP and regex patterns
        intent, confidence = self._detect_intent(doc, normalized)
        result.intent = intent
        result.confidence = confidence
        
        # Extract entities using spaCy's NER and our custom patterns
        result.entities = self._extract_entities(doc, intent)
        
        # Check if it's a follow-up question (lacks explicit references)
        result.follow_up = len(result.entities) == 0 and any(token.text.lower() == 'it' for token in doc)
        
        return result
    
    def _validate_question(self, doc) -> Tuple[bool, Optional[str]]:
        """
        Check if a question is valid for code understanding using spaCy doc.
        
        Args:
            doc: spaCy processed document
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Get words from the document
        words = [token.text.lower() for token in doc if not token.is_punct and not token.is_space]
        
        # Check for nonsense words
        for word in words:
            if word in self.nonsense_words:
                return False, f"Question contains nonsense word: '{word}'"
        
        # Check if it's a statistical question (these can be shorter)
        question_text = doc.text.lower()
        is_statistical = any(term in question_text for term in [
            'how many', 'count', 'number of', 'total', 'statistics'
        ])
        
        # Check for minimum question length (excluding stopwords)
        content_words = [token.text for token in doc if not token.is_stop and not token.is_punct and token.text.lower() not in ['how', 'many']]
        # Be more lenient with question length - accept any non-empty question
        if len(content_words) < 1:
            return False, f"Question is too short or empty"
        
        # Too many question marks often indicates confusion or nonsense
        if question_text.count('?') > 2:
            return False, "Too many question marks"
            
        # Extremely long questions are often problematic
        if len(question_text) > 200:
            return False, "Question is too long"
            
        # If question doesn't contain any programming terms/concepts, it might not be code-related
        # But skip this check for statistical questions which might be more general
        if not is_statistical:
            has_code_term = any(term in question_text for term in self.code_terms)
            if not has_code_term:
                return False, "Question doesn't appear to be code-related"
        
        return True, None
    
    def _detect_intent(self, doc, normalized_text: str) -> Tuple[QuestionIntent, float]:
        """
        Detect the intent of a question using spaCy and patterns.
        
        Args:
            doc: spaCy processed document
            normalized_text: The normalized question text
            
        Returns:
            Tuple of (intent, confidence_score)
        """
        # First try regex patterns for precise matching
        for pattern, intent in self.intent_patterns.items():
            if re.search(pattern, normalized_text, re.IGNORECASE):
                # Strong match for a specific pattern
                return intent, 0.9
        
        # If no direct pattern match, use spaCy and keyword analysis
        scores = {intent: 0.0 for intent in QuestionIntent if intent != QuestionIntent.INVALID}
        
        # Extract question keywords and check against our intent keywords
        question_keywords = [token.lemma_.lower() for token in doc 
                           if not token.is_stop and not token.is_punct]
                           
        # Calculate scores based on keyword matches
        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                # Check if multi-word keyword
                if ' ' in keyword and keyword.lower() in normalized_text.lower():
                    scores[intent] += 2.0  # Multi-word matches are stronger
                elif keyword.lower() in question_keywords:
                    scores[intent] += 1.0
            
            # Normalize by number of keywords
            if scores[intent] > 0:
                scores[intent] /= max(len(keywords), 1)  # Avoid division by zero
        
        # Get the highest scoring intent
        if max(scores.values()) > 0:
            best_intent = max(scores, key=scores.get)
            confidence = min(0.85, scores[best_intent] + 0.4)  # Scale confidence
            return best_intent, confidence
        
        return QuestionIntent.UNKNOWN, 0.3
    
    def _extract_entities(self, doc, intent: QuestionIntent) -> Dict[str, EntityType]:
        """
        Extract code entities from the question using spaCy.
        
        Args:
            doc: spaCy processed document
            intent: The detected question intent
            
        Returns:
            Dictionary mapping entity names to their types
        """
        entities = {}
        
        # First extract any entities recognized by our custom entity ruler
        for ent in doc.ents:
            if ent.label_.startswith('CODE_'):
                entity_type = None
                if ent.label_ == 'CODE_CLASS':
                    entity_type = EntityType.CLASS
                elif ent.label_ == 'CODE_FUNCTION':
                    entity_type = EntityType.FUNCTION
                elif ent.label_ == 'CODE_METHOD':
                    entity_type = EntityType.METHOD
                elif ent.label_ == 'CODE_PARAMETER':
                    entity_type = EntityType.PARAMETER
                elif ent.label_ == 'CODE_MODULE':
                    entity_type = EntityType.MODULE
                
                if entity_type:
                    # Clean up the entity name (remove trailing parentheses for functions)
                    name = ent.text
                    if name.endswith('('):
                        name = name[:-1]
                    entities[name] = entity_type
        
        # Use regex as backup for entity extraction based on intent
        normalized_text = doc.text.lower()
        
        if intent == QuestionIntent.PURPOSE:
            # Extract class or module name
            match = re.search(r'what (does|is) (the )?(class|module|function|method) ([\w_]+)( do| for)?', normalized_text)
            if match and not entities:
                entity_type = match.group(3)
                entity_name = match.group(4)
                if entity_type == 'class':
                    entities[entity_name] = EntityType.CLASS
                elif entity_type == 'module':
                    entities[entity_name] = EntityType.MODULE
                elif entity_type in ('function', 'method'):
                    entities[entity_name] = EntityType.FUNCTION
            
            # Alternative purpose pattern
            alt_match = re.search(r'what is (the )?(purpose|role) of ([\w_]+)', normalized_text)
            if alt_match and not entities:
                entities[alt_match.group(3)] = EntityType.UNKNOWN
        
        elif intent == QuestionIntent.IMPLEMENTATION:
            # Extract function, method or class name
            match = re.search(r'how (does|is) (the )?(function|method|class|module|service|component) ([\w_]+) (work|implemented)', normalized_text)
            if match and not entities:
                entity_type = match.group(3)
                entity_name = match.group(4)
                if entity_type in ('function', 'method'):
                    entities[entity_name] = EntityType.FUNCTION
                elif entity_type == 'class':
                    entities[entity_name] = EntityType.CLASS
                else:
                    entities[entity_name] = EntityType.MODULE
            
            # Alternative implementation pattern
            alt_match = re.search(r'how does ([\w_]+) work', normalized_text)
            if alt_match and not entities:
                entities[alt_match.group(1)] = EntityType.UNKNOWN
        
        elif intent == QuestionIntent.PARAMETER_USAGE:
            # Extract both function name and parameter name
            match = re.search(r'how does ([\w_]+) use (the )?(parameter|argument) ([\w_]+)', normalized_text)
            if match and not entities:
                func_name = match.group(1)
                param_name = match.group(4)
                entities[func_name] = EntityType.FUNCTION
                entities[param_name] = EntityType.PARAMETER
        
        elif intent == QuestionIntent.METHOD_LISTING:
            # Extract class name
            match = re.search(r'what (methods|functions) (does|do) (the )?(class|module)? ?([\w_]+) have', normalized_text)
            if match and not entities:
                class_name = match.group(5)
                entities[class_name] = EntityType.CLASS
        
        # Extract potential code entities that weren't caught by the specific patterns
        if not entities:
            # Use spaCy NER to identify potential code entities
            for token in doc:
                # Look for camelCase, PascalCase or snake_case words as potential code entities
                if (token.text not in ['what', 'how', 'why', 'when', 'where'] and 
                    len(token.text) > 2 and 
                    not token.is_stop and
                    not token.is_punct and
                    re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', token.text) and  # Valid identifier name
                    (re.search(r'[A-Z]', token.text) or  # Contains uppercase (camelCase/PascalCase)
                     '_' in token.text)):  # Contains underscore (snake_case)
                    
                    # Try to determine entity type based on capitalization pattern
                    entity_type = EntityType.UNKNOWN
                    if token.text[0].isupper():  # PascalCase suggests class
                        entity_type = EntityType.CLASS
                    elif '_' in token.text:  # snake_case suggests function or variable
                        entity_type = EntityType.FUNCTION
                    elif any(c.isupper() for c in token.text[1:]):  # camelCase suggests method
                        entity_type = EntityType.METHOD
                        
                    entities[token.text] = entity_type
            
            # If still no entities found, try more aggressive matching for any non-stopword nouns
            if not entities:
                for token in doc:
                    if ((token.pos_ == "NOUN" or token.pos_ == "PROPN") and 
                        len(token.text) > 2 and 
                        token.text.isalnum() and 
                        not token.is_stop):
                        entities[token.text] = EntityType.UNKNOWN
        
        return entities
