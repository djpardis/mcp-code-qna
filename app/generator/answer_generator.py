"""
Answer generation component for producing responses to questions about code.
"""

import re
import logging
import html
from typing import List, Dict, Any, Optional

from app.retriever.retriever import RetrievedChunk


class AnswerGenerator:
    """Generator for creating answers based on retrieved code chunks"""
    
    def __init__(self):
        pass
    
    def generate(self, question: str, retrieved_chunks: List[RetrievedChunk]) -> str:
        """
        Generate an answer to a question based on retrieved code chunks
        
        Args:
            question: The question to answer
            retrieved_chunks: List of relevant code chunks with scores
            
        Returns:
            Markdown-formatted answer
        """
        if not retrieved_chunks:
            return "I couldn't find any relevant code to answer your question."
        
        # Process the question to determine the type of answer needed
        answer = self._process_question(question, retrieved_chunks)
        
        return answer
    
    def _process_question(self, question: str, chunks: List[RetrievedChunk]) -> str:
        """Process the question and generate an appropriate answer"""
        question_lower = question.lower()
        
        # Identify the type of question
        if re.search(r'what does (the )?(class|module) [\w_]+ do', question_lower):
            # Question about a class or module purpose
            return self._answer_class_purpose(question, chunks)
        elif re.search(r'how is (the )?(service|component|function|method) [\w_]+ implemented', question_lower):
            # Question about implementation details
            return self._answer_implementation(question, chunks)
        elif re.search(r'how does (the )?(method|function) [\w_]+ use (the )?parameter [\w_]+', question_lower):
            # Question about parameter usage
            return self._answer_parameter_usage(question, chunks)
        elif re.search(r'what (functions|methods) does (the )?(class )?(\w+) have', question_lower):
            # Question about functions in a class
            return self._answer_class_methods(question, chunks)
        else:
            # General code question
            return self._general_answer(question, chunks)
    
    def _answer_class_purpose(self, question: str, chunks: List[RetrievedChunk]) -> str:
        """Generate an answer about a class's purpose"""
        # Extract the class name from the question
        match = re.search(r'what does (the )?(class|module) ([\w_]+) do', question.lower())
        if match:
            class_name = match.group(3)
            
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
        return self._general_answer(question, chunks)
    
    def _answer_implementation(self, question: str, chunks: List[RetrievedChunk]) -> str:
        """Generate an answer about implementation details"""
        # Extract the service/component/function name from the question
        match = re.search(r'how is (the )?(service|component|function|method) ([\w_]+) implemented', question.lower())
        if match:
            item_type = match.group(2)
            item_name = match.group(3)
            
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
        return self._general_answer(question, chunks)
    
    def _answer_parameter_usage(self, question: str, chunks: List[RetrievedChunk]) -> str:
        """Generate an answer about how a parameter is used"""
        # Extract method and parameter names from the question
        match = re.search(r'how does (the )?(method|function) ([\w_]+) use (the )?parameter ([\w_]+)', question.lower())
        if match:
            method_name = match.group(3)
            param_name = match.group(5)
            
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
        return self._general_answer(question, chunks)
    
    def _answer_class_methods(self, question: str, chunks: List[RetrievedChunk]) -> str:
        """Generate an answer listing all methods in a class"""
        # Extract the class name from the question
        match = re.search(r'what (functions|methods) does (the )?(class )?(\w+) have', question.lower())
        if match:
            class_name = match.group(4)
            
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
        return self._general_answer(question, chunks)
        
    def _general_answer(self, question: str, chunks: List[RetrievedChunk]) -> str:
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
