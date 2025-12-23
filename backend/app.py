from flask import Flask, request, jsonify
import json
import os
import time
from whisper_wrapper import transcribe
from prompt_optimizer import optimize_prompt
from ollama_wrapper import get_raw_code

app = Flask(__name__)

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

def load_coder_config():
    """
    Loads the coder configuration (for Agent 2) from settings.json.
    Returns both the prompt template and the language setting.
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config', 'settings.json')
    
    try:
        with open(config_path, 'r') as f:
            settings = json.load(f)
            # Try 'coder_prompt' first, then fall back to 'master_prompt'
            prompt_template = settings.get("coder_prompt", settings.get("master_prompt", ""))
            language = settings.get("language", "python")
            return prompt_template, language
    except FileNotFoundError:
        return "You are an expert programmer. Please generate the code for the following command:", "python"
    except json.JSONDecodeError:
        return "Error: Could not decode settings.json.", "python"

@app.route('/process-audio', methods=['POST'])
def process_audio():
    audio_path = request.json.get('path')
    if not audio_path:
        return jsonify({"error": "Audio path not provided"}), 400

    # Initialize timing dictionary
    timings = {}
    pipeline_start_time = time.time()

    print("\n" + "=" * 70)
    print("VOICE2CODE - TWO-AGENT PROCESSING PIPELINE")
    print("=" * 70)

    # STEP 1: Transcribe audio to text
    print("\nSTEP 1: SPEECH TRANSCRIPTION (whisper.cpp)")
    print("-" * 70)
    whisper_start = time.time()
    transcribed_text = transcribe(audio_path)
    whisper_end = time.time()
    timings['whisper'] = round(whisper_end - whisper_start, 3)
    print(f"⏱️  Whisper Time: {timings['whisper']}s")
    
    # Check if transcription is blank, empty, or meaningless
    if not transcribed_text or transcribed_text.strip() == "":
        print("ERROR: Transcription is blank or empty - no audio detected")
        return jsonify({
            "error": "No audio was recorded. Please try speaking again.",
            "error_type": "no_audio"
        }), 400
    
    # Check for Whisper's blank audio markers
    cleaned_text = transcribed_text.strip()
    if cleaned_text.upper() in ["[BLANK_AUDIO]", "(BLANK_AUDIO)", "[SILENCE]", "(SILENCE)", "[BLANK]", "(BLANK)"]:
        print(f"ERROR: Whisper detected blank audio: '{transcribed_text}'")
        return jsonify({
            "error": "No audio was recorded. Please try speaking again.",
            "error_type": "no_audio"
        }), 400
    
    # Check if transcription is too short or just whitespace/punctuation
    if len(cleaned_text) < 3 or cleaned_text.replace('.', '').replace(',', '').replace('!', '').replace('?', '').strip() == "":
        print(f"ERROR: Transcription too short or meaningless: '{transcribed_text}'")
        return jsonify({
            "error": "No audio was recorded. Please try speaking again.",
            "error_type": "no_audio"
        }), 400
    
    print(f"Transcribed Text: {transcribed_text}")

    # STEP 2: Optimize the prompt using Agent 1 (Prompt Optimizer)
    print("\n" + "=" * 70)
    print("STEP 2: AGENT 1 - PROMPT OPTIMIZER")
    print("=" * 70)
    agent1_start = time.time()
    optimized_prompt = optimize_prompt(transcribed_text)
    agent1_end = time.time()
    timings['agent1'] = round(agent1_end - agent1_start, 3)
    print(f"⏱️  Agent 1 Time: {timings['agent1']}s")
    if not optimized_prompt:
        print("WARNING: Optimization failed, using original transcription")
        optimized_prompt = transcribed_text
    
    # STEP 3: Generate code using Agent 2 (Coder Agent)
    print("\n" + "=" * 70)
    print("STEP 3: AGENT 2 - CODER AGENT")
    print("=" * 70)
    
    # Load the coder prompt template and language
    coder_prompt_template, language = load_coder_config()
    if "Error" in coder_prompt_template:
        return jsonify({"error": coder_prompt_template}), 500

    # Inject language into the prompt template
    coder_prompt = coder_prompt_template.replace("{language}", language.capitalize())
    print(f"Target Language: {language.capitalize()}")

    # Combine coder prompt with optimized prompt
    full_prompt = f"{coder_prompt}\n\n{optimized_prompt}"
    print(f"Full Prompt to Coder:\n{full_prompt}")
    print("-" * 70)

    # Get raw code from Ollama (Agent 2)
    agent2_start = time.time()
    raw_code = get_raw_code(full_prompt)
    agent2_end = time.time()
    timings['agent2'] = round(agent2_end - agent2_start, 3)
    print(f"⏱️  Agent 2 Time: {timings['agent2']}s")
    if not raw_code:
        return jsonify({"error": "Failed to get code from the AI model"}), 500

    # STEP 4: Finalize and return
    # Strip any markdown code blocks that the LLM might have added
    final_code = strip_markdown_code_blocks(raw_code)

    print("\n" + "=" * 70)
    print("STEP 4: FINAL OUTPUT")
    print("=" * 70)
    print(f"Generated Code:\n{final_code}")
    print("=" * 70 + "\n")

    # Calculate total pipeline time
    pipeline_end_time = time.time()
    timings['total'] = round(pipeline_end_time - pipeline_start_time, 3)

    # STEP 5: Timing Summary
    print("\n" + "=" * 70)
    print("STEP 5: TIMING SUMMARY")
    print("=" * 70)
    print(f"  🎤 Whisper (Speech-to-Text): {timings['whisper']}s")
    print(f"  🧠 Agent 1 (Prompt Optimizer): {timings['agent1']}s")
    print(f"  💻 Agent 2 (Code Generator): {timings['agent2']}s")
    print(f"  ⏱️  Total Pipeline Time: {timings['total']}s")
    print("=" * 70 + "\n")

    return jsonify({"code": final_code, "timings": timings})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
