import webview
import subprocess
import time
import socket
import sys
import os
import ctypes

WORKDIR = os.path.dirname(os.path.abspath(__file__))
PORT_START = 8501
PORT_END = 8599
PORT_WAIT_SECONDS = 60
LOG_MAX_BYTES = 5 * 1024 * 1024


def log_path():
    if os.name == 'nt':
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    folder = os.path.join(base, "ChemTox Profiler")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "chemtox.log")


LOG_PATH = log_path()


def show_error(text):
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(None, text, "ChemTox Profiler", 0x10)
    else:
        print(text, file=sys.stderr)


def port_is_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def start_streamlit(port, log):
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
        "--browser.gatherUsageStats=false",
    ]
    return subprocess.Popen(
        cmd,
        cwd=WORKDIR,
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def start_server_and_wait(log):
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
            except OSError:
                continue

        proc = start_streamlit(port, log)
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
    too_big = os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > LOG_MAX_BYTES
    log = open(LOG_PATH, "wb" if too_big else "ab")
    port, proc = start_server_and_wait(log)
    if port is None:
        log.close()
        show_error(f"Не удалось запустить сервер (порты {PORT_START}-{PORT_END}).\nПодробности в журнале:\n{LOG_PATH}")
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
        log.close()
