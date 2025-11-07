from flask import Flask, request, jsonify
import json
import os
from whisper_wrapper import transcribe
from ollama_wrapper import get_raw_code
from dual_stage_llm import improve_transcript, generate_code_from_task, CONFIG

app = Flask(__name__)

def load_master_prompt():
    # Construct the absolute path to settings.json
    # Assuming the script is in the 'backend' directory and config is a sibling
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config', 'settings.json')
    
    try:
        with open(config_path, 'r') as f:
            settings = json.load(f)
            return settings.get("master_prompt", "")
    except FileNotFoundError:
        return "You are an expert programmer. Please generate the code for the following command:"
    except json.JSONDecodeError:
        return "Error: Could not decode settings.json."

@app.route('/process-audio', methods=['POST'])
def process_audio():
    audio_path = request.json.get('path')
    if not audio_path:
        return jsonify({"error": "Audio path not provided"}), 400

    # 1. Get transcribed text
    transcribed_text = transcribe(audio_path)
    if not transcribed_text:
        return jsonify({"error": "Transcription failed"}), 500

    if CONFIG.get('USE_DUAL_STAGE'):
        try:
            task = improve_transcript(transcribed_text)
            if task.get('error'):
                return jsonify(task), 400
            
            code = generate_code_from_task(task)
            if isinstance(code, dict) and code.get('error'):
                return jsonify(code), 400

            return jsonify({"task": task, "code": code, "meta": {"improver_model": CONFIG['OLLAMA_MODEL'], "coder_model": CONFIG['OLLAMA_MODEL']}}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        # 2. Load the master prompt
        master_prompt = load_master_prompt()
        if "Error" in master_prompt:
            return jsonify({"error": master_prompt}), 500

        # 3. Combine prompt and transcribed text
        full_prompt = f"{master_prompt}\n\n{transcribed_text}"

        # 4. Get raw code from Ollama
        raw_code = get_raw_code(full_prompt)
        if not raw_code:
            return jsonify({"error": "Failed to get code from the AI model"}), 500

        # 5. Sanitize the output (basic stripping)
        final_code = raw_code.strip()

        print(f"--- Code Generation Complete ---")
        print(f"Final generated code:\n{final_code}")
        print("------------------------------")

        return jsonify({"code": final_code})

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
