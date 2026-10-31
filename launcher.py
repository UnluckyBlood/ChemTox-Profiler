import webview
import subprocess
import time
import socket
import sys
import os

WORKDIR = os.path.dirname(os.path.abspath(__file__))
PORT_START = 8501
PORT_END = 8599
PORT_WAIT_SECONDS = 60


def port_is_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def start_streamlit(port):
    if os.name == 'nt':
        python_exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
        creationflags = subprocess.CREATE_NO_WINDOW
    else:
        python_exe = sys.executable
        creationflags = 0

    cmd = [
        python_exe, "-m", "streamlit", "run",
        os.path.join(WORKDIR, "streamlit_app.py"),
        "--server.headless=true",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.enableCORS=false",
    ]
    return subprocess.Popen(cmd, cwd=WORKDIR, creationflags=creationflags)


def start_server_and_wait():
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue

        proc = start_streamlit(port)
        deadline = time.time() + PORT_WAIT_SECONDS
        ok = False

        while time.time() < deadline:
            if proc.poll() is not None:
                break
            if port_is_open(port):
                ok = True
                break
            time.sleep(0.5)

        if ok:
            return port, proc

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    return None, None


if __name__ == '__main__':
    port, proc = start_server_and_wait()
    if port is None:
        print(f"Не удалось занять порт в диапазоне {PORT_START}-{PORT_END}.")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"
    webview.create_window("ChemTox Profiler", url, width=1400, height=900)
    try:
        if os.name == 'nt':
            webview.start(gui='edgechromium')
        else:
            webview.start()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass