import subprocess
import sys
import os
import socket
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

DEFAULT_PORT = 5000
LOG_DIR = "deploy_logs"
HISTORY_FILE = "deploy_history.json"
IMAGE_NAME = "autodeploy-app"
ROLLBACK_TAG = "rollback"
HEALTH_PATH = "/health"
HEALTH_RETRIES = 10
HEALTH_DELAY = 3


def run_cmd(cmd_list, log_file=None, cwd=None):
    """Run a command safely (list args, no shell=True), print output, and optionally log it."""
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    process = subprocess.Popen(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=cwd,
    )

    output_lines = []
    with open(log_file, "a", encoding="utf-8") if log_file else open(os.devnull, "w") as f:
        for line in process.stdout:
            print(line, end="")
            output_lines.append(line)
            if log_file:
                f.write(line)
    process.wait()

    if process.returncode != 0:
        raise RuntimeError(f"Command failed ({process.returncode}): {' '.join(cmd_list)}")

    return "".join(output_lines)


def run_cmd_capture(cmd_list):
    """Run a command and capture stdout without raising on non-zero exit."""
    result = subprocess.run(
        cmd_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=False,
    )
    return result.returncode, result.stdout.strip()


def find_free_port(start_port=DEFAULT_PORT):
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


def check_health(port, retries=HEALTH_RETRIES, delay=HEALTH_DELAY):
    """Poll /health on the given port. Returns True if it responds 2xx."""
    url = f"http://localhost:{port}{HEALTH_PATH}"
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if 200 <= resp.status < 300:
                    print(f"✅ Health check passed (attempt {attempt}/{retries})")
                    return True
                print(f"⚠️ Attempt {attempt}/{retries}: HTTP {resp.status}")
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            print(f"⚠️ Attempt {attempt}/{retries}: not ready yet ({e})")
        time.sleep(delay)
    return False


def get_container_on_port(port):
    """Return the container ID currently publishing this port, if any."""
    code, output = run_cmd_capture(["docker", "ps", "-q", "--filter", f"publish={port}"])
    if code != 0 or not output:
        return None
    return output.splitlines()[0]


def backup_current_image(port):
    """Tag the image currently running on this port as a rollback candidate."""
    container_id = get_container_on_port(port)
    if not container_id:
        print("ℹ️ No running container on this port — nothing to back up.")
        return False

    code, image = run_cmd_capture(
        ["docker", "inspect", "--format={{.Config.Image}}", container_id]
    )
    if code != 0 or not image:
        print("⚠️ Could not inspect running container. Skipping backup.")
        return False

    rollback_ref = f"{IMAGE_NAME}:{ROLLBACK_TAG}-{port}"
    subprocess.run(["docker", "tag", image, rollback_ref], check=False)
    print(f"💾 Backed up '{image}' as '{rollback_ref}' for rollback.")
    return True


def rollback(port, log_file):
    rollback_ref = f"{IMAGE_NAME}:{ROLLBACK_TAG}-{port}"
    code, exists = run_cmd_capture(["docker", "images", "-q", rollback_ref])
    if code != 0 or not exists:
        print("❌ No rollback image available. Manual intervention required.")
        return False

    print(f"↩️ Rolling back to {rollback_ref}...")
    container_name = f"autodeploy-{port}"
    subprocess.run(["docker", "rm", "-f", container_name], check=False)
    run_cmd(
        ["docker", "run", "-d", "--name", container_name,
         "-p", f"{port}:{port}", rollback_ref],
        log_file,
    )
    if check_health(port):
        print("✅ Rollback successful — previous version restored.")
        return True
    print("❌ Rollback deployment also failed its health check.")
    return False


def deploy(path="."):
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"deploy_{timestamp}.log")

    print("🚀 Starting deployment...")
    abs_path = os.path.abspath(path)
    if not os.path.isdir(abs_path):
        print(f"❌ Path does not exist: {abs_path}")
        return

    print(f"📁 Deploying project at: {abs_path}")

    port = find_free_port(DEFAULT_PORT)
    print(f"🔌 Using port {port} for container")

    container_name = f"autodeploy-{port}"
    image_tag = f"{IMAGE_NAME}:{timestamp}"

    # Back up whatever is currently running on this port, so we can roll back
    rollback_available = backup_current_image(port)

    # Now it's safe to stop the old container
    old_container = get_container_on_port(port)
    if old_container:
        print(f"🛑 Stopping old container {old_container}...")
        subprocess.run(["docker", "rm", "-f", old_container], check=False)
    else:
        print("✅ No old container found on this port.")

    status = "failed"
    url = None

    try:
        print("📦 Building Docker image...")
        run_cmd(
            ["docker", "build", "-t", image_tag, "-t", f"{IMAGE_NAME}:latest", abs_path],
            log_file,
        )

        print("▶️ Running container...")
        run_cmd(
            ["docker", "run", "-d", "--name", container_name,
             "-e", f"APP_VERSION={timestamp}",
             "-p", f"{port}:{port}", image_tag],
            log_file,
        )

        print("🩺 Running health check...")
        if not check_health(port):
            raise RuntimeError("Health check failed after deployment.")

        url = f"http://localhost:{port}"
        print("✅ Deployment complete!")
        print(f"🌐 App running on: {url}")
        print(f"📝 Log saved at: {log_file}")
        status = "success"

    except Exception as e:
        print(f"❌ Deployment failed: {e}")
        subprocess.run(["docker", "rm", "-f", container_name], check=False)
        if rollback_available:
            if rollback(port, log_file):
                status = "rolled_back"
                url = f"http://localhost:{port}"

    subprocess.run(["docker", "image", "prune", "-f"], check=False)

    history = load_history()
    history.append({
        "timestamp": timestamp,
        "project_path": abs_path,
        "port": port,
        "image_tag": image_tag,
        "url": url,
        "log_file": log_file,
        "status": status,
    })
    save_history(history)


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "deploy":
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        deploy(path)
    else:
        print("Usage: python main.py deploy [project_path]")
        print("Example: python main.py deploy ../test-app")
