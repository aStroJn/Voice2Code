"""
Test script for the Prompt Optimizer (Agent 1)

This script tests the prompt_optimizer module independently to verify
that it correctly optimizes informal voice commands into clear coding requests.
"""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prompt_optimizer import optimize_prompt

def test_optimizer():
    """Test the prompt optimizer with various inputs"""
    
    test_cases = [
        {
            "input": "make a function it should add two numbers",
            "description": "Simple function request"
        },
        {
            "input": "I need to sort a list but in reverse",
            "description": "List operation with clarification"
        },
        {
            "input": "function to check if number is even",
            "description": "Single function with condition"
        },
        {
            "input": "create a loop that prints numbers from 1 to 10",
            "description": "Loop request"
        }
    ]
    
    print("=" * 70)
    print("TESTING AGENT 1 - PROMPT OPTIMIZER")
    print("=" * 70)
    print()
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['description']}")
        print("-" * 70)
        print(f"Input: {test_case['input']}")
        print()
        
        try:
            optimized = optimize_prompt(test_case['input'])
            print(f"Optimized Output: {optimized}")
            print("-" * 70)
        except Exception as e:
            print(f"ERROR: {e}")
            print("-" * 70)
    
    print("\n" + "=" * 70)
    print("TESTING COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    test_optimizer()
