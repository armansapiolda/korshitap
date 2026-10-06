"""Automated SSH tunnel manager for KORSHI TAP WebApp."""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

PUBLIC_URL_FILE = Path(__file__).resolve().parent / "app" / "public_url.txt"

def run_tunnel():
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=3",
        "-o", "ExitOnForwardFailure=yes",
        "-R", "80:localhost:8000",
        "nokey@localhost.run"
    ]
    print("🚀 Запуск SSH-туннеля для KORSHI TAP WebApp...", flush=True)
    while True:
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            for line in proc.stdout:
                match = re.search(r"https://[a-zA-Z0-9.-]+\.lhr\.life", line)
                if match:
                    url = match.group(0)
                    PUBLIC_URL_FILE.write_text(url.strip())
                    print(f"✅ Публичный HTTPS URL: {url}", flush=True)
                    print(f"📱 Карта Алматы для мобильного: {url}/map", flush=True)
            proc.wait()
        except Exception as e:
            print(f"⚠️ Ошибка туннеля: {e}", flush=True)
        print("🔄 Перезапуск туннеля через 5 секунд...", flush=True)
        time.sleep(5)

if __name__ == "__main__":
    run_tunnel()
