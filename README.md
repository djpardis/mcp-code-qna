# MCP Code Repository Question Answering

This project implements a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction) server that answers questions about a local code repository using a Retrieval-Augmented Generation (RAG) system.

## Features

- MCP-compliant server for question answering
- Intelligent code chunking based on logical blocks (functions, classes, etc.)
- Semantic search for finding relevant code snippets
- Natural language answers with relevant code references
- Dynamic repository path support for querying multiple repositories without server restart
- Comprehensive evaluation framework with quality metrics

## Getting Started

### Prerequisites

- Python 3.9+
- A local Python repository to analyze

### Installation

1. Clone this repository
2. Install dependencies using one of the following methods:

   **Option 1: Using requirements.txt (Basic)**
   ```bash
   python3 -m pip install -r requirements.txt
   ```
   
   **Option 2: Using setup.py (Recommended)**
   ```bash
   python3 -m pip install -e .
   ```
   This will install all dependencies and additional components like the spaCy language model.

   > **Note:** This project uses `python3 -m pip` instead of standalone `pip` command to ensure compatibility with the correct Python installation. This is the recommended approach by Python packaging authorities as it's more explicit about which Python environment you're installing packages into.

### Running the MCP Server

```bash
# Start the MCP server with a specific repository path
python -m app.mcp_web_server --repo-path /path/to/your/repo

# Or start with a specific port (default is 8000)
python -m app.mcp_web_server --repo-path /path/to/your/repo --port 8002
```

### Accessing the Web Interface

Open `http://localhost:8000` (or your specified port) in your browser to access the web interface.

### Running Evaluations

```bash
# Run evaluation on the Grip repository
python run_test_evaluation.py --server-url http://localhost:8002 \
  --repo-path /path/to/grip-repo \
  --repo-type grip

# Run evaluation on the Sample Python repository
python run_test_evaluation.py --server-url http://localhost:8002 \
  --repo-path /path/to/sample-python-repo \
  --repo-type sample_repo
```

### End-to-End Testing

To run a complete evaluation of the MCP server:

1. Start the MCP server in one terminal:
   ```bash
   python -m app.mcp_web_server --port 8002
   ```

2. Run evaluations for both repositories in another terminal:
   ```bash
    # Run evaluation on the Grip repository
    python run_test_evaluation.py --server-url http://localhost:8002 \
      --repo-path /path/to/grip-repo \
      --repo-type grip
    
    # Run evaluation on the Sample Python repository
    python run_test_evaluation.py --server-url http://localhost:8002 \
      --repo-path /path/to/sample-python-repo \
      --repo-type sample_repo
   ```

3. Review the evaluation results in the `evaluation_results` directory

## Usage

### MCP Agent

The MCP Agent is a powerful tool that leverages the MCP server to perform comprehensive repository analysis. It generates detailed reports about a codebase's architecture, dependencies, and design patterns.

#### Features

- **Architecture Analysis**: Examines the overall structure, components, and organization of the repository
- **Dependency Analysis**: Identifies external libraries, frameworks, and how dependencies are managed
- **Design Pattern Detection**: Recognizes common design patterns used in the codebase
- **Multi-format Reports**: Generates reports in JSON, Markdown, and interactive HTML formats

#### Usage

```bash
# Basic usage
./scripts/mcp_agent.py --server-url http://localhost:8002 --repo-path /path/to/your/repo

# Specify a custom output directory for reports
./scripts/mcp_agent.py --server-url http://localhost:8002 --repo-path /path/to/your/repo --output-dir ./my-reports

# Specify repository type for better organization
./scripts/mcp_agent.py --server-url http://localhost:8002 --repo-path /path/to/your/repo --repo-type grip
```

#### Report Types

1. **JSON Report** (`reports/{repo_type}/{repo_name}_report_{timestamp}.json`)
   - Raw structured data for programmatic processing
   - Contains all questions and answers from the analysis

2. **Markdown Report** (`reports/{repo_type}/{repo_name}_report_{timestamp}.md`)
   - Human-readable formatted text
   - Perfect for viewing in GitHub or any markdown viewer

3. **HTML Report** (`reports/{repo_type}/{repo_name}_report_{timestamp}.html`)
   - Interactive web-based report with formatting and styling
   - Includes collapsible sections and syntax highlighting
   - Best for sharing with team members

#### Organized Directory Structure

Reports and evaluation results are automatically organized by repository type:

```
├── reports/
│   ├── sample_repo/   # Reports for the sample Python repository
│   ├── grip/          # Reports for the Grip repository
│   └── other/         # Reports for other repositories
│
└── evaluation_results/
    ├── sample_repo/   # Evaluation results for sample Python repository
    └── grip/          # Evaluation results for Grip repository
```

You can specify the repository type when running the MCP Agent:

```bash
./scripts/mcp_agent.py --server-url http://localhost:8002 --repo-path /path/to/repo --repo-type grip
```

#### Example Report Contents

- **Architecture Analysis**
  - Overall architecture description
  - Component interaction diagrams
  - Entry points and code organization
  
- **Dependency Analysis**
  - External libraries and frameworks
  - Dependency management approach
  - Core vs. development dependencies
  
- **Design Pattern Identification**
  - Detected design patterns with confidence levels
  - Code snippets showing pattern implementations
  - Explanations of how patterns are used

### Web UI Interface (Recommended)

A user-friendly web interface is available for the easiest interaction:

```bash
# Start the server with a default repository
./mcp serve --repo_path /path/to/your/repo

# Or start the server in dynamic mode (no default repository)
./mcp serve
```

Then open your browser to [http://localhost:8000](http://localhost:8000) to access the web interface.

## Evaluation Framework

The MCP server includes a comprehensive evaluation framework to assess its performance across different repositories and question types.

### MCP Quality Score (MQS)

The evaluation framework calculates an MCP Quality Score (MQS) based on several key metrics:

- **Response Time (30%)**: Rewards faster response times with diminishing returns
- **Error Rate (70%)**: Percentage of questions that receive error-free responses

The MQS is a score from 0-10 that provides an overall assessment of the system's performance.

### Document Assessment Criteria

When evaluating the quality of answers, the following criteria are used:

1. **Accuracy**: Does the answer correctly address the question and provide factually correct information?
   - Excellent (9-10): Answer is completely accurate with precise details
   - Good (7-8): Answer is mostly accurate with minor imprecisions
   - Acceptable (5-6): Answer has some inaccuracies but is generally helpful
   - Poor (0-4): Answer contains significant factual errors

2. **Relevance**: Does the answer directly address the question asked?
   - Excellent (9-10): Answer directly addresses all aspects of the question
   - Good (7-8): Answer addresses the main points of the question
   - Acceptable (5-6): Answer is somewhat related but misses key aspects
   - Poor (0-4): Answer is largely unrelated to the question

3. **Completeness**: Does the answer provide a comprehensive response?
   - Excellent (9-10): Answer covers all aspects thoroughly
   - Good (7-8): Answer covers most important aspects
   - Acceptable (5-6): Answer provides basic information but lacks depth
   - Poor (0-4): Answer is incomplete or superficial

4. **Code Context**: Does the answer include relevant code snippets when appropriate?
   - Excellent (9-10): Includes precisely relevant code with good explanations
   - Good (7-8): Includes relevant code with adequate explanations
   - Acceptable (5-6): Includes some code but with limited explanation
   - Poor (0-4): Missing relevant code or includes irrelevant code

### Running Evaluations

The evaluation framework uses the exact questions from the test files (`test_sample_repo_question_understanding.py` and `run_comprehensive_evaluation.py`). These questions are also displayed in the web interface to ensure consistency between testing and user interaction.

```bash
# Run evaluation on the sample Python repository
python run_test_evaluation.py --server-url http://localhost:8002 \
  --repo-path /path/to/sample-python-repo \
  --repo-type sample_repo

# Run evaluation on the grip repository
python run_test_evaluation.py --server-url http://localhost:8002 \
  --repo-path /path/to/grip-repo \
  --repo-type grip
```

Make sure the MCP server is running before executing the evaluation script. The default server port is 8000, but you can specify a different port with the `--server-url` parameter.

The evaluation script will:
1. Extract questions from the web interface that match the test files
2. Send each question to the MCP server with the specified repository path
3. Measure response time and error rate
4. Calculate the MCP Quality Score (MQS)
5. Save detailed results to JSON files in the evaluation_results directory

The evaluation generates detailed reports with:

- Overall quality metrics including MQS
- Per-question performance analysis
- Response time statistics
- Error rate analysis

### Interpreting Results

MQS scores can be interpreted as follows:

- **9-10**: Excellent - Answers are highly accurate and relevant with fast response times
- **7-8**: Good - Most answers are accurate with occasional minor issues
- **5-6**: Acceptable - Answers are generally helpful but may contain inaccuracies
- **3-4**: Needs improvement - Significant issues with accuracy or relevance
- **0-2**: Poor - Major problems with answer quality

For production use, aim for an MQS of 7 or higher.

### Recent Evaluation Results

#### Grip Repository Performance
- **MCP Quality Score (MQS)**: 6.16/10
- **Average Response Time**: 0.22s
- **Error Rate**: 50.00%

#### Sample Python Repository Performance
- **MCP Quality Score (MQS)**: 5.49/10
- **Average Response Time**: 0.20s
- **Error Rate**: 60.00%

The web UI provides:
- A simple form to enter your questions
- A repository path input field to specify which code repository to analyze
- Sample questions organized by category to help you get started
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

## System Components and Workflow

The MCP Code Repository Q&A Project consists of three main components that work together to provide a complete code understanding solution:

1. **MCP Server** - The core RAG (Retrieval-Augmented Generation) engine that processes questions about code
2. **Evaluation Framework** - Tools to measure and assess the quality of MCP responses
3. **MCP Agent** - An intelligent agent that uses the MCP server to generate comprehensive repository analyses

### How Components Work Together

```
┌─────────────────┐     Questions     ┌─────────────────┐
│                 │ ◄───────────────► │                 │
│    MCP Server   │                   │     Web UI      │
│                 │ ─────────────────►│                 │
└─────────┬───────┘     Answers      └─────────────────┘
          │
          │ Questions/Answers
          ▼
┌─────────────────┐                  ┌─────────────────┐
│   Evaluation    │◄────────────────►│    MCP Agent    │
│    Framework    │   Uses Server    │                 │
└─────────────────┘                  └─────────────────┘
          │                                    │
          │                                    │
          ▼                                    ▼
┌─────────────────┐                  ┌─────────────────┐
│   Evaluation    │                  │  Architecture   │
│     Results     │                  │     Reports     │
└─────────────────┘                  └─────────────────┘
```

### MCP Server Architecture

The MCP Server consists of three main components:

1. **Code Indexer**: Parses the repository, extracts logical code blocks, and creates embeddings
2. **Retriever**: Performs semantic search to find relevant code chunks for a question
3. **Generator**: Uses the retrieved code chunks to generate accurate answers with relevant code snippets

## Project Structure

```
.
├── app/                # Core application code
│   ├── generator/     # Answer generation components
│   ├── indexer/       # Code indexing and parsing
│   ├── retriever/     # Semantic search and retrieval
│   ├── static/        # Static web assets
│   ├── mcp_web_server.py  # Main MCP server implementation
│   ├── main.py        # FastAPI application
│   └── cli.py         # Command-line interface
├── scripts/           # Utility scripts
│   ├── mcp_agent.py   # Repository analysis agent
│   └── report_template.html # HTML template for agent reports
├── evaluation_scripts/ # Evaluation tools
│   ├── evaluate_mcp.py # Main evaluation script
│   ├── run_comprehensive_evaluation.py # Comprehensive evaluation
│   ├── run_simple_evaluation.py # Simple evaluation
│   └── run_test_evaluation.py # Test-based evaluation
├── tests/            # Test files
│   ├── test_grip_dataset_evaluation.py # Grip dataset tests
│   └── test_sample_repo_question_understanding.py # Sample repo tests
├── reports/          # Repository analysis reports
│   ├── sample_repo/  # Sample Python repository reports
│   ├── grip/         # Grip repository reports
│   └── other/        # Other repository reports
├── evaluation_results/ # MCP server evaluation results
│   ├── sample_repo/  # Sample Python repository evaluations
│   └── grip/         # Grip repository evaluations
├── mcp              # CLI script entry point
├── setup.py          # Installation script
├── requirements.txt  # Project dependencies
├── TODO.md           # Project tasks and roadmap
└── README.md         # This file
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

### Generating the Sample Python Repository

You can generate the sample Python repository using the included script:

```bash
# Clone this repository if you haven't already
git clone https://github.com/your-username/mcp-code-qa-project.git
cd mcp-code-qa-project

# Run the script to generate the sample repository
python -m scripts.generate_sample_repo
```

This will create a `sample-python-repo` directory with all the necessary files for testing.

You can use this sample repo to test the system with questions like:

```
What does class UserService do?
How is service OrderProcessor implemented?
How does method process_payment use parameter payment_method?
```

## Testing

We've tested the system using both the CLI and server approaches. The CLI interface provides immediate results and is recommended for initial testing. The server provides the full MCP protocol implementation necessary for agent integration.

> **Note:** The Grip dataset used for evaluation can be found at: https://github.com/joeyespo/grip/tree/master

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
