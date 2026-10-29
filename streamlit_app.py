import base64, json, subprocess, sys, os
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from rdkit import Chem
from rdkit.Chem import Descriptors, Lipinski, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D

WORKDIR = Path(__file__).resolve().parent
ESKAPE_DIR = WORKDIR / "eskape_output"
DB_PATH = WORKDIR / "db"
ESKAPE_DIR.mkdir(exist_ok=True)

st.set_page_config(page_title="ChemTox Profiler", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 1.5rem;}
.card { padding: 14px; border-radius: 10px; margin-bottom: 8px; }
.card-green { background: rgba(46, 125, 50, 0.15); border-left: 5px solid #2e7d32; }
.card-red { background: rgba(198, 40, 40, 0.15); border-left: 5px solid #c62828; }
.card-yellow { background: rgba(249, 168, 37, 0.15); border-left: 5px solid #f9a825; }
.card-gray { background: rgba(97, 97, 97, 0.15); border-left: 5px solid #616161; }
.big { font-size: 42px; font-weight: 700; line-height: 1; }
</style>
""", unsafe_allow_html=True)

# Перевод LD50 из log(mol/kg) в мг/кг
def ld50_mgkg(log_molkg, mw): 
    return (10 ** (-log_molkg)) * mw * 1000

# Определение класса опасности GHS
def ghs_class(mg):
    if mg is None: return "—"
    if mg < 5: return "1 — смертельно"
    if mg < 50: return "2 — смертельно"
    if mg < 300: return "3 — токсично"
    if mg < 2000: return "4 — вредно"
    if mg < 5000: return "5 — малоопасно"
    return "> 5000 — нетоксично"

# Определение цвета карточки по уровню токсичности
def color_for(mg):
    if mg is None: return "gray"
    if mg < 300: return "red"
    if mg < 2000: return "yellow"
    return "green"

# Генерация SVG-изображения молекулы
def mol_svg(mol, w=340, h=340):
    d = rdMolDraw2D.MolDraw2DSVG(w, h)
    rdMolDraw2D.PrepareAndDrawMolecule(d, mol)
    d.FinishDrawing()
    b64 = base64.b64encode(d.GetDrawingText().encode()).decode()
    return f'<div style="background:#fff;padding:10px;border-radius:10px;text-align:center"><img src="data:image/svg+xml;base64,{b64}" width="{w}"/></div>'

# Прогноз токсичности через ADMET-AI
def run_admet(smiles):
    try:
        from admet_ai import ADMETModel
        p = ADMETModel().predict(smiles=smiles)
        keys = {"hERG": "hERG", "DILI": "DILI", "Ames": "AMES", "LD50": "LD50_Zhu"}
        out = {}
        for l, k in keys.items():
            if isinstance(p, dict) and k in p: out[l] = float(p[k])
        return out
    except Exception as e: 
        return {"error": str(e)}

# Прогноз антибактериальной активности (Random Forest)
def run_eskape(smiles):
    csv_in = ESKAPE_DIR / "input.csv"
    pd.DataFrame({"smiles": [smiles]}).to_csv(csv_in, index=False)
    
    for f in ESKAPE_DIR.glob("*"):
        if f.name != "input.csv":
            try: f.unlink()
            except: pass

    pathogens = ["AB", "BW", "DKO", "EF", "KP", "PA", "SA"]
    results = {"rf": {}}
    db_dir = WORKDIR / "db" / "models" / "all"
    sklearn_exe = str(WORKDIR / "python" / "Scripts" / "sklearn_predict.exe")

    for p in pathogens:
        preds_path = ESKAPE_DIR / f"{p}_rf.csv"
        model_dir = db_dir / f"{p}_rf"
        try:
            subprocess.run(
                [sklearn_exe, "--test_path", str(csv_in), "--checkpoint_dir", str(model_dir), "--preds_path", str(preds_path)],
                capture_output=True, text=True, timeout=300
            )
            if preds_path.exists():
                df = pd.read_csv(preds_path)
                if not df.empty:
                    results["rf"][p] = float(df.iloc[0]["activity"])
        except Exception:
            pass

    return {"input.csv": {smiles: results}}, None

# Поиск противогрибковых SMARTS-паттернов
def antifungal(mol):
    out = []
    if mol.HasSubstructMatch(Chem.MolFromSmarts("n1cncc1")): out.append("Азольное кольцо")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("C=C-C=C-C=C")): out.append("Полиеновая система")
    if mol.HasSubstructMatch(Chem.MolFromSmarts("c[Cl,Br,F]")): out.append("Галоген-ароматика")
    return out

with st.sidebar:
    st.header("Ввод")
    smiles_in = st.text_area("SMILES", "CN(C)CCCN(CCCN(C)C)C(=O)C(Cc1ccccc1)NC(=O)C12CC3CC(CC(C3)C1)C2", height=90)
    with st.expander("Справочные LD50 (вручную)"):
        ref_oral = st.number_input("Перорально, мг/кг", min_value=0.0, value=0.0)
        ref_ip = st.number_input("i.p., мг/кг", min_value=0.0, value=0.0)
        calc_ip = st.checkbox("Рассчитать i.p. из oral (x0.33)", value=True)
    
    calc_btn = st.button("Рассчитать всё", type="primary", use_container_width=True)

if not smiles_in or not smiles_in.strip():
    st.info("Введите SMILES слева."); st.stop()
mol = Chem.MolFromSmiles(smiles_in.strip())
if mol is None:
    st.error("Неверный SMILES."); st.stop()

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
                    if v not in ("", None): esk_merged.setdefault(p, []).append(float(v))
    esk_merged = {p: sum(vs)/len(vs) for p, vs in esk_merged.items()}

desc = {"MW": round(Descriptors.MolWt(mol), 1), "LogP": round(Descriptors.MolLogP(mol), 2), "TPSA": round(Descriptors.TPSA(mol), 1), "H-доноры": Lipinski.NumHDonors(mol), "H-акцепторы": Lipinski.NumHAcceptors(mol)}
st.title("Профиль молекулы")
st.caption(f"SMILES: `{smiles}` · Формула: **{rdMolDescriptors.CalcMolFormula(mol)}**")

c1, c2, c3 = st.columns([1, 1.1, 1.4])
with c1:
    st.markdown("#### Структура"); st.markdown(mol_svg(mol), unsafe_allow_html=True)
with c2:
    st.markdown("#### Вердикт")
    herg, dil = tox.get("hERG", 0), tox.get("DILI", 0)
    max_esk = max(esk_merged.values()) if esk_merged else 0
    antif = antifungal(mol)
    def card(lbl, val, style): st.markdown(f'<div class="card card-{style}"><b>{lbl}:</b> {val}</div>', unsafe_allow_html=True)
    card("Антибактериальная", "ДА" if max_esk >= 0.5 else "НЕТ", "red" if max_esk >= 0.5 else "green")
    card("Антифунгальная", "МОЖЕТ БЫТЬ" if antif else "НЕТ", "yellow" if antif else "green")
    card("Кардиориск (hERG)", f"{'ВЫСОКИЙ' if herg > 0.5 else 'НИЗКИЙ'} ({herg:.3f})", "red" if herg > 0.5 else "green")
    card("Гепатотоксичность", f"{'ВЫСОКАЯ' if dil > 0.5 else 'НИЗКАЯ'} ({dil:.3f})", "red" if dil > 0.5 else "green")
with c3:
    st.markdown("#### Свойства")
    st.dataframe(pd.DataFrame({"Значение": [str(v) for v in desc.values()]}, index=list(desc.keys())), use_container_width=True, height=250)

c4, c5, c6 = st.columns([1, 1.4, 1.4])
with c4:
    st.markdown("#### LD50")
    ld50_log = tox.get("LD50")
    if ld50_log:
        ld50 = ld50_mgkg(ld50_log, desc["MW"])
        col = color_for(ld50)
        st.markdown(f'<div class="card card-{col}" style="text-align:center"><div class="big">{ld50:.0f}</div><div>мг/кг (oral)</div><div style="font-weight:700;margin-top:8px">GHS {ghs_class(ld50)}</div></div>', unsafe_allow_html=True)
        if calc_ip: st.markdown(f"**Оценка i.p.: {ld50*0.33:.0f} мг/кг**")
    elif "error" in tox:
        st.error(tox["error"])
with c5:
    st.markdown("#### Токсичность")
    pk = [k for k in tox if k != "LD50" and k != "error"]
    if pk:
        vals = [tox[k] for k in pk]
        fig = go.Figure(go.Bar(x=vals, y=pk, orientation="h", marker_color=["#d62728" if v > 0.5 else "#2ca02c" for v in vals], text=[f"{v:.3f}" for v in vals], textposition="auto"))
        fig.update_layout(xaxis_range=[0, 1], height=230, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
with c6:
    st.markdown("#### Антибактериальная (ESKAPE)")
    if esk_merged:
        paths = sorted(esk_merged, key=lambda p: esk_merged[p])
        vals = [esk_merged[p] for p in paths]
        fig = go.Figure(go.Bar(x=vals, y=paths, orientation="h", marker_color=["#d62728" if v > 0.5 else "#2ca02c" for v in vals], text=[f"{v:.3f}" for v in vals], textposition="auto"))
        fig.update_layout(xaxis_range=[0, 1], height=230, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    elif esk_err:
        st.error(f"Ошибка ESKAPE: {esk_err}")
    else:
        st.info("Нажмите 'Рассчитать всё'")

if antif:
    st.markdown("#### Противогрибковые мотивы")
    for a in antif: st.warning(a)