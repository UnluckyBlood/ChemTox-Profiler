#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
activity_profiler.py - локальный расчёт профиля биологической активности по SMILES.

Как это работает
----------------
1. Берётся готовая открытая модель ChEMBL Multitask (многозадачная нейросеть, MIT).
   Вход: Morgan-отпечаток (r=2, 1024 бит). Выход: вероятность того, что вещество
   является активным лигандом для каждой из ~800 белковых мишеней ChEMBL
   (пороги: киназы <=30 нМ, GPCR и ядерные рецепторы <=100 нМ, ионные каналы <=10 мкМ,
   остальные <=1 мкМ).
2. Мишени сгруппированы в фармакологические классы (противовоспалительная,
   противоопухолевая, антигипертензивная и т.д., см. ACTIVITY_GROUPS).
3. Для каждого класса выводится максимальная вероятность по его мишеням,
   лучшая мишень и процентиль относительно набора эталонных лекарств
   (чтобы отсеять "фоновые" мишени, которые модель завышает почти для любой молекулы).

Установка (один раз):
    pip install rdkit onnxruntime numpy
Модель (~10 МБ) скачивается с GitHub при первом запуске в папку ./models
и дальше всё считается офлайн.

Примеры:
    python activity_profiler.py -s "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
    python activity_profiler.py -i molecules.csv --smiles-col smiles -o result.csv
    python activity_profiler.py -i library.sdf -o result.csv --dump-targets all_targets.csv
    python activity_profiler.py --verify-names      # сверить ID мишеней с названиями в ChEMBL

Важно: это вероятность связывания с белковыми мишенями (механизм), а не клинический
эффект и не "Pa" из PASS. Результат - гипотеза для приоритизации, а не доказательство.
"""
import argparse
import csv
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import onnxruntime as ort
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import Descriptors, rdFingerprintGenerator
from rdkit.Chem.MolStandardize import rdMolStandardize

RDLogger.DisableLog("rdApp.*")

# ----------------------------------------------------------------------------------
# Модель
# ----------------------------------------------------------------------------------
MODEL_BASE_URL = ("https://raw.githubusercontent.com/chembl/chembl_multitask_model/"
                  "main/trained_models/chembl_37/")
MODEL_FILE = "chembl_37_multitask.onnx"
TARGETS_FILE = "targets_37_all.json"
FP_SIZE, FP_RADIUS = 1024, 2

# ----------------------------------------------------------------------------------
# Группы активности: класс -> {ChEMBL ID мишени: короткое название}
# Редактируйте свободно или передайте свой JSON через --groups (тот же формат).
# Названия можно сверить с ChEMBL командой --verify-names.
# ----------------------------------------------------------------------------------
ACTIVITY_GROUPS = {
    "Противовоспалительная": {
        "CHEMBL221": "COX-1", "CHEMBL230": "COX-2", "CHEMBL215": "5-LOX",
        "CHEMBL260": "p38alpha MAPK", "CHEMBL275": "PDE4B", "CHEMBL288": "PDE4D",
        "CHEMBL2835": "JAK1", "CHEMBL2971": "JAK2", "CHEMBL2148": "JAK3",
        "CHEMBL3553": "TYK2", "CHEMBL2034": "глюкокортикоидный рецептор",
        "CHEMBL5251": "BTK", "CHEMBL1825": "TNF-alpha",
    },
    "Анальгетическая": {
        "CHEMBL233": "mu-опиоидный", "CHEMBL237": "kappa-опиоидный",
        "CHEMBL236": "delta-опиоидный", "CHEMBL218": "CB1", "CHEMBL253": "CB2",
        "CHEMBL221": "COX-1", "CHEMBL230": "COX-2",
    },
    "Противоопухолевая": {
        "CHEMBL203": "EGFR", "CHEMBL1824": "HER2", "CHEMBL279": "VEGFR2",
        "CHEMBL5145": "BRAF", "CHEMBL1862": "ABL1", "CHEMBL301": "CDK2",
        "CHEMBL2842": "mTOR", "CHEMBL4005": "PI3K-alpha", "CHEMBL325": "HDAC1",
        "CHEMBL3105": "PARP1",
    },
    "Антигипертензивная / кардио": {
        "CHEMBL1808": "ACE", "CHEMBL227": "AT1", "CHEMBL213": "beta-1 AR",
        "CHEMBL210": "beta-2 AR", "CHEMBL229": "alpha-1A AR",
    },
    "Антидиабетическая": {
        "CHEMBL284": "DPP-4", "CHEMBL335": "PTP1B", "CHEMBL235": "PPAR-gamma",
        "CHEMBL239": "PPAR-alpha", "CHEMBL1784": "GLP-1R",
    },
    "Антипсихотическая": {
        "CHEMBL217": "D2", "CHEMBL234": "D3", "CHEMBL224": "5-HT2A",
    },
    "Антидепрессивная / анксиолитическая": {
        "CHEMBL228": "SERT", "CHEMBL222": "NET", "CHEMBL238": "DAT",
        "CHEMBL1951": "MAO-A", "CHEMBL214": "5-HT1A",
    },
    "Антигистаминная": {"CHEMBL231": "H1"},
    "Противовирусная (ВИЧ)": {
        "CHEMBL243": "HIV-1 протеаза", "CHEMBL247": "HIV-1 RT", "CHEMBL3471": "HIV-1 интеграза",
    },
    "Антикоагулянтная": {"CHEMBL204": "тромбин", "CHEMBL244": "фактор Xa"},
    "Нейродегенерация (Альцгеймер)": {
        "CHEMBL220": "AChE", "CHEMBL1914": "BChE", "CHEMBL4822": "BACE1",
    },
}
# Мишени sEH, Ca-канал L-типа и HMG-CoA редуктаза в текущей версии модели (ChEMBL 37) отсутствуют.

# Эталонный набор лекарств для процентилей (невалидные SMILES пропускаются автоматически).
REFERENCE_SMILES = [
    "CC(=O)Oc1ccccc1C(=O)O", "CC(=O)Nc1ccc(O)cc1", "CN(C)C(=N)N=C(N)N",
    "CC(C)Cc1ccc(cc1)C(C)C(=O)O", "COc1ccc2cc(ccc2c1)C(C)C(=O)O",
    "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl", "CCOC(=O)C1=C(C)NC(C)=C(C1c1ccccc1[N+]([O-])=O)C(=O)OC",
    "CCCCc1nc(Cl)c(CO)n1Cc1ccc(cc1)-c1ccccc1-c1nn[nH]n1",
    "COc1ccc2[nH]cc(CCNC(C)=O)c2c1", "CN1CCC[C@H]1c1cccnc1",
    "CN(C)CCCN1c2ccccc2CCc2ccccc21", "CNCCC(Oc1ccc(cc1)C(F)(F)F)c1ccccc1",
    "CN1C(=O)CN=C(c2ccccc2)c2cc(Cl)ccc12", "OC1(CCN(CCCC(=O)c2ccc(F)cc2)CC1)c1ccc(Cl)cc1",
    "CN1CCC23c4c5ccc(O)c4OC2C(O)C=CC3C1C5", "CC(=O)C(C(=O)c1ccccc1)c1ccc(O)cc1O",
    "OC(=O)C1=CN(C2CC2)c2cc(N3CCNCC3)c(F)cc2C1=O", "CC1(C)SC2C(NC(=O)Cc3ccccc3)C(=O)N2C1C(O)=O",
    "CC(C)NCC(O)COc1cccc2ccccc12", "CC(C)(C)NCC(O)c1ccc(O)c(CO)c1",
    "NS(=O)(=O)c1cc2c(cc1Cl)NCNS2(=O)=O", "COc1cc2nc(nc(N)c2cc1OC)N1CCN(CC1)C(=O)c1ccco1",
    "Cc1ccc(cc1)S(=O)(=O)NC(=O)NN1CCCCC1", "CC(C)n1c(C=CC(O)CC(O)CC(O)=O)c(-c2ccccc2)c(-c2ccc(F)cc2)c1C(=O)Nc1ccccc1",
    "COc1ccc(CCN(C)CCCC(C#N)(C(C)C)c2ccc(OC)c(OC)c2)cc1OC", "CC(C)(C)c1ccc(cc1)C(O)CCCN1CCC(CC1)C(O)(c1ccccc1)c1ccccc1",
    "Clc1ccc(cc1)C(c1ccccc1)N1CCN(CC1)CCOCC(O)=O", "NC(=O)N1c2ccccc2C=Cc2ccccc21",
    "CCC1(c2ccccc2)C(=O)NC(=O)NC1=O", "O=C1NC(=O)C(c2ccccc2)(CC)C(=O)N1",
    "Nc1nc(N)c2nc(-c3ccccc3)c(N)nc2n1", "CC(C)(C)NC(=O)C1CC2CCCCC2CN1CC(O)C(Cc1ccccc1)NC(=O)C(CC(N)=O)NC(=O)c1ccc2ccccc2n1",
    "Cn1cnc2c1c(=O)n(C)c(=O)n2C", "Nc1ncnc2c1ncn2C1OC(CO)C(O)C1O",
    "COC(=O)C1=C(C)NC(C)=C(C1c1cccc(c1)[N+]([O-])=O)C(=O)OCCN(C)Cc1ccccc1",
    "CC1=C(C(=O)Nc2ccccc2)C(c2ccccc2)=C(C)N1", "O=C(Nc1ccc(cc1)S(N)(=O)=O)c1ccccc1",
    "Cc1ccc(cc1)-c1cc(nn1-c1ccc(cc1)S(N)(=O)=O)C(F)(F)F", "CN1CCN(CC1)c1ccc(cc1)Nc1nccc(n1)-c1cccnc1",
    "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(n1)-c1cccnc1",
    "COCCOc1cc2ncnc(Nc3cccc(c3)C#C)c2cc1OCCOC", "C[C@@H]1CCN(C[C@@H]1N(C)c1ncnc2[nH]ccc12)C(=O)CC#N",
    "O=C(Nc1c(Cl)cncc1Cl)c1ccc(OC(F)F)c(OCC2CC2)c1",
    "C[C@@H]1C[C@H]2[C@@H]3CCC4=CC(=O)C=C[C@]4([C@]3([C@H](C[C@@]2([C@]1(C(=O)CO)O)C)O)F)C",
    "CC(C)NC(=O)c1ccc(cc1)CNNC", "NC(=O)c1cccnc1", "OC(=O)c1ccccc1O",
    "CCN(CC)CCNC(=O)c1ccc(N)cc1", "Clc1ccc(cc1)C(=O)NCCN1CCOCC1",
    "Cc1cc(C)nc(NS(=O)(=O)c2ccc(N)cc2)n1", "CC(=O)Nc1ccc(cc1)S(N)(=O)=O",
    "O=C(O)CCc1ccccc1", "OCC1OC(O)C(O)C(O)C1O", "CCCc1cc(=O)[nH]c(=S)[nH]1",
]

LEVELS = (("высокая", 0.70, 0.90), ("средняя", 0.50, 0.75))  # (метка, мин. p, мин. процентиль)
STD_UNCHARGER = rdMolStandardize.Uncharger()
LFC = rdMolStandardize.LargestFragmentChooser()


# ----------------------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------------------
def download_model(model_dir: Path, base_url: str) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    for name in (MODEL_FILE, TARGETS_FILE):
        dst = model_dir / name
        if dst.exists() and dst.stat().st_size > 0:
            continue
        print(f"[i] скачиваю {name} ...", file=sys.stderr)
        try:
            urllib.request.urlretrieve(base_url + name, dst)
        except Exception as exc:  # noqa: BLE001
            dst.unlink(missing_ok=True)
            raise RuntimeError(
                f"не удалось скачать {base_url + name}: {exc}. "
                f"Скачайте {MODEL_FILE} и {TARGETS_FILE} вручную в папку {model_dir} "
                f"(репозиторий chembl/chembl_multitask_model, trained_models/chembl_37).") from exc


def standardize(mol):
    mol = LFC.choose(mol)
    mol = STD_UNCHARGER.uncharge(mol)
    Chem.SanitizeMol(mol)
    return mol


def make_fp_fn():
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=FP_RADIUS, fpSize=FP_SIZE)

    def fp(m):
        # совместимо и со старыми версиями RDKit (без GetFingerprintAsNumPy)
        arr = np.zeros((FP_SIZE,), dtype=np.float32)
        DataStructs.ConvertToNumpyArray(gen.GetFingerprint(m), arr)
        return arr
    return fp


class Profiler:
    def __init__(self, model_dir: Path, groups: dict):
        self.targets = json.load(open(model_dir / TARGETS_FILE))
        self.idx = {t: i for i, t in enumerate(self.targets)}
        self.sess = ort.InferenceSession(str(model_dir / MODEL_FILE),
                                         providers=["CPUExecutionProvider"])
        self.in_name = self.sess.get_inputs()[0].name
        self.fp = make_fp_fn()
        self.groups = {}
        for g, members in groups.items():
            present = {t: n for t, n in members.items() if t in self.idx}
            missing = [t for t in members if t not in self.idx]
            if missing:
                print(f"[!] группа '{g}': этих мишеней нет в модели и они пропущены: {missing}",
                      file=sys.stderr)
            if present:
                self.groups[g] = present
        self.ref = self._build_reference()

    def predict(self, mol) -> np.ndarray:
        out = self.sess.run(None, {self.in_name: self.fp(mol)})
        return np.concatenate(out).ravel()

    def _build_reference(self) -> np.ndarray:
        rows = []
        for smi in REFERENCE_SMILES:
            m = Chem.MolFromSmiles(smi)
            if m is not None:
                rows.append(self.predict(standardize(m)))
        if len(rows) < 20:
            raise RuntimeError("слишком мало валидных эталонных молекул")
        return np.vstack(rows)

    def profile(self, mol):
        p = self.predict(mol)
        res = {}
        for g, members in self.groups.items():
            ids = list(members)
            best = max(ids, key=lambda t: p[self.idx[t]])
            pb = float(p[self.idx[best]])
            pct = float((self.ref[:, self.idx[best]] < pb).mean())
            level = "низкая"
            for label, pmin, cmin in LEVELS:
                if pb >= pmin and pct >= cmin:
                    level = label
                    break
            top = sorted(ids, key=lambda t: -p[self.idx[t]])[:3]
            top_str = "; ".join(f"{members[t]} {p[self.idx[t]]:.2f}" for t in top)
            res[g] = {"p": pb, "pct": pct, "level": level, "top": top_str,
                      "best_id": best, "best_name": members[best]}
        return p, res


def read_input(args):
    """Возвращает список (имя, исходная_строка_SMILES, mol|None)."""
    items = []
    if args.smiles:
        for i, s in enumerate(args.smiles, 1):
            items.append((f"mol{i}", s, Chem.MolFromSmiles(s)))
    if args.input:
        path = Path(args.input)
        ext = path.suffix.lower()
        if ext in (".sdf", ".sd"):
            for i, m in enumerate(Chem.SDMolSupplier(str(path)), 1):
                name = m.GetProp("_Name") if m is not None and m.HasProp("_Name") and m.GetProp("_Name") else f"mol{i}"
                items.append((name, Chem.MolToSmiles(m) if m else "", m))
        elif ext in (".csv", ".tsv"):
            delim = "\t" if ext == ".tsv" else ","
            with open(path, newline="", encoding="utf-8-sig") as fh:
                for i, row in enumerate(csv.DictReader(fh, delimiter=delim), 1):
                    smi = row.get(args.smiles_col)
                    if smi is None:
                        sys.exit(f"[!] в файле нет столбца '{args.smiles_col}' (есть: {list(row)})")
                    name = row.get(args.name_col) or f"mol{i}"
                    items.append((name, smi, Chem.MolFromSmiles(smi)))
        else:  # .smi / .txt: "SMILES [имя]"
            for i, line in enumerate(open(path, encoding="utf-8"), 1):
                parts = line.strip().split(None, 1)
                if parts:
                    items.append((parts[1] if len(parts) > 1 else f"mol{i}", parts[0],
                                  Chem.MolFromSmiles(parts[0])))
    if not items:
        sys.exit("[!] нет входных данных: используйте -s или -i (см. --help)")
    return items


def fetch_chembl_names(ids):
    names = {}
    ids = list(ids)
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        url = ("https://www.ebi.ac.uk/chembl/api/data/target.json?" + urllib.parse.urlencode({
            "target_chembl_id__in": ",".join(chunk), "limit": 100,
            "only": "target_chembl_id,pref_name"}, safe=","))
        with urllib.request.urlopen(url, timeout=60) as r:
            for t in json.load(r)["targets"]:
                names[t["target_chembl_id"]] = t["pref_name"]
    return names


def verify_names(groups):
    ids = sorted({t for m in groups.values() for t in m})
    try:
        names = fetch_chembl_names(ids)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"[!] ChEMBL API недоступен: {exc}")
    print(f"{'ID':<14}{'мое название':<32}название в ChEMBL")
    for g, m in groups.items():
        print(f"\n# {g}")
        for t, n in m.items():
            print(f"{t:<14}{n:<32}{names.get(t, '??? не найден')}")


# ----------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Локальный профиль биологической активности (ChEMBL multitask)")
    ap.add_argument("-s", "--smiles", nargs="+", help="один или несколько SMILES")
    ap.add_argument("-i", "--input", help="файл: .csv/.tsv, .smi/.txt или .sdf")
    ap.add_argument("--smiles-col", default="smiles", help="столбец SMILES в csv/tsv (по умолчанию smiles)")
    ap.add_argument("--name-col", default="name", help="столбец с названием в csv/tsv (по умолчанию name)")
    ap.add_argument("-o", "--output", help="сохранить сводную таблицу в CSV")
    ap.add_argument("--dump-targets", help="сохранить вероятности по ВСЕМ мишеням в CSV")
    ap.add_argument("--groups", help="JSON с вашими группами: {\"Группа\": {\"CHEMBLxxx\": \"название\"}}")
    ap.add_argument("--model-dir", default="models", help="папка с моделью (по умолчанию ./models)")
    ap.add_argument("--model-url", default=MODEL_BASE_URL, help="откуда скачать модель")
    ap.add_argument("--verify-names", action="store_true", help="сверить ID мишеней с названиями в ChEMBL и выйти")
    ap.add_argument("--quiet", action="store_true", help="не печатать таблицы в консоль")
    args = ap.parse_args()

    groups = ACTIVITY_GROUPS
    if args.groups:
        groups = json.load(open(args.groups, encoding="utf-8"))
    if args.verify_names:
        verify_names(groups)
        return

    model_dir = Path(args.model_dir)
    try:
        download_model(model_dir, args.model_url)
    except RuntimeError as exc:
        sys.exit(f"[!] {exc}")
    prof = Profiler(model_dir, groups)
    items = read_input(args)

    rows, all_t = [], []
    for name, smi_in, mol in items:
        row = {"name": name, "smiles_input": smi_in, "status": "ok", "warning": ""}
        if mol is None:
            row["status"] = "invalid_smiles"
            rows.append(row)
            continue
        try:
            mol = standardize(mol)
        except Exception:  # noqa: BLE001
            row["status"] = "standardization_failed"
            rows.append(row)
            continue
        mw = Descriptors.MolWt(mol)
        if mw < 150 or mw > 900:
            row["warning"] = f"MW={mw:.0f}: вне типичного диапазона лекарственных молекул, оценка ненадёжна"
        row["smiles_std"] = Chem.MolToSmiles(mol)
        p, res = prof.profile(mol)
        for g, r in res.items():
            row[f"{g} | p"] = round(r["p"], 3)
            row[f"{g} | процентиль"] = round(r["pct"], 3)
            row[f"{g} | уровень"] = r["level"]
            row[f"{g} | мишень"] = f'{r["best_name"]} ({r["best_id"]})'
            row[f"{g} | топ-3 мишени"] = r["top"]
        rows.append(row)
        all_t.append((name, p))

        if not args.quiet:
            print(f"\n=== {name}  {row['smiles_std']}")
            if row["warning"]:
                print(f"    ! {row['warning']}")
            print(f"    {'Класс активности':<38}{'p':>6}{'проц.':>7}  {'уровень':<9}топ-3 мишени (p)")
            for g, r in sorted(res.items(), key=lambda kv: -kv[1]["p"]):
                print(f"    {g:<38}{r['p']:>6.2f}{r['pct']:>7.2f}  {r['level']:<9}{r['top']}")
    if args.output:
        cols = []
        for r in rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        with open(args.output, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
        print(f"\n[i] сводная таблица: {args.output}", file=sys.stderr)
    if args.dump_targets:
        with open(args.dump_targets, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["name"] + prof.targets)
            for name, p in all_t:
                w.writerow([name] + [round(float(x), 4) for x in p])
        print(f"[i] все мишени: {args.dump_targets}", file=sys.stderr)


if __name__ == "__main__":
    main()
