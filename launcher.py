import webview
import subprocess
import time
import socket
import threading
import sys
import os

WORKDIR = os.path.dirname(os.path.abspath(__file__))

# Запуск Streamlit-сервера в фоновом режиме
def start_server():
    python_exe = os.path.join(os.path.dirname(sys.executable), "python.exe")
    cmd = [python_exe, "-m", "streamlit", "run", os.path.join(WORKDIR, "streamlit_app.py"),
           "--server.headless=true", "--server.port=8501"]
    subprocess.Popen(cmd, cwd=WORKDIR,
                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)

if __name__ == '__main__':
    # Ожидание запуска сервера и открытие нативного окна
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()
    
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", 8501), timeout=1):
                break
        except OSError:
            time.sleep(1)
            
    webview.create_window("ChemTox Profiler", "http://127.0.0.1:8501", width=1400, height=900)
    webview.start()