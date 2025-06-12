#!/usr/bin/env python3
"""
Script to install required NLP models for the MCP Code QA Project.
Run this after installing the package dependencies.
"""

import subprocess
import sys

def install_spacy_model():
    """Install the required spaCy language model."""
    print("Installing spaCy language model...")
    try:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        print("Successfully installed spaCy language model.")
        return True
    except Exception as e:
        print(f"Error installing spaCy language model: {e}")
        print("You may need to manually install it with: python -m spacy download en_core_web_sm")
        return False

if __name__ == "__main__":
    success = install_spacy_model()
    if success:
        print("\nNLP model installation complete! You can now use the MCP Code QA Project.")
    else:
        print("\nNLP model installation encountered issues. Please check the error messages above.")
        sys.exit(1)
