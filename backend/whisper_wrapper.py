import subprocess
import json
import os

def transcribe(audio_file: str) -> str:
    """
    Transcribes the given audio file using the whisper.cpp executable.
    It relies on the executable creating a .json file with the same name.
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    executable_dir = os.path.join(backend_dir, "models", "whisper.cpp")
    executable_path = os.path.join(executable_dir, "whisper-cli.exe")
    model_path = os.path.join(backend_dir, "models", "ggml-base.bin")

    command = [
        executable_path,
        "--model", model_path,
        "--file", audio_file,
        "--output-json", # This flag makes it create a .json file
        "--language", "en"
    ]

    print(f"Running Whisper.cpp command: {' '.join(command)}")
    print(f"Executing in directory: {executable_dir}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=executable_dir
        )

        if result.stderr:
            # Print stderr for debugging, but don't treat it as a fatal error unless the return code is non-zero
            print("--- Whisper.cpp STDERR ---")
            print(result.stderr.strip())
            print("--------------------------")

        if result.returncode != 0:
            print(f"FATAL ERROR: Whisper.cpp process exited with code {result.returncode}.")
            return ""

        # --- KEY CHANGE --- 
        # The executable creates a .json file, so we read that file instead of stdout.
        json_file_path = audio_file + ".json"
        print(f"Attempting to read JSON output from: {json_file_path}")

        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # The structure of the JSON might be a list of segments
        transcribed_text = " ".join([segment['text'] for segment in data.get('transcription', [])])
        
        if not transcribed_text:
            # Fallback for a different JSON structure
            transcribed_text = data.get('text', '').strip()

        print(f"Transcription successful: {transcribed_text}")
        # Clean up the generated .json file
        os.remove(json_file_path)
        return transcribed_text.strip()

    except FileNotFoundError:
        print(f"FATAL ERROR: Could not find the generated JSON file at '{json_file_path}'.")
        return ""
    except json.JSONDecodeError:
        print(f"FATAL ERROR: Failed to decode JSON from file '{json_file_path}'.")
        return ""
    except Exception as e:
        print(f"An unexpected error occurred in whisper_wrapper: {e}")
        return ""
