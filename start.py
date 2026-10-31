import sys
import subprocess
import platform
from pathlib import Path

WORKDIR = Path(__file__).resolve().parent
MODELS_DIR = WORKDIR / "db" / "models" / "all"


def run_installer(script, command):
    if not script.exists():
        print(f"Ошибка: не найден {script.name}.")
        sys.exit(1)
    print("Выполняется установка...")
    result = subprocess.run(command, cwd=WORKDIR)
    if result.returncode != 0:
        print("Установка завершилась с ошибкой.")
        sys.exit(1)


# Запуск приложения с учетом ОС
def main():
    os_type = platform.system()

    if os_type == "Windows":
        py_exe = WORKDIR / "python" / "pythonw.exe"
        if not py_exe.exists() or not MODELS_DIR.exists():
            installer = WORKDIR / "install.bat"
            run_installer(installer, ["cmd", "/c", str(installer)])
        if not py_exe.exists():
            print("Ошибка: портативный Python не найден. Убедитесь, что папка 'python' находится рядом с этим файлом.")
            sys.exit(1)

        launcher = WORKDIR / "launcher.py"
        print("Запуск ChemTox Profiler (Windows)...")
        subprocess.Popen([str(py_exe), str(launcher)], cwd=WORKDIR)

    elif os_type == "Linux":
        streamlit_exe = WORKDIR / "venv" / "bin" / "streamlit"
        if not streamlit_exe.exists() or not MODELS_DIR.exists():
            installer = WORKDIR / "install.sh"
            run_installer(installer, ["bash", str(installer)])

        # Запуск Streamlit через venv
        print("Запуск ChemTox Profiler (Linux)...")
        print("Приложение будет доступно в браузере по адресу: http://localhost:8501")

        # На Linux надежнее открывать в браузере, так как pywebview требует GTK
        subprocess.run([
            str(streamlit_exe), "run", str(WORKDIR / "streamlit_app.py"),
            "--server.headless=false",
            "--browser.gatherUsageStats=false",
        ])

    else:
        print(f"ОС {os_type} не поддерживается данным скриптом.")


if __name__ == '__main__':
    main()
