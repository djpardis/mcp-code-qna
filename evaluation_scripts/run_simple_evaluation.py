#!/usr/bin/env python3
"""
Simple MCP Evaluation Script

This script runs a simple evaluation of the MCP server using questions from our test files.
"""

import argparse
import json
import os
import requests
import time
from pathlib import Path

def extract_test_questions(test_file):
    """Extract test questions from a test file"""
    questions = []
    
    with open(test_file, 'r') as f:
        content = f.read()
        
    # Extract questions from test_sample_repo_question_understanding.py
    if "test_sample_repo_question_understanding.py" in test_file:
        # Simple extraction - not perfect but works for our test file
        lines = content.split('\n')
        for line in lines:
            if '("' in line and '",' in line and "QuestionIntent" in line:
                question = line.split('("')[1].split('",')[0]
                questions.append(question)
                
    return questions

def ask_question(question, server_url, repo_path=None):
    """Ask a question to the MCP server"""
    start_time = time.time()
    request_data = {"question": question}
    
    # Add repo_path if provided
    if repo_path:
        request_data["repo_path"] = repo_path
        
    try:
        response = requests.post(
            f"{server_url}/question",
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response_time = time.time() - start_time
        
        if response.status_code != 200:
            return {"error": f"Server returned status code {response.status_code}"}, response_time
            
        result = response.json()
        return result, response_time
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}, time.time() - start_time

def run_evaluation(questions, server_url, repo_path=None, output_dir=None):
    """Run evaluation on a list of questions"""
    results = []
    
    # Create output directory if needed
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    
    print(f"Running evaluation on {len(questions)} questions...")
    print(f"Repository path: {repo_path or 'Not specified'}")
    print("-" * 50)
    
    for i, question in enumerate(questions, 1):
        print(f"Question {i}/{len(questions)}: {question}")
        
        response, response_time = ask_question(question, server_url, repo_path)
        
        # Check for errors
        if "error" in response:
            print(f"ERROR: {response['error']}")
            answer = f"ERROR: {response['error']}"
        else:
            answer = response.get("content", "No content in response")
            print(f"Response received in {response_time:.2f}s")
        
        result = {
            "question_id": i,
            "question": question,
            "answer": answer,
            "response_time_seconds": response_time,
        }
        
        results.append(result)
        print("-" * 50)
    
    # Save results if output directory is specified
    if output_dir:
        timestamp = int(time.time())
        results_file = os.path.join(output_dir, f"evaluation_results_{timestamp}.json")
        
        with open(results_file, 'w') as f:
            json.dump({
                "total_questions": len(results),
                "average_response_time": sum(r["response_time_seconds"] for r in results) / len(results) if results else 0,
                "repository_path": repo_path,
                "results": results
            }, f, indent=2)
            
        print(f"Results saved to {results_file}")
    
    # Print summary
    if results:
        avg_time = sum(r["response_time_seconds"] for r in results) / len(results)
        print(f"\nEvaluation complete. {len(results)} questions processed.")
        print(f"Average response time: {avg_time:.2f}s")
    else:
        print("\nNo results to report.")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Run a simple MCP evaluation")
    parser.add_argument("--server-url", default="http://localhost:8000", help="URL of the MCP server")
    parser.add_argument("--repo-path", help="Repository path to use for evaluation")
    parser.add_argument("--output-dir", default="evaluation_results", help="Directory to save evaluation results")
    args = parser.parse_args()
    
    # Extract questions from test files
    sample_repo_questions = extract_test_questions("tests/test_sample_repo_question_understanding.py")
    
    # Run evaluation
    run_evaluation(sample_repo_questions, args.server_url, args.repo_path, args.output_dir)

if __name__ == "__main__":
    main()
