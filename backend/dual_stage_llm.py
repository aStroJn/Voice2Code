import requests
import json
import time
import os
import re
import jsonschema
import logging
import html
from typing import List
from functools import wraps

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
def load_config():
    cfg = {}
    try:
        # Construct the absolute path to settings.json
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, '..', 'config', 'settings.json')
        with open(config_path, 'r') as f:
            cfg = json.load(f)
    except FileNotFoundError:
        cfg = {}
    cfg['TEMPERATURE'] = float(os.getenv('TEMPERATURE', cfg.get('TEMPERATURE', 0.2))) 
    cfg['OLLAMA_ENDPOINT'] = os.getenv('OLLAMA_ENDPOINT', cfg.get('OLLAMA_ENDPOINT', 'http://127.0.0.1:11434/api/generate'))
    cfg['OLLAMA_MODEL'] = os.getenv('OLLAMA_MODEL', cfg.get('OLLAMA_MODEL', 'gemma3:1b'))
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

def call_ollama_system(user_text: str,
                       system_prompt: str,
                       model: str = None,
                       temperature: float = None,
                       max_tokens: int = None) -> str:
    """
    Call the Ollama endpoint with a system + user message payload.
    Uses CONFIG for defaults (OLLAMA_ENDPOINT, OLLAMA_MODEL, timeouts, retries).
    Returns the model's best-effort textual response (raw string).
    Raises RuntimeError on permanent failure.
    """
    endpoint = CONFIG.get('OLLAMA_ENDPOINT')
    model = model or CONFIG.get('OLLAMA_MODEL')
    temperature = CONFIG.get('TEMPERATURE') if temperature is None else temperature
    max_tokens = CONFIG.get('CODER_MAX_TOKENS') if max_tokens is None else max_tokens
    timeout = CONFIG.get('OLLAMA_TIMEOUT_SECONDS', 60)
    retries = CONFIG.get('LLM_RETRY_COUNT', 2)

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text}
        ],
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False
    }

    last_err = None
    for attempt in range(1, retries + 2):  # attempts = retries+1
        try:
            logging.info(f"Calling Ollama (model={model}) attempt {attempt}/{retries+1}")
            resp = requests.post(endpoint, json=payload, timeout=timeout)
            resp.raise_for_status()

            # Try parse JSON - Ollama versions vary in shape
            try:
                data = resp.json()
            except ValueError:
                # Not JSON; return raw text
                text = resp.text or ""
                logging.debug("Ollama returned non-JSON text.")
                return text.strip()

            # Common patterns:
            # 1) {"response": "..."}  2) {"text": "..."}  3) {"message": {"content": "..."}} 
            # 4) {"choices":[{"message":{"content":"..."}}]}  5) {"choices":[{"text":"..."}]}
            if isinstance(data, dict):
                if "response" in data and isinstance(data["response"], str):
                    return data["response"].strip()
                if "text" in data and isinstance(data["text"], str):
                    return data["text"].strip()
                if "message" in data and isinstance(data["message"], dict) and "content" in data["message"]:
                    return data["message"]["content"].strip()
                if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0:
                    first = data["choices"][0]
                    if isinstance(first, dict):
                        if "message" in first and isinstance(first["message"], dict) and "content" in first["message"]:
                            return first["message"]["content"].strip()
                        if "text" in first and isinstance(first["text"], str):
                            return first["text"].strip()

            # Fallback — return stringified JSON if helpful, else raw text
            try:
                fallback = json.dumps(data, ensure_ascii=False)
                logging.debug("Ollama returned JSON but no known fields matched; returning JSON string fallback.")
                return fallback
            except Exception:
                return (resp.text or "").strip()

        except requests.exceptions.RequestException as e:
            last_err = e
            logging.warning(f"Ollama request attempt {attempt} failed: {e}")
            # backoff
            if attempt <= retries:
                wait = 2 ** (attempt - 1)
                logging.info(f"Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logging.error(f"Ollama API call failed after {retries+1} attempts.")
                break

    # If we get here, all attempts failed
    raise RuntimeError(f"Ollama API call failed after {retries+1} attempts: {last_err}")

def strip_fencing(text: str) -> str:
    """
    - Extracts all code blocks inside ```...``` (with optional language tag) and concatenates them.
    - Removes inline/backtick fences.
    - Unescapes common HTML entities and normalizes whitespace.
    - Returns best-effort raw code text.
    """
    if not text:
        return ""

    t = text.strip()
    # Normalize CRLF
    t = t.replace("\r\n", "\n")

    # 1) If there are fenced code blocks, extract them all and join.
    # Matches ``` or ```lang  ... ```
    fence_pattern = re.compile(r"```(?:[\w+-]*)\n(.*?)```", re.DOTALL | re.IGNORECASE)
    matches = fence_pattern.findall(t)
    if matches:
        # join with two newlines to avoid accidental token merging
        joined = "\n\n".join(m.strip() for m in matches if m and m.strip())
        # final cleanup
        return html.unescape(joined.strip())

    # 2) Otherwise, remove any remaining backticks and leading/trailing single backtick blocks
    t = re.sub(r"`+", "", t)

    # 3) If the model returned JSON or quoted JSON containing code, try to find the first { or first triple-quoted block fallback
    # (we keep it simple here)

    # Unescape HTML entities if any
    t = html.unescape(t).strip()
    return t

def fix_simple_python2_prints(code: str) -> str:
    """
    Best-effort convert simple Python2 print statements to Python3 print() calls.
    - Handles: print 'hello', print("ok") untouched, print var -> print(var)
    - Does NOT attempt full parsing — only simple line-level transformations.
    """
    lines: List[str] = []
    for line in code.splitlines():
        stripped = line.lstrip()
        indent = line[:len(line)-len(stripped)]
        # simple regex: line starts with print <something> and not 'print('
        m = re.match(r"print\s+(.+)$", stripped)
        if m and not stripped.startswith("print(") and not stripped.startswith("print)"):
            inner = m.group(1).strip()
            # avoid converting if it's a statement like print >>file, which is rare
            if not inner.startswith(">>"):
                # ensure single quotes or double quotes are preserved
                lines.append(f"{indent}print({inner})")
                continue
        lines.append(line)
    return "\n".join(lines)


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
            raw_output = call_ollama_system(transcript_text, system_prompt, temperature=CONFIG['TEMPERATURE'], max_tokens=CONFIG['IMPROVER_MAX_TOKENS'])
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
    "You are a precise software engineer. You will receive a JSON task object (already validated). "
    "Produce the exact source code required — nothing else. Output must be ONLY the raw source code text. "
    "REQUIREMENTS:\n"
    "1) Do NOT include markdown, backticks, or any text outside the code itself.\n"
    "2) Use Python 3 syntax (e.g., use print(...)).\n"
    "3) Do not wrap code in ``` fences. Do not include file headers or comments unless the task explicitly requires them.\n"
    "4) If the task needs multiple files, concatenate them in logical order separated by TWO newlines.\n"
    "5) If you cannot comply, output exactly the single-line token: <CANNOT_COMPLY>\n"
    )

    user_input = json.dumps(task_json, ensure_ascii=False)
    try:
        raw_output = call_ollama_system(user_input, system_prompt, temperature=0.0, max_tokens=CONFIG['CODER_MAX_TOKENS'])
        logging.debug(f"Raw coder output:\n{raw_output[:2000]}")  # log the first chunk for debugging
        cleaned_output = strip_fencing(raw_output)
        if cleaned_output.strip() == "<CANNOT_COMPLY>":
            raise RuntimeError("Coder refused to comply with strict output rules.")
        # best-effort fix Python2 prints
        cleaned_output = fix_simple_python2_prints(cleaned_output)
        # remove leading/trailing blank lines
        cleaned_output = cleaned_output.strip() + "\n"
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