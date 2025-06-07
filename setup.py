"""
Setup script for MCP Code QA Project.
This will install all required dependencies including spaCy language models.
"""

import subprocess
import sys
from setuptools import setup, find_packages

# Define package metadata
setup(
    name="mcp-code-qa",
    version="0.1.0",
    description="MCP Code QA Project",
    author="MCP Team",
    packages=find_packages(),
    install_requires=[
        # Core dependencies will be read from requirements.txt
    ],
)

# Install spaCy language model
print("Installing spaCy language model...")
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
    print("Successfully installed spaCy language model.")
except Exception as e:
    print(f"Error installing spaCy language model: {e}")
    print("You may need to manually install it with: python -m spacy download en_core_web_sm")

print("\nSetup complete! You can now use the MCP Code QA Project.")
