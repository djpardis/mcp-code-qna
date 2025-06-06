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
from app.retriever.retriever import Retriever
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
        
        # Pattern match question to understand what the user is asking
        # This will help debug the answer generator's pattern matching
        import re
        question_lower = question.lower()
        match_class = re.search(r'what does (the )?(class|module) ([\w_]+) do', question_lower)
        match_impl = re.search(r'how is (the )?(service|component|function|method) ([\w_]+) implemented', question_lower)
        match_param = re.search(r'how does (the )?(method|function) ([\w_]+) use (the )?parameter ([\w_]+)', question_lower)
        match_funcs = re.search(r'what functions does ([\w_]+) have', question_lower)
        
        if match_class:
            print(f"Question type: CLASS PURPOSE - Looking for class: {match_class.group(3)}")
        elif match_impl:
            print(f"Question type: IMPLEMENTATION - Looking for: {match_impl.group(3)}")
        elif match_param:
            print(f"Question type: PARAMETER USAGE - Method: {match_param.group(3)}, Param: {match_param.group(5)}")
        elif match_funcs:
            print(f"Question type: FUNCTIONS LIST - Looking for class: {match_funcs.group(1)}")
            # We need custom handling for this type
        else:
            print("Question type: GENERAL - No specific pattern matched")
        
        # Process the question
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
        
        # Use the standard answer generator
        answer = generator.generate(question, relevant_chunks)
        print(f"\nDEBUG: Generated standard answer")
        
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
