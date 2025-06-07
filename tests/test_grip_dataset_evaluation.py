#!/usr/bin/env python3
"""
Test script to evaluate MCP Code QA against the grip dataset questions
"""
import os
import sys
import json
import time
import argparse
import requests
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import difflib

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class GripQAEvaluator:
    """Evaluates MCP Code QA against the grip dataset questions"""
    
    def __init__(self, qa_dir: str, server_url: str, output_dir: Optional[str] = None):
        """
        Initialize the evaluator
        
        Args:
            qa_dir: Path to the grip_qa directory containing question and answer files
            server_url: URL of the MCP server
            output_dir: Directory to save evaluation results (optional)
        """
        self.qa_dir = Path(qa_dir)
        self.server_url = server_url.rstrip('/')
        self.output_dir = Path(output_dir) if output_dir else Path("evaluation_results")
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # Validate the QA directory
        if not self.qa_dir.exists() or not self.qa_dir.is_dir():
            raise ValueError(f"QA directory {qa_dir} does not exist or is not a directory")
            
        # Find all question files
        self.question_files = sorted([f for f in self.qa_dir.glob("*.q.md")])
        if not self.question_files:
            raise ValueError(f"No question files found in {qa_dir}")
            
        print(f"Found {len(self.question_files)} question files in {qa_dir}")
        
    def read_question(self, question_file: Path) -> str:
        """Read a question from a file"""
        with open(question_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
            
    def read_answer(self, answer_file: Path) -> str:
        """Read an answer from a file"""
        with open(answer_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
            
    def get_answer_file(self, question_file: Path) -> Path:
        """Get the corresponding answer file for a question file"""
        answer_file = question_file.with_name(question_file.name.replace('.q.md', '.a.md'))
        if not answer_file.exists():
            raise ValueError(f"Answer file {answer_file} does not exist")
        return answer_file
        
    def ask_question(self, question: str) -> Tuple[str, float]:
        """
        Ask a question to the MCP server
        
        Returns:
            Tuple of (answer, response_time_seconds)
        """
        start_time = time.time()
        response = requests.post(
            f"{self.server_url}/question",
            json={"question": question},
            headers={"Content-Type": "application/json"}
        )
        response_time = time.time() - start_time
        
        if response.status_code != 200:
            return f"ERROR: Server returned status code {response.status_code}", response_time
            
        try:
            result = response.json()
            return result.get("content", "ERROR: No content in response"), response_time
        except Exception as e:
            return f"ERROR: Failed to parse response: {str(e)}", response_time
            
    def calculate_similarity(self, expected: str, actual: str) -> float:
        """
        Calculate similarity between expected and actual answers
        
        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize text for comparison
        def normalize(text):
            # Remove markdown formatting
            text = re.sub(r'[*_`#]', '', text)
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.lower().strip()
            
        expected_norm = normalize(expected)
        actual_norm = normalize(actual)
        
        # Use difflib's SequenceMatcher for similarity calculation
        similarity = difflib.SequenceMatcher(None, expected_norm, actual_norm).ratio()
        return similarity
        
    def evaluate_question(self, question_file: Path) -> Dict:
        """
        Evaluate a single question
        
        Returns:
            Dictionary with evaluation results
        """
        question_id = question_file.stem.split('.')[0]
        question = self.read_question(question_file)
        answer_file = self.get_answer_file(question_file)
        expected_answer = self.read_answer(answer_file)
        
        print(f"\nEvaluating question {question_id}: {question}")
        actual_answer, response_time = self.ask_question(question)
        
        similarity = self.calculate_similarity(expected_answer, actual_answer)
        
        result = {
            "question_id": question_id,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "response_time_seconds": response_time,
            "similarity_score": similarity,
        }
        
        print(f"Response time: {response_time:.2f}s, Similarity score: {similarity:.2f}")
        
        return result
        
    def run_evaluation(self) -> List[Dict]:
        """
        Run evaluation on all questions
        
        Returns:
            List of evaluation results
        """
        results = []
        
        for question_file in self.question_files:
            try:
                result = self.evaluate_question(question_file)
                results.append(result)
                
                # Save individual result
                result_file = self.output_dir / f"{result['question_id']}_result.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2)
                    
            except Exception as e:
                print(f"Error evaluating question {question_file}: {str(e)}")
                
        # Save summary results
        summary_file = self.output_dir / "evaluation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            summary = {
                "total_questions": len(results),
                "average_similarity": sum(r["similarity_score"] for r in results) / len(results) if results else 0,
                "average_response_time": sum(r["response_time_seconds"] for r in results) / len(results) if results else 0,
                "results": results
            }
            json.dump(summary, f, indent=2)
            
        print(f"\nEvaluation complete. Results saved to {self.output_dir}")
        print(f"Total questions: {len(results)}")
        print(f"Average similarity score: {summary['average_similarity']:.2f}")
        print(f"Average response time: {summary['average_response_time']:.2f}s")
        
        return results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Evaluate MCP Code QA against grip dataset questions")
    parser.add_argument("qa_dir", help="Path to the grip_qa directory containing question and answer files")
    parser.add_argument("--server-url", default="http://localhost:8001", help="URL of the MCP server")
    parser.add_argument("--output-dir", help="Directory to save evaluation results")
    args = parser.parse_args()
    
    evaluator = GripQAEvaluator(args.qa_dir, args.server_url, args.output_dir)
    evaluator.run_evaluation()

if __name__ == "__main__":
    main()
