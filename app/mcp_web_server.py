#!/usr/bin/env python3
"""
MCP Web Server for code repository question answering
"""
import os
import sys
import argparse
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.indexer.code_indexer import CodeIndexer
from app.retriever.retriever import Retriever, RetrievedChunk
from app.generator.answer_generator import AnswerGenerator

# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="MCP Web Server for code repository question answering")
    parser.add_argument("--repo_path", "-r", help="Path to the code repository (optional)")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild the index")
    parser.add_argument("--port", "-p", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to run the server on")
    return parser.parse_args()

# Initialize components
args = parse_args()
repo_path = args.repo_path

# Initialize with empty/default values if no repo path provided
indexer = None
retriever = None

if repo_path:
    print(f"Initializing components with repo path: {repo_path}")
    try:
        indexer = CodeIndexer(repo_path=repo_path)
        print("Building index...")
        
        # Handle rebuild flag
        if args.rebuild:
            print("Forcing index rebuild...")
            indexer.build_index()
        else:
            indexer.load_or_build_index()
            
        retriever = Retriever(indexer=indexer)
        print("Components initialized successfully with repository")
    except Exception as e:
        print(f"Warning: Failed to initialize with repo path {repo_path}: {str(e)}")
        print("Server will start without a default repository")
        repo_path = None
else:
    print("No repository path provided. Server will start in dynamic mode.")
    print("Each question must include a valid repo_path parameter.")

# Always initialize the generator
generator = AnswerGenerator()

# Initialize FastAPI app
app = FastAPI(title="Debug MCP Server")

# Mount static files
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
print(f"Static directory: {static_dir}")
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
    repo_path = None if indexer is None else indexer.repo_path
    
    return {
        "resources": [
            {
                "uri": "questions",
                "title": "Repository Q&A",
                "description": "Ask questions about the code repository",
                "metadata": {"repo_path": repo_path}
            }
        ],
        "cursor": None
    }

@app.post("/question")
async def handle_question(request: Request):
    """Handle a question about the code repository"""
    try:
        # Parse request data
        data = await request.json()
        if "question" not in data:
            return {"error": "No question provided"}
            
        question = data["question"]
        print(f"\nDEBUG: Received question: {data}")
        
        # Get repository path from request or use global default
        current_repo_path = None
        current_indexer = None
        current_retriever = None
        
        # Check if request includes a repo path
        if "repo_path" in data and data["repo_path"]:
            custom_path = data["repo_path"]
            if os.path.isdir(custom_path):
                current_repo_path = custom_path
                print(f"Using custom repo path from request: {custom_path}")
                
                # Create a new indexer and retriever for this specific request
                try:
                    current_indexer = CodeIndexer(repo_path=current_repo_path)
                    current_indexer.load_or_build_index()
                    current_retriever = Retriever(indexer=current_indexer)
                except Exception as e:
                    return {
                        "content": f"Error initializing repository: {str(e)}",
                        "metadata": {
                            "question": question,
                            "format": "text/markdown",
                            "error": str(e)
                        }
                    }
            else:
                return {
                    "content": f"The provided repository path '{custom_path}' is not a valid directory.",
                    "metadata": {
                        "question": question,
                        "format": "text/markdown",
                        "error": "Invalid repository path"
                    }
                }
        # Use global repo path if available
        elif repo_path:
            current_repo_path = repo_path
            current_indexer = indexer
            current_retriever = retriever
            print(f"Using default repo path: {current_repo_path}")
        else:
            # No repo path provided in request and no default repo path
            return {
                "content": "No repository path provided. Please include a 'repo_path' parameter in your request.",
                "metadata": {
                    "question": question,
                    "format": "text/markdown",
                    "error": "Missing repository path"
                }
            }
        
        # Simple statistics question detection
        is_statistics_question = False
        question_lower = question.lower()
        if ('how many' in question_lower or 'count' in question_lower) and \
           any(term in question_lower for term in ['function', 'method', 'class', 'file', 'module']):
            is_statistics_question = True
            print("Detected statistics question")
            
        # Generate answer based on question type
        if is_statistics_question:
            print("Detected statistics question")
            try:
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
                        self.current_class = True
                        self.generic_visit(node)
                        self.current_class = old_class
                    
                    def visit_FunctionDef(self, node):
                        if self.current_class:
                            self.methods += 1
                        else:
                            self.functions += 1
                        self.generic_visit(node)
                
                # Verify repository path exists
                if not os.path.exists(current_repo_path):
                    print(f"WARNING: Repository path {current_repo_path} does not exist")
                    return {
                        "content": f"Error: Repository path {current_repo_path} does not exist",
                        "metadata": {
                            "question": question,
                            "format": "text/markdown",
                            "error": "Repository path does not exist"
                        }
                    }
                
                # Find all Python files in the repository
                python_files = []
                for root, _, files in os.walk(current_repo_path):
                    for file in files:
                        if file.endswith('.py'):
                            python_files.append(os.path.join(root, file))
                
                print(f"Found {len(python_files)} Python files")
                
                # Count code elements in each file
                counts = {'function': 0, 'method': 0, 'class': 0, 'module': len(python_files)}
                counts['file'] = counts['module']  # Alias for module count
                
                # Additional statistics
                counts['lines'] = 0
                counts['empty_lines'] = 0
                counts['comment_lines'] = 0
                
                # Track file types
                file_types = {}
                
                for file_path in python_files:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        try:
                            content = f.read()
                            lines = content.split('\n')
                            counts['lines'] += len(lines)
                            
                            # Count empty lines and comment lines
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    counts['empty_lines'] += 1
                                elif line.startswith('#'):
                                    counts['comment_lines'] += 1
                            
                            # Parse the file and count elements
                            tree = ast.parse(content)
                            visitor = CodeVisitor()
                            visitor.visit(tree)
                            
                            counts['function'] += visitor.functions
                            counts['method'] += visitor.methods
                            counts['class'] += visitor.classes
                            
                            # Track file extension
                            ext = os.path.splitext(file_path)[1]
                            file_types[ext] = file_types.get(ext, 0) + 1
                            
                        except Exception as e:
                            print(f"Error parsing {file_path}: {str(e)}")
                
                # Generate the answer
                file_count = len(python_files)
                answer_parts = ["## Code Statistics\n"]
                
                # Basic counts
                answer_parts.append(f"The codebase contains:")
                answer_parts.append(f"- **{counts['function']}** top-level functions")
                answer_parts.append(f"- **{counts['method']}** class methods")
                answer_parts.append(f"- **{counts['class']}** classes")
                answer_parts.append(f"- **{file_count}** Python files")
                answer_parts.append(f"- **{counts['lines']}** total lines of code")
                answer_parts.append(f"- **{counts['empty_lines']}** empty lines")
                answer_parts.append(f"- **{counts['comment_lines']}** comment lines")
                
                # File type distribution
                answer_parts.append(f"\n### File Type Distribution")
                for ext, count in file_types.items():
                    answer_parts.append(f"- **{ext}**: {count} files")
                
                # Additional insights
                answer_parts.append(f"\n### Additional Insights")
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
        
        # For all other question types, use the retriever and generator
        if current_retriever is None:
            return {
                "content": "Error: No retriever available for this repository. Please check the repository path.",
                "metadata": {
                    "question": question,
                    "format": "text/markdown",
                    "error": "No retriever available"
                }
            }
        
        relevant_chunks = current_retriever.retrieve(question)
        print(f"\nDEBUG: Retrieved {len(relevant_chunks)} relevant chunks")
        
        # Generate answer
        answer = generator.generate(question, relevant_chunks)
        print(f"\nDEBUG: Generated answer")
        
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
    print(f"Starting MCP web server on http://{args.host}:{args.port}")
    print(f"Repository path: {repo_path}")
    uvicorn.run(app, host=args.host, port=args.port)
