#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_install.py - проверка установки ChemTox Profiler, докачка недостающего и запуск.

    python check_install.py               проверить и починить то, что можно
    python check_install.py --launch      то же + запустить приложение
    python check_install.py --check-only  только проверить, ничего не скачивать и не ставить

Проверяет по шагам:
  1. Python и pip
  2. Библиотеки из requirements.txt (докатывает pip-ом)
  3. Модели ESKAPE (7 _rf) и LFS-заглушки (докачивает)
  4. Модель биоактивности ChEMBL + самотест расчёта (докачивает)
Работает на Windows (портативный Python) и на Linux (venv).
"""
import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ESKAPE_REPO = "https://github.com/arnolp3/The-ESKAPE-Model"
ESKAPE_ZIP_URL = ESKAPE_REPO + "/archive/refs/heads/main.zip"
ESKAPE_LFS_BASE = "https://media.githubusercontent.com/media/arnolp3/The-ESKAPE-Model/main"
LOCAL_ZIPS = ["The-ESKAPE-Model-main.zip", "eskape-main.zip"]
PATHOGENS = ["AB", "BW", "DKO", "EF", "KP", "PA", "SA"]
DB_ALL = ROOT / "db" / "models" / "all"
CHEMBL_DIR = ROOT / "db" / "models" / "chembl"
MODULES = [  # (имя для import, имя пакета в pip)
    ("rdkit", "rdkit"), ("pandas", "pandas"), ("plotly", "plotly"),
    ("streamlit", "streamlit"), ("admet_ai", "admet-ai"), ("sklearn", "scikit-learn"),
    ("numpy", "numpy"), ("webview", "pywebview"), ("chemprop", "chemprop"),
    ("onnxruntime", "onnxruntime"),
]
TOTAL_STEPS = 4
MARK = {"ok": "[OK]", "warn": "[!!]", "fail": "[XX]"}


def step(n, title):
    print(f"\n=== {n}/{TOTAL_STEPS}  {title} ===", flush=True)


def line(status, text):
    print(f"  {MARK[status]} {text}", flush=True)


def download(url, dest, label=None, quiet=False):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "ChemTox-Profiler"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, 0.0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if not quiet and time.time() - last > 0.5:
                pct = f" ({done * 100 // total}%)" if total else ""
                tot = f" / {total / 1e6:.0f}" if total else ""
                print(f"\r    {label or dest.name}: {done / 1e6:.0f}{tot} МБ{pct}   ", end="", flush=True)
                last = time.time()
    tmp.replace(dest)
    if not quiet:
        print()


# ------------------------------------------------------------------ 1. Python
def check_python():
    step(1, "Python и pip")
    line("ok", f"Python {sys.version.split()[0]} ({sys.executable})")
    r = subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True)
    if r.returncode != 0:
        line("fail", "pip не найден в этом Python")
        return False
    line("ok", "pip " + r.stdout.split()[1])
    return True


# ------------------------------------------------------------------ 2. библиотеки
def missing_modules():
    miss = []
    for mod, pkg in MODULES:
        if mod == "webview" and os.name != "nt":
            continue  # на Linux интерфейс открывается в браузере
        try:
            found = importlib.util.find_spec(mod) is not None
        except Exception:  # noqa: BLE001
            found = False
        if not found:
            miss.append(pkg)
    return miss


def check_modules(fix):
    step(2, "Библиотеки Python")
    miss = missing_modules()
    if miss and fix:
        line("warn", "Не хватает: " + ", ".join(miss) + " - устанавливаю из requirements.txt")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
        importlib.invalidate_caches()
        miss = missing_modules()
    if miss:
        line("fail", "Не установлены: " + ", ".join(miss))
        return False
    line("ok", "Все библиотеки на месте")
    r = subprocess.run([sys.executable, "-c", "from chemprop.sklearn_predict import sklearn_predict"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        tail = (r.stderr.strip().splitlines() or ["?"])[-1]
        line("fail", f"chemprop.sklearn_predict не импортируется (нужен расчёт ESKAPE): {tail}")
        return False
    line("ok", "chemprop (sklearn_predict) импортируется")
    return True


# ------------------------------------------------------------------ 3. ESKAPE
def has_files(d):
    return d.is_dir() and any(p.is_file() for p in d.rglob("*"))


def is_lfs_pointer(p):
    try:
        size = p.stat().st_size
        if size == 0 or size > 256:
            return False
        with open(p, "rb") as fh:
            return fh.read(60).startswith(b"version https://git-lfs.github.com/spec/v1")
    except OSError:
        return False


def find_lfs_pointers():
    db = ROOT / "db"
    return [p for p in db.rglob("*") if p.is_file() and is_lfs_pointer(p)] if db.is_dir() else []


def eskape_status():
    missing = [f"{p}_rf" for p in PATHOGENS if not has_files(DB_ALL / f"{p}_rf")]
    return missing, find_lfs_pointers()


def extract_db(zip_path):
    """Достаёт из архива только db/models/... и кладёт в ./db (чужие файлы в db не трогает)."""
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = info.filename.split("/")
            if ".." in parts:
                continue
            idx = next((i for i in range(len(parts) - 1) if parts[i] == "db" and parts[i + 1] == "models"), None)
            if idx is None:
                continue
            dest = ROOT.joinpath(*parts[idx:])
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
            if n % 200 == 0:
                print(f"\r    распаковано файлов: {n}", end="", flush=True)
    print(f"\r    распаковано файлов: {n}      ")
    return n


def fill_lfs(pointers):
    failed = 0
    for i, p in enumerate(pointers, 1):
        rel = p.relative_to(ROOT).as_posix()
        print(f"\r    докачка LFS: {i}/{len(pointers)}   ", end="", flush=True)
        try:
            download(ESKAPE_LFS_BASE + "/" + urllib.parse.quote(rel), p, quiet=True)
        except Exception:  # noqa: BLE001
            failed += 1
        if is_lfs_pointer(p):
            failed += 1
    print()
    return failed


def check_eskape(fix):
    step(3, "Модели ESKAPE (7 RF-моделей)")
    missing, pointers = eskape_status()
    if fix and missing:
        line("warn", f"Нет моделей: {', '.join(missing)}")
        zip_path = next((ROOT / z for z in LOCAL_ZIPS if (ROOT / z).exists()), None)
        downloaded = False
        try:
            if zip_path:
                line("ok", f"Нашёл локальный архив {zip_path.name} - использую его")
            else:
                line("warn", f"Локального архива нет - скачиваю с {ESKAPE_REPO} (~3.5 ГБ, это надолго)")
                zip_path = ROOT / "eskape-main.zip"
                download(ESKAPE_ZIP_URL, zip_path, "ESKAPE")
                downloaded = True
            extract_db(zip_path)
        except Exception as exc:  # noqa: BLE001
            line("fail", f"Не удалось получить модели: {type(exc).__name__}: {exc}")
        finally:
            if downloaded and zip_path.exists():
                zip_path.unlink()
        missing, pointers = eskape_status()
    if fix and pointers:
        line("warn", f"LFS-заглушек: {len(pointers)} - докачиваю реальные файлы")
        fill_lfs(pointers)
        missing, pointers = eskape_status()
    ok = True
    if missing:
        line("fail", f"Нет RF-моделей: {len(missing)} из {len(PATHOGENS)} ({', '.join(missing)})")
        ok = False
    if pointers:
        line("fail", f"LFS-заглушек осталось: {len(pointers)} (файлы не скачаны полностью)")
        ok = False
    if ok:
        line("ok", f"ESKAPE: {len(PATHOGENS)}/{len(PATHOGENS)} RF-моделей, LFS-заглушек нет")
    return ok


# ------------------------------------------------------------------ 4. ChEMBL
def chembl_selftest(ap):
    from rdkit import Chem
    prof = ap.Profiler(CHEMBL_DIR, ap.ACTIVITY_GROUPS)
    # целекоксиб - заведомо должен считаться; значение не проверяем, важно что расчёт проходит
    mol = ap.standardize(Chem.MolFromSmiles("Cc1ccc(cc1)-c1cc(nn1-c1ccc(cc1)S(N)(=O)=O)C(F)(F)F"))
    _, res = prof.profile(mol)
    p = res["Противовоспалительная"]["p"]
    if not 0.0 <= p <= 1.0:
        raise RuntimeError(f"странный результат самотеста: {p}")
    return len(prof.targets), len(prof.groups), p


def check_chembl(fix):
    step(4, "Модель биоактивности (ChEMBL Multitask)")
    try:
        import activity_profiler as ap
    except ImportError as exc:
        line("fail", f"activity_profiler не загрузился (нужен onnxruntime): {exc}")
        return False
    names = [ap.MODEL_FILE, ap.TARGETS_FILE]
    if fix and not all((CHEMBL_DIR / n).exists() and (CHEMBL_DIR / n).stat().st_size > 1000 for n in names):
        line("warn", "Модель не найдена - скачиваю (~10 МБ)")
        for n in names:
            (CHEMBL_DIR / n).unlink(missing_ok=True)
        try:
            ap.download_model(CHEMBL_DIR, ap.MODEL_BASE_URL)
        except Exception as exc:  # noqa: BLE001
            line("fail", str(exc))
            return False
    if not all((CHEMBL_DIR / n).exists() for n in names):
        line("fail", f"Модель не скачана (нет файлов в {CHEMBL_DIR.relative_to(ROOT)}); запустите без --check-only")
        return False
    for attempt in (1, 2):
        try:
            n_t, n_g, p = chembl_selftest(ap)
            line("ok", f"Модель работает: {n_t} мишеней, {n_g} классов активности; "
                       f"самотест (целекоксиб, противовоспалительная) p={p:.2f}")
            return True
        except Exception as exc:  # noqa: BLE001
            if attempt == 1 and fix:
                line("warn", f"Самотест не прошёл ({type(exc).__name__}: {exc}); перекачиваю модель")
                for n in names:
                    (CHEMBL_DIR / n).unlink(missing_ok=True)
                try:
                    ap.download_model(CHEMBL_DIR, ap.MODEL_BASE_URL)
                except Exception as exc2:  # noqa: BLE001
                    line("fail", str(exc2))
                    return False
            else:
                line("fail", f"Модель не работает: {type(exc).__name__}: {exc}")
                return False
    return False


# ------------------------------------------------------------------ запуск
def launch():
    print("\nЗапускаю ChemTox Profiler...", flush=True)
    if os.name == "nt":
        pyw = Path(sys.executable).with_name("pythonw.exe")
        exe = pyw if pyw.exists() else Path(sys.executable)
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen([str(exe), str(ROOT / "launcher.py")], cwd=ROOT, creationflags=flags)
        print("Окно приложения откроется через несколько секунд. Эту консоль можно закрыть.")
    else:
        print("Приложение откроется в браузере (http://localhost:8501).")
        os.execv(sys.executable, [sys.executable, "-m", "streamlit", "run",
                                  str(ROOT / "streamlit_app.py"), "--server.headless=false"])


def main():
    ap_ = argparse.ArgumentParser(description="Проверка установки ChemTox Profiler")
    ap_.add_argument("--launch", action="store_true", help="запустить приложение после проверки")
    ap_.add_argument("--check-only", action="store_true", help="только проверить, ничего не скачивать")
    args = ap_.parse_args()
    fix = not args.check_only

    print("=" * 50)
    print(" ChemTox Profiler - проверка установки")
    print("=" * 50)

    results = {}
    results["Python"] = check_python()
    results["Библиотеки"] = check_modules(fix) if results["Python"] else False
    results["Модели ESKAPE"] = check_eskape(fix)
    results["Биоактивность (ChEMBL)"] = check_chembl(fix)

    print("\n" + "=" * 50)
    for name, ok in results.items():
        line("ok" if ok else "fail", name)
    bad = [n for n, ok in results.items() if not ok]
    print("=" * 50)

    if not bad:
        print("Всё готово.")
        if args.launch:
            launch()
        return 0

    print("Проблемы: " + ", ".join(bad))
    if args.launch and sys.stdin and sys.stdin.isatty():
        # частичная работа возможна: ADMET-AI, ESKAPE и биоактивность независимы
        try:
            ans = input("Запустить приложение всё равно (часть функций может не работать)? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans in ("y", "yes", "д", "да"):
            launch()
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
