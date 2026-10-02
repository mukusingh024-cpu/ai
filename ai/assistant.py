from __future__ import annotations

import math
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import webbrowser
from collections import deque
from pathlib import Path
from tkinter import END, Button, Entry, Frame, Label, Scrollbar, Text, Tk

from ai_service import ask_ai

try:
    import pyttsx3
    import sounddevice as sd
    import speech_recognition as sr
except ImportError as exc:
    raise SystemExit(
        "Required packages are missing. Run: python -m pip install -r requirements.txt"
    ) from exc


APP_DIRECTORY = Path(__file__).resolve().parent
APP_ALLOWLIST = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
}
VS_CODE_LOCATIONS = (
    Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
    Path(os.getenv("ProgramFiles", "")) / "Microsoft VS Code" / "Code.exe",
)
APP_ALIASES = {
    "notepad": "notepad",
    "notes": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "browser": "browser",
    "web browser": "browser",
    "vs": "vscode",
    "vs code": "vscode",
    "vscode": "vscode",
    "visual studio code": "vscode",
}


def load_local_environment() -> None:
    env_file = APP_DIRECTORY / ".env"
    if not env_file.exists():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        name = name.strip()
        value = value.strip()
        if separator and name and not name.startswith("#") and name not in os.environ:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[name] = value


def parse_command(text: str) -> tuple[str, str] | None:
    normalized = text.strip()
    lowered = normalized.casefold()
    spoken_phrase = re.sub(r"[.!?,]+", "", lowered).strip()

    if spoken_phrase in {
        "hello vs",
        "helo vs",
        "hrlo vs",
        "hello v s",
        "helo v s",
        "hello vscode",
        "helo vscode",
        "hello visual studio code",
        "helo visual studio code",
    }:
        return "launch", "vscode"

    for prefix in ("search for ", "search "):
        if lowered.startswith(prefix):
            query = normalized[len(prefix):].strip()
            return ("search", query) if query else ("empty_search", "")

    for prefix in ("open ", "launch ", "start "):
        if lowered.startswith(prefix):
            requested_app = lowered[len(prefix):].strip()
            if requested_app in APP_ALIASES:
                return "launch", APP_ALIASES[requested_app]
            return "unknown_app", requested_app

    return None


def run_local_command(command: tuple[str, str]) -> str:
    action, value = command
    if action == "empty_search":
        return "Batayein, web par kya search karna hai?"
    if action == "search":
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(value)
        webbrowser.open_new_tab(url)
        return f"Browser mein search khol diya: {value}"
    if action == "unknown_app":
        available = ", ".join(sorted(APP_ALIASES))
        return f"Yeh app allowed nahi hai. Available commands: open {available}."
    if value == "browser":
        webbrowser.open_new_tab("https://www.google.com")
        return "Browser khol diya."
    if value == "vscode":
        executable = shutil.which("code")
        if executable is None:
            executable = next(
                (str(path) for path in VS_CODE_LOCATIONS if path.is_file()),
                None,
            )
        if executable is None:
            raise FileNotFoundError(
                "Visual Studio Code nahi mila. Install karein ya 'code' ko PATH mein add karein."
            )
        subprocess.Popen([executable], shell=False)
        return "Visual Studio Code khol diya."

    executable = APP_ALLOWLIST[value]
    subprocess.Popen([executable], shell=False)
    return f"{value.title()} khol diya."


class JarvisApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Jarvis AI")
        self.root.geometry("720x560")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.jobs: queue.Queue[tuple[str, str] | None] = queue.Queue()
        self.audio_blocks: queue.Queue[bytes] = queue.Queue(maxsize=40)
        self.history: list[dict[str, str]] = []
        self.speech_lock = threading.Lock()
        self._wake_running = threading.Event()
        self._wake_running.set()
        self._build_window()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._wake_word_loop, daemon=True).start()
        self.root.after(100, self._process_events)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

    def _build_window(self) -> None:
        Label(self.root, text="Jarvis AI", font=("Segoe UI", 20, "bold")).pack(pady=(12, 4))
        Label(
            self.root,
            text="Say 'hello VS' any time to open Visual Studio Code.",
            font=("Segoe UI", 10),
        ).pack(pady=(0, 10))
        Label(
            self.root,
            text="Always listening for the wake phrase. Speech recognition uses Google online.",
            font=("Segoe UI", 9),
        ).pack(pady=(0, 8))

        transcript_frame = Frame(self.root)
        transcript_frame.pack(fill="both", expand=True, padx=14, pady=4)
        scrollbar = Scrollbar(transcript_frame)
        scrollbar.pack(side="right", fill="y")
        self.transcript = Text(
            transcript_frame,
            wrap="word",
            state="disabled",
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 10),
        )
        self.transcript.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.transcript.yview)

        input_frame = Frame(self.root)
        input_frame.pack(fill="x", padx=14, pady=12)
        self.input = Entry(input_frame, font=("Segoe UI", 11))
        self.input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.input.bind("<Return>", self._send_text)
        Button(input_frame, text="Send", command=self._send_text).pack(side="left", padx=(0, 6))
        self._append("Jarvis", "Namaste! Boliye 'hello VS' to open Visual Studio Code.")

    def _append(self, speaker: str, text: str) -> None:
        self.transcript.config(state="normal")
        self.transcript.insert(END, f"{speaker}: {text}\n\n")
        self.transcript.see(END)
        self.transcript.config(state="disabled")

    def _send_text(self, _event: object = None) -> None:
        text = self.input.get().strip()
        if not text:
            return
        self.input.delete(0, END)
        self._append("You", text)
        self.jobs.put(("command", text))

    def _worker(self) -> None:
        while True:
            job = self.jobs.get()
            if job is None:
                return
            action, text = job
            command = parse_command(text)
            try:
                answer = run_local_command(command) if command else ask_ai(text, self.history)
            except OSError as exc:
                self.events.put(("error", f"Command could not be completed: {exc}"))
                continue
            if command is None and not answer.startswith(("AI chat ke liye", "AI service", "AI configuration")):
                self.history.extend(
                    [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]
                )
                self.history = self.history[-10:]
            self.events.put(("reply", answer))
            self._speak(answer)

    def _wake_word_loop(self) -> None:
        sample_rate = 16000
        block_size = 1024
        silence_blocks_to_end = 13
        max_phrase_blocks = int(6 * sample_rate / block_size)
        pre_roll: deque[bytes] = deque(maxlen=5)
        recognizer = sr.Recognizer()

        def receive_audio(indata: object, _frames: int, _time: object, _status: object) -> None:
            try:
                self.audio_blocks.put_nowait(indata.tobytes())
            except queue.Full:
                pass

        while self._wake_running.is_set():
            try:
                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=block_size,
                    callback=receive_audio,
                ):
                    self.events.put(("status", "Always listening for 'hello VS'."))
                    speech: list[bytes] = []
                    silent_blocks = 0
                    while self._wake_running.is_set():
                        try:
                            block = self.audio_blocks.get(timeout=0.5)
                        except queue.Empty:
                            continue
                        samples = memoryview(block).cast("h")
                        rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
                        if not speech:
                            if rms >= 400:
                                speech.extend(pre_roll)
                                speech.append(block)
                            else:
                                pre_roll.append(block)
                            continue

                        speech.append(block)
                        silent_blocks = silent_blocks + 1 if rms < 400 else 0
                        if silent_blocks < silence_blocks_to_end and len(speech) < max_phrase_blocks:
                            continue

                        audio = sr.AudioData(b"".join(speech), sample_rate, sample_width=2)
                        speech.clear()
                        pre_roll.clear()
                        silent_blocks = 0
                        try:
                            phrase = recognizer.recognize_google(
                                audio,
                                language=os.getenv("SPEECH_LANGUAGE", "en-IN").strip(),
                            )
                        except sr.UnknownValueError:
                            continue
                        except sr.RequestError as exc:
                            self.events.put(("error", f"Speech recognition service error: {exc}"))
                            continue

                        if parse_command(phrase) == ("launch", "vscode"):
                            self.events.put(("wake", phrase))
            except (OSError, sd.PortAudioError) as exc:
                self.events.put(("error", f"Microphone unavailable: {exc}"))
                time.sleep(2)

    def _speak(self, text: str) -> None:
        try:
            with self.speech_lock:
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                engine.stop()
        except (RuntimeError, OSError) as exc:
            self.events.put(("error", f"Text-to-speech error: {exc}"))

    def _process_events(self) -> None:
        while True:
            try:
                event, text = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "reply":
                self._append("Jarvis", text)
            elif event == "voice":
                self._append("You (voice)", text)
                self.jobs.put(("command", text))
            elif event == "wake":
                self._append("You (wake word)", text)
                self.jobs.put(("command", text))
            elif event == "status":
                self._append("Status", text)
            elif event == "error":
                self._append("Notice", text)
        self.root.after(100, self._process_events)

    def _close(self) -> None:
        self._wake_running.clear()
        self.jobs.put(None)
        self.root.destroy()


def main() -> None:
    load_local_environment()
    root = Tk()
    JarvisApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
