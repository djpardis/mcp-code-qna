"""
Retrieval component for finding relevant code chunks for a given query.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass

from app.indexer.code_indexer import CodeIndexer, CodeChunk


@dataclass
class RetrievedChunk:
    """Class representing a retrieved code chunk with relevance score"""
    chunk: CodeChunk
    score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        result = self.chunk.to_dict()
        result['relevance_score'] = self.score
        return result


class Retriever:
    """Retriever for finding relevant code chunks"""
    
    def __init__(self, indexer: CodeIndexer, top_k: int = 5):
        self.indexer = indexer
        self.top_k = top_k
    
    def retrieve(self, query: str, k: Optional[int] = None) -> List[RetrievedChunk]:
        """
        Retrieve relevant code chunks for a given query
        
        Args:
            query: The query to search for
            k: Number of results to return, defaults to the value set in the constructor
            
        Returns:
            List of RetrievedChunk objects ordered by relevance
        """
        k = k or self.top_k
        
        # Search for relevant chunks using the indexer
        chunks = self.indexer.search(query, k=k)
        
        # Calculate relevance scores
        scores = self._calculate_relevance_scores(query, chunks)
        
        # Create RetrievedChunk objects
        retrieved_chunks = [
            RetrievedChunk(chunk=chunk, score=score)
            for chunk, score in zip(chunks, scores)
        ]
        
        # Sort by relevance score (highest first)
        retrieved_chunks.sort(key=lambda x: x.score, reverse=True)
        
        return retrieved_chunks
    
    def _calculate_relevance_scores(self, query: str, chunks: List[CodeChunk]) -> List[float]:
        """
        Calculate relevance scores between query and chunks
        
        Uses cosine similarity between query embedding and chunk embeddings.
        
        Args:
            query: The query string
            chunks: List of code chunks
            
        Returns:
            List of relevance scores
        """
        if not chunks:
            return []
            
        # Get query embedding
        query_embedding = self.indexer.embedding_model.encode([query])[0]
        
        # Calculate cosine similarities
        scores = []
        for chunk in chunks:
            if chunk.embedding:
                # Cosine similarity calculation
                dot_product = np.dot(query_embedding, chunk.embedding)
                norm_query = np.linalg.norm(query_embedding)
                norm_chunk = np.linalg.norm(chunk.embedding)
                
                if norm_query * norm_chunk == 0:
                    score = 0.0
                else:
                    score = dot_product / (norm_query * norm_chunk)
                
                scores.append(float(score))
            else:
                scores.append(0.0)
        
        return scores
