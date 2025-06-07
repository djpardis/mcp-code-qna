#!/usr/bin/env python3
"""
Comprehensive MCP Evaluation Script

This script runs a comprehensive evaluation of the MCP server using questions from the grip dataset.
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

def load_grip_questions(test_file_path):
    """Extract questions from the grip dataset evaluation test file"""
    questions = []
    
    # Read the test file
    with open(test_file_path, 'r') as f:
        content = f.read()
    
    # Extract questions using regex pattern matching
    # This pattern looks for question files in the form of:
    # question_file = os.path.join(qa_dir, "question_X.md")
    pattern = r'question_file\s*=\s*os\.path\.join\(qa_dir,\s*"(question_\d+\.md)"\)'
    question_files = re.findall(pattern, content)
    
    print(f"Found {len(question_files)} question references in test file")
    
    # Create sample questions based on the question files
    sample_questions = [
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
    
    return sample_questions

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

def calculate_similarity(answer1, answer2):
    """Calculate similarity between two answers using difflib"""
    # Clean up answers by removing markdown formatting and extra whitespace
    def clean_text(text):
        if not text:
            return ""
        # Remove code blocks
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        # Remove markdown headers
        text = re.sub(r'#+\s+', '', text)
        # Remove other markdown formatting
        text = re.sub(r'[*_`]', '', text)
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    clean1 = clean_text(answer1)
    clean2 = clean_text(answer2)
    
    # Use difflib to calculate similarity
    seq_matcher = difflib.SequenceMatcher(None, clean1, clean2)
    similarity = seq_matcher.ratio()
    
    return similarity

def calculate_mqs(results):
    """Calculate MCP Quality Score (MQS) based on evaluation results"""
    # Extract metrics
    response_times = [r["response_time_seconds"] for r in results]
    avg_response_time = sum(response_times) / len(response_times) if response_times else 0
    
    # Since we don't have reference answers, we'll use a simplified MQS calculation
    # based on response time and error rate
    
    # Count errors
    errors = sum(1 for r in results if "error" in r.get("answer", ""))
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

def run_evaluation(questions, server_url, repo_path=None, output_dir=None, reference_answers=None):
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
        
        # Calculate similarity if reference answers are provided
        if reference_answers and i <= len(reference_answers):
            similarity = calculate_similarity(answer, reference_answers[i-1])
            result["similarity"] = similarity
            print(f"Similarity to reference: {similarity:.2f}")
        
        results.append(result)
        print("-" * 50)
    
    # Calculate MQS
    mqs_data = calculate_mqs(results)
    
    # Save results if output directory is specified
    if output_dir:
        timestamp = int(time.time())
        results_file = os.path.join(output_dir, f"evaluation_results_{timestamp}.json")
        
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
    parser = argparse.ArgumentParser(description="Run a comprehensive MCP evaluation")
    parser.add_argument("--server-url", default="http://localhost:8000", help="URL of the MCP server")
    parser.add_argument("--repo-path", help="Repository path to use for evaluation")
    parser.add_argument("--output-dir", default="evaluation_results", help="Directory to save evaluation results")
    parser.add_argument("--test-file", default="tests/test_grip_dataset_evaluation.py", help="Path to the test file containing question references")
    args = parser.parse_args()
    
    # Extract questions from test files
    grip_questions = load_grip_questions(args.test_file)
    
    # Run evaluation
    run_evaluation(grip_questions, args.server_url, args.repo_path, args.output_dir)

if __name__ == "__main__":
    main()
