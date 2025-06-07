"""
Question understanding component for analyzing and classifying questions about code.
Uses TextBlob and spaCy for better NLP processing.
"""

import re
import logging
from enum import Enum, auto
from typing import Dict, Set, List, Tuple, Optional

# Import NLP libraries
import spacy
try:
    from textblob import TextBlob
except ImportError:
    # Fallback if TextBlob is not installed
    TextBlob = None


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
    
    def analyze_question(self, question_text: str) -> QuestionAnalysis:
        """Analyze a question and return structured information about it"""
        # Create a new analysis object
        analysis = QuestionAnalysis()
        
        # Process the question with spaCy
        doc = self.nlp(question_text)
        
        # Use TextBlob for additional NLP features if available
        blob = None
        if TextBlob is not None:
            blob = TextBlob(question_text)
        
        # Validate the question
        is_valid, reason = self._validate_question(question_text, doc, blob)
        if not is_valid:
            analysis.is_valid = False
            analysis.intent = QuestionIntent.INVALID
            analysis.invalid_reason = reason
            return analysis
            
        # Normalize text (lowercase, remove extra whitespace)
        normalized_text = " ".join([token.text.lower() for token in doc if not token.is_punct]).strip()
        
        # Detect intent
        intent, confidence = self._detect_intent(doc, normalized_text, blob)
        analysis.intent = intent
        analysis.confidence = confidence
        
        # Extract entities
        entities = self._extract_entities(doc, intent, blob)
        analysis.entities = entities
        
        return analysis
    
    def _validate_question(self, question_text: str, doc, blob=None) -> Tuple[bool, Optional[str]]:
        """
        Validate if a question is well-formed and answerable.
        
        Args:
            question_text: The raw question text
            doc: spaCy processed document
            blob: TextBlob object if available
            
        Returns:
            Tuple of (is_valid, reason_if_invalid)
        """
        # Get the question text
        question_text = question_text.strip()
        
        # Only reject completely empty questions
        if not question_text:
            return False, "Question is empty"
            
        # Check if it's too long
        if len(question_text) > 500:
            return False, "Question is too long"
            
        # Accept everything else - we'll be very lenient
        # This ensures all reasonable questions are accepted
        return True, None
    
    def _detect_intent(self, doc, normalized_text: str, blob=None) -> Tuple[QuestionIntent, float]:
        """
        Detect the intent of a question using NLP and pattern matching.
        Uses TextBlob for sentiment and subjectivity analysis if available.
        
        Args:
            doc: spaCy processed document
            normalized_text: Normalized question text
            blob: TextBlob object if available
            
        Returns:
            Tuple of (intent, confidence)
        """
        question_lower = normalized_text.lower()
        
        # Use TextBlob for additional NLP features if available
        sentiment_score = 0
        if blob is not None:
            # TextBlob provides sentiment analysis which can help determine question intent
            sentiment_score = blob.sentiment.polarity
        
        # Check for statistical questions first
        if ('how many' in question_lower or 
            'count' in question_lower or 
            'number of' in question_lower or 
            'total' in question_lower or 
            'statistics' in question_lower):
            
            if ('function' in question_lower or 'functions' in question_lower or
                'method' in question_lower or 'methods' in question_lower or
                'class' in question_lower or 'classes' in question_lower or
                'module' in question_lower or 'modules' in question_lower or
                'file' in question_lower or 'files' in question_lower):
                return QuestionIntent.STATISTICS, 0.95
        
        # Check for "what methods does X have" pattern (METHOD_LISTING) - this has high priority
        if (re.search(r'what (?:methods|functions) (?:does|do) [a-zA-Z0-9_]+ have', question_lower) or 
            re.search(r'methods (?:of|in) [a-zA-Z0-9_]+', question_lower) or
            'list methods' in question_lower or 
            'list functions' in question_lower or
            'methods of' in question_lower or
            'methods in' in question_lower or
            'what methods' in question_lower or
            'what functions' in question_lower):
            return QuestionIntent.METHOD_LISTING, 0.9
            
        # Check for "how is X implemented" pattern (IMPLEMENTATION)
        if (re.search(r'how (?:is|are) [a-zA-Z0-9_]+ implemented', question_lower) or 
            'implementation' in question_lower or
            'how does it work internally' in question_lower or
            'system implemented' in question_lower or
            'how is the' in question_lower and 'implemented' in question_lower):
            return QuestionIntent.IMPLEMENTATION, 0.9
        
        # Check for "explain" pattern - this is tricky as it could be CODE_WALKTHROUGH or PURPOSE
        # We need to be more specific about when to classify as CODE_WALKTHROUGH
        if ('walk me through' in question_lower or 
            'walk through' in question_lower or 
            'understand this code' in question_lower):
            return QuestionIntent.CODE_WALKTHROUGH, 0.85
            
        # For "explain X" questions, default to PURPOSE unless it's clearly about code implementation
        if 'explain' in question_lower:
            # If it contains implementation-related words, it's a CODE_WALKTHROUGH
            if any(word in question_lower for word in ['implementation', 'how it works', 'step by step', 'algorithm']):
                return QuestionIntent.CODE_WALKTHROUGH, 0.85
            # Otherwise, it's likely a PURPOSE question
            return QuestionIntent.PURPOSE, 0.8
            
        # Check for "how do I use X" pattern (USAGE_EXAMPLE)
        if (re.search(r'how (?:do|can|to) (?:i|we|you)? use [a-zA-Z0-9_]+', question_lower) or 
            'example' in question_lower or
            'usage' in question_lower or
            'how to use' in question_lower):
            return QuestionIntent.USAGE_EXAMPLE, 0.85
            
        # Check for "how does X use Y" pattern (PARAMETER_USAGE)
        if (re.search(r'how (?:does|do) [a-zA-Z0-9_]+ use [a-zA-Z0-9_]+', question_lower) or 
            'parameter' in question_lower or
            'argument' in question_lower):
            return QuestionIntent.PARAMETER_USAGE, 0.85
            
        # Check for "what does X do" pattern (PURPOSE)
        if (re.search(r'what (?:does|do|is) [a-zA-Z0-9_]+ (?:do|mean|used for)', question_lower) or
            'purpose of' in question_lower or
            'what is the purpose' in question_lower or
            'explain the purpose' in question_lower):
            return QuestionIntent.PURPOSE, 0.9
            
        # Check for "how does X handle errors" pattern (ERROR_HANDLING)
        if (re.search(r'how (?:does|do) [a-zA-Z0-9_]+ handle (?:errors|exceptions)', question_lower) or 
            'error handling' in question_lower or
            'exception' in question_lower):
            return QuestionIntent.ERROR_HANDLING, 0.85
            
        # Check for "what design pattern does X use" pattern (DESIGN_PATTERN)
        if (re.search(r'what design pattern (?:does|do) [a-zA-Z0-9_]+ use', question_lower) or 
            'design pattern' in question_lower or
            'architecture' in question_lower):
            return QuestionIntent.DESIGN_PATTERN, 0.9
            
        # Check for "what dependencies does X have" pattern (DEPENDENCY)
        if (re.search(r'what dependencies (?:does|do) [a-zA-Z0-9_]+ have', question_lower) or 
            'dependency' in question_lower or
            'dependencies' in question_lower or
            'imports' in question_lower):
            return QuestionIntent.DEPENDENCY, 0.85
        
        # If we can't determine a specific intent, default to PURPOSE as it's the most general
        return QuestionIntent.PURPOSE, 0.4
    
    def _extract_entities(self, doc, intent: QuestionIntent, blob=None) -> Dict[str, EntityType]:
        """
        Extract entities from a question using spaCy and TextBlob.
        
        Args:
            doc: spaCy processed document
            intent: The detected question intent
            blob: TextBlob object if available
            
        Returns:
            Dictionary mapping entity names to their types
        """
        # For statistical questions, we don't need to extract entities
        if intent == QuestionIntent.STATISTICS:
            return {}
            
        # Get the question text
        question_text = doc.text
        question_lower = question_text.lower()
        entities = {}
        
        # List of common words to exclude as entities
        common_words = [
            'the', 'and', 'or', 'what', 'how', 'why', 'when', 'where', 'who', 'which', 
            'explain', 'tell', 'show', 'list', 'find', 'get', 'use', 'using', 'used',
            'implement', 'implementation', 'function', 'method', 'class', 'variable',
            'this', 'that', 'these', 'those', 'there', 'here', 'have', 'has', 'had',
            'does', 'do', 'did', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'can', 'could', 'will', 'would', 'shall', 'should', 'may', 'might',
            'must', 'about', 'above', 'across', 'after', 'against', 'along', 'among',
            'around', 'at', 'before', 'behind', 'below', 'beneath', 'beside', 'between',
            'beyond', 'but', 'by', 'despite', 'down', 'during', 'except', 'for', 'from',
            'in', 'inside', 'into', 'like', 'near', 'of', 'off', 'on', 'onto', 'out',
            'outside', 'over', 'past', 'since', 'through', 'throughout', 'to', 'toward',
            'under', 'underneath', 'until', 'up', 'upon', 'with', 'within', 'without'
        ]
        
        # First try to extract entities using targeted regex patterns - these are the most reliable
        targeted_patterns = [
            # What does X do?
            (r"what (?:does|do|is) ([a-zA-Z][a-zA-Z0-9_]+) (?:do|mean|used for)", question_lower),
            # How does X work?
            (r"how (?:does|do) ([a-zA-Z][a-zA-Z0-9_]+) work", question_lower),
            # How to use X?
            (r"how to use ([a-zA-Z][a-zA-Z0-9_]+)", question_lower),
            # Explain X
            (r"explain (?:the|) ([a-zA-Z][a-zA-Z0-9_]+)", question_lower),
            # Tell me about X
            (r"tell me about (?:the|) ([a-zA-Z][a-zA-Z0-9_]+)", question_lower),
            # What methods does X have?
            (r"what (?:methods|functions) (?:does|do) (?:the|) ([a-zA-Z][a-zA-Z0-9_]+) have", question_lower),
            # How does X use Y?
            (r"how (?:does|do) (?:the|) ([a-zA-Z][a-zA-Z0-9_]+) use ([a-zA-Z][a-zA-Z0-9_]+)", question_lower),
            # Purpose of X
            (r"purpose of (?:the|) ([a-zA-Z][a-zA-Z0-9_]+)", question_lower),
        ]
        
        for pattern, text in targeted_patterns:
            matches = re.findall(pattern, text)
            if matches:
                for match in matches:
                    # Handle tuple results from regex groups
                    if isinstance(match, tuple):
                        for m in match:
                            if m and len(m) > 2 and m.lower() not in common_words:
                                entities[m] = self._guess_entity_type(m)
                    elif match and len(match) > 2 and match.lower() not in common_words:
                        entities[match] = self._guess_entity_type(match)
        
        # If we didn't find entities with targeted patterns, look for code identifiers by naming convention
        if not entities:
            # Look for code identifiers with specific naming conventions
            code_patterns = [
                # Original text for case-sensitive patterns
                (r"([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)*)", question_text),  # PascalCase
                (r"([a-z][a-z0-9]*(?:_[a-z0-9]+)+)", question_text),  # snake_case
                (r"([a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+)", question_text)  # camelCase
            ]
            
            for pattern, text in code_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    if (match and len(match) > 2 and 
                        match.lower() not in common_words and
                        not any(match.lower() == word.lower() for word in common_words)):
                        entities[match] = self._guess_entity_type(match)
        
        # Use TextBlob for noun phrase extraction if available and we haven't found entities yet
        if not entities and blob is not None:
            for phrase in blob.noun_phrases:
                # Clean up the phrase and check if it looks like a code identifier
                clean_phrase = phrase.replace(' ', '')
                if (len(clean_phrase) > 2 and 
                    re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', clean_phrase) and
                    clean_phrase.lower() not in common_words):
                    entities[clean_phrase] = self._guess_entity_type(clean_phrase)
        
        # If we still didn't find entities, look for code-like identifiers in spaCy tokens
        if not entities:
            for token in doc:
                # Skip very short tokens, stopwords, and punctuation
                if (len(token.text) <= 2 or 
                    token.is_stop or 
                    token.is_punct or 
                    token.text.lower() in common_words):
                    continue
                    
                # Check for code identifier patterns
                if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', token.text):  # Valid identifier name
                    entities[token.text] = self._guess_entity_type(token.text)
        
        return entities
        
    def _guess_entity_type(self, identifier: str) -> EntityType:
        """Guess the entity type based on naming conventions."""
        # Check for common keywords in the identifier
        lower_id = identifier.lower()
        
        # Check naming conventions
        if identifier[0].isupper() and any(c.islower() for c in identifier):  # PascalCase
            if any(word in lower_id for word in ['exception', 'error']):
                return EntityType.CLASS
            return EntityType.CLASS
            
        elif '_' in identifier:  # snake_case
            if any(word in lower_id for word in ['test', 'check']):
                return EntityType.FUNCTION
            return EntityType.FUNCTION
            
        elif identifier[0].islower() and any(c.isupper() for c in identifier):  # camelCase
            if any(word in lower_id for word in ['get', 'set', 'is', 'has']):
                return EntityType.METHOD
            return EntityType.METHOD
            
        # Check for common keywords
        if any(word in lower_id for word in ['class', 'interface', 'enum']):
            return EntityType.CLASS
        elif any(word in lower_id for word in ['function', 'method', 'procedure']):
            return EntityType.FUNCTION
        elif any(word in lower_id for word in ['param', 'arg', 'argument', 'parameter']):
            return EntityType.PARAMETER
        elif any(word in lower_id for word in ['var', 'variable', 'const', 'constant']):
            return EntityType.VARIABLE
        elif any(word in lower_id for word in ['module', 'package', 'namespace']):
            return EntityType.MODULE
        elif any(word in lower_id for word in ['file', 'document']):
            return EntityType.FILE
            
        return EntityType.UNKNOWN
