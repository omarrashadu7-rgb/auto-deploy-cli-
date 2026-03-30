import subprocess
import sys
import os
import socket
import json
from datetime import datetime

DEFAULT_PORT = 5000
LOG_DIR = "deploy_logs"
HISTORY_FILE = "deploy_history.json"

def run_cmd(cmd, log_file=None):
    """Run a shell command, print output, and optionally log it"""
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    with open(log_file, "a", encoding="utf-8") if log_file else open(os.devnull, "w") as f:
        for line in process.stdout:
            print(line, end="")
            if log_file:
                f.write(line)
    process.wait()
    if process.returncode != 0:
        raise Exception(f"Command failed: {cmd}")

def find_free_port(start_port=5000):
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                port += 1

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def deploy(path="."):
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"deploy_{timestamp}.log")

    print("🚀 Starting deployment...")
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        print(f"❌ Path does not exist: {abs_path}")
        return
    os.chdir(abs_path)
    print(f"📁 Deploying project at: {abs_path}")

    # find free port
    port = find_free_port(DEFAULT_PORT)
    print(f"🔌 Using port {port} for container")

    # stop old containers using this port
    try:
        output = subprocess.check_output(f'docker ps -q --filter "publish={port}"', shell=True, text=True).strip()
        if output:
            container_ids = output.splitlines()
            for cid in container_ids:
                print(f"🛑 Stopping old container {cid}...")
                run_cmd(f"docker rm -f {cid}", log_file)
        else:
            print("✅ No old containers found on this port.")
    except subprocess.CalledProcessError:
        print("⚠️ Could not check existing containers. Skipping cleanup.")

    # cleanup old images
    try:
        images = subprocess.check_output(f'docker images -q autodeploy-app', shell=True, text=True).strip()
        for img in images.splitlines():
            if img:
                print(f"🧹 Removing old image {img}...")
                run_cmd(f"docker rmi -f {img}", log_file)
    except subprocess.CalledProcessError:
        pass

    # build docker image
    print("📦 Building Docker image...")
    run_cmd(f'docker build -t autodeploy-app "{abs_path}"', log_file)

    # run container
    print("▶️ Running container...")
    run_cmd(f'docker run -d -p {port}:{port} autodeploy-app', log_file)

    url = f"http://localhost:{port}"
    print("✅ Deployment complete!")
    print(f"🌐 App running on: {url}")
    print(f"📝 Log saved at: {log_file}")

    # save history
    history = load_history()
    history.append({
        "timestamp": timestamp,
        "project_path": abs_path,
        "port": port,
        "url": url,
        "log_file": log_file
    })
    save_history(history)

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "deploy":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        deploy(path)
    else:
        print("Usage: python main.py deploy [project_path]")
        print("Example: python main.py deploy ../test-app")