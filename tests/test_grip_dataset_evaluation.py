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
            repo_path: Optional repository path to use for this evaluation
            output_dir: Directory to save evaluation results (optional)
        """
        self.qa_dir = Path(qa_dir)
        self.server_url = server_url
        self.repo_path = repo_path
        
        # Create output directory
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path("evaluation_results") / f"eval_{int(time.time())}"  
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
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
        
    def ask_question(self, question: str, repo_path: str = None) -> Tuple[str, float]:
        """
        Ask a question to the MCP server
        
        Args:
            question: The question to ask
            repo_path: Optional repository path to use for this question
            
        Returns:
            Tuple of (answer, response_time_seconds)
        """
        start_time = time.time()
        request_data = {"question": question}
        
        # Add repo_path if provided
        if repo_path:
            request_data["repo_path"] = repo_path
            
        response = requests.post(
            f"{self.server_url}/question",
            json=request_data,
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
        
    def evaluate_question(self, question_file: Path, repo_path: str = None) -> Dict:
        """
        Evaluate a single question
        
        Args:
            question_file: Path to the question file
            repo_path: Optional repository path to use for this question
            
        Returns:
            Dictionary with evaluation results
        """
        question_id = question_file.stem.split('.')[0]
        question = self.read_question(question_file)
        answer_file = self.get_answer_file(question_file)
        expected_answer = self.read_answer(answer_file)
        
        print(f"\nEvaluating question {question_id}: {question}")
        actual_answer, response_time = self.ask_question(question, repo_path)
        
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
                # Use the repository path if provided
                result = self.evaluate_question(question_file, self.repo_path)
                results.append(result)
                
                # Save individual result
                result_file = self.output_dir / f"{result['question_id']}_result.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2)
                    
            except Exception as e:
                print(f"Error evaluating question {question_file}: {str(e)}")
                
        # Calculate additional metrics
        if results:
            similarity_scores = [r["similarity_score"] for r in results]
            response_times = [r["response_time_seconds"] for r in results]
            
            # Calculate percentile scores
            p90_similarity = sorted(similarity_scores)[int(len(similarity_scores) * 0.9)]
            p10_similarity = sorted(similarity_scores)[int(len(similarity_scores) * 0.1)]
            
            # Count high-quality answers (similarity > 0.7)
            high_quality = sum(1 for score in similarity_scores if score > 0.7)
            high_quality_percentage = (high_quality / len(results)) * 100 if results else 0
            
            # Calculate standard deviation
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            std_dev = (sum((x - avg_similarity) ** 2 for x in similarity_scores) / len(similarity_scores)) ** 0.5
        else:
            p90_similarity = 0
            p10_similarity = 0
            high_quality = 0
            high_quality_percentage = 0
            avg_similarity = 0
            std_dev = 0
                
        # Save summary results
        summary_file = self.output_dir / "evaluation_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            summary = {
                "total_questions": len(results),
                "average_similarity": sum(r["similarity_score"] for r in results) / len(results) if results else 0,
                "average_response_time": sum(r["response_time_seconds"] for r in results) / len(results) if results else 0,
                "p90_similarity": p90_similarity,
                "p10_similarity": p10_similarity,
                "high_quality_answers": high_quality,
                "high_quality_percentage": high_quality_percentage,
                "similarity_std_dev": std_dev,
                "repository_path": self.repo_path,
                "results": results
            }
            json.dump(summary, f, indent=2)
            
        print(f"\nEvaluation complete. Results saved to {self.output_dir}")
        print(f"Total questions: {len(results)}")
        print(f"Average similarity score: {summary['average_similarity']:.2f}")
        print(f"P90 similarity score: {p90_similarity:.2f}")
        print(f"High-quality answers: {high_quality_percentage:.1f}%")
        print(f"Average response time: {summary['average_response_time']:.2f}s")
        
        return results

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Evaluate MCP Code QA against grip dataset questions")
    parser.add_argument("qa_dir", help="Path to the grip_qa directory containing question and answer files")
    parser.add_argument("--server-url", default="http://localhost:8001", help="URL of the MCP server")
    parser.add_argument("--repo-path", help="Repository path to use for evaluation")
    parser.add_argument("--output-dir", help="Directory to save evaluation results")
    args = parser.parse_args()
    
    evaluator = GripQAEvaluator(args.qa_dir, args.server_url, args.repo_path, args.output_dir)
    evaluator.run_evaluation()

if __name__ == "__main__":
    main()
