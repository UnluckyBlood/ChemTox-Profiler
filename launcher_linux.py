import os
os.environ["PYWEBVIEW_GUI"] = "qt"
import webview
import subprocess
import time
import socket
import threading
import sys
import os

WORKDIR = os.path.dirname(os.path.abspath(__file__))

def start_server():
    # Запускаем Streamlit в фоновом режиме
    cmd = [
        os.path.join(WORKDIR, "venv", "bin", "streamlit"),
        "run",
        os.path.join(WORKDIR, "streamlit_app.py"),
        "--server.headless=true",
        "--server.port=8501"
    ]
    # Отключаем вывод в консоль, чтобы не засорять терминал
    subprocess.Popen(cmd, cwd=WORKDIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

if __name__ == '__main__':
    # Запускаем сервер в отдельном потоке
    t = threading.Thread(target=start_server)
    t.daemon = True
    t.start()

    # Ждем, пока сервер запустится (максимум 30 секунд)
    for _ in range(30):
        try:
            with socket.create_connection(("127.0.0.1", 8501), timeout=1):
                print("Streamlit сервер готов. Открываем окно...")
                break
        except OSError:
            time.sleep(1)
    else:
        print("Ошибка: Streamlit сервер не запустился за 30 секунд.")
        sys.exit(1)

    # Создаем и запускаем нативное окно
    webview.create_window("ChemTox Profiler", "http://127.0.0.1:8501", width=1400, height=900)
    webview.start()
