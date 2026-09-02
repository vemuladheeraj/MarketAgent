#!/usr/bin/env python3
"""
Start the complete MarketAgent system:
- Python backend with pipeline daemon and REST API
- React/Vite web dashboard frontend

Usage::

    python start_dashboard.py [--config path/to.yaml] [--web-port 8000] [--frontend-port 3000]

Or with PowerShell::

    python.exe start_dashboard.py
"""

import subprocess
import time
import sys
import threading
from pathlib import Path

def run_command(cmd, name):
    """Run a command in a subprocess and stream output."""
    print(f"\n[{name}] Starting: {' '.join(cmd)}\n")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        for line in process.stdout:
            print(f"[{name}] {line.rstrip()}")
        process.wait()
        if process.returncode != 0:
            print(f"[{name}] Process exited with code {process.returncode}")
    except Exception as e:
        print(f"[{name}] Error: {e}")

def main():
    # Determine project root
    script_dir = Path(__file__).parent
    
    # Start the backend in a separate thread
    backend_thread = threading.Thread(
        target=run_command,
        args=(
            [
                sys.executable, "-m", "app.web.server",
                "--web-port", "8000",
                "--web-host", "127.0.0.1",
            ],
            "BACKEND",
        ),
        daemon=False,
    )
    backend_thread.start()

    # Give backend time to start
    print("\n[MAIN] Waiting for backend to initialize (5 seconds)...")
    time.sleep(5)

    # Start the frontend in a separate thread
    frontend_thread = threading.Thread(
        target=run_command,
        args=(
            [sys.executable, "-m", "http.server", "3000", "--directory", "web/dist"],
            "FRONTEND",
        ),
        daemon=False,
    )
    
    print("\n[MAIN] ============================================================")
    print("[MAIN] MarketAgent Dashboard")
    print("[MAIN] ============================================================")
    print("[MAIN] Backend API:     http://127.0.0.1:8000/api/health")
    print("[MAIN] Dashboard:       http://127.0.0.1:3000 (after npm run build)")
    print("[MAIN] ============================================================")
    print("[MAIN]")
    print("[MAIN] To build the frontend, run:")
    print("[MAIN]   cd web && npm run build")
    print("[MAIN]")
    print("[MAIN] Then start this script again.")
    print("[MAIN]")
    print("[MAIN] Press Ctrl+C to stop.")
    print("[MAIN] ============================================================\n")
    
    # Check if frontend is built
    web_dist = script_dir / "web" / "dist" / "index.html"
    if web_dist.exists():
        frontend_thread.start()
    else:
        print("[MAIN] Frontend not built. Run 'cd web && npm run build' first.")

    # Keep main thread alive
    try:
        backend_thread.join()
    except KeyboardInterrupt:
        print("\n[MAIN] Shutdown requested")
        sys.exit(0)

if __name__ == "__main__":
    main()
