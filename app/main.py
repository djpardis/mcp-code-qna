"""
Main entry point for the MCP server that answers questions about code repositories.
"""

import argparse
import os
import sys
from typing import Dict, Optional, List, Any

import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

# Add app directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.indexer.code_indexer import CodeIndexer
from app.retriever.retriever import Retriever
from app.generator.answer_generator import AnswerGenerator

# Initialize FastAPI app
app = FastAPI(title="MCP Code Repository QA", 
              description="MCP server that answers questions about code repositories")

# Mount static files for web UI
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")

# Global state for components
indexer: Optional[CodeIndexer] = None
retriever: Optional[Retriever] = None
generator: Optional[AnswerGenerator] = None

# Root route redirects to the web UI
@app.get("/", include_in_schema=False)
async def root():
    # This will return the index.html file directly
    return FileResponse(os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html"))


class Resource(BaseModel):
    """MCP Resource model"""
    uri: str
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ListResourcesResponse(BaseModel):
    """Response model for list_resources endpoint"""
    resources: List[Resource] = Field(default_factory=list)
    cursor: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup"""
    global indexer, retriever, generator
    
    # Note: Components are now initialized in app.cli.py's setup_components function
    # This function is kept for FastAPI lifecycle management
    pass


@app.get("/.well-known/mcp")
async def get_mcp_metadata():
    """Return MCP server metadata"""
    return {
        "api_version": "0.1.0",
        "server_name": "code-repository-qa",
        "server_version": "0.1.0",
        "capabilities": ["list_resources", "read_resource"],
        "description": "An MCP server that answers questions about code repositories",
        "documentation_url": "https://modelcontextprotocol.io/introduction"
    }


@app.get("/list_resources")
async def list_resources(cursor: Optional[str] = None) -> ListResourcesResponse:
    """List available repository question resources"""
    if indexer is None:
        raise HTTPException(status_code=500, detail="Server not fully initialized")
    
    # Return a resource for asking questions about the repository
    return ListResourcesResponse(
        resources=[
            Resource(
                uri="questions",
                title="Repository Q&A",
                description="Ask questions about the code repository",
                metadata={"repo_path": indexer.repo_path}
            )
        ],
        cursor=None  # No pagination needed for this simple case
    )


@app.post("/read_resource")
async def read_resource(request: Request) -> Dict[str, Any]:
    """Read a repository question resource"""
    if indexer is None or retriever is None or generator is None:
        raise HTTPException(status_code=500, detail="Server not fully initialized")
    
    try:
        # Parse the request data
        request_data = await request.json()
        
        # Print request for debugging
        print(f"Received request: {request_data}")
        
        uri = request_data.get("uri")
        if uri != "questions":
            raise HTTPException(status_code=404, detail=f"Resource {uri} not found")
        
        # Extract the question from the request data
        parameters = request_data.get("parameters", {})
        question = parameters.get("question")
        if not question:
            raise HTTPException(status_code=400, detail="No question provided")
        
        # Process the question
        # Retrieve relevant code chunks
        relevant_chunks = retriever.retrieve(question)
        
        # Generate an answer
        answer = generator.generate(question, relevant_chunks)
        
        return {
            "content": answer,
            "metadata": {
                "question": question,
                "format": "text/markdown"
            }
        }
    except Exception as e:
        import traceback
        print(f"Error processing request: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error processing question: {str(e)}")


def main():
    """Main entry point with command-line parsing"""
    parser = argparse.ArgumentParser(description="MCP server for code repository Q&A")
    parser.add_argument("--repo_path", required=True, help="Path to the code repository")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind the server to")
    parser.add_argument("--rebuild_index", action="store_true", help="Force rebuilding the index")
    
    args = parser.parse_args()
    
    global indexer, retriever, generator
    
    # Initialize components
    indexer = CodeIndexer(repo_path=args.repo_path)
    retriever = Retriever(indexer=indexer)
    generator = AnswerGenerator()
    
    # Build or load the index
    if args.rebuild_index:
        print(f"Building index for repository: {args.repo_path}")
        indexer.build_index()
    else:
        print(f"Loading index for repository: {args.repo_path}")
        indexer.load_or_build_index()
    
    # Run the server
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
