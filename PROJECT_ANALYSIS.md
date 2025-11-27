# Voice2Code - Complete Project Analysis

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Complete Workflow](#complete-workflow)
4. [Backend Python Components](#backend-python-components)
5. [Electron Application Components](#electron-application-components)
6. [Node.js Services](#nodejs-services)
7. [Configuration Files](#configuration-files)
8. [Git Configuration](#git-configuration)
9. [Dependencies and Relationships](#dependencies-and-relationships)
10. [Key Technical Details](#key-technical-details)

---

## Project Overview

Voice2Code is a desktop application that enables users to generate code snippets through voice commands. The system integrates multiple technologies:
- **Electron** for the desktop UI and system integration
- **Python Flask backend** for AI processing (speech-to-text and code generation)
- **Node.js services** for system-level operations (global hotkeys, automation)
- **Whisper.cpp** for local speech transcription
- **Ollama** for local LLM-based code generation

---

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Electron UI   │    │  Node.js Services│    │  Python Backend │
│                 │    │                  │    │                 │
│ • Main Window   │◄──►│ • Hotkey Listener│◄──►│ • Flask Server  │
│ • HUD Display   │    │ • Automation     │    │ • Whisper       │
│ • Settings      │    │ • IPC Bridge     │    │ • Ollama        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌──────────────────┐
                    │  Configuration   │
                    │                  │
                    │ • paths.json     │
                    │ • settings.json  │
                    └──────────────────┘
```

---

## Complete Workflow

### Step-by-Step Process:

1. **Application Startup**
   - Electron main process launches
   - Creates system tray icon
   - Spawns hotkey listener service
   - Creates HUD window (hidden)
   - Python Flask backend starts on port 5001

2. **Hotkey Activation**
   - User presses configured hotkey (default: NUMPAD 5)
   - `hotkeyListener.js` detects the key combination
   - Sends IPC message to main process
   - Main process shows HUD window

3. **Audio Recording**
   - HUD window requests microphone access
   - `MediaRecorder` API captures audio
   - Visual feedback shows recording status
   - Audio chunks stored in memory

4. **Audio Processing**
   - When hotkey is released, recording stops
   - Audio data sent to main process via IPC
   - Main process saves as temporary WAV file
   - FFmpeg converts to 16kHz mono format

5. **Speech Transcription**
   - Converted audio sent to Flask backend
   - `whisper_wrapper.py` calls whisper.cpp
   - Transcription returned as text

6. **Code Generation**
   - Transcribed text combined with master prompt
   - `ollama_wrapper.py` sends to local Ollama instance
   - LLM generates code based on the prompt

7. **Code Output**
   - Generated code returned to Electron
   - `automation.js` copies code to clipboard
   - Code ready for manual paste by user

---

## Backend Python Components

### `backend/app.py` - Flask API Server

**Purpose**: Main HTTP API endpoint that orchestrates the audio processing pipeline.

**Line-by-Line Analysis**:
```python
# Lines 1-7: Imports and Flask initialization
from flask import Flask, request, jsonify
import json
import os
from whisper_wrapper import transcribe
from ollama_wrapper import get_raw_code

app = Flask(__name__)
```
- Imports necessary modules for web server, JSON handling, and custom wrappers
- Creates Flask application instance

```python
# Lines 9-23: Master prompt loading
def load_master_prompt():
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
```
- Constructs absolute path to settings.json
- Loads master prompt for LLM context
- Provides fallback prompts for error cases

```python
# Lines 24-55: Main audio processing endpoint
@app.route('/process-audio', methods=['POST'])
def process_audio():
    audio_path = request.json.get('path')
    if not audio_path:
        return jsonify({"error": "Audio path not provided"}), 400

    # 1. Get transcribed text
    transcribed_text = transcribe(audio_path)
    if not transcribed_text:
        return jsonify({"error": "Transcription failed"}), 500

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

    # 5. Sanitize the output
    final_code = raw_code.strip()

    print(f"--- Code Generation Complete ---")
    print(f"Final generated code:\n{final_code}")
    print("------------------------------")

    return jsonify({"code": final_code})
```
- Validates incoming audio path
- Orchestrates transcription → prompt combination → code generation
- Handles error cases at each step
- Returns final generated code

```python
# Lines 57-58: Server startup
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001)
```
- Starts Flask server on localhost port 5001

### `backend/whisper_wrapper.py` - Speech Transcription Interface

**Purpose**: Wrapper around whisper.cpp for local speech-to-text processing.

**Line-by-Line Analysis**:
```python
# Lines 1-4: Imports
import subprocess
import json
import os
```
- Required for subprocess execution, JSON parsing, and file operations

```python
# Lines 5-14: Main transcription function
def transcribe(audio_file: str) -> str:
    """
    Transcribes the given audio file using the whisper.cpp executable.
    It relies on the executable creating a .json file with the same name.
    """
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    executable_dir = os.path.join(backend_dir, "models", "whisper.cpp")
    executable_path = os.path.join(executable_dir, "whisper-cli.exe")
    model_path = os.path.join(backend_dir, "models", "ggml-base.bin")
```
- Constructs paths to whisper executable and model
- Uses relative paths from script location

```python
# Lines 15-21: Command construction
command = [
    executable_path,
    "--model", model_path,
    "--file", audio_file,
    "--output-json", # Creates JSON output file
    "--language", "en"
]
```
- Builds whisper.cpp command with required parameters
- Forces English language and JSON output format

```python
# Lines 26-32: Subprocess execution
result = subprocess.run(
    command,
    capture_output=True,
    text=True,
    cwd=executable_dir
)
```
- Executes whisper.cpp as subprocess
- Captures stdout/stderr for debugging
- Runs in whisper.cpp directory

```python
# Lines 44-62: JSON output processing
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
```
- Reads JSON output file created by whisper.cpp
- Handles multiple possible JSON structures
- Cleans up temporary JSON file
- Returns transcribed text

### `backend/ollama_wrapper.py` - LLM Integration

**Purpose**: Handles communication with Ollama for code generation.

**Line-by-Line Analysis**:
```python
# Lines 1-8: Imports and logging setup
import requests
import json
import os
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
```
- HTTP requests library for API calls
- Comprehensive logging for debugging

```python
# Lines 10-25: Configuration loading
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
```
- Loads configuration from multiple sources
- Merges paths.json and settings.json
- Provides fallback values

```python
# Lines 39-98: Main code generation function
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

    # Retry mechanism
    max_retries = 3
    retry_delay = 1  # seconds

    for attempt in range(max_retries):
        try:
            payload = {
                "model": ollama_model,
                "prompt": prompt,
                "stream": False
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
                logging.info(f"Ollama raw code: {message_content.strip()}")
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
```
- Implements retry mechanism with exponential backoff
- Sends POST request to Ollama API
- Handles various error scenarios
- Returns generated code or empty string on failure

### `backend/requirements.txt` - Python Dependencies

```
flask
requests
```
- **flask**: Web framework for the API server
- **requests**: HTTP client for Ollama API communication

---

## Electron Application Components

### `electron-app/main.js` - Main Electron Process

**Purpose**: Controls the application lifecycle, window management, and inter-process communication.

**Line-by-Line Analysis**:
```javascript
// Lines 1-11: Imports and global variables
const { app, BrowserWindow, ipcMain, Tray, Menu, screen } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');

let tray = null;
let mainWindow = null;
let hudWindow = null;
let settingsWindow = null;
```
- Imports Electron modules for app control
- Node.js modules for file system and process management
- Global variables for window references

```javascript
// Lines 12-30: Main window creation
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 480,
    height: 500,
    frame: false,
    resizable: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false
    }
  });

  mainWindow.loadFile('renderer/index.html');

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}
```
- Creates frameless, non-resizable main window
- Loads the bootloader HTML
- Implements security best practices with context isolation

```javascript
// Lines 32-46: System tray creation
function createTray() {
  tray = new Tray(path.join(__dirname, 'assets/icons/icon.png'));
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Settings', type: 'normal', click: () => {
        if (settingsWindow) {
          settingsWindow.focus();
        } else {
          createSettingsWindow();
        }
      } },
    { label: 'Quit', type: 'normal', click: () => app.quit() }
  ]);
  tray.setToolTip('Voice2Code');
  tray.setContextMenu(contextMenu);
}
```
- Creates system tray icon with context menu
- Provides access to settings and quit functionality

```javascript
// Lines 48-71: HUD window creation
function createHudWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { width: screenWidth } = primaryDisplay.workAreaSize;
  const hudWidth = 300;
  const hudHeight = 150;

  hudWindow = new BrowserWindow({
    width: hudWidth,
    height: hudHeight,
    x: screenWidth - hudWidth - 1,
    y: 1,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      enableRemoteModule: false
    }
  });

  hudWindow.loadFile('renderer/hud.html');
  hudWindow.hide();
}
```
- Creates transparent, always-on-top HUD window
- Positions in top-right corner of screen
- Initially hidden, shown on hotkey press

```javascript
// Lines 109-131: Application ready event
app.on('ready', () => {
  createWindow();
  createTray();
  createHudWindow();

  const hotkeyListener = spawn('node', [path.join(__dirname, '../node-services/hotkeyListener.js')], { stdio: ['pipe', 'pipe', 'pipe', 'ipc'] });

  hotkeyListener.stdout.on('data', (data) => {
    console.log(`hotkeyListener stdout: ${data}`);
  });

  hotkeyListener.stderr.on('data', (data) => {
    console.error(`hotkeyListener stderr: ${data}`);
  });

  hotkeyListener.on('message', (message) => {
    if (message.command === 'show-hud') {
      showHud();
    } else if (message.command === 'hide-hud') {
      hideHud();
    }
  });
});
```
- Initializes all UI components
- Spawns hotkey listener as separate process
- Sets up IPC communication with hotkey service

```javascript
// Lines 149-238: Audio data processing
ipcMain.on('audio-data', (event, data) => {
  const tempPathUnconverted = path.join(os.tmpdir(), 'temp_audio_unconverted.wav');
  const tempPathConverted = path.join(os.tmpdir(), 'temp_audio_converted.wav');
  const ffmpegPath = path.join(__dirname, '../backend/models/ffmpeg/ffmpeg.exe');

  fs.writeFile(tempPathUnconverted, Buffer.from(data), (err) => {
    if (err) {
      console.error('Failed to save unconverted audio file:', err);
      return;
    }
    console.log('Unconverted audio file saved to:', tempPathUnconverted);

    // FFmpeg conversion command
    const ffmpegCommand = [
      ffmpegPath,
      '-i', tempPathUnconverted,
      '-ar', '16000',
      '-ac', '1',
      '-c:a', 'pcm_s16le',
      '-y', tempPathConverted
    ];

    const ffmpegProcess = spawn(ffmpegPath, [
      '-i', tempPathUnconverted,
      '-ar', '16000',
      '-ac', '1',
      '-c:a', 'pcm_s16le',
      '-y', tempPathConverted
    ]);

    ffmpegProcess.on('close', (code) => {
      if (code !== 0) {
        console.error(`ffmpeg process exited with code ${code}`);
        return;
      }
      console.log('Converted audio file saved to:', tempPathConverted);

      // Send to Python backend
      const axios = require('axios');
      axios.post('http://127.0.0.1:5001/process-audio', { path: tempPathConverted })
        .then(response => {
          const code = response.data.code;
          const automation = spawn('node', [path.join(__dirname, '../node-services/automation.js'), code], { stdio: ['pipe', 'pipe', 'pipe', 'ipc'] });

          automation.on('close', (code) => {
            console.log(`automation.js exited with code ${code}`);
          });
        })
        .catch(error => {
          console.error('Error processing audio:', error);
        });
    });
  });
});
```
- Handles audio data from renderer process
- Saves as temporary WAV file
- Converts audio using FFmpeg to required format
- Sends converted audio to Python backend
- Spawns automation service with generated code

### `electron-app/preload.js` - Security Bridge

**Purpose**: Provides secure communication between renderer and main processes.

**Line-by-Line Analysis**:
```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  send: (channel, data) => ipcRenderer.send(channel, data),
  receive: (channel, func) => ipcRenderer.on(channel, (event, ...args) => func(...args)),
  closeLoadingWindow: () => ipcRenderer.send('close-loading-window')
});
```
- Uses contextBridge for secure IPC exposure
- Provides send/receive methods for communication
- Exposes specific functionality to renderer process

### `electron-app/package.json` - Electron App Configuration

**Purpose**: Defines the Electron application metadata and dependencies.

**Analysis**:
```json
{
  "name": "echo-assist",
  "version": "0.1.0",
  "description": "Voice to code widget",
  "main": "main.js",
  "scripts": {
    "start": "electron ."
  },
  "devDependencies": {
    "electron": "^28.0.0"
  },
  "dependencies": {
    "axios": "^1.12.2"
  }
}
```
- **electron**: Desktop application framework
- **axios**: HTTP client for backend communication

### `electron-app/renderer/index.html` - Bootloader UI

**Purpose**: Animated loading screen that shows application startup progress.

**Key Features**:
- GSAP animations for smooth transitions
- Service status indicators
- Progress bar
- Automatic window closure after initialization

**Animation Sequence**:
1. Logo scale animation with elastic effect
2. Title fade-in
3. Service cards slide in with checkmarks
4. Progress bar updates
5. Final "System Ready" message
6. Window closes after 1.5 seconds

### `electron-app/renderer/hud.html` - Recording Interface

**Purpose**: Heads-up display shown during audio recording.

**Key Features**:
- Transparent background with blur effect
- Animated microphone icon
- Audio visualizer bars
- Smooth slide-in/out animations
- Positioned in top-right corner

**CSS Classes**:
- `.hud-listening`: Main container with transform animations
- `.hud-mic`: Microphone icon with gradient styling
- `.hud-visualizer`: Animated frequency bars
- `.hud-bar`: Individual visualizer bars with height transitions

### `electron-app/renderer/hud.js` - Recording Logic

**Purpose**: Handles audio recording and visual feedback.

**Line-by-Line Analysis**:
```javascript
// Lines 1-3: Global variables
let mediaRecorder;
let audioChunks = [];
let visualizerInterval = null;
```
- MediaRecorder instance for audio capture
- Array to store audio data chunks
- Interval for visualizer animation

```javascript
// Lines 9-34: Visualizer functions
function animateBars() {
  bars.forEach(bar => {
    const base = 8;
    const variance = 14;
    const newHeight = base + Math.random() * variance;
    bar.style.height = `${newHeight}px`;
  });
}

function startVisualizer() {
  if (!visualizerInterval) {
    visualizerInterval = setInterval(animateBars, 160);
  }
}
```
- Creates random height animations for visualizer bars
- Starts/stops animation intervals

```javascript
// Lines 48-84: IPC message handler
window.electronAPI.receive('update-status', async (status) => {
  if (status === 'Listening...') {
    // Reset recording state
    audioChunks = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = (event) => {
        audioChunks.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        const reader = new FileReader();
        reader.onload = () => {
          window.electronAPI.send('audio-data', reader.result);
        };
        reader.readAsArrayBuffer(audioBlob);
      };

      mediaRecorder.start();
      showHUD(status);
    } catch (err) {
      console.error('Mic access failed:', err);
      window.electronAPI.send('mic-error', err.message);
      hideHUD();
    }
  } else {
    // Stop recording and hide HUD
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    hideHUD();
  }
});
```
- Handles 'update-status' messages from main process
- Requests microphone access when recording starts
- Collects audio chunks during recording
- Converts to ArrayBuffer and sends to main process on stop

### `electron-app/renderer/settings.html` - Settings Interface

**Purpose**: Basic settings window (currently minimal implementation).

**Current State**:
- Simple HTML structure with basic styling
- Placeholder for future settings implementation
- Accessible via system tray menu

---

## Node.js Services

### `node-services/hotkeyListener.js` - Global Hotkey Detection

**Purpose**: Listens for global hotkey presses and communicates with main process.

**Line-by-Line Analysis**:
```javascript
// Lines 1-6: Imports and configuration
const { GlobalKeyboardListener } = require('node-global-key-listener');
const fs = require('fs');
const path = require('path');
const { sendCommand } = require('./ipcBridge');

const SETTINGS_PATH = path.join(__dirname, '../config/settings.json');
```
- Imports global keyboard listener library
- File system modules for configuration loading
- IPC bridge for communication with main process

```javascript
// Lines 8-16: Settings loading
function loadSettings() {
    try {
        const settingsContent = fs.readFileSync(SETTINGS_PATH, 'utf8');
        return JSON.parse(settingsContent);
    } catch (error) {
        console.error('Error loading settings.json:', error);
        return {};
    }
}

const settings = loadSettings();
const configuredHotkey = settings.hotkey || 'NUMPAD 5'; // Default to NUMPAD 5 if not found
```
- Loads hotkey configuration from settings.json
- Provides default fallback hotkey

```javascript
// Lines 21-37: Hotkey parsing
const hotkeyParts = configuredHotkey.toLowerCase().split(' + ').map(part => part.trim());
let modifierKey = null;
let mainKey = null;

const modifierMap = {
    'alt': 'LEFT ALT',
    'control': 'LEFT CONTROL',
    'shift': 'LEFT SHIFT',
    'commandorcontrol': process.platform === 'darwin' ? 'LEFT COMMAND' : 'LEFT CONTROL'
};

if (hotkeyParts.length > 1) {
    modifierKey = modifierMap[hotkeyParts[0]];
    mainKey = hotkeyParts[1].toUpperCase();
} else {
    mainKey = hotkeyParts[0].toUpperCase();
}
```
- Parses hotkey string into components
- Maps modifier keys to platform-specific values
- Handles both single keys and key combinations

```javascript
// Lines 42-74: Keyboard event handling
const v = new GlobalKeyboardListener();

v.addListener(function (e) {
    const isKeyDown = (e.state === 'DOWN');

    if (modifierKey) {
        if (e.name === modifierKey) {
            isModifierDown = isKeyDown;
            if (!isKeyDown && hotkeyActive) { // Modifier released, hotkey was active
                sendCommand({ command: 'hide-hud' });
                hotkeyActive = false;
            }
        }

        if (e.name === mainKey) {
            if (isKeyDown && isModifierDown && !hotkeyActive) {
                sendCommand({ command: 'show-hud' });
                hotkeyActive = true;
            } else if (!isKeyDown && hotkeyActive) {
                sendCommand({ command: 'hide-hud' });
                hotkeyActive = false;
            }
        }
    } else if (e.name === mainKey) {
        if (isKeyDown && !hotkeyActive) {
            sendCommand({ command: 'show-hud' });
            hotkeyActive = true;
        } else if (!isKeyDown && hotkeyActive) {
            sendCommand({ command: 'hide-hud' });
            hotkeyActive = false;
        }
    }
});
```
- Listens for global keyboard events
- Tracks modifier key state
- Sends commands on hotkey press/release
- Prevents duplicate command sending

### `node-services/automation.js` - Clipboard Operations

**Purpose**: Copies generated code to system clipboard.

**Line-by-Line Analysis**:
```javascript
// Lines 1-5: Imports and function definition
const { clipboard } = require("@nut-tree-fork/nut-js");

async function copyToClipboard(text) {
    await clipboard.setContent(text);
}
```
- Imports clipboard functionality from nut-js library
- Defines async function for clipboard operations

```javascript
// Lines 7-14: Command line execution
const codeToCopy = process.argv[2];
if (codeToCopy) {
    copyToClipboard(codeToCopy).then(() => {
        if (process.send) {
            process.send({ status: 'success' });
        }
    });
}
```
- Gets code from command line argument
- Copies to clipboard and sends success message
- Handles IPC communication with parent process

### `node-services/ipcBridge.js` - IPC Communication Helper

**Purpose**: Provides standardized IPC communication for Node.js services.

**Line-by-Line Analysis**:
```javascript
function sendCommand(command) {
  if (process.send) {
    process.send(command);
  }
}

module.exports = { sendCommand };
```
- Wraps process.send for safe IPC communication
- Checks if IPC channel is available before sending
- Exports function for use in other services

### `node-services/package.json` - Node Services Configuration

**Purpose**: Defines dependencies for Node.js services.

**Analysis**:
```json
{
  "name": "echo-assist-services",
  "version": "0.1.0",
  "description": "Backend services for EchoAssist",
  "main": "ipcBridge.js",
  "dependencies": {
    "@nut-tree-fork/nut-js": "^4.2.6",
    "node-global-key-listener": "^0.1.1"
  }
}
```
- **@nut-tree-fork/nut-js**: Cross-platform automation library (clipboard)
- **node-global-key-listener**: Global hotkey detection

---

## Configuration Files

### `config/paths.json` - System Paths Configuration

**Purpose**: Defines paths to external tools and services.

**Analysis**:
```json
{
  "whisper_cpp_path": "(1)\\backend\\models\\whisper.cpp",
  "ollama_endpoint": "http://localhost:11434/api/generate"
}
```
- **whisper_cpp_path**: Path to whisper.cpp installation
- **ollama_endpoint**: Ollama API endpoint URL

### `config/settings.json` - User Settings (Gitignored)

**Purpose**: Stores user-configurable settings (not in repository).

**Expected Structure**:
```json
{
  "hotkey": "NUMPAD 5",
  "master_prompt": "You are an expert programmer. Please generate the code for the following command:",
  "ollama_model": "codellama"
}
```

---

## Git Configuration

### `.gitignore` - Version Control Exclusions

**Purpose**: Specifies files and directories to exclude from version control.

**Analysis**:
```
electron-app/node_modules/electron/dist/electron.exe
backend/models/ffmpeg/ffmpeg.exe
backend/models/ggml-base.bin
(Improvements)Intents.txt
newhudscript.txt
/.genkit
voice2code.txt
voice2code.txt
GEMINI.md
config/settings.json
config/settings.json
```
- Excludes binary executables and model files
- Excludes user configuration files
- Excludes temporary and development files

### `.gitattributes` - Git Attributes

**Purpose**: Configures Git behavior for different file types.

**Analysis**:
```
# Auto detect text files and perform LF normalization
* text=auto
```
- Enables automatic line ending normalization
- Ensures consistent line endings across platforms

---

## Dependencies and Relationships

### Dependency Graph:

```
Electron Main Process
├── Node Services (spawned processes)
│   ├── hotkeyListener.js
│   │   ├── node-global-key-listener
│   │   └── ipcBridge.js
│   └── automation.js
│       └── @nut-tree-fork/nut-js
├── Renderer Processes
│   ├── index.html (bootloader)
│   │   └── GSAP animations
│   ├── hud.html
│   │   └── MediaRecorder API
│   └── settings.html
└── Python Backend (HTTP API)
    ├── Flask
    ├── whisper_wrapper.py
    │   └── whisper.cpp (external)
    └── ollama_wrapper.py
        └── Ollama (external service)
```

### Communication Flow:

1. **IPC Communication**: Electron main process ↔ Node services
2. **HTTP API**: Electron main process → Python Flask backend
3. **File I/O**: Temporary audio files between processes
4. **External APIs**: whisper.cpp and Ollama integration

---

## Key Technical Details

### Security Considerations:

1. **Context Isolation**: Enabled in all Electron windows
2. **Preload Scripts**: Secure bridge between renderer and main processes
3. **Localhost Only**: Flask server binds to 127.0.0.1
4. **No Remote Module**: Disabled in webPreferences

### Performance Optimizations:

1. **Lazy Loading**: Services spawned on demand
2. **Temporary Files**: Cleaned up after processing
3. **Retry Logic**: Exponential backoff for API calls
4. **Async Operations**: Non-blocking audio processing

### Error Handling:

1. **Graceful Degradation**: Fallback prompts and settings
2. **Comprehensive Logging**: Debug information at each step
3. **User Feedback**: HUD status updates
4. **Process Monitoring**: Child process error handling

### Cross-Platform Considerations:

1. **Path Handling**: Uses path.join() for compatibility
2. **Platform-Specific Keys**: Different modifier keys for macOS vs Windows/Linux
3. **Executable Extensions**: Handles .exe for Windows
4. **Temporary Directories**: Uses OS temp directory

---

## File Summary Matrix

| File | Purpose | Key Technologies | Dependencies |
|------|---------|-------------------|--------------|
| `backend/app.py` | Flask API server | Flask, Python | whisper_wrapper, ollama_wrapper |
| `backend/whisper_wrapper.py` | Speech transcription | subprocess, whisper.cpp | External whisper.cpp |
| `backend/ollama_wrapper.py` | LLM integration | requests, Ollama | External Ollama service |
| `backend/requirements.txt` | Python dependencies | pip | - |
| `electron-app/main.js` | Electron main process | Electron, Node.js | Node services, Python backend |
| `electron-app/preload.js` | Security bridge | contextBridge | - |
| `electron-app/package.json` | Electron config | npm | electron, axios |
| `electron-app/renderer/index.html` | Bootloader UI | HTML, GSAP | - |
| `electron-app/renderer/hud.html` | Recording interface | HTML, CSS | - |
| `electron-app/renderer/hud.js` | Audio recording | MediaRecorder API | - |
| `electron-app/renderer/settings.html` | Settings UI | HTML | - |
| `node-services/hotkeyListener.js` | Global hotkeys | node-global-key-listener | ipcBridge |
| `node-services/automation.js` | Clipboard operations | @nut-tree-fork/nut-js | - |
| `node-services/ipcBridge.js` | IPC helper | Node.js IPC | - |
| `node-services/package.json` | Node services config | npm | nut-js, global-key-listener |
| `config/paths.json` | System paths | JSON | - |
| `.gitignore` | Git exclusions | Git | - |
| `.gitattributes` | Git behavior | Git | - |

This comprehensive analysis provides a complete understanding of the Voice2Code project architecture, implementation details, and inter-component relationships.