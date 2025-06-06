"""
Code indexer module for parsing and indexing Python code repositories.
"""

import os
import ast
import json
import pickle
import hashlib
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

import libcst as cst
from libcst.metadata import PositionProvider
from sentence_transformers import SentenceTransformer
import faiss


@dataclass
class CodeChunk:
    """Class representing a logical chunk of code with metadata"""
    id: str
    file_path: str
    type: str  # "function", "class", "method", etc.
    name: str
    content: str
    docstring: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    parent_name: Optional[str] = None
    embedding: Optional[List[float]] = field(default=None, repr=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding the embedding"""
        result = asdict(self)
        # Don't include embedding in serialized form
        if 'embedding' in result:
            del result['embedding']
        return result


class PythonCodeVisitor(ast.NodeVisitor):
    """AST visitor for extracting logical code blocks from Python files"""
    
    def __init__(self, code: str, file_path: str):
        self.code = code
        self.file_path = file_path
        self.chunks: List[CodeChunk] = []
        self.lines = code.split('\n')
        self.current_class = None
    
    def get_source_segment(self, node) -> str:
        """Extract source code for a given AST node"""
        if hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            start = node.lineno - 1  # AST line numbers are 1-indexed
            end = node.end_lineno
            source_lines = self.lines[start:end]
            return '\n'.join(source_lines)
        return ""
    
    def get_docstring(self, node) -> Optional[str]:
        """Extract docstring from an AST node if present"""
        if (isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Module)) and
                node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, ast.Constant) and
                isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value.strip()
        return None
    
    def create_chunk_id(self, node_type: str, name: str, file_path: str) -> str:
        """Create a unique ID for a code chunk"""
        content = f"{node_type}:{name}:{file_path}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def visit_ClassDef(self, node):
        """Visit a class definition node"""
        old_class = self.current_class
        self.current_class = node.name
        
        docstring = self.get_docstring(node)
        content = self.get_source_segment(node)
        
        chunk = CodeChunk(
            id=self.create_chunk_id("class", node.name, self.file_path),
            file_path=self.file_path,
            type="class",
            name=node.name,
            content=content,
            docstring=docstring,
            start_line=node.lineno,
            end_line=node.end_lineno,
            parent_name=old_class
        )
        self.chunks.append(chunk)
        
        # Visit children
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node):
        """Visit a function definition node"""
        docstring = self.get_docstring(node)
        content = self.get_source_segment(node)
        
        chunk = CodeChunk(
            id=self.create_chunk_id(
                "method" if self.current_class else "function",
                node.name,
                self.file_path
            ),
            file_path=self.file_path,
            type="method" if self.current_class else "function",
            name=node.name,
            content=content,
            docstring=docstring,
            start_line=node.lineno,
            end_line=node.end_lineno,
            parent_name=self.current_class
        )
        self.chunks.append(chunk)
        
        # Visit children
        self.generic_visit(node)
    
    def visit_AsyncFunctionDef(self, node):
        """Visit an async function definition node"""
        self.visit_FunctionDef(node)  # Reuse the same logic


class CodeIndexer:
    """Main class for indexing code repositories"""
    
    def __init__(self, repo_path: str, embedding_model: str = "all-MiniLM-L6-v2", index_dir: str = None):
        self.repo_path = os.path.abspath(repo_path)
        self.embedding_model = SentenceTransformer(embedding_model)
        self.index_dir = index_dir or os.path.join(self.repo_path, ".code_index")
        
        # Initialize storage
        self.chunks: List[CodeChunk] = []
        self.chunk_by_id: Dict[str, CodeChunk] = {}
        self.index = None
        self.embedding_dim = self.embedding_model.get_sentence_embedding_dimension()
        
        # Create index directory if it doesn't exist
        os.makedirs(self.index_dir, exist_ok=True)
    
    def get_python_files(self) -> List[str]:
        """Find all Python files in the repository"""
        python_files = []
        for root, _, files in os.walk(self.repo_path):
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    # Skip the index directory and any virtual environments
                    if (self.index_dir in full_path or
                        "venv" in full_path or 
                        "env" in full_path or 
                        "__pycache__" in full_path):
                        continue
                    python_files.append(full_path)
        return python_files
    
    def process_file(self, file_path: str) -> List[CodeChunk]:
        """Process a single Python file and extract code chunks"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code = f.read()
            
            # Parse the code
            visitor = PythonCodeVisitor(code, file_path)
            tree = ast.parse(code)
            visitor.visit(tree)
            
            return visitor.chunks
        except Exception as e:
            print(f"Error processing file {file_path}: {str(e)}")
            return []
    
    def create_embeddings(self, chunks: List[CodeChunk]) -> List[CodeChunk]:
        """Create embeddings for code chunks"""
        texts = []
        for chunk in chunks:
            # Create a rich text representation for embedding
            text = f"{chunk.name} {chunk.type}\n"
            if chunk.docstring:
                text += f"{chunk.docstring}\n"
            text += chunk.content
            texts.append(text)
        
        # Generate embeddings in batches
        embeddings = self.embedding_model.encode(texts, show_progress_bar=True)
        
        # Assign embeddings to chunks
        for i, chunk in enumerate(chunks):
            chunk.embedding = embeddings[i].tolist()
        
        return chunks
    
    def build_index(self) -> None:
        """Build the index from scratch"""
        print(f"Building index for repository: {self.repo_path}")
        
        # Find all Python files
        python_files = self.get_python_files()
        print(f"Found {len(python_files)} Python files")
        
        # Process each file and collect chunks
        all_chunks = []
        for file_path in python_files:
            chunks = self.process_file(file_path)
            all_chunks.extend(chunks)
        
        print(f"Extracted {len(all_chunks)} code chunks")
        
        # Create embeddings for all chunks
        self.chunks = self.create_embeddings(all_chunks)
        self.chunk_by_id = {chunk.id: chunk for chunk in self.chunks}
        
        # Create FAISS index
        self._create_faiss_index()
        
        # Save the index to disk
        self.save_index()
    
    def _create_faiss_index(self) -> None:
        """Create a FAISS index from embeddings"""
        if not self.chunks:
            print("No chunks to index")
            return
        
        # Create a new index
        self.index = faiss.IndexFlatL2(self.embedding_dim)
        
        # Add embeddings to the index
        embeddings = [chunk.embedding for chunk in self.chunks]
        embeddings_array = np.array(embeddings).astype('float32')
        self.index.add(embeddings_array)
    
    def save_index(self) -> None:
        """Save the index to disk"""
        # Save chunks without embeddings
        chunks_data = [chunk.to_dict() for chunk in self.chunks]
        with open(os.path.join(self.index_dir, "chunks.json"), "w") as f:
            json.dump(chunks_data, f)
        
        # Save embeddings separately
        embeddings = [chunk.embedding for chunk in self.chunks]
        with open(os.path.join(self.index_dir, "embeddings.pkl"), "wb") as f:
            pickle.dump(embeddings, f)
        
        # Save FAISS index
        if self.index:
            faiss.write_index(self.index, os.path.join(self.index_dir, "faiss.index"))
    
    def load_index(self) -> bool:
        """Load the index from disk, returns True if successful"""
        chunks_path = os.path.join(self.index_dir, "chunks.json")
        embeddings_path = os.path.join(self.index_dir, "embeddings.pkl")
        faiss_path = os.path.join(self.index_dir, "faiss.index")
        
        if not all(os.path.exists(p) for p in [chunks_path, embeddings_path, faiss_path]):
            return False
        
        try:
            # Load chunks
            with open(chunks_path, "r") as f:
                chunks_data = json.load(f)
            
            # Load embeddings
            with open(embeddings_path, "rb") as f:
                embeddings = pickle.load(f)
            
            # Reconstruct chunks with embeddings
            self.chunks = []
            for i, chunk_data in enumerate(chunks_data):
                chunk = CodeChunk(**chunk_data)
                chunk.embedding = embeddings[i]
                self.chunks.append(chunk)
            
            # Rebuild the chunk_by_id dictionary
            self.chunk_by_id = {chunk.id: chunk for chunk in self.chunks}
            
            # Load FAISS index
            self.index = faiss.read_index(faiss_path)
            
            return True
        
        except Exception as e:
            print(f"Error loading index: {str(e)}")
            return False
    
    def load_or_build_index(self) -> None:
        """Load the index if it exists, otherwise build it"""
        if not self.load_index():
            self.build_index()
    
    def search(self, query: str, k: int = 5) -> List[CodeChunk]:
        """Search the index for chunks relevant to the query"""
        if not self.index:
            raise ValueError("Index not built or loaded")
        
        # Create query embedding
        query_embedding = self.embedding_model.encode([query])[0]
        query_embedding = np.array([query_embedding]).astype('float32')
        
        # Search the index
        distances, indices = self.index.search(query_embedding, k=min(k, len(self.chunks)))
        
        # Return the chunks
        return [self.chunks[idx] for idx in indices[0]]


# End of CodeIndexer class
