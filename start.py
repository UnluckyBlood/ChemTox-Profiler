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
            print("Ошибка: портативный Python не найден. Убедитесь, что папка 'python' находится рядом с этим файлом.")
            sys.exit(1)
            
        launcher = WORKDIR / "launcher.py"
        print("Запуск ChemTox Profiler (Windows)...")
        subprocess.Popen([str(py_exe), str(launcher)], cwd=WORKDIR)
        
    elif os_type == "Linux":
        venv_dir = WORKDIR / "venv"
        req_file = WORKDIR / "requirements.txt"
        
        if not venv_dir.exists():
            print("Первый запуск на Linux. Создание виртуального окружения...")
            try:
                subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
            except subprocess.CalledProcessError:
                print("\n[ОШИБКА] Не удалось создать venv. Убедитесь, что установлен пакет python3-venv:")
                print("sudo apt install python3-venv")
                sys.exit(1)
            
            print("Установка зависимостей (это может занять 2-5 минут)...")
            pip_exe = venv_dir / "bin" / "pip"
            subprocess.run([str(pip_exe), "install", "-r", str(req_file)], check=True)
            print("Установка завершена.")
        
        # Запуск Streamlit через venv
        streamlit_exe = venv_dir / "bin" / "streamlit"
        print("Запуск ChemTox Profiler (Linux)...")
        print("Приложение будет доступно в браузере по адресу: http://localhost:8501")
        
        # На Linux надежнее открывать в браузере, так как pywebview требует GTK
        subprocess.run([str(streamlit_exe), "run", str(WORKDIR / "streamlit_app.py"), "--server.headless=false"])
        
    else:
        print(f"ОС {os_type} не поддерживается данным скриптом.")

if __name__ == '__main__':
    main()