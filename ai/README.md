# Jarvis AI for Windows

A small desktop assistant with voice input, spoken replies, AI chat, web search,
and an intentionally limited app launcher.

## Setup

1. Install Python 3.10 or newer.
2. In this folder, create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and add an API key for an OpenAI-compatible
   chat-completions service. AI chat is optional; app launching and search work
   without an API key.
4. Start the assistant:

   ```powershell
   python assistant.py
   ```

   The AI chat implementation is in `ai_service.py` and is called by the desktop
   app for text messages. It needs a valid provider API key in `.env`; no AI model
   or API key is bundled with this project.

## Commands

- Say `hello VS` (or `helo VS`) at any time to open Visual Studio Code; no button
  press is needed while Jarvis is running.
- `search for [query]`
- Any other text is sent to the configured AI chat service.

Jarvis keeps the microphone active while the app is open, detects speech locally,
and sends speech clips to Google's online speech-recognition service (`en-IN` by
default) to check for the wake phrase. An internet connection is required. Set
`SPEECH_LANGUAGE=hi-IN` in `.env` if you mainly speak Hindi. AI chat also sends
your prompt and recent conversation to the configured API provider.

For safety, the assistant does not execute arbitrary shell commands or modify
system settings. The hands-free voice wake command only launches Visual Studio
Code; typed commands can search the web or launch the listed apps. Do not put
your API key in source code or share the `.env` file.
