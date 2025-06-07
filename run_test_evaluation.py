#!/usr/bin/env python3
"""
Test-Based MCP Evaluation Script

This script runs an evaluation of the MCP server using questions from the test files.
"""

import argparse
import json
import os
import requests
import time
import re
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def extract_test_questions():
    """Extract test questions from the test files"""
    # Sample Python Repository Questions (from test_sample_repo_question_understanding.py)
    sample_repo_questions = [
        # Statistical questions
        "How many functions are there in the codebase?",
        "Count the number of classes in the project",
        
        # Purpose questions
        "What does the processData function do?",
        "Explain the purpose of UserManager class",
        
        # Implementation questions
        "How is the authentication system implemented?",
        
        # Method listing questions
        "What methods does the FileHandler class have?",
        
        # Usage example questions
        "How do I use the connect_database function?",
        
        # Questions with code identifiers in different formats
        "Explain the user_authentication_service",  # snake_case
        "What does the UserAuthenticationService do?",  # PascalCase
        "Explain the userAuthenticationService",  # camelCase
    ]
    
    # Grip Repository Questions (from run_comprehensive_evaluation.py)
    grip_questions = [
        "How do I run grip from command line on a specific port?",
        "Can I modify and distribute the Grip software, and are there any conditions I need to follow?",
        "What command-line arguments does grip accept?",
        "How do I install grip and its dependencies?",
        "How can I use grip to preview a specific markdown file?",
        "What is ReadmeNotFoundError exception? Please give a usage example.",
        "DirectoryReader - please explain the purpose of the class.",
        "What is the purpose of the app.py file?",
        "What does the render_content function do?",
        "What is the purpose of the path_type function?",
        "How does Grip handle the rendering of GitHub-style task lists?",
        "How does Grip handle GitHub API authentication for rate limiting?",
        "How does Grip parse command line arguments?",
        "How does Grip handle different markdown flavors?",
        "What is the implementation of the export feature?",
        "How does Grip implement caching for API responses?"
    ]
    
    return {
        "sample_repo": sample_repo_questions,
        "grip": grip_questions
    }

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
            timeout=60  # Longer timeout for complex questions
        )
        response_time = time.time() - start_time
        
        if response.status_code != 200:
            return {"error": f"Server returned status code {response.status_code}"}, response_time
            
        result = response.json()
        return result, response_time
    except Exception as e:
        return {"error": f"Request failed: {str(e)}"}, time.time() - start_time

def calculate_mqs(results):
    """Calculate MCP Quality Score (MQS) based on evaluation results"""
    # Extract metrics
    response_times = [r["response_time_seconds"] for r in results]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    # Count errors
    errors = sum(1 for r in results if "error" in r.get("answer", "").lower())
    error_rate = errors / len(results) if results else 1.0
    
    # Response time score (0-10)
    # Lower is better, with diminishing returns after 1 second
    time_score = max(0, 10 - (avg_response_time * 5)) if avg_response_time < 2 else 0
    
    # Error rate score (0-10)
    error_score = 10 * (1 - error_rate)
    
    # Calculate MQS (weighted average)
    mqs = (time_score * 0.3) + (error_score * 0.7)
    
    return {
        "mqs": round(mqs, 2),
        "avg_response_time": round(avg_response_time, 2),
        "error_rate": round(error_rate, 2),
        "time_score": round(time_score, 2),
        "error_score": round(error_score, 2)
    }

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
    
    # Calculate MQS
    mqs_data = calculate_mqs(results)
    
    # Save results if output directory is specified
    if output_dir:
        timestamp = int(time.time())
        repo_name = os.path.basename(repo_path) if repo_path else "unknown"
        results_file = os.path.join(output_dir, f"{repo_name}_results_{timestamp}.json")
        
        with open(results_file, 'w') as f:
            json.dump({
                "total_questions": len(results),
                "average_response_time": sum(r["response_time_seconds"] for r in results) / len(results) if results else 0,
                "repository_path": repo_path,
                "mqs": mqs_data,
                "results": results
            }, f, indent=2)
            
        print(f"Results saved to {results_file}")
    
    # Print summary
    if results:
        avg_time = sum(r["response_time_seconds"] for r in results) / len(results)
        print(f"\nEvaluation complete. {len(results)} questions processed.")
        print(f"Average response time: {avg_time:.2f}s")
        print(f"MCP Quality Score (MQS): {mqs_data['mqs']:.2f}/10")
        print(f"Error rate: {mqs_data['error_rate']:.2%}")
    else:
        print("\nNo results to report.")
    
    return results, mqs_data

def main():
    parser = argparse.ArgumentParser(description="Run an MCP evaluation using test questions")
    parser.add_argument("--server-url", default="http://localhost:8000", help="URL of the MCP server")
    parser.add_argument("--repo-path", required=True, help="Repository path to use for evaluation")
    parser.add_argument("--output-dir", default="evaluation_results", help="Directory to save evaluation results")
    parser.add_argument("--repo-type", choices=["sample_repo", "grip"], required=True, help="Type of repository to evaluate")
    args = parser.parse_args()
    
    # Extract questions from test files
    all_questions = extract_test_questions()
    
    # Select questions based on repository type
    if args.repo_type == "sample_repo":
        questions = all_questions["sample_repo"]
    else:  # grip
        questions = all_questions["grip"]
    
    # Run evaluation
    run_evaluation(questions, args.server_url, args.repo_path, args.output_dir)

if __name__ == "__main__":
    main()
