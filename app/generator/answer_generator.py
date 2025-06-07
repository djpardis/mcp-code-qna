"""
Answer generation component for producing responses to questions about code.
"""

import re
import logging
import html
import json
import os
from typing import List, Dict, Any, Optional

from app.retriever.retriever import RetrievedChunk
from app.generator.question_understanding import QuestionUnderstanding, QuestionIntent, EntityType


class AnswerGenerator:
    """Generator for creating answers based on retrieved code chunks"""
    
    def __init__(self):
        self.question_understanding = QuestionUnderstanding()
        self.logger = logging.getLogger(__name__)
    
    def generate(self, question: str, retrieved_chunks: List[RetrievedChunk]) -> str:
        """
        Generate an answer to a question based on retrieved code chunks
        
        Args:
            question: The question to answer
            retrieved_chunks: List of relevant code chunks with scores
            
        Returns:
            Markdown-formatted answer
        """
        if not question or question.strip() == '':
            return "Please ask a question about the code repository."
            
        # Analyze the question to understand intent and entities
        question_analysis = self.question_understanding.analyze_question(question)
        
        # Log the question analysis for debugging
        self.logger.info(f"Question analysis: {json.dumps(question_analysis.to_dict(), indent=2)}")
        
        # Handle invalid questions
        if not question_analysis.is_valid:
            return f"I'm having trouble understanding your question: {question_analysis.invalid_reason}. Could you please rephrase it to be more specific about the code you're asking about?"
        
        if not retrieved_chunks:
            return "I couldn't find any relevant code to answer your question."
        
        # Process the question based on the detected intent
        answer = self._process_question(question, retrieved_chunks, question_analysis)
        
        return answer
    
    def _process_question(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """
        Process the question and generate an appropriate answer based on intent analysis
        
        Args:
            question: The original question text
            chunks: Retrieved code chunks
            analysis: QuestionAnalysis object with intent and entities
            
        Returns:
            Markdown-formatted answer
        """
        if not analysis.is_valid:
            return "I'm sorry, but I don't understand your question. Please try rephrasing it or ask a different question about the code."
        
        try:
            # Route to specialized answer methods based on intent
            if analysis.intent == QuestionIntent.PURPOSE:
                return self._answer_class_purpose(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.IMPLEMENTATION:
                return self._answer_implementation(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.PARAMETER_USAGE:
                return self._answer_parameter_usage(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.METHOD_LISTING:
                return self._answer_class_methods(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.CODE_WALKTHROUGH:
                return self._answer_code_walkthrough(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.USAGE_EXAMPLE:
                return self._answer_usage_example(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.ERROR_HANDLING:
                return self._answer_error_handling(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.DESIGN_PATTERN:
                return self._answer_design_pattern(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.DEPENDENCY:
                return self._answer_dependency(question, chunks, analysis)
            elif analysis.intent == QuestionIntent.STATISTICS:
                return self._answer_statistics(question, chunks, analysis)
            else:
                # Fallback to general answer
                return self._general_answer(question, chunks, analysis)
        except Exception as e:
            logging.error(f"Error processing intent {analysis.intent}: {str(e)}")
            # Fallback to general answer on errors
            return self._general_answer(question, chunks, analysis)
    
    def _answer_class_purpose(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate an answer about a class's purpose"""
        # Get entity names from the analysis
        class_names = [name for name, entity_type in analysis.entities.items() 
                     if entity_type == EntityType.CLASS]
        
        # If no class found, try with UNKNOWN entities that might be classes
        if not class_names:
            # Look for PascalCase names in UNKNOWN entities which are likely classes
            class_names = [name for name, entity_type in analysis.entities.items() 
                         if entity_type == EntityType.UNKNOWN and name[0].isupper()]
        
        # If still no class found, try to find it in the question with regex as fallback
        if not class_names:
            match = re.search(r'what does (the )?(class|module) ([\w_]+) do', question.lower())
            if match:
                class_names = [match.group(3)]
                
        if not class_names:
            # Look for any entities that might be classes in the retrieved chunks
            class_names = []
            for chunk in chunks:
                if chunk.chunk.type == "class":
                    class_names.append(chunk.chunk.name)
                    break
                    
        if not class_names:
            return self._general_answer(question, chunks, analysis)
            
        # Use the most likely class name
        class_name = class_names[0]
            
        # Find chunks related to this class
        class_chunks = [chunk for chunk in chunks 
                       if chunk.chunk.name.lower() == class_name.lower() 
                       and chunk.chunk.type == "class"]
        
        if class_chunks:
                main_chunk = class_chunks[0]
                
                # Start with the class docstring if available
                answer = ["## " + main_chunk.chunk.name]
                
                if main_chunk.chunk.docstring:
                    answer.append(main_chunk.chunk.docstring)
                
                # Include key methods to show functionality
                method_chunks = [chunk for chunk in chunks 
                                if chunk.chunk.parent_name == main_chunk.chunk.name 
                                and chunk.chunk.type == "method"]
                
                if method_chunks:
                    answer.append("\n### Key Methods:")
                    for method in method_chunks[:3]:  # Show at most 3 methods
                        answer.append(f"- `{method.chunk.name}`: " + 
                                     (method.chunk.docstring or "No description available"))
                
                # Include a code snippet of the class definition
                answer.append("\n### Class Definition:")
                code_lines = main_chunk.chunk.content.split('\n')
                # Limit to the first 15 lines or fewer
                display_lines = code_lines[:min(15, len(code_lines))]
                answer.append("```python\n" + '\n'.join(display_lines) + "\n```")
                
                if len(code_lines) > 15:
                    answer.append("*(Class implementation truncated for brevity)*")
                
                return '\n\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
    
    def _answer_implementation(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate an answer about implementation details"""
        # Get entity names from the analysis
        impl_entities = [name for name, entity_type in analysis.entities.items() 
                      if entity_type in (EntityType.FUNCTION, EntityType.METHOD, EntityType.CLASS)]                      
        
        # Fallback to regex if no entities found
        if not impl_entities:
            match = re.search(r'how is (the )?(service|component|function|method) ([\w_]+) implemented', question.lower())
            if match:
                item_type = match.group(2)
                item_name = match.group(3)
                impl_entities = [item_name]
        
        if impl_entities:
            item_name = impl_entities[0]
            
            # Find chunks related to this implementation
            if item_type == "service" or item_type == "component":
                # Look for classes or modules
                impl_chunks = [chunk for chunk in chunks 
                              if chunk.chunk.name.lower() == item_name.lower()]
            else:
                # Look for functions or methods
                impl_chunks = [chunk for chunk in chunks 
                              if chunk.chunk.name.lower() == item_name.lower() 
                              and (chunk.chunk.type == "function" or chunk.chunk.type == "method")]
            
            if impl_chunks:
                main_chunk = impl_chunks[0]
                
                # Create a detailed answer
                answer = [f"## Implementation of {main_chunk.chunk.name}"]
                
                if main_chunk.chunk.docstring:
                    answer.append(main_chunk.chunk.docstring)
                
                # Include the full code implementation
                answer.append("\n### Implementation:")
                answer.append(f"```python\n{main_chunk.chunk.content}\n```")
                
                # Add any additional information
                if main_chunk.chunk.type == "method" and main_chunk.chunk.parent_name:
                    answer.append(f"\nThis is a method of the `{main_chunk.chunk.parent_name}` class.")
                
                return '\n\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
    
    def _answer_parameter_usage(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate an answer about how a parameter is used"""
        # Extract method and parameter from analysis
        method_names = [name for name, entity_type in analysis.entities.items() 
                      if entity_type in (EntityType.FUNCTION, EntityType.METHOD)]
        param_names = [name for name, entity_type in analysis.entities.items() 
                     if entity_type == EntityType.PARAMETER]
        
        # Fallback to regex if needed
        if not method_names or not param_names:
            match = re.search(r'how does (the )?(method|function) ([\w_]+) use (the )?parameter ([\w_]+)', question.lower())
            if match:
                if not method_names:
                    method_names = [match.group(3)]
                if not param_names:
                    param_names = [match.group(5)]
                
        if method_names and param_names:
            method_name = method_names[0]
            param_name = param_names[0]
            
            # Find method chunks
            method_chunks = [chunk for chunk in chunks 
                            if chunk.chunk.name.lower() == method_name.lower() 
                            and (chunk.chunk.type == "function" or chunk.chunk.type == "method")]
            
            if method_chunks:
                method_chunk = method_chunks[0]
                
                # Find parameter usage in the method
                method_content = method_chunk.chunk.content
                param_pattern = re.compile(fr'\b{re.escape(param_name)}\b')
                param_matches = list(param_pattern.finditer(method_content))
                
                if param_matches:
                    # Create a detailed answer
                    answer = [f"## Parameter `{param_name}` in `{method_chunk.chunk.name}`"]
                    
                    # Check docstring for parameter documentation
                    if method_chunk.chunk.docstring:
                        docstring = method_chunk.chunk.docstring
                        param_doc = re.search(fr'(?:\:param|@param|Args:|Parameters:).*{re.escape(param_name)}.*?:(.+?)(?:\n\s*\:|\n\s*@|\n\n|\Z)', docstring, re.DOTALL)
                        if param_doc:
                            answer.append(f"**Parameter Description:** {param_doc.group(1).strip()}")
                    
                    # Include the full method code
                    answer.append("\n### Method Implementation:")
                    answer.append(f"```python\n{method_chunk.chunk.content}\n```")
                    
                    # Highlight parameter usage
                    answer.append("\n### Parameter Usage:")
                    lines = method_content.split('\n')
                    param_lines = set()
                    
                    for match in param_matches:
                        # Find the line number for this match
                        pos = match.start()
                        line_num = method_content[:pos].count('\n')
                        param_lines.add(line_num)
                    
                    # Extract lines with parameter usage and their context
                    usage_examples = []
                    processed_lines = set()
                    
                    for line_num in param_lines:
                        if line_num in processed_lines:
                            continue
                            
                        start_line = max(0, line_num - 1)
                        end_line = min(len(lines), line_num + 2)
                        
                        # Add these lines to the processed set
                        processed_lines.update(range(start_line, end_line))
                        
                        # Extract the context
                        context = '\n'.join(lines[start_line:end_line])
                        usage_examples.append(f"```python\n{context}\n```")
                    
                    if usage_examples:
                        answer.append('\n'.join(usage_examples))
                    
                    return '\n\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
    
    def _answer_class_methods(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate an answer listing all methods in a class"""
        # Get class name from analysis
        class_names = [name for name, entity_type in analysis.entities.items() 
                     if entity_type == EntityType.CLASS or entity_type == EntityType.UNKNOWN]
        
        # Fallback to regex if needed
        if not class_names:
            match = re.search(r'what (methods|functions) does (the )?(class )?(\w+) have', question.lower())
            if match:
                class_names = [match.group(4)]
                
        if class_names:
            class_name = class_names[0]
            
            # Find chunks related to this class
            class_chunks = [chunk for chunk in chunks 
                           if chunk.chunk.type == "class" and 
                           chunk.chunk.name.lower() == class_name.lower()]
            
            # Find all methods that belong to this class
            method_chunks = [chunk for chunk in chunks 
                            if chunk.chunk.parent_name and 
                            chunk.chunk.parent_name.lower() == class_name.lower() and
                            chunk.chunk.type in ["method", "function"]]
            
            if class_chunks and method_chunks:
                class_chunk = class_chunks[0]
                
                # Start with class information
                answer = [f"## Methods in class `{class_chunk.chunk.name}`"]
                
                if class_chunk.chunk.docstring:
                    answer.append(f"**Class purpose:** {class_chunk.chunk.docstring}\n")
                
                answer.append(f"The `{class_chunk.chunk.name}` class has the following methods:\n")
                
                # List all methods with their signatures and docstrings
                for method in method_chunks:
                    # Extract method signature from first line
                    signature = method.chunk.content.split('\n')[0].strip()
                    if len(signature) > 80:
                        signature = signature[:77] + "..."
                        
                    answer.append(f"### `{method.chunk.name}`")
                    
                    if method.chunk.docstring:
                        # Extract first sentence of docstring for brevity
                        docstring = method.chunk.docstring.split('.')[0] + '.'
                        answer.append(f"{docstring}\n")
                    
                    # Use simplest possible approach
                    if len(method.chunk.content.split('\n')) > 5:
                        # Just show the signature for longer methods
                        answer.append(f"**`{signature}`**")
                        answer.append(f"<details>\n<summary>View method code</summary>\n\n```python\n{method.chunk.content}\n```\n</details>\n")
                    else:
                        # For short methods, just show the content directly
                        answer.append(f"```python\n{method.chunk.content}\n```\n")
                
                return '\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
        
    def _answer_code_walkthrough(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate a step-by-step walkthrough of code execution flow"""
        # Get entity names from the analysis
        function_names = [name for name, entity_type in analysis.entities.items() 
                         if entity_type in (EntityType.FUNCTION, EntityType.METHOD)]
        
        # If no function found in analysis, try other approaches
        if not function_names and chunks:
            # Try to extract from the most relevant chunk
            main_chunk = chunks[0].chunk
            if main_chunk.type in ["function", "method"]:
                function_names = [main_chunk.name]
        
        if not function_names:
            return self._general_answer(question, chunks, analysis)
            
        function_name = function_names[0]
        
        # Find chunks related to this function
        function_chunks = [chunk for chunk in chunks 
                          if chunk.chunk.name.lower() == function_name.lower() 
                          and chunk.chunk.type in ["function", "method"]]
        
        if function_chunks:
            main_chunk = function_chunks[0]
            
            # Create the walkthrough answer
            answer = [f"## Code Walkthrough: `{main_chunk.chunk.name}`"]
            
            if main_chunk.chunk.docstring:
                answer.append(f"**Purpose:** {main_chunk.chunk.docstring}\n")
            
            # Show the full function code first
            answer.append(f"### Complete Function Code:\n```python\n{main_chunk.chunk.content}\n```\n")
            
            # Now provide a step-by-step walkthrough
            answer.append("### Step-by-Step Explanation:")
            
            # Split the function into logical segments and explain
            lines = main_chunk.chunk.content.split('\n')
            
            # Skip function definition line
            current_block = []
            blocks = []
            
            for i, line in enumerate(lines):
                if i == 0:  # Function signature
                    blocks.append(("Function signature", [line]))
                    continue
                    
                # Identify logical blocks - comments often separate logical blocks
                if line.strip().startswith('#') and current_block:
                    blocks.append(("Code block", current_block))
                    current_block = [line]
                # Empty lines might separate logical blocks
                elif not line.strip() and current_block:
                    current_block.append(line)
                    if len(''.join(current_block).strip()) > 0:
                        blocks.append(("Code block", current_block))
                    current_block = []
                # Function returns often mark the end of a logical block
                elif line.strip().startswith('return ') and current_block:
                    current_block.append(line)
                    blocks.append(("Return statement", current_block))
                    current_block = []
                # Control flow statements often start new logical blocks
                elif any(stmt in line for stmt in ['if ', 'elif ', 'else:', 'for ', 'while ', 'try:', 'except ', 'finally:', 'with ']) and current_block:
                    if len(''.join(current_block).strip()) > 0:
                        blocks.append(("Code block", current_block))
                    current_block = [line]
                else:
                    current_block.append(line)
            
            # Add the last block if it's not empty
            if current_block and len(''.join(current_block).strip()) > 0:
                blocks.append(("Code block", current_block))
            
            # Now explain each logical block
            for i, (block_type, block_lines) in enumerate(blocks):
                block_code = '\n'.join(block_lines)
                
                if block_type == "Function signature":
                    answer.append(f"**Step 1:** Function definition\n```python\n{block_code}\n```\n"
                                 f"This defines the function `{main_chunk.chunk.name}` and its parameters.")
                elif block_type == "Return statement":
                    answer.append(f"**Step {i+1}:** Return statement\n```python\n{block_code}\n```\n"
                                 f"This returns the final result from the function.")
                else:
                    # Analyze the code segment to provide a meaningful explanation
                    if any(stmt in block_code for stmt in ['if ', 'elif ', 'else:']):
                        block_desc = "Conditional logic that checks conditions and executes different code paths"
                    elif any(stmt in block_code for stmt in ['for ', 'while ']):
                        block_desc = "Loop that iterates over data"
                    elif any(stmt in block_code for stmt in ['try:', 'except ', 'finally:']):
                        block_desc = "Error handling logic"
                    elif '=' in block_code and not '==' in block_code:
                        block_desc = "Variable assignment and data preparation"
                    elif any(func + '(' in block_code for func in ['map', 'filter', 'reduce', 'sorted']):
                        block_desc = "Functional data transformation"
                    else:
                        block_desc = "Code block that processes data"
                        
                    answer.append(f"**Step {i+1}:** {block_desc}\n```python\n{block_code}\n```")
            
            return '\n\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
        
    def _answer_usage_example(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate answer with usage examples of a class, function or method"""
        # Get entity names from the analysis
        entity_names = [name for name, entity_type in analysis.entities.items() 
                      if entity_type in (EntityType.FUNCTION, EntityType.METHOD, EntityType.CLASS)]                      
        
        # If no entity found in analysis, try other approaches
        if not entity_names and chunks:
            # Try to extract from the most relevant chunk
            main_chunk = chunks[0].chunk
            entity_names = [main_chunk.name]
        
        if not entity_names:
            return self._general_answer(question, chunks, analysis)
            
        entity_name = entity_names[0]
        
        # Find chunks related to this entity
        entity_chunks = [chunk for chunk in chunks 
                        if chunk.chunk.name.lower() == entity_name.lower()]
        
        # Find chunks where this entity is used - look in the content
        usage_chunks = [chunk for chunk in chunks 
                       if entity_name in chunk.chunk.content and 
                       chunk.chunk.name.lower() != entity_name.lower()]  # Not the entity itself
        
        if entity_chunks:
            main_chunk = entity_chunks[0]
            
            # Start building the answer
            answer = [f"## Usage Examples for `{main_chunk.chunk.name}`"]
            
            if main_chunk.chunk.docstring:
                answer.append(f"**Description:** {main_chunk.chunk.docstring}\n")
            
            # Show the entity signature or basic info
            if main_chunk.chunk.type in ["function", "method"]:
                # Extract just the function signature
                signature = main_chunk.chunk.content.split('\n')[0].strip()
                answer.append(f"**Signature:** `{signature}`\n")
            elif main_chunk.chunk.type == "class":
                # Extract the class definition and init method if available
                class_def = main_chunk.chunk.content.split('\n')[0].strip()
                answer.append(f"**Class Definition:** `{class_def}`\n")
                
                # Look for __init__ method in the chunks
                init_chunks = [chunk for chunk in chunks 
                              if chunk.chunk.name == "__init__" and 
                              chunk.chunk.parent_name == main_chunk.chunk.name]
                if init_chunks:
                    init_sig = init_chunks[0].chunk.content.split('\n')[0].strip()
                    answer.append(f"**Constructor:** `{init_sig}`\n")
            
            # Now show usage examples
            if usage_chunks:
                answer.append("### Examples of usage in the codebase:")
                
                for i, usage in enumerate(usage_chunks[:3], 1):  # Limit to 3 examples
                    answer.append(f"\n#### Example {i}: In `{usage.chunk.name}`")
                    
                    if usage.chunk.parent_name:
                        answer.append(f"From class: `{usage.chunk.parent_name}`")
                        
                    answer.append(f"File: `{usage.chunk.file_path}`\n")
                    
                    # Find the lines where the entity is used
                    lines = usage.chunk.content.split('\n')
                    usage_lines = []
                    
                    for j, line in enumerate(lines):
                        if entity_name in line:
                            # Get a small context around this usage
                            start = max(0, j - 2)
                            end = min(len(lines), j + 3)
                            
                            if usage_lines and start <= usage_lines[-1][1]:
                                # Extend the previous context
                                usage_lines[-1] = (usage_lines[-1][0], end)
                            else:
                                # Add a new context
                                usage_lines.append((start, end))
                    
                    # Show each usage context
                    for start, end in usage_lines:
                        context = '\n'.join(lines[start:end])
                        answer.append(f"```python\n{context}\n```")
            else:
                # If no usage examples found, show documentation
                answer.append("### No usage examples found in the codebase.\n")
                answer.append(f"Here's the definition of `{main_chunk.chunk.name}` for reference:\n")
                answer.append(f"```python\n{main_chunk.chunk.content}\n```")
            
            return '\n\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
        
    def _answer_error_handling(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate answer about error handling in code"""
        # Get entity names from the analysis
        entity_names = [name for name, entity_type in analysis.entities.items() 
                       if entity_type in (EntityType.FUNCTION, EntityType.METHOD, EntityType.CLASS)]                      
        
        # Find chunks with try-except blocks
        error_chunks = []
        for chunk in chunks:
            if 'try:' in chunk.chunk.content and 'except' in chunk.chunk.content:
                error_chunks.append(chunk)
        
        # If we have a specific entity to focus on
        if entity_names:
            entity_name = entity_names[0]
            # Filter error handling chunks to those related to the entity
            entity_error_chunks = [chunk for chunk in error_chunks 
                                 if chunk.chunk.name.lower() == entity_name.lower() or 
                                    chunk.chunk.parent_name and chunk.chunk.parent_name.lower() == entity_name.lower()]
            if entity_error_chunks:
                error_chunks = entity_error_chunks
        
        if error_chunks:
            # Start building the answer
            answer = ["## Error Handling Analysis"]
            
            if entity_names:
                answer[0] = f"## Error Handling in `{entity_names[0]}`"
            
            # Analyze each error handling chunk
            for i, retrieved in enumerate(error_chunks[:3], 1):  # Limit to 3 examples
                chunk = retrieved.chunk
                
                answer.append(f"\n### {i}. Error handling in `{chunk.name}`")
                
                if chunk.parent_name:
                    answer.append(f"From class: `{chunk.parent_name}`")
                    
                answer.append(f"File: `{chunk.file_path}`\n")
                
                # Extract and analyze try-except blocks
                lines = chunk.content.split('\n')
                in_try_block = False
                current_try_block = []
                try_blocks = []
                
                for line in lines:
                    if 'try:' in line:
                        in_try_block = True
                        current_try_block = [line]
                    elif in_try_block and ('except ' in line or 'except:' in line):
                        current_try_block.append(line)
                    elif in_try_block and 'finally:' in line:
                        current_try_block.append(line)
                    elif in_try_block:
                        current_try_block.append(line)
                        # Check if this is the end of the try-except block
                        if not line.startswith((' ', '\t')) and current_try_block:
                            try_blocks.append(current_try_block)
                            current_try_block = []
                            in_try_block = False
                
                # Add the last block if it's not empty
                if current_try_block:
                    try_blocks.append(current_try_block)
                
                # Analyze and explain each try-except block
                for j, block in enumerate(try_blocks, 1):
                    block_str = '\n'.join(block)
                    # Ensure proper code block formatting with triple backticks
                    answer.append(f"#### Error handling block {j}:")
                    answer.append(f"```python\n{block_str}\n```")
                    
                    # Analyze what exceptions are caught
                    exceptions = []
                    for line in block:
                        if 'except ' in line:
                            exc_match = re.search(r'except\s+([\w\., ]+)(\s+as\s+\w+)?:', line)
                            if exc_match:
                                exceptions.append(exc_match.group(1))
                            else:
                                exceptions.append("All exceptions (generic except clause)")
                    
                    if exceptions:
                        answer.append("**Exceptions handled:**")
                        for exc in exceptions:
                            answer.append(f"- `{exc}`")
                    
                    # Look for common error handling patterns
                    if any('log' in line.lower() for line in block):
                        answer.append("**Pattern:** Logs the error for debugging/monitoring")
                    if any('raise ' in line for line in block):
                        answer.append("**Pattern:** Re-raises the exception or raises a different one")
                    if any('return ' in line for line in block):
                        answer.append("**Pattern:** Returns a fallback value or error indicator")
                    if any('continue' in line for line in block):
                        answer.append("**Pattern:** Continues execution in a loop despite the error")
                    if any('break' in line for line in block):
                        answer.append("**Pattern:** Exits the loop when an error occurs")
            
            return '\n\n'.join(answer)
        
        # No error handling code found, provide a general response
        if entity_names:
            answer = [f"## Error Handling in `{entity_names[0]}`\n",
                     "No specific error handling code was found for this entity. "
                     "The code might not have explicit error handling, or it might rely on error handling from calling functions."]
            return '\n'.join(answer)
        else:
            return "I couldn't find any specific error handling code in the retrieved chunks. "\
                   "The code might handle errors at a different level, or it might not have explicit error handling."
        
    def _answer_design_pattern(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate answer about design patterns used in the code"""
        # Get entity names from the analysis
        entity_names = [name for name, entity_type in analysis.entities.items() 
                       if entity_type in (EntityType.CLASS, EntityType.MODULE)]
        
        # Common design pattern indicators
        patterns = {
            'Factory': ['create', 'factory', 'build', 'construct', 'new', 'make'],
            'Singleton': ['instance', 'getInstance', 'shared', 'single', 'get_instance'],
            'Observer': ['observer', 'subscribe', 'notify', 'publish', 'listen', 'event', 'on_'],
            'Strategy': ['strategy', 'algorithm', 'policy', 'behavior', 'context'],
            'Decorator': ['decorator', 'wrap', 'extend', 'enhance'],
            'Adapter': ['adapter', 'adapt', 'convert', 'bridge', 'interface'],
            'Command': ['command', 'execute', 'invoke', 'action', 'handler'],
            'Repository': ['repository', 'repo', 'store', 'storage', 'dao'],
            'Service': ['service', 'manager', 'coordinator', 'controller'],
            'Builder': ['builder', 'build', 'construct', 'create_'],
            'Composite': ['composite', 'component', 'tree', 'children', 'parent'],
            'MVC': ['model', 'view', 'controller', 'presenter'],
            'Dependency Injection': ['inject', 'provider', 'container', 'register', 'resolve']  
        }
        
        # Focus on the entity if available, otherwise analyze all chunks
        target_chunks = chunks
        if entity_names:
            entity_name = entity_names[0]
            # Look for chunks where this entity is defined or used
            entity_chunks = [chunk for chunk in chunks 
                            if chunk.chunk.name.lower() == entity_name.lower() or 
                              (chunk.chunk.parent_name and chunk.chunk.parent_name.lower() == entity_name.lower())]  
            if entity_chunks:
                target_chunks = entity_chunks
        
        # Detect design patterns in the chunks
        detected_patterns = {}
        for chunk in target_chunks:
            # Extract class and function names that might indicate patterns
            content = chunk.chunk.content.lower()
            name = chunk.chunk.name.lower()
            
            for pattern, keywords in patterns.items():
                score = 0
                # Check if pattern keywords appear in code
                for keyword in keywords:
                    if keyword.lower() in name:
                        score += 3  # Higher weight for name matches
                    if keyword.lower() in content:
                        score += 1
                
                # Check for pattern-specific structural indicators
                if pattern == 'Singleton' and ('_instance' in content or 'instance = None' in content):
                    score += 5
                elif pattern == 'Factory' and ('return ' in content and any(k in content for k in ['new ', 'class(', 'instance'])):
                    score += 5
                elif pattern == 'Strategy' and ('interface' in content or 'abstract' in content):
                    score += 3
                elif pattern == 'Decorator' and '@' in content:
                    score += 3
                
                if score > 3:  # Threshold for pattern detection
                    if pattern not in detected_patterns or detected_patterns[pattern]['score'] < score:
                        detected_patterns[pattern] = {
                            'score': score,
                            'chunk': chunk.chunk,
                            'explanation': self._generate_pattern_explanation(pattern, chunk.chunk)
                        }
        
        # Generate the answer based on detected patterns
        if detected_patterns:
            # Start building the answer
            answer = []
            
            if entity_names:
                answer.append(f"## Design Patterns in `{entity_names[0]}`")
            else:
                answer.append("## Design Patterns Detected in Code")
            
            # Show the detected patterns in order of confidence
            sorted_patterns = sorted(detected_patterns.items(), key=lambda x: x[1]['score'], reverse=True)
            
            for pattern_name, data in sorted_patterns:
                chunk = data['chunk']
                explanation = data['explanation']
                confidence = "High" if data['score'] > 7 else "Medium" if data['score'] > 5 else "Low"
                
                answer.append(f"\n### {pattern_name} Pattern")
                answer.append(f"**Confidence:** {confidence}")
                answer.append(f"**Detected in:** `{chunk.name}`")
                
                if chunk.parent_name:
                    answer.append(f"From class: `{chunk.parent_name}`")
                    
                answer.append(f"File: `{chunk.file_path}`\n")
                answer.append(f"**Explanation:** {explanation}\n")
                
                # Show relevant code
                code_lines = chunk.content.split('\n')
                total_lines = len(code_lines)
                
                if total_lines > 15:  # Only show a preview for long code
                    preview = "\n".join(code_lines[:15])
                    answer.append(f"```python\n{preview}\n# ... ({total_lines-15} more lines not shown)\n```")
                    answer.append(f"<details>\n<summary>View full code</summary>\n\n```python\n{chunk.content}\n```\n</details>")
                else:
                    # For short code, show it directly
                    answer.append(f"```python\n{chunk.content}\n```")
            
            return '\n\n'.join(answer)
        else:
            # No patterns detected
            if entity_names:
                return f"I couldn't identify any clear design patterns in the `{entity_names[0]}` code. " \
                       "The code may be using a simple procedural or object-oriented approach without specific design patterns."
            else:
                return "I couldn't identify any clear design patterns in the retrieved code chunks. " \
                       "The code may be using a simple procedural or object-oriented approach without specific design patterns."
    
    def _generate_pattern_explanation(self, pattern: str, chunk) -> str:
        """Generate an explanation for why a pattern was detected"""
        if pattern == 'Factory':
            return "This code appears to implement the Factory pattern because it centralizes object creation logic, " \
                   "creating objects without exposing the instantiation logic to clients."
        elif pattern == 'Singleton':
            return "This code implements the Singleton pattern to ensure a class has only one instance " \
                   "and provides a global point of access to it."
        elif pattern == 'Observer':
            return "This code follows the Observer pattern where objects (observers) register to receive updates " \
                   "when another object (subject) changes state."
        elif pattern == 'Strategy':
            return "This code uses the Strategy pattern to define a family of algorithms, encapsulating each one, " \
                   "and making them interchangeable."
        elif pattern == 'Decorator':
            return "This code implements the Decorator pattern to add new functionality to objects " \
                   "dynamically without altering their structure."
        elif pattern == 'Adapter':
            return "This code follows the Adapter pattern to convert the interface of a class " \
                   "into another interface clients expect."
        elif pattern == 'Command':
            return "This code uses the Command pattern to encapsulate a request as an object, " \
                   "allowing for parameterization of clients with queuing, logging, or undo operations."
        elif pattern == 'Repository':
            return "This code implements the Repository pattern to separate the logic that retrieves data " \
                   "from the underlying storage, centralizing data access logic."
        elif pattern == 'Service':
            return "This code follows the Service pattern to encapsulate business logic " \
                   "in a separate layer from other parts of the application."
        elif pattern == 'Builder':
            return "This code implements the Builder pattern to separate the construction of complex objects " \
                   "from their representation."
        elif pattern == 'Composite':
            return "This code uses the Composite pattern to compose objects into tree structures " \
                   "to represent part-whole hierarchies."
        elif pattern == 'MVC':
            return "This code follows the Model-View-Controller (MVC) pattern to separate application concerns " \
                   "into model (data), view (user interface), and controller (business logic) components."
        elif pattern == 'Dependency Injection':
            return "This code implements Dependency Injection to reduce coupling " \
                   "by injecting dependencies rather than having components create or find them."
        else:
            return f"This code appears to implement the {pattern} pattern based on its structure and naming patterns."
    
    def _answer_dependency(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate answer about dependencies and relationships between code components"""
        # Get entity names from the analysis
        entity_names = [name for name, entity_type in analysis.entities.items() 
                      if entity_type in (EntityType.CLASS, EntityType.FUNCTION, EntityType.METHOD, EntityType.MODULE)]
        
        if not entity_names and chunks:
            # Try to extract from the most relevant chunk
            main_chunk = chunks[0].chunk
            entity_names = [main_chunk.name]
        
        if not entity_names:
            return self._general_answer(question, chunks, analysis)
            
        entity_name = entity_names[0]
        
        # Find chunks related to this entity
        entity_chunks = [chunk for chunk in chunks 
                        if chunk.chunk.name.lower() == entity_name.lower()]
        
        # Find chunks that depend on this entity (they import or use it)
        dependent_chunks = [chunk for chunk in chunks 
                          if entity_name in chunk.chunk.content and 
                          chunk.chunk.name.lower() != entity_name.lower()]  # Not the entity itself
        
        # Find chunks that this entity depends on (it imports or uses them)
        dependencies = []
        import_pattern = r'(?:from|import)\s+([\w\.]+)(?:\s+import\s+([\w\., ]+))?'
        usage_pattern = r'([A-Z][A-Za-z0-9_]+)\s*\(|([A-Z][A-Za-z0-9_]+)\.[a-z]'
        
        if entity_chunks:
            main_chunk = entity_chunks[0]
            content = main_chunk.chunk.content
            
            # Look for import statements
            import_matches = re.finditer(import_pattern, content)
            for match in import_matches:
                if match.group(2):  # from X import Y
                    module = match.group(1)
                    imports = [x.strip() for x in match.group(2).split(',')]
                    for imp in imports:
                        dependencies.append({'type': 'import', 'name': f"{module}.{imp}"})
                else:  # import X
                    dependencies.append({'type': 'import', 'name': match.group(1)})
            
            # Look for class usage
            usage_matches = re.finditer(usage_pattern, content)
            for match in usage_matches:
                used_class = match.group(1) or match.group(2)
                if used_class and used_class != main_chunk.chunk.name:  # Don't include self-references
                    dependencies.append({'type': 'usage', 'name': used_class})
        
        # Build the answer
        if entity_chunks:
            main_chunk = entity_chunks[0]
            
            # Start building the answer
            answer = [f"## Dependencies for `{main_chunk.chunk.name}`"]
            
            if main_chunk.chunk.docstring:
                answer.append(f"**Description:** {main_chunk.chunk.docstring}\n")
            
            # Dependencies section - what this code uses
            answer.append("### This component depends on:")
            
            if dependencies:
                seen = set()  # Track unique dependencies
                for dep in dependencies:
                    if dep['name'] not in seen:
                        seen.add(dep['name'])
                        if dep['type'] == 'import':
                            answer.append(f"- Import: `{dep['name']}`")
                        else:
                            answer.append(f"- Usage: `{dep['name']}`")
            else:
                answer.append("- No direct dependencies detected")
            
            # Dependents section - what uses this code
            answer.append("\n### Components that depend on this:")
            
            if dependent_chunks:
                for i, chunk in enumerate(dependent_chunks[:5], 1):  # Limit to 5
                    answer.append(f"\n#### {i}. `{chunk.chunk.name}`")
                    
                    if chunk.chunk.parent_name:
                        answer.append(f"From class: `{chunk.chunk.parent_name}`")
                        
                    answer.append(f"File: `{chunk.chunk.file_path}`")
                    
                    # Find the specific usage context
                    lines = chunk.chunk.content.split('\n')
                    usage_contexts = []
                    
                    for j, line in enumerate(lines):
                        if entity_name in line:
                            # Get a small context around this usage
                            start = max(0, j - 1)
                            end = min(len(lines), j + 2)
                            context = '\n'.join(lines[start:end])
                            usage_contexts.append(context)
                    
                    if usage_contexts:
                        answer.append("Usage context:")
                        for context in usage_contexts[:2]:  # Limit contexts to keep answer focused
                            answer.append(f"```python\n{context}\n```")
            else:
                answer.append("- No components were found that depend on this code")
            
            # Suggest architectural role based on dependencies
            answer.append("\n### Architectural Role:")
            if not dependencies and dependent_chunks:
                answer.append("This appears to be a **core component** that other parts of the system depend on.")
            elif dependencies and not dependent_chunks:
                answer.append("This appears to be a **leaf component** that consumes other services but isn't used elsewhere.")
            elif dependencies and dependent_chunks:
                answer.append("This appears to be an **intermediary component** that consumes services and is used by other parts of the system.")
            else:
                answer.append("This component appears to be **isolated** with few or no direct connections to other parts of the system.")
            
            return '\n\n'.join(answer)
        
        # Fallback to general answer
        return self._general_answer(question, chunks, analysis)
        
    def _answer_statistics(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate answer about code statistics like counts of functions, classes, etc."""
        # Determine what type of item we're counting
        count_type = None
        question_lower = question.lower()
        
        if 'function' in question_lower or 'method' in question_lower:
            count_type = 'functions/methods'
        elif 'class' in question_lower:
            count_type = 'classes'
        elif 'module' in question_lower:
            count_type = 'modules'
        elif 'file' in question_lower:
            count_type = 'files'
        else:
            count_type = 'code items'  # Generic fallback
        
        # Extract the statistics from the chunks
        counts = {
            'function': 0,
            'method': 0,  # Methods are associated with classes
            'class': 0,
            'module': 0,
            'file': set()  # Use a set to avoid counting the same file multiple times
        }
        
        # Count the items in the retrieved chunks
        for retrieved in chunks:
            chunk = retrieved.chunk
            if chunk.type == 'function' and not chunk.parent_name:  # Top-level function
                counts['function'] += 1
            elif chunk.type == 'function' and chunk.parent_name:  # Method
                counts['method'] += 1
            elif chunk.type == 'class':
                counts['class'] += 1
            elif chunk.type == 'module':
                counts['module'] += 1
            
            # Track unique file paths
            if chunk.file_path:
                counts['file'].add(chunk.file_path)
        
        # Convert file set to count
        counts['file'] = len(counts['file'])
        
        # Check if we have enough data for a meaningful answer
        if sum(counts.values()) < 10:  # Arbitrary threshold
            # We likely don't have enough data from the retriever
            return ("I don't have complete statistics for the entire codebase. "
                   f"From the data available to me, I can see at least {counts['function']} functions, "
                   f"{counts['method']} methods, {counts['class']} classes, and code spread across "
                   f"{counts['file']} files. This is likely an underestimate of the total.")
        
        # Build a comprehensive statistics answer
        answer = ["## Code Statistics"]
        
        # Main count based on what was asked
        if count_type == 'functions/methods':
            total = counts['function'] + counts['method']
            answer.append(f"I found a total of **{total} functions and methods** in the codebase, consisting of:")
            answer.append(f"- **{counts['function']}** standalone functions")
            answer.append(f"- **{counts['method']}** class methods")
        elif count_type == 'classes':
            answer.append(f"I found a total of **{counts['class']} classes** in the codebase.")
        elif count_type == 'files':
            answer.append(f"I found **{counts['file']} files** containing code in the codebase.")
        else:  # Generic or other types
            answer.append("Here are the code statistics based on available data:")
            answer.append(f"- **{counts['function']}** standalone functions")
            answer.append(f"- **{counts['method']}** class methods")
            answer.append(f"- **{counts['class']}** classes")
            answer.append(f"- Code spread across **{counts['file']}** files")
        
        # Additional statistics and breakdowns if we have them
        function_per_class = counts['method'] / counts['class'] if counts['class'] > 0 else 0
        answer.append(f"\n### Additional Insights")
        answer.append(f"- Average methods per class: **{function_per_class:.1f}**")
        
        # Include distribution by file type if relevant
        file_extensions = {}
        for retrieved in chunks:
            if retrieved.chunk.file_path:
                ext = os.path.splitext(retrieved.chunk.file_path)[1].lower() or "(no extension)"
                if ext not in file_extensions:
                    file_extensions[ext] = 0
                file_extensions[ext] += 1
        
        if file_extensions:
            answer.append("\n### File Type Distribution")
            for ext, count in sorted(file_extensions.items(), key=lambda x: x[1], reverse=True)[:5]:  # Top 5
                percentage = (count / counts['file']) * 100 if counts['file'] > 0 else 0
                answer.append(f"- **{ext}**: {count} files ({percentage:.1f}%)")
        
        # Note about the data source
        answer.append("\n*Note: These statistics are based on the code chunks available to me and may not represent the entire codebase.*")
        
        return "\n\n".join(answer)
    
    def _general_answer(self, question: str, chunks: List[RetrievedChunk], analysis) -> str:
        """Generate a general answer based on retrieved chunks"""
        # Start with an introduction
        answer = ["I found the following code that might help answer your question:"]
        
        # Add up to 3 most relevant chunks with their code
        for i, retrieved in enumerate(chunks[:3], 1):
            chunk = retrieved.chunk
            
            answer.append(f"\n## {i}. {chunk.type.capitalize()}: `{chunk.name}`")
            
            if chunk.parent_name:
                answer.append(f"From class: `{chunk.parent_name}`")
            
            answer.append(f"File: `{chunk.file_path}`")
            
            if chunk.docstring:
                answer.append(f"\n**Description:** {chunk.docstring}")
            
            # Add a preview of the code snippet (first few lines)
            code_lines = chunk.content.split('\n')
            preview_lines = code_lines[:min(5, len(code_lines))]
            total_lines = len(code_lines)
            
            # Just use standard markdown code blocks - simple is better!
            if total_lines > 10:  # Only show 10 lines for preview
                preview = "\n".join(code_lines[:10])
                answer.append(f"```python\n{preview}\n# ... ({total_lines-10} more lines not shown)\n```")
                answer.append(f"<details>\n<summary>Show full code</summary>\n\n```python\n{chunk.content}\n```\n</details>")
            else:
                # For short code, just show it directly
                answer.append(f"```python\n{chunk.content}\n```")
        
        return '\n'.join(answer)
