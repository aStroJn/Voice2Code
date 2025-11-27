"""
Quick test for the markdown stripping function
"""

def strip_markdown_code_blocks(code: str) -> str:
    """
    Strips markdown code block formatting from generated code.
    Removes ```language and ``` delimiters.
    """
    code = code.strip()
    
    # Remove opening code block with language specifier (e.g., ```python, ```javascript)
    if code.startswith('```'):
        # Find the first newline after the opening ```
        first_newline = code.find('\n')
        if first_newline != -1:
            code = code[first_newline + 1:]
    
    # Remove closing code block
    if code.endswith('```'):
        code = code[:-3]
    
    return code.strip()

# Test cases
test1 = """```python
print("Hello, World!")
```"""

test2 = """```javascript
console.log("Hello, World!");
```"""

test3 = """print("Already clean")"""

print("Test 1 - Python with markdown:")
print(f"Input:\n{test1}")
print(f"\nOutput:\n{strip_markdown_code_blocks(test1)}")
print("\n" + "="*50 + "\n")

print("Test 2 - JavaScript with markdown:")
print(f"Input:\n{test2}")
print(f"\nOutput:\n{strip_markdown_code_blocks(test2)}")
print("\n" + "="*50 + "\n")

print("Test 3 - Already clean:")
print(f"Input:\n{test3}")
print(f"\nOutput:\n{strip_markdown_code_blocks(test3)}")
