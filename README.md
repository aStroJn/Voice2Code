# Project: Voice2Code (EchoAssist)

## Project Overview

This project is a "Voice-to-Code" desktop application that allows users to generate code snippets by speaking commands. It uses a combination of an Electron frontend, a Python backend for AI processing, and Node.js services for desktop integration.

The core workflow is as follows:
1.  A global hotkey press triggers audio recording.
2.  The recorded audio is sent to a Python backend.
3.  The backend transcribes the audio using Whisper.
4.  The transcribed text is combined with a master prompt from the settings.
5.  The combined prompt is sent to a Large Language Model (via Ollama) to generate a raw code snippet.
6.  The final code snippet is sanitized and typed out into the user's active window.