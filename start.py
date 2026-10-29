import sys
import os
import subprocess
import platform
from pathlib import Path

WORKDIR = Path(__file__).resolve().parent

# Запуск приложения с учетом ОС
def main():
    os_type = platform.system()

    if os_type == "Windows":
        py_exe = WORKDIR / "python" / "pythonw.exe"
        if not py_exe.exists():
            print("Ошибка: портативный Python не найден. Убедитесь, что папка python находится рядом с этим файлом.")
            sys.exit(1)
            
        launcher = WORKDIR / "launcher.py"
        print("Запуск ChemTox Profiler (Windows)...")
        # Запуск без консольного окна
        subprocess.Popen([str(py_exe), str(launcher)], cwd=WORKDIR)
        
    elif os_type == "Linux":
        venv_dir = WORKDIR / "venv"
        if not venv_dir.exists():
            print("Настройка окружения Linux (первый запуск может занять время)...")
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)])
            pip_exe = venv_dir / "bin" / "pip"
            subprocess.run([str(pip_exe), "install", "-r", str(WORKDIR / "requirements.txt")])
        
        streamlit_exe = venv_dir / "bin" / "streamlit"
        print("Запуск ChemTox Profiler (Linux)...")
        subprocess.run([str(streamlit_exe), "run", str(WORKDIR / "streamlit_app.py"), "--server.headless=false"])
        
    else:
        print(f"ОС {os_type} не поддерживается.")

if __name__ == '__main__':
    main()