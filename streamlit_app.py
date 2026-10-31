import base64
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

WORKDIR = Path(__file__).resolve().parent
DB_PATH = WORKDIR / "db"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
PATHOGENS = ["AB", "BW", "DKO", "EF", "KP", "PA", "SA"]
ESKAPE_RUNNER = (
    "import sys;"
    "sys.argv[0]='sklearn_predict';"
    "from chemprop.sklearn_predict import sklearn_predict;"
    "sys.exit(sklearn_predict())"
)

st.set_page_config(page_title="ChemTox Profiler", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
.card { padding: 14px; border-radius: 10px; margin-bottom: 8px; }
.card-green { background: rgba(46, 125, 50, 0.15); border-left: 5px solid #2e7d32; }
.card-red { background: rgba(198, 40, 40, 0.15); border-left: 5px solid #c62828; }
.card-yellow { background: rgba(249, 168, 37, 0.15); border-left: 5px solid #f9a825; }
.card-blue { background: rgba(25, 118, 210, 0.15); border-left: 5px solid #1976d2; }
.card-gray { background: rgba(97, 97, 97, 0.15); border-left: 5px solid #616161; }
.big { font-size: 42px; font-weight: 700; line-height: 1; }
</style>
""", unsafe_allow_html=True)


def ld50_mgkg(log_molkg, mw):
    return (10 ** (-log_molkg)) * mw * 1000


def ghs_class(mg):
    if mg is None:
        return "—"
    if mg <= 5:
        return "1 — смертельно"
    if mg <= 50:
        return "2 — смертельно"
    if mg <= 300:
        return "3 — токсично"
    if mg <= 2000:
        return "4 — вредно"
    if mg <= 5000:
        return "5 — малоопасно"
    return "> 5000 — нетоксично"


def color_for(mg):
    if mg is None:
        return "gray"
    if mg <= 300:
        return "red"
    if mg <= 2000:
        return "yellow"
    return "green"


def mol_svg(mol, w=340, h=340):
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
    d.FinishDrawing()
    b64 = base64.b64encode(d.GetDrawingText().encode()).decode()
    return (
        f'<div style="background:#fff;padding:10px;border-radius:10px;text-align:center">'
        f'<img src="data:image/svg+xml;base64,{b64}" width="{w}"/></div>'
    )


@st.cache_resource(show_spinner=False)
def get_admet_model():
    from admet_ai import ADMETModel
    return ADMETModel()


def run_admet(smiles):
    try:
        p = get_admet_model().predict(smiles=smiles)
        keys = {"hERG": "hERG", "DILI": "DILI", "Ames": "AMES", "LD50": "LD50_Zhu"}
        out = {}
        for label, key in keys.items():
            if isinstance(p, dict) and key in p:
                out[label] = float(p[key])
        return out
    except Exception as e:
        return {"error": str(e)}


def predict_pathogen(csv_in, out_dir, db_dir, pathogen):
    preds_path = out_dir / f"{pathogen}_rf.csv"
    model_dir = db_dir / f"{pathogen}_rf"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", ESKAPE_RUNNER,
             "--test_path", str(csv_in),
             "--checkpoint_dir", str(model_dir),
             "--preds_path", str(preds_path)],
            cwd=str(WORKDIR),
            capture_output=True,
            text=True,
            timeout=300,
            creationflags=NO_WINDOW,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()
            tail = tail[-3:] if tail else []
            return pathogen, None, f"rc={proc.returncode}; " + " | ".join(tail)
        if not preds_path.exists():
            return pathogen, None, "файл предсказаний не создан"
        df = pd.read_csv(preds_path)
        if df.empty:
            return pathogen, None, "пустой файл предсказаний"
        return pathogen, float(df.iloc[0]["activity"]), None
    except subprocess.TimeoutExpired:
        return pathogen, None, "timeout 300s"
    except Exception as e:
        return pathogen, None, f"{type(e).__name__}: {e}"


def run_eskape(smiles):
    results = {"rf": {}}
    db_dir = WORKDIR / "db" / "models" / "all"
    errors = []

    with tempfile.TemporaryDirectory(prefix="chemtox_") as tmp:
        out_dir = Path(tmp)
        csv_in = out_dir / "input.csv"
        pd.DataFrame({"smiles": [smiles]}).to_csv(csv_in, index=False)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(predict_pathogen, csv_in, out_dir, db_dir, p) for p in PATHOGENS]
            for fut in futures:
                pathogen, value, err = fut.result()
                if err:
                    errors.append(f"{pathogen}: {err}")
                else:
                    results["rf"][pathogen] = value

    err_text = "; ".join(errors) if errors else None
    if not results["rf"]:
        return {}, err_text
    return {"input.csv": {smiles: results}}, err_text


def antifungal(mol):
    out = []
    if mol.HasSubstructMatch(Chem.MolFromSmarts("[CX4][nX3]1cncc1")) or mol.HasSubstructMatch(Chem.MolFromSmarts("[CX4][nX3]1cncn1")):
        out.append("N-замещённый азол (имидазол / 1,2,4-триазол)")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("[CX3]=[CX3]-[CX3]=[CX3]-[CX3]=[CX3]-[CX3]=[CX3]")):
        out.append("Полиеновая система (4+ сопряжённых связи)")
    return out


with st.sidebar:
    st.header("Ввод")
    smiles_in = st.text_area(
        "SMILES",
        "CN(C)CCCN(CCCN(C)C)C(=O)C(Cc1ccccc1)NC(=O)C12CC3CC(CC(C3)C1)C2",
        height=90,
    )
    with st.expander("Справочные LD50 (вручную)"):
        ref_oral = st.number_input("Перорально, мг/кг", min_value=0.0, value=0.0)
        ref_ip = st.number_input("i.p., мг/кг", min_value=0.0, value=0.0)
        calc_ip = st.checkbox("Рассчитать i.p. из oral (x0.33)", value=True)
    calc_btn = st.button("Рассчитать всё", type="primary", use_container_width=True)

if not smiles_in or not smiles_in.strip():
    st.info("Введите SMILES слева.")
    st.stop()

mol = Chem.MolFromSmiles(smiles_in.strip())
if mol is None:
    st.error("Неверный SMILES.")
    st.stop()

smiles = Chem.MolToSmiles(mol)

if 'current_smiles' not in st.session_state or st.session_state['current_smiles'] != smiles:
    st.session_state['current_smiles'] = smiles
    st.session_state['esk'] = {}
    st.session_state['esk_err'] = None
    st.session_state['tox'] = {}

if calc_btn:
    with st.status("1/2: Расчет токсичности (ADMET-AI)...", expanded=True) as status:
        st.session_state['tox'] = run_admet(smiles)
        status.update(label="2/2: Расчет ESKAPE (RF)...", state="running")
        esk_data, esk_err = run_eskape(smiles)
        st.session_state['esk'] = esk_data
        st.session_state['esk_err'] = esk_err
        if esk_data:
            status.update(label="Готово", state="complete", expanded=False)
        else:
            status.update(label="Ошибка ESKAPE", state="error")
    st.rerun()

tox = st.session_state.get('tox', {})
esk = st.session_state.get('esk', {})
esk_err = st.session_state.get('esk_err')

esk_merged = {}
if esk:
    for _, by_s in esk.items():
        for s_json, r in by_s.items():
            for method in ("rf", "chemprop", "rdkit"):
                for p, v in (r.get(method) or {}).items():
                    if v not in ("", None):
                        esk_merged.setdefault(p, []).append(float(v))
    esk_merged = {p: sum(vs) / len(vs) for p, vs in esk_merged.items()}

desc = {
    "MW": round(Descriptors.MolWt(mol), 1),
    "LogP": round(Descriptors.MolLogP(mol), 2),
    "TPSA": round(Descriptors.TPSA(mol), 1),
    "H-доноры": Lipinski.NumHDonors(mol),
    "H-акцепторы": Lipinski.NumHAcceptors(mol),
}

st.title("Профиль молекулы")
st.caption(f"SMILES: `{smiles}` · Формула: **{rdMolDescriptors.CalcMolFormula(mol)}**")

c1, c2, c3 = st.columns([1, 1.1, 1.4])
with c1:
    st.markdown("#### Структура")
    st.markdown(mol_svg(mol), unsafe_allow_html=True)
with c2:
    st.markdown("#### Вердикт")
    herg = tox.get("hERG")
    dil = tox.get("DILI")
    ames = tox.get("Ames")
    max_esk = max(esk_merged.values()) if esk_merged else None
    antif = antifungal(mol)

    def card(lbl, val, style):
        st.markdown(f'<div class="card card-{style}"><b>{lbl}:</b> {val}</div>', unsafe_allow_html=True)

    def risk_card(lbl, value, high_text, low_text):
        if value is None:
            card(lbl, "не рассчитано", "gray")
        elif value > 0.5:
            card(lbl, f"{high_text} ({value:.3f})", "red")
        else:
            card(lbl, f"{low_text} ({value:.3f})", "green")

    if max_esk is None:
        card("Антибактериальная активность", "не рассчитано", "gray")
    elif max_esk >= 0.5:
        card("Антибактериальная активность", f"ВЕРОЯТНА ({max_esk:.3f})", "blue")
    else:
        card("Антибактериальная активность", f"НЕ ВЕРОЯТНА ({max_esk:.3f})", "gray")
    card("Антифунгальные алерты", "ЕСТЬ" if antif else "не найдены", "yellow" if antif else "gray")
    risk_card("Кардиориск (hERG)", herg, "ВЫСОКИЙ", "НИЗКИЙ")
    risk_card("Гепатотоксичность", dil, "ВЫСОКАЯ", "НИЗКАЯ")
    risk_card("Мутагенность (Ames)", ames, "ВЕРОЯТНА", "НЕ ВЕРОЯТНА")
with c3:
    st.markdown("#### Свойства")
    st.dataframe(
        pd.DataFrame({"Значение": [str(v) for v in desc.values()]}, index=list(desc.keys())),
        use_container_width=True,
        height=250,
    )

c4, c5, c6 = st.columns([1, 1.4, 1.4])
with c4:
    st.markdown("#### LD50")
    ld50_log = tox.get("LD50")
    if ld50_log is not None:
        ld50 = ld50_mgkg(ld50_log, desc["MW"])
        col = color_for(ld50)
        st.markdown(
            f'<div class="card card-{col}" style="text-align:center">'
            f'<div class="big">{ld50:.0f}</div><div>мг/кг (крыса, oral)</div>'
            f'<div style="font-weight:700;margin-top:8px">GHS {ghs_class(ld50)}</div></div>',
            unsafe_allow_html=True,
        )
        if calc_ip:
            st.markdown(f"**Оценка i.p.: {ld50 * 0.33:.0f} мг/кг**")
    elif "error" in tox:
        st.error(tox["error"])
    if ref_oral > 0:
        st.markdown(f"Справочное oral: **{ref_oral:.0f} мг/кг**")
    if ref_ip > 0:
        st.markdown(f"Справочное i.p.: **{ref_ip:.0f} мг/кг**")
with c5:
    st.markdown("#### Токсичность")
    pk = [k for k in tox if k != "LD50" and k != "error"]
    if pk:
        vals = [tox[k] for k in pk]
        fig = go.Figure(go.Bar(
            x=vals, y=pk, orientation="h",
            marker_color=["#d62728" if v > 0.5 else "#2ca02c" for v in vals],
            text=[f"{v:.3f}" for v in vals], textposition="auto",
        ))
        fig.update_layout(
            xaxis_range=[0, 1], height=230,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
with c6:
    st.markdown("#### Антибактериальная (ESKAPE)")
    if esk_merged:
        paths = sorted(esk_merged, key=lambda p: esk_merged[p])
        vals = [esk_merged[p] for p in paths]
        fig = go.Figure(go.Bar(
            x=vals, y=paths, orientation="h",
            marker_color=["#1976d2" if v > 0.5 else "#9e9e9e" for v in vals],
            text=[f"{v:.3f}" for v in vals], textposition="auto",
        ))
        fig.update_layout(
            xaxis_range=[0, 1], height=230,
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
        if esk_err:
            st.warning(f"Частичный результат ESKAPE: {esk_err}")
    elif esk_err:
        st.error(f"Ошибка ESKAPE: {esk_err}")
    else:
        st.info("Нажмите 'Рассчитать всё'")

if antif:
    st.markdown("#### Структурные алерты (не прогноз)")
    for a in antif:
        st.warning(a)

st.caption(
    "Расчёт in silico, не заменяет эксперимент. Для молекул, непохожих на обучающие выборки, "
    "результаты менее надёжны. Значения LD50 — оценка порядка величины."
)
