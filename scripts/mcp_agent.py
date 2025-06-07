#!/usr/bin/env python3
"""
MCP Agent - Repository Analysis Tool

This agent uses the MCP server to analyze code repositories and generate
architecture reports, dependency analyses, and design pattern identifications.
"""

import argparse
import json
import os
import requests
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

class MCPAgent:
    """
    Agent that uses the MCP server to analyze repositories and generate reports
    """
    
    def __init__(self, server_url: str, repo_path: str, repo_type: Optional[str] = None):
        """
        Initialize the MCP Agent
        
        Args:
            server_url: URL of the MCP server
            repo_path: Path to the repository to analyze
            repo_type: Type of repository (grip, sample_repo, or other)
        """
        self.server_url = server_url
        self.repo_path = repo_path
        self.repo_type = repo_type
        self.verify_server_connection()
    
    def verify_server_connection(self) -> None:
        """Verify that the MCP server is running and accessible"""
        try:
            # First check if the server is responding at all
            response = requests.get(f"{self.server_url}", timeout=5)
            if response.status_code != 200:
                print(f"Warning: MCP server base URL returned status code {response.status_code}")
                print("Trying to connect to the question endpoint instead...")
            
            # Test with a simple question to verify the server is working
            test_request = {
                "question": "Hello",
                "repo_path": self.repo_path
            }
            
            response = requests.post(
                f"{self.server_url}/question",
                json=test_request,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code != 200:
                print(f"Error: MCP server question endpoint returned status code {response.status_code}")
                print("The server might be running but not properly configured or accessible.")
                print("Please check that the MCP server is running and the repository path is valid.")
                sys.exit(1)
                
        except requests.exceptions.RequestException as e:
            print(f"Error: Could not connect to MCP server at {self.server_url}")
            print(f"Exception: {str(e)}")
            print("\nPlease make sure the MCP server is running with:")
            print(f"  python -m app.mcp_web_server --repo-path {self.repo_path} --port {self.server_url.split(':')[-1]}")
            sys.exit(1)
        
        print(f"✓ Successfully connected to MCP server at {self.server_url}")
        print(f"✓ Repository path: {self.repo_path}")

    
    def ask_question(self, question: str) -> Dict:
        """
        Ask a question to the MCP server
        
        Args:
            question: The question to ask
            
        Returns:
            The response from the server
        """
        request_data = {
            "question": question,
            "repo_path": self.repo_path
        }
        
        try:
            response = requests.post(
                f"{self.server_url}/question",
                json=request_data,
                headers={"Content-Type": "application/json"},
                timeout=60  # Longer timeout for complex questions
            )
            
            if response.status_code != 200:
                error_message = f"Server returned status code {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_message += f": {error_data['error']}"
                except:
                    pass
                return {"error": error_message, "content": f"Unable to answer question due to server error. The MCP server returned: {error_message}"}
            
            try:    
                return response.json()
            except ValueError:
                return {"error": "Invalid JSON response", "content": "The server response could not be parsed as JSON. The question might be too complex or the repository analysis might be incomplete."}
        except requests.exceptions.Timeout:
            return {"error": "Request timed out", "content": "The server took too long to respond. This might be due to the complexity of the question or the size of the repository."}
        except Exception as e:
            return {"error": f"Request failed: {str(e)}", "content": f"Failed to get an answer from the MCP server: {str(e)}. Please check that the server is running and the repository path is valid."}
    
    def analyze_architecture(self) -> Dict:
        """
        Analyze the repository architecture
        
        Returns:
            Dictionary with architecture analysis
        """
        print("Analyzing repository architecture...")
        
        # Questions to ask about the architecture
        questions = [
            "What is the overall architecture of this repository?",
            "What are the main components of this repository?",
            "How do the components interact with each other?",
            "What design patterns are used in this repository?",
            "What is the entry point of this application?",
            "How is the code organized in this repository?"
        ]
        
        results = {}
        for question in questions:
            print(f"  • {question}")
            response = self.ask_question(question)
            if "error" in response:
                results[question] = f"Error: {response['error']}"
            else:
                results[question] = response.get("content", "No content in response")
            
            # Avoid overwhelming the server
            time.sleep(0.5)
        
        return {
            "title": "Architecture Analysis",
            "description": "Analysis of the repository's overall architecture",
            "results": results
        }
    
    def analyze_dependencies(self) -> Dict:
        """
        Analyze the repository dependencies
        
        Returns:
            Dictionary with dependency analysis
        """
        print("Analyzing repository dependencies...")
        
        # Questions to ask about dependencies
        questions = [
            "What external dependencies does this repository use?",
            "What are the main libraries or frameworks used in this repository?",
            "Are there any dependency version constraints?",
            "How are dependencies managed in this repository?",
            "What are the core dependencies vs. development dependencies?"
        ]
        
        results = {}
        for question in questions:
            print(f"  • {question}")
            response = self.ask_question(question)
            if "error" in response:
                results[question] = f"Error: {response['error']}"
            else:
                results[question] = response.get("content", "No content in response")
            
            # Avoid overwhelming the server
            time.sleep(0.5)
        
        return {
            "title": "Dependency Analysis",
            "description": "Analysis of the repository's external dependencies",
            "results": results
        }
    
    def identify_design_patterns(self) -> Dict:
        """
        Identify design patterns used in the repository
        
        Returns:
            Dictionary with design pattern identification
        """
        print("Identifying design patterns...")
        
        # Questions to ask about design patterns
        questions = [
            "What design patterns are implemented in this repository?",
            "Is there any use of the Singleton pattern in this code?",
            "Is there any use of the Factory pattern in this code?",
            "Is there any use of the Observer pattern in this code?",
            "Is there any use of the Strategy pattern in this code?",
            "Is there any use of the Decorator pattern in this code?"
        ]
        
        results = {}
        for question in questions:
            print(f"  • {question}")
            response = self.ask_question(question)
            if "error" in response:
                results[question] = f"Error: {response['error']}"
            else:
                results[question] = response.get("content", "No content in response")
            
            # Avoid overwhelming the server
            time.sleep(0.5)
        
        return {
            "title": "Design Pattern Identification",
            "description": "Identification of design patterns used in the repository",
            "results": results
        }
    
    def generate_report(self, output_dir: str = "reports") -> str:
        """
        Generate a comprehensive report of the repository
        
        Args:
            output_dir: Directory to save the report
            
        Returns:
            Path to the generated report
        """
        print(f"Generating comprehensive report for {self.repo_path}...")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate report sections
        architecture_analysis = self.analyze_architecture()
        dependency_analysis = self.analyze_dependencies()
        design_pattern_identification = self.identify_design_patterns()
        
        # Combine all sections into a single report
        report = {
            "repository_path": self.repo_path,
            "generation_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sections": [
                architecture_analysis,
                dependency_analysis,
                design_pattern_identification
            ]
        }
        
        # Determine repository type for organizing reports
        repo_name = os.path.basename(self.repo_path)
        
        # Use provided repo_type if available, otherwise infer from repo name
        if self.repo_type:
            repo_subdir = self.repo_type
        else:
            # Map common repository names to subdirectories
            repo_type_mapping = {
                "grip": "grip",
                "grip-no-tests": "grip",
                "sample-python-repo": "sample_repo",
                "sample_python_repo": "sample_repo"
            }
            
            # Determine subdirectory based on repo name or use 'other' as default
            repo_subdir = repo_type_mapping.get(repo_name.lower(), "other")
        
        # Create subdirectory if it doesn't exist
        repo_output_dir = os.path.join(output_dir, repo_subdir)
        os.makedirs(repo_output_dir, exist_ok=True)
        
        # Generate filenames with timestamp
        timestamp = int(time.time())
        report_file = os.path.join(repo_output_dir, f"{repo_name}_report_{timestamp}.json")
        markdown_file = os.path.join(repo_output_dir, f"{repo_name}_report_{timestamp}.md")
        html_file = os.path.join(repo_output_dir, f"{repo_name}_report_{timestamp}.html")
        
        # Save report as JSON
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Generate markdown report
        self._generate_markdown_report(report, markdown_file)
        
        # Generate HTML report
        self._generate_html_report(report, html_file)
        
        print(f"Report generated and saved to:")
        print(f"  • JSON: {report_file}")
        print(f"  • Markdown: {markdown_file}")
        print(f"  • HTML: {html_file}")
        
        return html_file
    
    def _generate_markdown_report(self, report: Dict, output_file: str) -> None:
        """
        Generate a markdown report from the JSON report
        
        Args:
            report: The JSON report
            output_file: Path to save the markdown report
        """
        with open(output_file, 'w') as f:
            # Write header
            f.write(f"# Repository Analysis Report\n\n")
            f.write(f"**Repository:** {report['repository_path']}\n\n")
            f.write(f"**Generated:** {report['generation_time']}\n\n")
            
            # Write each section
            for section in report['sections']:
                f.write(f"## {section['title']}\n\n")
                f.write(f"{section['description']}\n\n")
                
                for question, answer in section['results'].items():
                    f.write(f"### {question}\n\n")
                    f.write(f"{answer}\n\n")
    
    def _generate_html_report(self, report: Dict, output_file: str) -> None:
        """
        Generate an HTML report from the JSON report using the template
        
        Args:
            report: The JSON report
            output_file: Path to save the HTML report
        """
        # Read the HTML template
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'report_template.html')
        
        try:
            with open(template_path, 'r') as f:
                template_content = f.read()
                
            # Replace the placeholder with the actual JSON data
            json_data = json.dumps(report)
            html_content = template_content.replace('REPORT_DATA_PLACEHOLDER', json_data)
            
            # Write the HTML report
            with open(output_file, 'w') as f:
                f.write(html_content)
                
        except FileNotFoundError:
            print(f"Warning: HTML template not found at {template_path}. Skipping HTML report generation.")
        except Exception as e:
            print(f"Error generating HTML report: {str(e)}")
            # Fallback to a simple HTML report if template fails
            self._generate_simple_html_report(report, output_file)
            
    def _generate_simple_html_report(self, report: Dict, output_file: str) -> None:
        """
        Generate a simple HTML report without using the template
        
        Args:
            report: The JSON report
            output_file: Path to save the HTML report
        """
        with open(output_file, 'w') as f:
            # Write basic HTML structure
            f.write('<!DOCTYPE html>\n<html lang="en">\n<head>\n')
            f.write('    <meta charset="UTF-8">\n')
            f.write('    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n')
            f.write('    <title>Repository Analysis Report</title>\n')
            f.write('    <style>\n')
            f.write('        body { font-family: Arial, sans-serif; line-height: 1.6; padding: 20px; }\n')
            f.write('        h1 { color: #333; }\n')
            f.write('        h2 { color: #0066cc; margin-top: 30px; }\n')
            f.write('        h3 { color: #444; margin-top: 20px; }\n')
            f.write('        .info { color: #666; }\n')
            f.write('        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }\n')
            f.write('        .question { font-weight: bold; margin-top: 15px; }\n')
            f.write('        .answer { margin-left: 15px; white-space: pre-wrap; }\n')
            f.write('    </style>\n')
            f.write('</head>\n<body>\n')
            
            # Write header
            f.write('    <h1>Repository Analysis Report</h1>\n')
            f.write(f'    <p class="info"><strong>Repository:</strong> {report["repository_path"]}</p>\n')
            f.write(f'    <p class="info"><strong>Generated:</strong> {report["generation_time"]}</p>\n')
            
            # Write each section
            for section in report['sections']:
                f.write(f'    <div class="section">\n')
                f.write(f'        <h2>{section["title"]}</h2>\n')
                f.write(f'        <p>{section["description"]}</p>\n')
                
                for question, answer in section['results'].items():
                    f.write(f'        <div class="question">{question}</div>\n')
                    f.write(f'        <div class="answer">{answer}</div>\n')
                
                f.write('    </div>\n')
            
            # Close HTML
            f.write('    <p class="info">Generated by MCP Agent - Model Context Protocol</p>\n')
            f.write('</body>\n</html>')


def main():
    """Main entry point for the MCP Agent"""
    parser = argparse.ArgumentParser(description="MCP Agent for Repository Analysis")
    parser.add_argument("--server-url", default="http://localhost:8002", help="URL of the MCP server")
    parser.add_argument("--repo-path", required=True, help="Path to the repository to analyze")
    parser.add_argument("--output-dir", default="reports", help="Directory to save the reports")
    parser.add_argument("--repo-type", choices=["grip", "sample_repo", "other"], 
                      help="Type of repository for organizing reports (grip, sample_repo, other)")
    
    args = parser.parse_args()
    
    try:
        agent = MCPAgent(args.server_url, args.repo_path, args.repo_type)
        agent.generate_report(args.output_dir)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
