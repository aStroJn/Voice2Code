import requests
import json
import time
import os
import re
import jsonschema
import logging
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
def load_config():
    cfg = {}
    try:
        with open('config/settings.json', 'r') as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    cfg['OLLAMA_ENDPOINT'] = os.getenv('OLLAMA_ENDPOINT', cfg.get('OLLAMA_ENDPOINT', 'http://127.0.0.1:11434/api/generate'))
    cfg['OLLAMA_MODEL'] = os.getenv('OLLAMA_MODEL', cfg.get('OLLAMA_MODEL', 'codellama'))
    cfg['OLLAMA_TIMEOUT_SECONDS'] = int(os.getenv('OLLAMA_TIMEOUT_SECONDS', cfg.get('OLLAMA_TIMEOUT_SECONDS', 60)))
    cfg['LLM_RETRY_COUNT'] = int(os.getenv('LLM_RETRY_COUNT', cfg.get('LLM_RETRY_COUNT', 2)))
    cfg['IMPROVER_MAX_TOKENS'] = int(os.getenv('IMPROVER_MAX_TOKENS', cfg.get('IMPROVER_MAX_TOKENS', 512)))
    cfg['CODER_MAX_TOKENS'] = int(os.getenv('CODER_MAX_TOKENS', cfg.get('CODER_MAX_TOKENS', 1600)))
    return cfg

CONFIG = load_config()

# Schemas for validation
IMPROVER_SCHEMA = {
  "type": "object",
  "required": ["summary", "requirements", "constraints"],
  "properties": {
    "summary": {"type": "string"},
    "requirements": {
      "type": "array",
      "items": {"type": "string"},
      "minItems": 1,
      "maxItems": 7
    },
    "constraints": {
      "type": "array",
      "items": {"type": "string"}
    },
    "example_io": {"type": "object"}
  }
}

CODER_SCHEMA = {
    "type": "string"
}

def strip_fencing(text: str) -> str:
    if not text:
        return ""
    t = text.strip()
    
    # Remove common markdown fences
    t = re.sub(r"^```[\w-]*\s*", "", t)      # remove opening fence with language
    t = re.sub(r"```$", "", t)               # remove trailing fence at end
    t = re.sub(r"```", "", t)                # remove any remaining fences
    t = re.sub(r"^`+|`+$", "", t)            # remove stray backticks
    
    # Trim again and normalize line endings
    t = t.strip().replace("\r\n", "\n")
    return t

def validate_schema(obj, schema):
    try:
        jsonschema.validate(instance=obj, schema=schema)
        return None
    except jsonschema.exceptions.ValidationError as e:
        return e

def improve_transcript(transcript_text):
    system_prompt = (
        "You are an assistant that converts raw transcribed user speech into a clear, unambiguous JSON task "
        "object for a code generator. Output EXACTLY one JSON object with keys: summary, requirements, constraints, example_io (optional). "
        "Do not produce any additional text."
        "\n\nExample Input: \"make a function that downloads s3 files and unzip them\""
        "\n\nExample Output: {\"summary\": \"Downloads files from S3 and unzips them.\", \"requirements\": [\"Create a Python function that takes a bucket name and a list of file keys as input.\", \"Download the files from S3.\", \"Unzip the downloaded files.\"], \"constraints\": [\"Use the boto3 library.\", \"The function should handle errors gracefully.\"]} "

    )
    for attempt in range(CONFIG['LLM_RETRY_COUNT']):
        try:
            raw_output = call_ollama_system(transcript_text, system_prompt, max_tokens=CONFIG['IMPROVER_MAX_TOKENS'])
            cleaned_output = strip_fencing(raw_output)
            task_json = json.loads(cleaned_output)
            error = validate_schema(task_json, IMPROVER_SCHEMA)
            if error:
                raise ValueError(f"Schema validation failed: {error}")
            return task_json
        except Exception as e:
            logging.error(f"Attempt {attempt + 1}/{CONFIG['LLM_RETRY_COUNT']}: Failed to improve transcript. Error: {e}")
            if attempt < CONFIG['LLM_RETRY_COUNT'] - 1:
                system_prompt = "Output EXACTLY one JSON object and nothing else."
            else:
                if not os.path.exists('logs'):
                    os.makedirs('logs')
                debug_id = f"llm_fail_{int(time.time())}_{hash(transcript_text)}.log"
                with open(f"logs/{debug_id}", "w") as f:
                    f.write(f"Transcript: {transcript_text}\n")
                    f.write(f"Raw Output: {raw_output}\n")
                    f.write(f"Exception: {e}\n")
                return {"error": "improver_parse_failed", "raw": raw_output[:100], "debug_id": debug_id}
    return {"error": "improver_parse_failed", "raw": "", "debug_id": ""}

def generate_code_from_task(task_json):
    system_prompt = (
    "You are a precise software engineer. You receive a JSON task object. Produce the code to complete the task."
    "In the 'content' field, write only the raw code — "
    "DO NOT use markdown fences, backticks, syntax highlighting tags, or commentary. "
    "No ```python``` fences, no markdown, no explanations outside the JSON structure."
    )

    user_input = json.dumps(task_json, ensure_ascii=False)
    try:
        raw_output = call_ollama_system(user_input, system_prompt, max_tokens=CONFIG['CODER_MAX_TOKENS'])
        cleaned_output = strip_fencing(raw_output)
        return cleaned_output
    except Exception as e:
        logging.error(f"Failed to generate code. Error: {e}")
        if not os.path.exists('logs'):
            os.makedirs('logs')
        debug_id = f"llm_fail_{int(time.time())}_{hash(user_input)}.log"
        with open(f"logs/{debug_id}", "w") as f:
            f.write(f"Task: {user_input}\n")
            f.write(f"Exception: {e}\n")
        return {"error": "coder_failed", "debug_id": debug_id}
