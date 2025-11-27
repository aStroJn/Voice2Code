"""
Test script for the Coder Agent (Agent 2)

This script tests the ollama_wrapper module with optimized prompts
to verify code generation quality.
"""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ollama_wrapper import get_raw_code

def test_coder():
    """Test the coder agent with pre-optimized prompts"""
    
    test_cases = [
        {
            "input": "Create a Python function named 'add' that takes two parameters and returns their sum.",
            "description": "Addition function (optimized input)"
        },
        {
            "input": "Create Python code to sort a list in descending order.",
            "description": "List sorting (optimized input)"
        },
        {
            "input": "Create a Python function named 'is_even' that takes a number as input and returns True if it's even, False otherwise.",
            "description": "Even number checker (optimized input)"
        }
    ]
    
    print("=" * 70)
    print("TESTING AGENT 2 - CODER AGENT")
    print("=" * 70)
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['description']}")
        print("-" * 70)
        print(f"Input (Optimized Prompt): {test_case['input']}")
        print()
        
        try:
            # Create full prompt with coder instructions
            coder_prompt = """You are an expert Python programmer.
A user has provided a coding request (already optimized and clarified).

Generate only the Python code to fulfill this request.
- Do not add explanations or markdown formatting like ```python
- Provide only the code snippet
- Do not create/define new functions unless explicitly requested

CODING REQUEST:"""
            
            full_prompt = f"{coder_prompt}\n\n{test_case['input']}"
            
            code = get_raw_code(full_prompt)
            print(f"Generated Code:\n{code}")
            print("-" * 70)
        except Exception as e:
            print(f"ERROR: {e}")
            print("-" * 70)
    
    print("\n" + "=" * 70)
    print("TESTING COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_coder()
