#!/usr/bin/env python3
"""
Debug server script to identify component initialization issues
"""
import os
import sys
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add app directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.indexer.code_indexer import CodeIndexer
from app.retriever.retriever import Retriever, RetrievedChunk
from app.generator.answer_generator import AnswerGenerator

# Initialize components directly
repo_path = "/Users/pardisnoorzad/Documents/sample-python-repo"
print(f"Initializing components with repo path: {repo_path}")
indexer = CodeIndexer(repo_path=repo_path)
print("Building index...")
indexer.load_or_build_index()
retriever = Retriever(indexer=indexer)
generator = AnswerGenerator()
print("Components initialized successfully")

# Initialize FastAPI app
app = FastAPI(title="Debug MCP Server")

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/.well-known/mcp")
async def get_mcp_metadata():
    return {
        "api_version": "0.1.0",
        "server_name": "code-repository-qa",
        "server_version": "0.1.0",
        "capabilities": ["list_resources", "read_resource"],
        "description": "Debug MCP server for testing"
    }

@app.get("/list_resources")
async def list_resources():
    # Return a resource for asking questions about the repository
    return {
        "resources": [
            {
                "uri": "questions",
                "title": "Repository Q&A",
                "description": "Ask questions about the code repository",
                "metadata": {"repo_path": indexer.repo_path}
            }
        ],
        "cursor": None
    }

@app.post("/read_resource")
async def read_resource(request: Request):
    try:
        # Parse the request data
        request_data = await request.json()
        print(f"DEBUG: Received request: {request_data}")
        
        uri = request_data.get("uri")
        if uri != "questions":
            return JSONResponse(
                status_code=404, 
                content={"detail": f"Resource {uri} not found"}
            )
        
        # Extract the question from the request data
        parameters = request_data.get("parameters", {})
        question = parameters.get("question")
        if not question:
            return JSONResponse(
                status_code=400, 
                content={"detail": "No question provided"}
            )
        
        print(f"\n\nDEBUG: Processing question: {question}")
        
        # Add detailed debugging for question understanding
        try:
            from app.generator.question_understanding import QuestionUnderstanding, QuestionIntent, EntityType
            qu = QuestionUnderstanding()
            analysis = qu.analyze_question(question)
            print(f"DEBUG: Question analysis result:")
            print(f"  Intent: {analysis.intent.name if hasattr(analysis.intent, 'name') else analysis.intent}")
            print(f"  Entities: {analysis.entities}")
            print(f"  Confidence: {analysis.confidence}")
            print(f"  Is valid: {analysis.is_valid}")
            if not analysis.is_valid:
                print(f"  Invalid reason: {analysis.invalid_reason}")
        except Exception as e:
            import traceback
            print(f"ERROR in question analysis: {str(e)}")
            print(traceback.format_exc())
        
        # Pattern match question to understand what the user is asking
        # This will help debug the answer generator's pattern matching
        import re
        question_lower = question.lower()
        match_class = re.search(r'what does (the )?(class|module) ([\w_]+) do', question_lower)
        match_function = re.search(r'what does (the )?(function|method) ([\w_]+) do', question_lower)
        match_file = re.search(r'what does (the )?(file|module) ([\w_]+\.py) do', question_lower)
        # Enhanced regex for statistics questions to catch more variations
        match_stats = re.search(r'(how many|count|statistics|number of|total|sum|tally) (functions|methods|classes|files|code|lines|comments)', question_lower) or \
                     re.search(r'(code|repository|codebase) (statistics|metrics|analytics|overview|summary)', question_lower)
        
        if match_class:
            print(f"Question type: CLASS - Looking for class {match_class.group(3)}")
        elif match_function:
            print(f"Question type: FUNCTION - Looking for function {match_function.group(3)}")
        elif match_file:
            print(f"Question type: FILE - Looking for file {match_file.group(3)}")
        elif match_stats or analysis.intent == QuestionIntent.STATISTICS:
            print(f"Question type: STATISTICS - Looking for code statistics")
            # Handle statistics questions with direct file scanning
            
            # Direct file-based statistics calculation
            print("\nDEBUG: Using direct file-based statistics calculation")
            
            try:
                # Initialize counters
                counts = {
                    'function': 0,  # Top-level functions
                    'method': 0,    # Methods inside classes
                    'class': 0,     # Classes
                    'file': set(),  # Unique files
                    'file_types': {},  # File extensions
                    'lines': 0,    # Total lines of code
                    'empty_lines': 0,  # Empty lines
                    'comment_lines': 0  # Comment lines
                }
                
                # Get the repository path - make sure it exists
                repo_path = os.path.abspath(indexer.repo_path)
                if not os.path.exists(repo_path):
                    print(f"\nERROR: Repository path {repo_path} does not exist!")
                    # Try to find a valid path
                    if os.path.exists("/Users/pardisnoorzad/Documents/sample-python-repo"):
                        repo_path = "/Users/pardisnoorzad/Documents/sample-python-repo"
                        print(f"\nDEBUG: Using fallback repository path: {repo_path}")
                
                print(f"\nDEBUG: Scanning Python files in {repo_path}")
                
                # Use AST to parse Python files and count code elements
                import ast
                
                class CodeVisitor(ast.NodeVisitor):
                    def __init__(self):
                        self.classes = 0
                        self.functions = 0
                        self.methods = 0
                        self.current_class = None
                    
                    def visit_ClassDef(self, node):
                        self.classes += 1
                        old_class = self.current_class
                        self.current_class = node
                        # Visit all child nodes
                        self.generic_visit(node)
                        self.current_class = old_class
                    
                    def visit_FunctionDef(self, node):
                        if self.current_class is not None:
                            self.methods += 1
                        else:
                            self.functions += 1
                        self.generic_visit(node)
                    
                    # Also count async functions
                    def visit_AsyncFunctionDef(self, node):
                        if self.current_class is not None:
                            self.methods += 1
                        else:
                            self.functions += 1
                        self.generic_visit(node)
                
                # Walk through the directory structure
                for root, dirs, files in os.walk(repo_path):
                    for file in files:
                        # Track all file types
                        _, ext = os.path.splitext(file)
                        if ext:
                            # Remove the dot from extension
                            ext = ext[1:]
                            counts['file_types'][ext] = counts['file_types'].get(ext, 0) + 1
                        
                        if file.endswith('.py'):
                            file_path = os.path.join(root, file)
                            counts['file'].add(file_path)
                            
                            try:
                                # Parse the Python file
                                with open(file_path, 'r') as f:
                                    file_content = f.read()
                                    lines = file_content.split('\n')
                                    
                                    # Count lines
                                    counts['lines'] += len(lines)
                                    
                                    # Count empty lines and comments
                                    for line in lines:
                                        line = line.strip()
                                        if not line:
                                            counts['empty_lines'] += 1
                                        elif line.startswith('#'):
                                            counts['comment_lines'] += 1
                                
                                # Parse the AST
                                tree = ast.parse(file_content)
                                visitor = CodeVisitor()
                                visitor.visit(tree)
                                
                                # Update counts
                                counts['class'] += visitor.classes
                                counts['function'] += visitor.functions
                                counts['method'] += visitor.methods
                                
                            except Exception as e:
                                print(f"Error parsing {file_path}: {str(e)}")
                
                # Convert file set to count
                file_count = len(counts['file'])
                
                # Print detailed statistics for debugging
                print(f"\nDEBUG: Statistics Summary:")
                print(f"  - Functions: {counts['function']}")
                print(f"  - Methods: {counts['method']}")
                print(f"  - Classes: {counts['class']}")
                print(f"  - Python Files: {file_count}")
                print(f"  - Total Lines: {counts['lines']}")
                print(f"  - Code Lines: {counts['lines'] - counts['empty_lines'] - counts['comment_lines']}")
                print(f"  - Comment Lines: {counts['comment_lines']}")
                print(f"  - Empty Lines: {counts['empty_lines']}")
                
                # Print file type distribution
                print("\nDEBUG: File Type Distribution:")
                sorted_types = sorted(counts['file_types'].items(), key=lambda x: x[1], reverse=True)
                for ext, count in sorted_types[:10]:  # Show top 10 file types in debug
                    print(f"  - {ext}: {count} files")
                
                # Generate statistics answer
                answer_parts = ["## Code Statistics"]
                answer_parts.append(f"I found a total of **{counts['function'] + counts['method']} functions and methods** in the codebase, consisting of:")
                answer_parts.append(f"- **{counts['function']}** standalone functions")
                answer_parts.append(f"- **{counts['method']}** class methods")
                answer_parts.append(f"- **{counts['class']}** classes")
                answer_parts.append(f"- Code spread across **{file_count}** files")
                
                # Add code size metrics
                code_lines = counts['lines'] - counts['empty_lines'] - counts['comment_lines']
                answer_parts.append(f"\n### Code Size Metrics")
                answer_parts.append(f"- Total lines: **{counts['lines']}**")
                
                # Safeguard against division by zero
                if counts['lines'] > 0:
                    answer_parts.append(f"- Code lines: **{code_lines}** ({code_lines/counts['lines']*100:.1f}% of total)")
                    answer_parts.append(f"- Comment lines: **{counts['comment_lines']}** ({counts['comment_lines']/counts['lines']*100:.1f}% of total)")
                    answer_parts.append(f"- Empty lines: **{counts['empty_lines']}** ({counts['empty_lines']/counts['lines']*100:.1f}% of total)")
                else:
                    answer_parts.append(f"- Code lines: **{code_lines}**")
                    answer_parts.append(f"- Comment lines: **{counts['comment_lines']}**")
                    answer_parts.append(f"- Empty lines: **{counts['empty_lines']}**")
                
                # Add file type distribution
                if counts['file_types']:
                    answer_parts.append(f"\n### File Type Distribution")
                    # Sort file types by count
                    sorted_types = sorted(counts['file_types'].items(), key=lambda x: x[1], reverse=True)
                    for ext, count in sorted_types[:5]:  # Show top 5 file types
                        answer_parts.append(f"- **{ext}**: {count} files")
                    if len(sorted_types) > 5:
                        answer_parts.append(f"- *and {len(sorted_types)-5} more file types*")
                
                # Add code complexity insights
                answer_parts.append(f"\n### Code Complexity Insights")
                
                # Safeguard against division by zero
                if counts['class'] > 0:
                    avg_methods = counts['method'] / counts['class']
                    answer_parts.append(f"- Average methods per class: **{avg_methods:.1f}**")
                else:
                    answer_parts.append(f"- No classes found in the codebase")
                
                if file_count > 0:
                    avg_functions_per_file = (counts['function'] + counts['method']) / file_count
                    answer_parts.append(f"- Average functions/methods per file: **{avg_functions_per_file:.1f}**")
                    avg_classes_per_file = counts['class'] / file_count
                    answer_parts.append(f"- Average classes per file: **{avg_classes_per_file:.1f}**")
                    avg_lines_per_file = counts['lines'] / file_count
                    answer_parts.append(f"- Average lines per file: **{avg_lines_per_file:.1f}**")
                else:
                    answer_parts.append(f"- No Python files found in the codebase")
                
                # Return the statistics answer directly
                return {
                    "content": "\n\n".join(answer_parts),
                    "metadata": {
                        "question": question,
                        "format": "text/markdown"
                    }
                }
            except Exception as e:
                import traceback
                print(f"\nERROR in statistics calculation: {str(e)}")
                print(traceback.format_exc())
                
                # Return a graceful error message
                return {
                    "content": "## Statistics Error\n\nI encountered an error while calculating code statistics. This might be due to issues with the repository structure or parsing errors.\n\nError details: " + str(e),
                    "metadata": {
                        "question": question,
                        "format": "text/markdown"
                    }
                }
        else:
            print("Question type: GENERAL - No specific pattern matched")
            relevant_chunks = retriever.retrieve(question)
            
        print(f"\nDEBUG: Retrieved {len(relevant_chunks)} relevant chunks:")
        
        # Print details about each retrieved chunk
        for i, chunk in enumerate(relevant_chunks):
            print(f"\nChunk {i+1}: {chunk.chunk.type} '{chunk.chunk.name}' (score: {chunk.score:.4f})")
            print(f"  File: {chunk.chunk.file_path}")
            if chunk.chunk.parent_name:
                print(f"  Parent: {chunk.chunk.parent_name}")
            if chunk.chunk.docstring:
                print(f"  Docstring: {chunk.chunk.docstring[:100]}...")
            # Print first few lines of content
            content_preview = '\n'.join(chunk.chunk.content.split('\n')[:3])
            print(f"  Content preview: {content_preview}...")
        
        # Special handling for "what functions does X have" if needed
        if match_funcs and not match_class:
            class_name = match_funcs.group(1)
            # Find all methods of the class
            class_chunks = [c for c in relevant_chunks if c.chunk.type == "class" and c.chunk.name.lower() == class_name.lower()]
            method_chunks = [c for c in relevant_chunks if c.chunk.parent_name and c.chunk.parent_name.lower() == class_name.lower()]
            
            if class_chunks:
                # Generate a custom answer that lists all methods
                methods = [c.chunk for c in method_chunks]
                print(f"\nDEBUG: Found class {class_name} with {len(methods)} methods")
                
                # Custom answer for this question type
                answer_parts = [f"## Methods in class `{class_name}`\n"]
                answer_parts.append(f"The `{class_name}` class has the following methods:\n")
                
                for method in methods:
                    signature = method.content.split('\n')[0].strip()
                    if len(signature) > 80:
                        signature = signature[:77] + "..."
                    answer_parts.append(f"### `{method.name}`\n")
                    if method.docstring:
                        answer_parts.append(f"{method.docstring}\n")
                    answer_parts.append(f"```python\n{signature}\n```\n")
                
                answer = '\n'.join(answer_parts)
                print("\nDEBUG: Generated custom function list answer")
                
                return {
                    "content": answer,
                    "metadata": {
                        "question": question,
                        "format": "text/markdown"
                    }
                }
        
        # Special handling for error handling questions
        if analysis.intent == QuestionIntent.ERROR_HANDLING:
            print("\nDEBUG: Error handling question detected, ensuring proper formatting")
            
            # First, make sure we have enough context for error handling questions
            # Look for chunks with try-except blocks
            error_chunks = []
            for chunk in relevant_chunks:
                if 'try:' in chunk.chunk.content and 'except' in chunk.chunk.content:
                    error_chunks.append(chunk)
                    
            # If we found specific error handling chunks, prioritize them
            if error_chunks:
                print(f"\nDEBUG: Found {len(error_chunks)} chunks with error handling code")
                # Use these chunks first in the list
                # This ensures the answer generator focuses on them
                for chunk in error_chunks:
                    if chunk in relevant_chunks:
                        relevant_chunks.remove(chunk)
                # Put error chunks at the beginning
                relevant_chunks = error_chunks + relevant_chunks
                
            # Generate the answer with the reordered chunks
            answer = generator.generate(question, relevant_chunks)
            
            # Post-process the answer to ensure proper formatting
            # This helps with accordion rendering in the web UI
            if "```" in answer:
                # The answer already has code blocks, no need to modify
                pass
            else:
                # If there are no code blocks, try to fix the formatting
                answer_parts = answer.split("\n\n")
                formatted_answer = []
                for part in answer_parts:
                    if part.startswith("```") and part.endswith("```"):
                        formatted_answer.append(part)
                    elif "Error handling block" in part:
                        # Format as code block if it's not already
                        if not part.startswith("```"):
                            # Extract the code and wrap in proper code block
                            formatted_answer.append(f"```python\n{part}\n```")
                    else:
                        formatted_answer.append(part)
                answer = "\n\n".join(formatted_answer)
            
            return {
                "content": answer,
                "metadata": {
                    "question": question,
                    "format": "text/markdown"
                }
            }
        
        # Generate answer using the answer generator
        answer = generator.generate(question, relevant_chunks)
        
        # Return the answer
        return {
            "content": answer,
            "metadata": {
                "question": question,
                "format": "text/markdown"
            }
        }
    except Exception as e:
        import traceback
        print(f"ERROR: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error processing question: {str(e)}"}
        )

if __name__ == "__main__":
    print("Starting debug server on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
