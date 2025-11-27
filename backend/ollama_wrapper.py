import requests
import json
import os
import logging
import time

# Initialize logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _load_config() -> dict:
    """Loads configuration from both paths.json and settings.json."""
    config = {}
    dir_path = os.path.dirname(os.path.realpath(__file__))
    
    paths_config_path = os.path.join(dir_path, '..', 'config', 'paths.json')
    settings_config_path = os.path.join(dir_path, '..', 'config', 'settings.json')
    
    config = _load_json_config(paths_config_path, config)
    config = _load_json_config(settings_config_path, config)

    # Override paths from settings.json if they exist
    config['whisper_cpp_path'] = config.get('whisper_cpp_path', config.get('paths', {}).get('whisper_cpp_path'))
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

def get_raw_code(prompt: str) -> str:
    """
    Sends a prompt to Ollama and returns the raw code output.
    """
    config = _load_config()
    ollama_endpoint = config.get("ollama_endpoint")
    ollama_model = config.get("ollama_model")

    if not ollama_endpoint or not ollama_model:
        logging.error("Ollama endpoint or model not found in configuration.")
        return ""

    logging.info("Sending prompt to Ollama endpoint: %s", ollama_endpoint)
    logging.info("Using Coder Model (Agent 2): %s", ollama_model)

    # Retry mechanism
    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            # Build payload with LLM parameters
            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.get("coder_temperature", 0.2),
                    "top_p": config.get("coder_top_p", 0.9),
                    "top_k": config.get("coder_top_k", 40),
                    "num_predict": config.get("coder_max_tokens", 500)
                }
            }

            response = requests.post(
                ollama_endpoint,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            response_data = response.json()
            message_content = response_data.get('response', '')
            
            if message_content:
                logging.info("Agent 2 (Coder) Output: %s", message_content.strip()[:100] + "...")
                return message_content.strip()
            else:
                logging.warning("Could not find message content in Ollama response.")
                return ""

        except requests.exceptions.RequestException as e:
            logging.error(f"Attempt {attempt + 1}/{max_retries}: Could not connect to Ollama. Ensure it is running. Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
            else:
                logging.error("FATAL ERROR: Max retries reached. Could not connect to Ollama.")
                return ""
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON response from Ollama: {e}")
            return ""
        except Exception as e:
            logging.exception(f"An unexpected error occurred in ollama_wrapper: {e}")
            return ""
    
    return ""