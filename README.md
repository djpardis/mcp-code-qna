# MCP Code Repository Question Answering

This project implements a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that answers questions about a local code repository using a Retrieval-Augmented Generation (RAG) system.

## Features

- MCP-compliant server for question answering
- Intelligent code chunking based on logical blocks (functions, classes, etc.)
- Semantic search for finding relevant code snippets
- Natural language answers with relevant code references

## Getting Started

### Prerequisites

- Python 3.9+
- A local Python repository to analyze

### Installation

1. Clone this repository
2. Install dependencies using one of the following methods:

   **Option 1: Using requirements.txt (Basic)**
   ```
   python3 -m pip install -r requirements.txt
   ```
   
   **Option 2: Using setup.py (Recommended)**
   ```
   python3 -m pip install -e .
   ```
   This will install all dependencies and additional components like the spaCy language model.
   
   > **Note:** This project uses `python3 -m pip` instead of standalone `pip` command to ensure compatibility with the correct Python installation. This is the recommended approach by Python packaging authorities as it's more explicit about which Python environment you're installing packages into.

### Usage

#### Web UI Interface (Recommended)

A user-friendly web interface is available for the easiest interaction:

```bash
# Start the server with web UI enabled
./mcp serve /path/to/your/repo
```

Then open your browser to [http://localhost:8000](http://localhost:8000) to access the web interface.

The web UI provides:
- A simple form to enter your questions
- Markdown rendering of answers with syntax highlighting for code
- Connection status indicator
- Sample questions to try

#### Simple CLI Interface

```bash
# Start the server
./mcp serve /path/to/your/repo

# Ask a question directly
./mcp ask /path/to/your/repo "What does class UserService do?"

# Get help
./mcp --help
```

Options:
- `-p, --port PORT`: Specify server port (default: 8000)
- `-h, --host HOST`: Specify host address (default: 0.0.0.0) 
- `-r, --rebuild`: Force rebuild the index

#### Advanced Usage

The project also offers more detailed ways to interact with the code QA system:

#### Option 1: CLI Direct Questions

For quick testing and direct usage without starting a server:

```bash
python3 -m app.cli --repo_path /path/to/your/repo ask "What does class UserService do?"
```

This will output the answer directly in your terminal.

#### Option 2: MCP Server (Recommended)

Start the MCP server for API access and agent integration:

```bash
python3 -m app.cli --repo_path /path/to/your/repo serve [--port 8000] [--rebuild_index]
```

Options:
- `--port PORT`: Specify a port (default: 8000)
- `--host HOST`: Specify a host (default: 0.0.0.0)
- `--rebuild_index`: Force rebuild the index even if it exists

The server will be available at http://localhost:8000 (or your specified port)

#### Interacting with the MCP Server

1. Get server metadata:
   ```bash
   curl http://localhost:8000/.well-known/mcp
   ```

2. List available resources:
   ```bash
   curl http://localhost:8000/list_resources
   ```

3. Ask a question:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"uri": "questions", "parameters": {"question": "What does class UserService do?"}}' \
     http://localhost:8000/read_resource
   ```

4. Interactive documentation available at:
   ```
   http://localhost:8000/docs
   ```

## Architecture

The system consists of three main components:

1. **Code Indexer**: Parses the repository, extracts logical code blocks, and creates embeddings
2. **Retriever**: Performs semantic search to find relevant code chunks for a question
3. **Generator**: Produces natural language answers with relevant code snippets

## Project Structure

```
.
├── app/                      # Main application package
│   ├── generator/            # Answer generation components
│   ├── indexer/              # Code indexing and parsing
│   ├── retriever/            # Semantic search and retrieval
│   ├── static/               # Web UI static assets
│   ├── cli.py                # Command-line interface
│   ├── main.py               # FastAPI application
│   └── mcp_web_server.py     # Web UI server implementation
├── tests/                    # Test suite
├── mcp                       # CLI script entry point
├── requirements.txt          # Project dependencies
├── setup.py                  # Installation script
└── README.md                 # This file
```

## RAG System Details

- **Chunking**: Uses AST-based parsing to extract logical blocks of code (functions, classes, methods)
- **Storage**: Stores code chunks and their embeddings in a FAISS vector database
- **Indexing**: Creates semantic embeddings using SentenceTransformers
- **Retrieval**: Uses cosine similarity to find relevant code chunks
- **Generation**: Formats responses with appropriate context and code snippets

## Sample Repository

A sample Python repository is included at `/sample-python-repo` to test the system. It contains:

- `user_service.py`: A service for user management and authentication
- `order_processor.py`: A service for processing customer orders
- `database.py`: A mock database implementation for testing

You can use this sample repo to test the system with questions like:

```
What does class UserService do?
How is service OrderProcessor implemented?
How does method process_payment use parameter payment_method?
```

## Testing

We've tested the system using both the CLI and server approaches. The CLI interface provides immediate results and is recommended for initial testing. The server provides the full MCP protocol implementation necessary for agent integration.

Example test results show the system correctly identifies class purposes, implementation details, and parameter usage from the codebase.

## Troubleshooting

### First Run Takes a Long Time

On first run, the system needs to download the SentenceTransformer model files (approximately 270MB total). This is a one-time process, and subsequent runs will use the cached models.

### Port Already in Use

If you receive an error like `[Errno 48] error while attempting to bind on address: address already in use`, try:

1. Specifying a different port: `--port 8001`
2. Checking for existing servers: `lsof -i :8000`
3. Terminating existing processes: `kill <PID>`

### Installation Issues

If you encounter issues with package dependencies, particularly with `huggingface-hub` and `sentence-transformers`, ensure you're using the versions specified in `requirements.txt`. We've pinned specific versions to avoid compatibility issues.

## Related Projects

- The MCP Protocol: https://modelcontextprotocol.io/introduction
- SentenceTransformers: https://sbert.net
