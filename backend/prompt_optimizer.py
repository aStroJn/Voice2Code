import requests
import json
import os
import logging
import time

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _load_optimizer_config() -> dict:
    """Loads configuration from both paths.json and settings.json for the optimizer."""
    config = {}
    dir_path = os.path.dirname(os.path.realpath(__file__))
    
    paths_config_path = os.path.join(dir_path, '..', 'config', 'paths.json')
    settings_config_path = os.path.join(dir_path, '..', 'config', 'settings.json')
    
    config = _load_json_config(paths_config_path, config)
    config = _load_json_config(settings_config_path, config)

    # Get optimizer-specific configuration
    config['ollama_endpoint'] = config.get('ollama_endpoint', config.get('paths', {}).get('ollama_endpoint'))
         
    return config

def _load_json_config(file_path: str, config: dict) -> dict:
    """Loads a JSON configuration file and updates the provided config dictionary."""
    try:
        with open(file_path, "r") as f:
            config.update(json.load(f))
            logging.info(f"Loaded config from {file_path}")
    except FileNotFoundError:
        logging.warning(f"{file_path} not found.")
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON in {file_path}: {e}")
    return config

def optimize_prompt(transcribed_text: str) -> str:
    """
    Sends transcribed text to the Optimizer Agent (Agent 1) to clarify and optimize the prompt.
    
    Args:
        transcribed_text: Raw text from speech transcription
        
    Returns:
        Optimized, clarified prompt ready for code generation
    """
    config = _load_optimizer_config()
    ollama_endpoint = config.get("ollama_endpoint")
    optimizer_model = config.get("optimizer_model", config.get("ollama_model", "gemma3:1b"))
    optimizer_prompt_template = config.get("optimizer_prompt", _get_default_optimizer_prompt())
    language = config.get("language", "python").capitalize()  # Get language and capitalize it

    if not ollama_endpoint:
        logging.error("Ollama endpoint not found in configuration.")
        return transcribed_text  # Fallback: return original text

    # Inject the language into the prompt template
    optimizer_prompt = optimizer_prompt_template.replace("{language}", language)

    logging.info("=" * 60)
    logging.info("AGENT 1 - PROMPT OPTIMIZER")
    logging.info("=" * 60)
    logging.info(f"Endpoint: {ollama_endpoint}")
    logging.info(f"Model: {optimizer_model}")
    logging.info(f"Target Language: {language}")
    logging.info(f"Input (Transcribed): {transcribed_text}")

    # Retry mechanism
    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # Combine the optimizer's system prompt with the user's transcribed text
            full_prompt = f"{optimizer_prompt}\n\nUSER REQUEST:\n{transcribed_text}"
            
            payload = {
                "model": optimizer_model,
                "prompt": full_prompt,
                "stream": False
            }

            response = requests.post(
                ollama_endpoint,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            response_data = response.json()
            optimized_text = response_data.get('response', '')
            
            if optimized_text:
                optimized_text = optimized_text.strip()
                logging.info(f"Output (Optimized): {optimized_text}")
                logging.info("=" * 60)
                return optimized_text
            else:
                logging.warning("Could not find response in Ollama output.")
                return transcribed_text  # Fallback

        except requests.exceptions.RequestException as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries}: Could not connect to Ollama. Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logging.error("FATAL ERROR: Max retries reached for Optimizer Agent.")
                return transcribed_text  # Fallback
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response from Ollama: {e}")
            return transcribed_text  # Fallback
        except Exception as e:
            logging.exception(f"Unexpected error in prompt_optimizer: {e}")
            return transcribed_text  # Fallback
    
    return transcribed_text  # Final fallback

def _get_default_optimizer_prompt() -> str:
    """Returns the default optimizer prompt if not configured."""
    return """You are a prompt optimization assistant for a code generation system.

Your job is to take informal, potentially unclear voice-transcribed requests and convert them into clear, specific coding instructions.

Guidelines:
1. Identify the programming task the user wants to accomplish
2. Clarify any ambiguous terms or incomplete thoughts
3. Make reasonable assumptions about standard practices (e.g., function names, parameter names)
4. Output a clear, structured request for code generation
5. Do NOT generate any code yourself - only clarify and structure the request
6. Keep the output concise and focused on the task

Examples:
Input: "make a function it should add two numbers"
Output: "Create a Python function named 'add' that takes two parameters and returns their sum."

Input: "I need to sort a list but in reverse"
Output: "Create Python code to sort a list in descending order."

Input: "function to check if number is even"
Output: "Create a Python function named 'is_even' that takes a number as input and returns True if it's even, False otherwise."

Now process this request:"""
