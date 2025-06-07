#!/usr/bin/env python3
"""
MCP Evaluation Script

This script runs comprehensive evaluations of the MCP server against multiple repositories
and generates evaluation scores and reports.
"""

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

def run_server(host="127.0.0.1", port=8001, repo_path=None):
    """Start the MCP server in a subprocess"""
    cmd = ["python", "-m", "app.mcp_web_server", "--host", host, "--port", str(port)]
    
    if repo_path:
        cmd.extend(["--repo_path", repo_path])
        
    print(f"Starting MCP server: {' '.join(cmd)}")
    return subprocess.Popen(cmd)

def run_evaluation(qa_dir, server_url, repo_path=None, output_dir=None):
    """Run the evaluation using the test_grip_dataset_evaluation.py script"""
    cmd = ["python", "tests/test_grip_dataset_evaluation.py", qa_dir, 
           "--server-url", server_url]
    
    if repo_path:
        cmd.extend(["--repo-path", repo_path])
        
    if output_dir:
        cmd.extend(["--output-dir", output_dir])
    
    print(f"Running evaluation: {' '.join(cmd)}")
    subprocess.run(cmd)

def create_evaluation_report(eval_dirs, output_file="evaluation_report.md"):
    """Create a comprehensive evaluation report from multiple evaluation runs"""
    report = ["# MCP Evaluation Report\n", 
              f"Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"]
    
    all_results = []
    
    # Process each evaluation directory
    for eval_dir in eval_dirs:
        summary_file = Path(eval_dir) / "evaluation_summary.json"
        if not summary_file.exists():
            print(f"Warning: Summary file not found in {eval_dir}")
            continue
            
        with open(summary_file, 'r') as f:
            summary = json.load(f)
            
        repo_path = summary.get("repository_path", "Unknown")
        repo_name = os.path.basename(repo_path) if repo_path else "Unknown"
        
        report.append(f"\n## Repository: {repo_name}\n")
        report.append(f"Repository Path: `{repo_path}`\n")
        report.append(f"Total Questions: {summary['total_questions']}\n")
        report.append(f"Average Similarity Score: {summary['average_similarity']:.2f}\n")
        report.append(f"P90 Similarity Score: {summary['p90_similarity']:.2f}\n")
        report.append(f"P10 Similarity Score: {summary['p10_similarity']:.2f}\n")
        report.append(f"High-Quality Answers: {summary['high_quality_percentage']:.1f}%\n")
        report.append(f"Similarity Standard Deviation: {summary['similarity_std_dev']:.2f}\n")
        report.append(f"Average Response Time: {summary['average_response_time']:.2f}s\n")
        
        # Calculate MCP Quality Score (MQS)
        mqs = (
            0.5 * summary['average_similarity'] + 
            0.3 * (summary['high_quality_percentage'] / 100) + 
            0.1 * (1 - min(1, summary['similarity_std_dev'])) +  # Lower std dev is better
            0.1 * min(1, 5 / summary['average_response_time'])   # Faster is better, with diminishing returns
        ) * 10  # Scale to 0-10
        
        report.append(f"**MCP Quality Score (MQS): {mqs:.1f}/10**\n")
        
        # Store for comparison
        all_results.append({
            "repo_name": repo_name,
            "repo_path": repo_path,
            "mqs": mqs,
            "avg_similarity": summary['average_similarity'],
            "high_quality": summary['high_quality_percentage'],
            "response_time": summary['average_response_time']
        })
        
        # Add detailed question analysis
        report.append("\n### Question Analysis\n")
        report.append("| Question ID | Question | Similarity Score | Response Time (s) |\n")
        report.append("|------------|----------|------------------|------------------|\n")
        
        for result in summary['results']:
            question_short = result['question'][:50] + "..." if len(result['question']) > 50 else result['question']
            report.append(f"| {result['question_id']} | {question_short} | {result['similarity_score']:.2f} | {result['response_time_seconds']:.2f} |\n")
    
    # Add comparison section if we have multiple repositories
    if len(all_results) > 1:
        report.append("\n## Repository Comparison\n")
        report.append("| Repository | MQS | Avg Similarity | High-Quality % | Avg Response Time (s) |\n")
        report.append("|------------|-----|---------------|----------------|----------------------|\n")
        
        for result in all_results:
            report.append(f"| {result['repo_name']} | {result['mqs']:.1f} | {result['avg_similarity']:.2f} | {result['high_quality']:.1f}% | {result['response_time']:.2f} |\n")
    
    # Write the report
    with open(output_file, 'w') as f:
        f.writelines(report)
        
    print(f"Evaluation report written to {output_file}")
    
    # Create visualization if we have matplotlib
    try:
        if len(all_results) > 0:
            create_visualizations(all_results, output_file.replace('.md', '.png'))
    except Exception as e:
        print(f"Could not create visualizations: {str(e)}")

def create_visualizations(results, output_file):
    """Create visualizations of the evaluation results"""
    repo_names = [r['repo_name'] for r in results]
    mqs_scores = [r['mqs'] for r in results]
    similarities = [r['avg_similarity'] for r in results]
    high_qualities = [r['high_quality'] for r in results]
    response_times = [r['response_time'] for r in results]
    
    fig, axs = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle('MCP Evaluation Results')
    
    # MQS Scores
    axs[0, 0].bar(repo_names, mqs_scores)
    axs[0, 0].set_title('MCP Quality Score')
    axs[0, 0].set_ylim(0, 10)
    
    # Similarity Scores
    axs[0, 1].bar(repo_names, similarities)
    axs[0, 1].set_title('Average Similarity Score')
    axs[0, 1].set_ylim(0, 1)
    
    # High-Quality Percentages
    axs[1, 0].bar(repo_names, high_qualities)
    axs[1, 0].set_title('High-Quality Answers (%)')
    axs[1, 0].set_ylim(0, 100)
    
    # Response Times
    axs[1, 1].bar(repo_names, response_times)
    axs[1, 1].set_title('Average Response Time (s)')
    
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Visualization saved to {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Run comprehensive MCP evaluations")
    parser.add_argument("--start-server", action="store_true", help="Start the MCP server")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the MCP server")
    parser.add_argument("--port", type=int, default=8001, help="Port for the MCP server")
    parser.add_argument("--grip-qa-dir", help="Path to the grip_qa directory")
    parser.add_argument("--sample-qa-dir", help="Path to the sample repository QA directory")
    parser.add_argument("--grip-repo", default="/Users/pardisnoorzad/Documents/grip-no-tests", 
                        help="Path to the grip repository")
    parser.add_argument("--sample-repo", default="/Users/pardisnoorzad/Documents/sample-python-repo", 
                        help="Path to the sample Python repository")
    parser.add_argument("--output-dir", default="evaluation_results", 
                        help="Base directory to save evaluation results")
    args = parser.parse_args()
    
    server_url = f"http://{args.host}:{args.port}"
    server_process = None
    
    try:
        # Start the server if requested
        if args.start_server:
            server_process = run_server(args.host, args.port)
            print("Waiting for server to start...")
            time.sleep(5)  # Give the server time to start
        
        eval_dirs = []
        timestamp = int(time.time())
        
        # Run grip evaluation if QA directory is provided
        if args.grip_qa_dir:
            grip_output_dir = os.path.join(args.output_dir, f"grip_eval_{timestamp}")
            run_evaluation(args.grip_qa_dir, server_url, args.grip_repo, grip_output_dir)
            eval_dirs.append(grip_output_dir)
        
        # Run sample repo evaluation if QA directory is provided
        if args.sample_qa_dir:
            sample_output_dir = os.path.join(args.output_dir, f"sample_eval_{timestamp}")
            run_evaluation(args.sample_qa_dir, server_url, args.sample_repo, sample_output_dir)
            eval_dirs.append(sample_output_dir)
        
        # Create evaluation report
        if eval_dirs:
            create_evaluation_report(eval_dirs)
        
    finally:
        # Stop the server if we started it
        if server_process:
            print("Stopping MCP server...")
            server_process.terminate()
            server_process.wait()

if __name__ == "__main__":
    main()
