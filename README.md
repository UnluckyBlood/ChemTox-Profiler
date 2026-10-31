# ChemTox Profiler v1.2.0

Десктопное приложение для прогнозирования токсичности (ADMET-AI) и антибактериальной активности (ESKAPE, Random Forest) по SMILES-строке.

Расчёты выполняются in silico и не заменяют эксперимент. Для молекул, непохожих на обучающие выборки, результаты менее надёжны.

## Windows

### Через установщик (рекомендуется)
В разделе Releases доступны два установщика:
- `ChemTox-Profiler-Offline-Setup.exe` — содержит Python и модели, интернет не нужен.
- `ChemTox-Profiler-Online-Setup.exe` — после установки скачивает портативный Python, библиотеки и модели ESKAPE.

После установки запускайте программу с ярлыка на рабочем столе или из меню Пуск.

### Из исходников
1. Запустите `install.bat` — он скачает портативный Python 3.10, библиотеки и модели и создаст ярлыки.
2. Запускайте через ярлык или `launch.bat`.

Прямой запуск: `python\pythonw.exe launcher.py`

Журнал работы: `%LOCALAPPDATA%\ChemTox Profiler\chemtox.log`

## Linux (Debian/Ubuntu)

Системные пакеты:

`sudo apt update`
`sudo apt install python3 python3-venv python3-pip build-essential libgl1 curl unzip`

Установка и запуск:
1. `./install.sh` — создаёт `venv`, ставит библиотеки и скачивает модели.
2. `./launch.sh` — запускает приложение, оно откроется в браузере по адресу http://localhost:8501.

`python3 start.py` делает то же самое: при первом запуске вызывает `install.sh`, затем запускает приложение.

## Структура проекта
- `install.bat`, `setup.ps1` — установка на Windows
- `install.sh` — установка на Linux
- `launch.bat`, `launch.sh` — запуск
- `start.py` — универсальный скрипт: установка при необходимости и запуск
- `launcher.py` — точка входа для Windows (окно pywebview)
- `streamlit_app.py` — интерфейс и логика расчётов
- `requirements.txt` — зависимости
- `setup_offline.iss`, `setup_online.iss`, `version.iss` — сборка установщиков (Inno Setup)
- `python/` — портативный Python 3.10 (только Windows)
- `db/` — модели Random Forest

## Функционал
- Прогноз токсичности (ADMET-AI): hERG, DILI, Ames, LD50 (мг/кг, крыса, перорально, и класс GHS).
- Прогноз антибактериальной активности: 7 моделей Random Forest (AB, BW, DKO, EF, KP, PA, SA).
- Поиск структурных алертов противогрибковых классов (азолы, полиены). Это не прогноз активности.
- Физико-химические дескрипторы (MW, LogP, TPSA, H-доноры, H-акцепторы).

## Источники
- ADMET-AI: https://github.com/swansonk14/admet_ai
- ESKAPE-модели: https://github.com/arnolp3/The-ESKAPE-Model
