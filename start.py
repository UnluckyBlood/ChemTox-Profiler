import sys
import os
import subprocess
import platform
from pathlib import Path

WORKDIR = Path(__file__).resolve().parent

def main():
    os_type = platform.system()

    if os_type == "Windows":
        py_exe = WORKDIR / "python" / "pythonw.exe"
        if not py_exe.exists():
            print("Ошибка: портативный Python не найден.")
            sys.exit(1)
        launcher = WORKDIR / "launcher.py"
        print("Запуск ChemTox Profiler (Windows)...")
        subprocess.Popen([str(py_exe), str(launcher)], cwd=WORKDIR)
        
    elif os_type == "Linux":
        venv_dir = WORKDIR / "venv"
        req_file = WORKDIR / "requirements.txt"
        
        if not req_file.exists():
            print(f"Ошибка: файл {req_file} не найден.")
            sys.exit(1)
            
        need_venv = True
        if venv_dir.exists():
            try:
                v_out = subprocess.check_output([str(venv_dir / "bin" / "python"), "--version"], text=True, stderr=subprocess.STDOUT).strip()
                if "3.12" in v_out:
                    need_venv = False
            except Exception:
                pass
        
        if need_venv:
            print("Создание виртуального окружения...")
            python_exe = "python3.12" if subprocess.run(["which", "python3.12"], capture_output=True).returncode == 0 else sys.executable
            subprocess.run([python_exe, "-m", "venv", str(venv_dir)], check=True)
            
            print("Установка зависимостей (это займет несколько минут)...")
            pip_exe = venv_dir / "bin" / "pip"
            subprocess.run([str(pip_exe), "install", "-r", str(req_file)], check=True)
            print("Установка завершена.")
        
        print("Запуск ChemTox Profiler (Linux)...")
        print("Приложение откроется в вашем браузере по адресу: http://localhost:8501")
        print("Для остановки сервера нажмите Ctrl+C")
        
        streamlit_exe = venv_dir / "bin" / "streamlit"
        subprocess.run([str(streamlit_exe), "run", str(WORKDIR / "streamlit_app.py"), "--server.headless=false"])
        
    else:
        print(f"ОС {os_type} не поддерживается.")

if __name__ == '__main__':
    main()
