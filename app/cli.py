"""
Command-line interface for the MCP code repository question answering system.
"""

import argparse
import sys
import os
import uvicorn
from typing import List, Optional

# Add app directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app, indexer, retriever, generator
from app.indexer.code_indexer import CodeIndexer
from app.retriever.retriever import Retriever
from app.generator.answer_generator import AnswerGenerator


def setup_components(repo_path: str, rebuild_index: bool = False) -> None:
    """Set up the components with the given repository path"""
    global indexer, retriever, generator
    
    # Initialize components
    indexer = CodeIndexer(repo_path=repo_path)
    retriever = Retriever(indexer=indexer)
    generator = AnswerGenerator()
    
    # Build or load the index
    if rebuild_index:
        print(f"Building index for repository: {repo_path}")
        indexer.build_index()
    else:
        print(f"Loading index for repository: {repo_path}")
        indexer.load_or_build_index()


def start_server(host: str, port: int) -> None:
    """Start the FastAPI server"""
    print(f"Starting MCP server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


def ask_question(question: str) -> str:
    """Process a question directly and return the answer"""
    if not indexer or not retriever or not generator:
        raise ValueError("Components not initialized")
    
    # Retrieve relevant code chunks
    relevant_chunks = retriever.retrieve(question)
    
    # Generate an answer
    return generator.generate(question, relevant_chunks)


def main() -> None:
    """Main entry point with command-line parsing"""
    parser = argparse.ArgumentParser(description="MCP server for code repository Q&A")
    parser.add_argument("--repo_path", required=True, help="Path to the code repository")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind the server to")
    serve_parser.add_argument("--port", default=8000, type=int, help="Port to bind the server to")
    serve_parser.add_argument("--rebuild_index", action="store_true", help="Force rebuilding the index")
    
    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask a question directly")
    ask_parser.add_argument("question", help="Question to ask")
    ask_parser.add_argument("--rebuild_index", action="store_true", help="Force rebuilding the index")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Set up components
    setup_components(args.repo_path, args.rebuild_index if hasattr(args, "rebuild_index") else False)
    
    if args.command == "serve":
        # Start the server
        start_server(args.host, args.port)
    elif args.command == "ask":
        # Process a question directly
        answer = ask_question(args.question)
        print("\n" + answer)


if __name__ == "__main__":
    main()
