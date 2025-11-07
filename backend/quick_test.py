from dual_stage_llm import call_ollama_system, generate_code_from_task

task = {"summary": "say hello", "requirements": ["print hello"], "constraints": []}
print("=== GENERATED ===")
print(generate_code_from_task(task))
