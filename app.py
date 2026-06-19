import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import re, io
from datetime import datetime

st.set_page_config(
    page_title="Connect | KPI Carteras",
    page_icon="🔶",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Prompt',sans-serif !important;}
.hdr{background:linear-gradient(135deg,#001d3d 0%,#0a3060 100%);border-radius:12px;
     padding:16px 24px;margin-bottom:1rem;display:flex;align-items:center;gap:14px;}
.hdr-logo{background:#f15b2b;width:44px;height:44px;border-radius:9px;
          display:flex;align-items:center;justify-content:center;font-size:22px;flex-shrink:0;}
.hdr h1{color:#fff;font-size:1.4rem;font-weight:700;margin:0;}
.hdr p{color:rgba(255,255,255,0.6);font-size:0.82rem;margin:2px 0 0;}
.sec{font-size:1.05rem;font-weight:700;color:#001d3d;border-left:5px solid #f15b2b;
     padding:4px 0 4px 12px;margin:1.8rem 0 0.7rem;
     background:linear-gradient(90deg,#f0f4f8 0%,transparent 100%);}
.box-ok{background:#e8f5e9;border-radius:8px;padding:9px 13px;font-size:0.84rem;
        color:#1b5e20;margin:.35rem 0;border-left:4px solid #43a047;}
.box-warn{background:#fff8e1;border-radius:8px;padding:9px 13px;font-size:0.84rem;
          color:#6d4c00;margin:.35rem 0;border-left:4px solid #f15b2b;}
.box-danger{background:#fdecea;border-radius:8px;padding:9px 13px;font-size:0.84rem;
            color:#7f1d1d;margin:.35rem 0;border-left:4px solid #e53935;}
.box-info{background:#eef4fb;border-radius:8px;padding:9px 13px;font-size:0.84rem;
          color:#1a3a5c;margin:.35rem 0;border-left:4px solid #0d7377;}
.ai-box{background:linear-gradient(135deg,#001d3d,#0a3060);border-radius:12px;
        padding:20px 24px;color:#fff;margin-top:1rem;}
.ai-box h3{color:#f15b2b;margin-bottom:8px;font-size:1rem;}
.ai-box p{font-size:0.86rem;line-height:1.6;opacity:.92;margin:4px 0;}
div[data-testid="metric-container"]{background:#f8f9fa;border-radius:8px;
    padding:10px 14px;border:1px solid #e0e0e0;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hdr">
  <div class="hdr-logo">🔶</div>
  <div>
    <h1>Herramienta de Análisis de Carteras · Ingresos · Costos · KPI</h1>
    <p>Connect Assistance México · Actual vs Budget · Loss Ratio · Markowitz</p>
  </div>
</div>
""", unsafe_allow_html=True)

PAL = px.colors.qualitative.D3 + px.colors.qualitative.Plotly

# ── Exclusiones ───────────────────────────────────────────
EXCLUIR_CONTIENE = ['siniestro','on demand','employees','fleet services','connect assistance mexico']
EXCLUIR_EXACTO  = {'connect mx - on demand','employees mx','spee dee - fleet services','connect assistance mexico'}

def _es_cartera_valida(nombre):
    n = nombre.strip(); nl = n.lower()
    if not nl or nl.startswith('total'): return False
    if nl in EXCLUIR_EXACTO: return False
    if any(ex in nl for ex in EXCLUIR_CONTIENE): return False
    if nl in ('num clientes','no. servicios','revenue - services',
              'revenue - sales','service frequency'): return False
    return True

# ── Secciones KPI ─────────────────────────────────────────
SECCIONES = [
    ('clientes',   r'kpis\s*-\s*number of clients'),
    ('servicios',  r'kpis\s*-\s*service count (all|external)'),
    ('frecuencia', r'^service frequency$'),
    ('revenue',    r'^revenue\s*-\s*sales'),
    ('costo_svc',  r'^service costs?\s+external$'),
    ('avg_costo',  r'^average service cost'),
    ('gp_risk',    r'^gross profit at risk'),
    ('gp_fee',     r'^gross profit fee for service'),
    ('loss_ratio', r'^loss ratio\s*%'),
]
SKIP_RE = re.compile(r'^(cost of (revenue|sales)|revenue\s*-\s*services?$|total\b)', re.I)

def _clasificar_seccion(texto):
    t = texto.lower().strip()
    for nombre, pat in SECCIONES:
        if re.search(pat, t): return nombre
    return None

def _to_float(val):
    try:
        s = str(val).strip().replace(',','').replace('%','')
        if s in ('','nan','None','-',' '): return None
        return float(s)
    except: return None

def _detectar_columnas(fila_vals):
    """
    Detecta posición de cada campo en la fila de encabezados de columnas.
    Maneja las 5 variantes encontradas en los 24 archivos reales.
    """
    cols = {}
    vals = [str(v).strip() if v else '' for v in fila_vals]

    # 1. Encontrar las dos posiciones de "Actual" (mes y YTD)
    actual_pos = [i for i, v in enumerate(vals) if v.lower() == 'actual']
    if len(actual_pos) >= 1: cols['actual'] = actual_pos[0]
    if len(actual_pos) >= 2: cols['ytd_actual'] = actual_pos[1]

    # 2. Zona YTD: los 3 campos no-vacíos tras ytd_actual
    if 'ytd_actual' in cols:
        ytd_start = cols['ytd_actual'] + 1
        ytd_fields = [(i, v) for i, v in enumerate(vals[ytd_start:], ytd_start) if v]
        for j, (i, v) in enumerate(ytd_fields[:3]):
            cols[['ytd_budget','ytd_bud_diff','ytd_bud_pct'][j]] = i

    # 3. Zona MES: columnas entre actual y ytd_actual (o fin)
    mes_start = cols.get('actual', 1) + 1
    mes_end   = cols.get('ytd_actual', len(vals))
    mes_fields = [(i, vals[i]) for i in range(mes_start, mes_end) if vals[i]]

    for i, v in mes_fields:
        vl = v.lower()
        is_fc  = 'forecast' in vl or v.upper().startswith('FORECAST')
        is_bud = 'budget' in vl or 'connectmx_t2' in vl or 'ppto' in vl
        is_dif = 'diff' in vl
        is_pct = 'var' in vl or '%' in vl

        if is_fc and not is_dif and not is_pct:
            cols.setdefault('forecast', i)
        elif is_fc and is_dif:
            cols.setdefault('fc_diff', i)
        elif is_fc and is_pct:
            cols.setdefault('fc_pct', i)
        elif is_bud and not is_dif and not is_pct:
            cols.setdefault('budget', i)
        elif is_dif:
            cols.setdefault('bud_diff', i)
        elif is_pct:
            cols.setdefault('bud_pct', i)

    # 4. TIPO D especial: forecast + múltiples "budget" sin diff/pct en nombre
    #    → el 2do budget en mes es BudDiff, el 3ro es Bud%Var
    if 'forecast' in cols:
        budget_mes = [(i, v) for i, v in mes_fields
                     if ('connectmx_t2' in v.lower() or 'budget' in v.lower())
                     and 'diff' not in v.lower() and 'var' not in v.lower() and '%' not in v.lower()]
        if len(budget_mes) >= 2 and 'bud_diff' not in cols:
            cols.pop('budget', None)
            if len(budget_mes) >= 1: cols['bud_diff'] = budget_mes[0][0]
            if len(budget_mes) >= 2: cols['bud_pct']  = budget_mes[1][0]

    cols.setdefault('actual', 1)
    return cols

def _parse_fecha(nombre, df_raw):
    for _, row in df_raw.head(10).iterrows():
        for cell in row:
            s = str(cell) if pd.notna(cell) else ''
            m = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', s)
            if m:
                try: return datetime.strptime(m.group(1), '%m/%d/%Y')
                except: pass
            m = re.search(
                r'(January|February|March|April|May|June|July|August|'
                r'September|October|November|December)\s+\d{1,2},?\s+\d{4}', s, re.I)
            if m:
                try: return datetime.strptime(re.sub(r',','', m.group(0)).strip(), '%B %d %Y')
                except: pass
            if isinstance(cell, pd.Timestamp): return cell.to_pydatetime()
    base = re.sub(r'[^0-9]','', nombre)[:4]
    if len(base) == 4:
        try:
            mes = int(base[:2]); anio = int(base[2:])
            if 1 <= mes <= 12 and 24 <= anio <= 35:
                return datetime(2000+anio, mes, 1)
        except: pass
    return None

def _extraer_datos(df_raw):
    resultado = {}; seccion_actual = None; col_map = {}
    seen_costo = False; seen_avg = False

    for idx, row in df_raw.iterrows():
        c0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        if not c0: continue
        c0l = c0.lower().strip()
        if c0l.startswith('total'): continue
        if SKIP_RE.match(c0l): continue

        # Detectar fila de encabezados de columnas (siempre fila con c0=' ')
        row_str = [str(v).strip() if pd.notna(v) else '' for v in row.values]
        row_joined = ' '.join(row_str).lower()
        if (c0l in ('', ' ') and
            'actual' in row_joined and
            ('budget' in row_joined or 'forecast' in row_joined)):
            col_map = _detectar_columnas(row_str)
            continue

        # Ignorar filas de periodo/fecha
        if c0l in (' ','month ending','year to date'): continue
        if re.match(r'^\d{2}/\d{2}/\d{4}$', c0l): continue

        # ¿Es encabezado de sección?
        c1 = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ''
        try: float(c1.replace(',','')); es_dato = True
        except: es_dato = False

        if not es_dato and len(c0) > 3:
            sec = _clasificar_seccion(c0)
            if sec is not None:
                if sec == 'costo_svc':
                    if seen_costo: seccion_actual = '__skip__'; continue
                    seen_costo = True
                if sec == 'avg_costo':
                    if seen_avg: seccion_actual = '__skip__'; continue
                    seen_avg = True
                seccion_actual = sec
                resultado.setdefault(sec, {})
                continue
            else:
                seccion_actual = '__skip__'
                continue

        if seccion_actual is None or seccion_actual == '__skip__': continue
        if not _es_cartera_valida(c0): continue

        # Extraer valores
        datos = {}
        if col_map:
            for campo, idx_col in col_map.items():
                if isinstance(idx_col, bool): continue  # flags
                if idx_col < len(row):
                    v = _to_float(row.iloc[idx_col])
                    if v is not None: datos[campo] = v
        else:
            v = _to_float(row.iloc[1]) if len(row) > 1 else None
            if v is not None: datos['actual'] = v

        if datos and c0 not in resultado.get(seccion_actual, {}):
            resultado[seccion_actual][c0] = datos

    return resultado


@st.cache_data(show_spinner="📂 Procesando archivos Sage Intacct...", ttl=None)
def procesar_archivos(bytes_tuple, nombres_tuple):
    records, errores = [], []

    for fbytes, fname in zip(bytes_tuple, nombres_tuple):
        try:
            df_raw = pd.read_excel(io.BytesIO(fbytes), header=None)
            fecha = _parse_fecha(fname, df_raw)
            if not fecha:
                errores.append(f"⚠️ {fname}: no se detectó fecha"); continue

            mes_label   = fecha.strftime('%Y-%m')
            mes_display = fecha.strftime('%b-%Y')
            ext = _extraer_datos(df_raw)

            todas = set()
            for sec_data in ext.values(): todas.update(sec_data.keys())

            n = 0
            for cart in todas:
                def g(sec, campo='actual'):
                    d = ext.get(sec, {}).get(cart, {})
                    return d.get(campo) if isinstance(d, dict) else None

                rev = g('revenue','actual')
                if not rev or rev <= 0: continue

                # Para budget_pct: usar mes si disponible, sino ytd_bud_pct
                def bpct(sec):
                    v = g(sec,'bud_pct')
                    return v if v is not None else g(sec,'ytd_bud_pct')

                # Para budget absoluto: usar mes si disponible, sino ytd
                def babs(sec):
                    v = g(sec,'budget')
                    return v if v is not None else g(sec,'ytd_budget')

                records.append({
                    'Mes': mes_label, 'Mes_Display': mes_display, 'Cartera': cart,
                    'Revenue':    rev,
                    'Clientes':   g('clientes','actual'),
                    'Servicios':  g('servicios','actual'),
                    'Frecuencia': g('frecuencia','actual'),
                    'Costo_Svc':  g('costo_svc','actual'),
                    'Avg_Costo':  g('avg_costo','actual'),
                    'GP_Risk':    g('gp_risk','actual'),
                    'GP_Fee':     g('gp_fee','actual'),
                    'Loss_Ratio': g('loss_ratio','actual'),
                    # Budget
                    'Rev_Bud':      babs('revenue'),
                    'Rev_Bud_Pct':  bpct('revenue'),
                    'Rev_Bud_Diff': g('revenue','bud_diff'),
                    'LR_Bud':       babs('loss_ratio'),
                    'LR_Bud_Pct':   bpct('loss_ratio'),
                    'Cl_Bud':       babs('clientes'),
                    'Cl_Bud_Pct':   bpct('clientes'),
                    'GP_Bud':       babs('gp_risk'),
                    'GP_Bud_Pct':   bpct('gp_risk'),
                    'Avg_Bud':      babs('avg_costo'),
                    'Avg_Bud_Pct':  bpct('avg_costo'),
                    'Fee_Bud':      babs('gp_fee'),
                    'Fee_Bud_Pct':  bpct('gp_fee'),
                    # YTD
                    'Rev_YTD': g('revenue','ytd_actual'),
                    'LR_YTD':  g('loss_ratio','ytd_actual'),
                    'Cl_YTD':  g('clientes','ytd_actual'),
                    # Derivados
                    'Rev_x_Cl': rev / g('clientes','actual')
                                if g('clientes','actual') and g('clientes','actual') > 0 else None,
                    'GP_x_Cl':  g('gp_risk','actual') / g('clientes','actual')
                                if g('gp_risk','actual') and g('clientes','actual') and
                                   g('clientes','actual') > 0 else None,
                })
                n += 1

            if n == 0:
                errores.append(f"⚠️ {fname} ({mes_display}): sin carteras con revenue > 0")

        except Exception as e:
            errores.append(f"❌ {fname}: {type(e).__name__}: {e}")

    if not records:
        return None, errores, "No se extrajeron datos. " + (" | ".join(errores) if errores else "")

    df = pd.DataFrame(records).sort_values(['Cartera','Mes']).reset_index(drop=True)
    return df, errores, None


@st.cache_data(show_spinner="🎲 Simulación Monte Carlo...")
def monte_carlo(mu_t, cov_flat, n_prov, n_sim, carteras_t):
    mu  = np.array(mu_t)
    cov = np.array(cov_flat).reshape(n_prov, n_prov)
    np.random.seed(42)
    res = np.zeros((n_sim, 3 + n_prov))
    for i in range(n_sim):
        w = np.random.random(n_prov); w /= w.sum()
        r = float(np.dot(w, mu)); s = float(np.sqrt(w @ cov @ w))
        res[i] = [r, s, r/s if s > 0 else 0] + list(w)
    df_s = pd.DataFrame(res, columns=['Rent','Risk','Sharpe'] + list(carteras_t))
    return df_s, df_s.loc[df_s['Sharpe'].idxmax()], df_s.loc[df_s['Risk'].idxmin()]

# ── SIDEBAR ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuración")
    archivos = st.file_uploader(
        "📂 Archivos KPI Sage (.xlsx)",
        type=["xlsx"], accept_multiple_files=True,
        help="Un archivo por mes. Hasta 24 meses. Nombre: MMAA__KPI.xlsx"
    )
    st.markdown("---")
    lr_umbral    = st.slider("📉 Umbral Loss Ratio (%)", 40, 95, 65, 5) / 100
    freq_alerta  = st.slider("⚡ Alerta frecuencia (‰)", 5, 30, 12, 1) / 1000
    umbral_conc  = st.slider("⚠️ Concentración máx. (%)", 10, 40, 25, 5)
    n_sim        = st.select_slider("🎲 Simulaciones Markowitz", [1000,3000,5000,10000], 5000)
    min_meses_mk = st.slider("📅 Meses mínimos Markowitz", 3, 18, 6, 1)
    st.markdown("---")
    if st.button("🔄 Limpiar caché"):
        procesar_archivos.clear(); monte_carlo.clear(); st.rerun()
    st.caption("Connect Assistance México\nHerramienta KPI Carteras")

# ── PANTALLA INICIAL ──────────────────────────────────────
if not archivos:
    st.info("👈 Carga los archivos KPI mensuales de Sage Intacct para comenzar.")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("""
**¿Qué archivos subir?**
- Reportes KPI de Sage Intacct (.xlsx)
- Un archivo por mes · hasta 24 meses
- Nombre: `MMAA__KPI.xlsx` (ej: `0326__KPI.xlsx` = Marzo 2026)
        """)
    with c2:
        st.markdown("""
**Módulos:**
- 📊 Resumen Ejecutivo · scorecard con semáforo
- 👥 Clientes & Volumen · crecimiento, heatmap, frecuencia
- 💰 Revenue · vs budget, concentración, tendencia
- ⚙️ Costo & Eficiencia · avg cost + GP At Risk
- 📉 Rentabilidad · Loss Ratio + Fee for Service + señales
- 📈 Markowitz · frontera eficiente del portafolio
        """)
    st.stop()

# ── PROCESAR ──────────────────────────────────────────────
fb = [f.read() for f in archivos]
fn = [f.name  for f in archivos]
df, errores, error_fatal = procesar_archivos(tuple(fb), tuple(fn))

if errores:
    with st.expander(f"⚠️ {len(errores)} advertencia(s)", expanded=bool(error_fatal)):
        for e in errores: st.write(e)
if error_fatal:
    st.error(f"❌ {error_fatal}"); st.stop()

carteras  = sorted(df['Cartera'].unique())
meses_ord = sorted(df['Mes'].unique())
n_meses   = len(meses_ord)
mes_disp  = df.groupby('Mes')['Mes_Display'].first().to_dict()
xticks    = [mes_disp.get(m, m) for m in meses_ord]
ultimo    = meses_ord[-1]
df_ult    = df[df['Mes'] == ultimo]
tiene_bud = df['Rev_Bud'].notna().any()

st.success(
    f"✅ **{len(archivos)} archivo(s)** · **{len(carteras)} carteras** · "
    f"**{n_meses} período(s)** · "
    f"{mes_disp.get(meses_ord[0],'?')} → {mes_disp.get(ultimo,'?')}"
    + (" · 📊 con Budget" if tiene_bud else "")
)

def pvt(col):
    p = df.pivot_table(index='Mes', columns='Cartera', values=col, aggfunc='mean')
    return p.reindex(meses_ord)

rev_pvt  = pvt('Revenue');    bud_pvt  = pvt('Rev_Bud')
cl_pvt   = pvt('Clientes');   svc_pvt  = pvt('Servicios')
freq_pvt = pvt('Frecuencia'); avg_pvt  = pvt('Avg_Costo')
lr_pvt   = pvt('Loss_Ratio'); lr_b_pvt = pvt('LR_Bud')
gp_pvt   = pvt('GP_Risk');    fee_pvt  = pvt('GP_Fee')
rpc_pvt  = pvt('Rev_x_Cl')

rev_prom      = rev_pvt.mean()
rev_total_avg = rev_prom.sum()
participacion = rev_prom / rev_total_avg * 100

def sem(pct, invertido=False):
    if pct is None or (isinstance(pct, float) and np.isnan(pct)): return "⚪"
    malo  = pct > 5  if invertido else pct < -5
    bueno = pct < -5 if invertido else pct > 5
    return "🟢" if bueno else ("🔴" if malo else "🟡")

LAYOUT = dict(
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    font=dict(family='Prompt, sans-serif', color='#001d3d')
)

# ── NAVEGACIÓN ────────────────────────────────────────────
modulo = st.radio("",
    ["📊 Resumen Ejecutivo","👥 Clientes & Volumen","💰 Revenue",
     "⚙️ Costo & Eficiencia","📉 Rentabilidad","📈 Markowitz"],
    horizontal=True, label_visibility="collapsed")
st.markdown("---")

# ══════════════════════════════════════════════════════════
# M0 — RESUMEN EJECUTIVO
# ══════════════════════════════════════════════════════════
if modulo == "📊 Resumen Ejecutivo":
    mes_nombre = mes_disp.get(ultimo, ultimo)
    st.markdown(f'<div class="sec">Scorecard del Portafolio · {mes_nombre}</div>', unsafe_allow_html=True)

    kpis = [
        ('Revenue',    'Rev_Bud_Pct',  '💰 Revenue Total',      '${:,.0f}', False),
        ('Clientes',   'Cl_Bud_Pct',   '👥 Clientes',           '{:,.0f}',  False),
        ('Loss_Ratio', 'LR_Bud_Pct',   '📉 Loss Ratio Prom.',   '{:.1%}',   True),
        ('GP_Risk',    'GP_Bud_Pct',   '📊 GP At Risk',         '${:,.0f}', False),
        ('GP_Fee',     'Fee_Bud_Pct',  '💹 GP Fee for Service', '${:,.0f}', False),
        ('Avg_Costo',  'Avg_Bud_Pct',  '⚙️ Costo Prom. Svc',   '${:,.2f}', True),
    ]
    cols = st.columns(3)
    for i, (ca, cp, lbl, fmt, inv) in enumerate(kpis):
        act = df_ult[ca].mean() if ca in df_ult.columns else None
        pct = df_ult[cp].mean() if cp in df_ult.columns else None
        if act is None or (isinstance(act,float) and np.isnan(act)): continue
        s = sem(pct, inv)
        delta = f"{pct:+.1f}% vs Ppto" if pct is not None and not np.isnan(pct) else None
        with cols[i % 3]:
            st.metric(f"{s} {lbl}", fmt.format(act), delta)

    st.markdown('<div class="sec">Semáforo por Cartera · vs Presupuesto</div>', unsafe_allow_html=True)
    rows = []
    for c in carteras:
        sub = df_ult[df_ult['Cartera'] == c]
        if sub.empty: continue
        rv = sub['Revenue'].mean();    rvp = sub['Rev_Bud_Pct'].mean()
        lr = sub['Loss_Ratio'].mean(); lrp = sub['LR_Bud_Pct'].mean()
        cl = sub['Clientes'].mean();   clp = sub['Cl_Bud_Pct'].mean()
        gp = sub['GP_Risk'].mean();    gpp = sub['GP_Bud_Pct'].mean()
        n_m = df[df['Cartera'] == c]['Mes'].nunique()
        rows.append({
            'Cartera': ("🆕 " if n_m < 12 else "") + c,
            'Revenue': f"${rv:,.0f}"  if pd.notna(rv) else "—",
            'Rev 🚦': sem(rvp, False),
            'LR': f"{lr:.1%}"         if pd.notna(lr) else "—",
            'LR 🚦': sem(lrp, True),
            'Clientes': f"{cl:,.0f}"  if pd.notna(cl) else "—",
            'Cl 🚦': sem(clp, False),
            'GP Risk': f"${gp:,.0f}"  if pd.notna(gp) else "—",
            'GP 🚦': sem(gpp, False),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown('<div class="sec">Concentración de Revenue</div>', unsafe_allow_html=True)
    ps = participacion.sort_values(ascending=False)
    c1, c2 = st.columns([1.2, 1])
    with c1:
        df_c = pd.DataFrame({
            'Cartera': ps.index,
            'Revenue Prom.': rev_prom[ps.index].round(0),
            'Part. %': ps.values.round(1)
        }).reset_index(drop=True)
        def hl(v): return "background:#fdecea;font-weight:bold" if isinstance(v,float) and v>umbral_conc else ""
        st.dataframe(df_c.style.map(hl, subset=['Part. %'])
            .format({'Revenue Prom.':'${:,.0f}','Part. %':'{:.1f}%'}),
            use_container_width=True, hide_index=True)
        en_r = participacion[participacion > umbral_conc]
        for c, p in en_r.items():
            st.markdown(f'<div class="box-warn">⚠️ <b>{c}</b>: {p:.1f}% supera umbral {umbral_conc}%</div>', unsafe_allow_html=True)
        if en_r.empty:
            st.markdown(f'<div class="box-ok">✅ Ninguna cartera supera el umbral de {umbral_conc}%</div>', unsafe_allow_html=True)
    with c2:
        colors = ["#e53935" if participacion[c] > umbral_conc else "#001d3d" for c in ps.index]
        fig = go.Figure(go.Pie(labels=ps.index, values=ps.values, hole=0.45,
            textinfo="label+percent", marker=dict(colors=colors)))
        fig.update_layout(title="Revenue promedio por cartera", height=320,
            showlegend=False, margin=dict(t=35,b=5,l=5,r=5), **LAYOUT)
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════
# M1 — CLIENTES & VOLUMEN
# ══════════════════════════════════════════════════════════
elif modulo == "👥 Clientes & Volumen":
    st.markdown('<div class="sec">Clientes Activos por Cartera</div>', unsafe_allow_html=True)
    fig_cl = go.Figure()
    for i, c in enumerate(carteras):
        if c not in cl_pvt.columns or cl_pvt[c].notna().sum() < 2: continue
        s = cl_pvt[c].dropna()
        fig_cl.add_trace(go.Scatter(
            x=[mes_disp.get(m,m) for m in s.index], y=s.values,
            mode='lines+markers', name=c,
            line=dict(width=2,color=PAL[i%len(PAL)]), marker=dict(size=5),
            hovertemplate=f"<b>{c}</b><br>%{{x}}<br>{{y:,.0f}} clientes<extra></extra>"))
    fig_cl.update_layout(title="Evolución de Clientes (Actual)",
        xaxis_title="Mes", yaxis_title="Clientes", height=420,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified', legend=dict(orientation='h',y=-0.28), **LAYOUT)
    st.plotly_chart(fig_cl, use_container_width=True)

    crec = []
    for c in carteras:
        if c not in cl_pvt.columns: continue
        s = cl_pvt[c].dropna()
        if len(s) < 2: continue
        var_cl = (s.iloc[-1]-s.iloc[0])/s.iloc[0]*100
        fr_s = freq_pvt[c].dropna() if c in freq_pvt.columns else pd.Series(dtype=float)
        var_fr = (fr_s.iloc[-1]-fr_s.iloc[0])/fr_s.iloc[0]*100 if len(fr_s)>=2 else None
        alerta = "⚠️ Crece clientes, baja uso" if var_cl > 10 and var_fr is not None and var_fr < -10 else ""
        crec.append({'Cartera':c,'Clientes Inicio':s.iloc[0],'Clientes Fin':s.iloc[-1],
            'Var Cl %':var_cl,'Var Frec %':var_fr,'Meses':len(s),'Alerta':alerta})
    if crec:
        df_cr = pd.DataFrame(crec).sort_values('Var Cl %', ascending=False)
        def hl_cr(v):
            if isinstance(v,float):
                if v > 20: return "background:#e8f5e9"
                if v < -10: return "background:#fdecea"
            return ""
        st.dataframe(df_cr.style.map(hl_cr,subset=['Var Cl %'])
            .format({'Clientes Inicio':'{:,.0f}','Clientes Fin':'{:,.0f}',
                     'Var Cl %':'{:+.1f}%','Var Frec %':'{:+.1f}%'},na_rep="—"),
            use_container_width=True, hide_index=True)

    st.markdown('<div class="sec">Servicios y Temporalidad</div>', unsafe_allow_html=True)
    carts_s = [c for c in carteras if c in svc_pvt.columns and svc_pvt[c].notna().sum()>=2]
    if carts_s:
        mat = svc_pvt[carts_s].T
        fig_h = px.imshow(mat.values, x=xticks, y=carts_s,
            color_continuous_scale='RdYlGn_r', aspect='auto',
            title="Heatmap de Servicios (rojo = pico de demanda)")
        fig_h.update_layout(height=max(280,len(carts_s)*32+80), **LAYOUT)
        st.plotly_chart(fig_h, use_container_width=True)
        st.markdown('<div class="box-info">💡 Columnas en rojo en múltiples carteras = riesgo sistémico de costo ese mes.</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">Frecuencia de Uso</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="box-info">💡 Frecuencia = servicios / clientes. Alerta configurada en <b>{freq_alerta*1000:.0f}‰</b>.</div>', unsafe_allow_html=True)
    fig_fr = go.Figure()
    for i, c in enumerate(carteras):
        if c not in freq_pvt.columns or freq_pvt[c].notna().sum() < 2: continue
        s = freq_pvt[c].dropna()
        fig_fr.add_trace(go.Scatter(
            x=[mes_disp.get(m,m) for m in s.index], y=s.values*1000,
            mode='lines+markers', name=c,
            line=dict(width=2,color=PAL[i%len(PAL)]), marker=dict(size=5),
            hovertemplate=f"<b>{c}</b><br>%{{x}}<br>%{{y:.2f}}‰<extra></extra>"))
    fig_fr.add_hline(y=freq_alerta*1000, line_dash='dot', line_color='#f15b2b',
        annotation_text=f"Alerta {freq_alerta*1000:.0f}‰",
        annotation_font=dict(color='#f15b2b',size=10))
    fig_fr.update_layout(title="Frecuencia de Uso (‰ servicios/cliente)",
        xaxis_title="Mes", yaxis_title="‰", height=400,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified', legend=dict(orientation='h',y=-0.28), **LAYOUT)
    st.plotly_chart(fig_fr, use_container_width=True)

    fc = [c for c in carteras if c in freq_pvt.columns and freq_pvt[c].notna().sum()>=3]
    if len(fc) >= 2:
        corr = freq_pvt[fc].corr().round(2)
        fig_co = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r',
            zmin=-1, zmax=1, aspect='auto', title="Correlación de Frecuencia entre Carteras")
        fig_co.update_layout(height=380, **LAYOUT)
        st.plotly_chart(fig_co, use_container_width=True)
        st.markdown('<div class="box-info">💡 Alta correlación = picos de costo simultáneos. Baja = se compensan mutuamente.</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# M2 — REVENUE
# ══════════════════════════════════════════════════════════
elif modulo == "💰 Revenue":
    st.markdown('<div class="sec">Revenue por Cartera · Tendencia y vs Presupuesto</div>', unsafe_allow_html=True)
    fig_rv = go.Figure()
    for i, c in enumerate(carteras):
        if c not in rev_pvt.columns: continue
        fig_rv.add_trace(go.Bar(x=xticks, y=rev_pvt[c].values, name=c,
            marker_color=PAL[i%len(PAL)],
            hovertemplate=f"<b>{c}</b><br>%{{x}}<br>${{y:,.0f}}<extra></extra>"))
    fig_rv.update_layout(barmode='stack',
        title="Revenue Mensual Acumulado por Cartera (Actual)",
        xaxis_title="Mes", yaxis_title="USD", height=380,
        legend=dict(orientation='h',y=-0.28), **LAYOUT)
    st.plotly_chart(fig_rv, use_container_width=True)

    if tiene_bud:
        tab1, tab2 = st.tabs(["📊 Actual vs Presupuesto", "📈 Total del portafolio"])
        with tab1:
            rows_rv = []
            for c in carteras:
                sub = df_ult[df_ult['Cartera']==c]
                if sub.empty: continue
                rv=sub['Revenue'].mean(); rb=sub['Rev_Bud'].mean()
                rp=sub['Rev_Bud_Pct'].mean(); rd=sub['Rev_Bud_Diff'].mean()
                rows_rv.append({'Cartera':c,'Actual':rv,'Presupuesto':rb,
                    'Diferencia':rd,'% Var':rp,'🚦':sem(rp,False)})
            if rows_rv:
                df_rv = pd.DataFrame(rows_rv).sort_values('Actual',ascending=False)
                def hl_rv(v):
                    if isinstance(v,float):
                        if v>=5: return "background:#e8f5e9"
                        if v<-15: return "background:#fdecea"
                        if v<-5: return "background:#fff8e1"
                    return ""
                st.dataframe(df_rv.style.map(hl_rv,subset=['% Var'])
                    .format({'Actual':'${:,.0f}','Presupuesto':'${:,.0f}',
                             'Diferencia':'${:+,.0f}','% Var':'{:+.1f}%'},na_rep="—"),
                    use_container_width=True, hide_index=True)
                fig_gb = go.Figure()
                fig_gb.add_trace(go.Bar(name='Actual',x=df_rv['Cartera'],y=df_rv['Actual'],
                    marker_color='#001d3d',
                    text=df_rv['Actual'].apply(lambda v:f"${v:,.0f}"),textposition='outside'))
                fig_gb.add_trace(go.Bar(name='Presupuesto',x=df_rv['Cartera'],y=df_rv['Presupuesto'],
                    marker_color='#f15b2b',opacity=0.7,
                    text=df_rv['Presupuesto'].apply(lambda v:f"${v:,.0f}" if pd.notna(v) else ""),
                    textposition='outside'))
                fig_gb.update_layout(barmode='group',
                    title=f"Revenue Actual vs Presupuesto · {mes_disp.get(ultimo,ultimo)}",
                    height=420,legend=dict(orientation='h',y=-0.22),**LAYOUT)
                st.plotly_chart(fig_gb, use_container_width=True)
        with tab2:
            rev_tot = rev_pvt.sum(axis=1); bud_tot = bud_pvt.sum(axis=1)
            fig_t = go.Figure()
            fig_t.add_trace(go.Scatter(x=xticks,y=rev_tot.values,mode='lines+markers',
                name='Actual',line=dict(color='#001d3d',width=3),marker=dict(size=7)))
            if bud_tot.notna().any():
                fig_t.add_trace(go.Scatter(x=xticks,y=bud_tot.values,mode='lines',
                    name='Presupuesto',line=dict(color='#f15b2b',width=2,dash='dot')))
            fig_t.update_layout(title="Revenue Total (— Actual  ··· Presupuesto)",
                xaxis_title="Mes",yaxis_title="USD",height=380,
                hovermode='x unified',legend=dict(orientation='h',y=-0.2),**LAYOUT)
            st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.markdown('<div class="box-info">ℹ️ Sin datos de presupuesto en estos archivos. El Budget aparece en reportes 2025-2026.</div>', unsafe_allow_html=True)

    st.markdown('<div class="sec">Revenue por Cliente</div>', unsafe_allow_html=True)
    fig_rpc = go.Figure()
    for i, c in enumerate(carteras):
        if c not in rpc_pvt.columns or rpc_pvt[c].notna().sum()<2: continue
        s = rpc_pvt[c].dropna()
        fig_rpc.add_trace(go.Scatter(
            x=[mes_disp.get(m,m) for m in s.index],y=s.values,
            mode='lines+markers',name=c,line=dict(width=2,color=PAL[i%len(PAL)]),
            hovertemplate=f"<b>{c}</b><br>${{y:.2f}}/cliente<extra></extra>"))
    fig_rpc.update_layout(title="Revenue por Cliente ($)",
        xaxis_title="Mes",yaxis_title="$/cliente",height=380,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified',legend=dict(orientation='h',y=-0.28),**LAYOUT)
    st.plotly_chart(fig_rpc, use_container_width=True)

# ══════════════════════════════════════════════════════════
# M3 — COSTO & EFICIENCIA
# ══════════════════════════════════════════════════════════
elif modulo == "⚙️ Costo & Eficiencia":
    st.markdown('<div class="sec">Average Service Cost · Inflación Operativa</div>', unsafe_allow_html=True)
    st.markdown('<div class="box-info">💡 Si el costo sube sin que el precio contratado cambie, el margen se comprime mes a mes.</div>', unsafe_allow_html=True)
    fig_avg = go.Figure()
    for i, c in enumerate(carteras):
        if c not in avg_pvt.columns or avg_pvt[c].notna().sum()<2: continue
        s = avg_pvt[c].dropna()
        xc = [mes_disp.get(m,m) for m in s.index]; yc = s.values
        fig_avg.add_trace(go.Scatter(x=xc,y=yc,mode='lines+markers',name=c,
            line=dict(width=2,color=PAL[i%len(PAL)]),
            hovertemplate=f"<b>{c}</b><br>${{y:.2f}}/svc<extra></extra>"))
        if len(yc)>=3:
            xn=np.arange(len(yc)); z=np.polyfit(xn,yc,1)
            fig_avg.add_trace(go.Scatter(x=xc,y=np.poly1d(z)(xn),mode='lines',
                line=dict(width=1,dash='dot',color=PAL[i%len(PAL)]),
                showlegend=False,opacity=0.4))
    fig_avg.update_layout(title="Costo Promedio por Servicio + Tendencia (···)",
        xaxis_title="Mes",yaxis_title="$ / servicio",height=420,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified',legend=dict(orientation='h',y=-0.28),**LAYOUT)
    st.plotly_chart(fig_avg, use_container_width=True)

    rows_avg = []
    for c in carteras:
        if c not in avg_pvt.columns: continue
        s = avg_pvt[c].dropna()
        if len(s)<2: continue
        var=(s.iloc[-1]-s.iloc[0])/s.iloc[0]*100
        bpct_val=df_ult[df_ult['Cartera']==c]['Avg_Bud_Pct'].mean()
        rows_avg.append({'Cartera':c,'Costo Inicial':s.iloc[0],'Costo Actual':s.iloc[-1],
            'Var %':var,'vs Ppto %':bpct_val,'🚦':sem(bpct_val,True),
            'Tendencia':'📈' if var>5 else ('📉' if var<-5 else '➡️')})
    if rows_avg:
        df_av = pd.DataFrame(rows_avg).sort_values('Var %',ascending=False)
        def hl_av(v):
            if isinstance(v,float):
                if v>20: return "background:#fdecea"
                if v>10: return "background:#fff8e1"
                if v<-5: return "background:#e8f5e9"
            return ""
        st.dataframe(df_av.style.map(hl_av,subset=['Var %'])
            .format({'Costo Inicial':'${:.2f}','Costo Actual':'${:.2f}',
                     'Var %':'{:+.1f}%','vs Ppto %':'{:+.1f}%'},na_rep="—"),
            use_container_width=True, hide_index=True)

    st.markdown('<div class="sec">Gross Profit At Risk por Cartera</div>', unsafe_allow_html=True)
    fig_gp = go.Figure()
    for i, c in enumerate(carteras):
        if c not in gp_pvt.columns or gp_pvt[c].notna().sum()<2: continue
        s = gp_pvt[c].dropna()
        fig_gp.add_trace(go.Scatter(
            x=[mes_disp.get(m,m) for m in s.index],y=s.values,
            mode='lines+markers',name=c,line=dict(width=2,color=PAL[i%len(PAL)]),
            hovertemplate=f"<b>{c}</b><br>${{y:,.0f}}<extra></extra>"))
    fig_gp.update_layout(title="Gross Profit At Risk ($)",
        xaxis_title="Mes",yaxis_title="USD",height=400,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified',legend=dict(orientation='h',y=-0.28),**LAYOUT)
    st.plotly_chart(fig_gp, use_container_width=True)

# ══════════════════════════════════════════════════════════
# M4 — RENTABILIDAD
# ══════════════════════════════════════════════════════════
elif modulo == "📉 Rentabilidad":
    st.markdown('<div class="sec">Loss Ratio · Historial y Alertas</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="box-info">💡 Loss Ratio = Costo / Revenue. Umbral: <b>{lr_umbral:.0%}</b>. LR > 1.0 = pérdida directa.</div>', unsafe_allow_html=True)
    fig_lr = go.Figure()
    for i, c in enumerate(carteras):
        if c not in lr_pvt.columns or lr_pvt[c].notna().sum()<2: continue
        s = lr_pvt[c].dropna()
        fig_lr.add_trace(go.Scatter(
            x=[mes_disp.get(m,m) for m in s.index],y=s.values,
            mode='lines+markers',name=c,line=dict(width=2.5,color=PAL[i%len(PAL)]),
            hovertemplate=f"<b>{c}</b><br>%{{x}}<br>LR: %{{y:.3f}}<extra></extra>"))
        if c in lr_b_pvt.columns and lr_b_pvt[c].notna().sum()>=2:
            sb=lr_b_pvt[c].dropna()
            fig_lr.add_trace(go.Scatter(
                x=[mes_disp.get(m,m) for m in sb.index],y=sb.values,
                mode='lines',line=dict(width=1,dash='dot',color=PAL[i%len(PAL)]),
                showlegend=False,opacity=0.45))
    fig_lr.add_hline(y=lr_umbral,line_dash='dot',line_color='#f15b2b',line_width=2,
        annotation_text=f"Umbral {lr_umbral:.0%}",
        annotation_font=dict(color='#f15b2b',size=11))
    fig_lr.add_hline(y=1.0,line_dash='solid',line_color='#7f1d1d',line_width=1.5,
        annotation_text="LR=1.0 (sin margen)",annotation_position='bottom right',
        annotation_font=dict(color='#7f1d1d',size=9))
    fig_lr.update_layout(title="Loss Ratio (— Actual  ··· Presupuesto)",
        xaxis_title="Mes",yaxis_title="Loss Ratio",height=460,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified',legend=dict(orientation='h',y=-0.28),**LAYOUT)
    st.plotly_chart(fig_lr, use_container_width=True)

    lrc=[c for c in carteras if c in lr_pvt.columns and lr_pvt[c].notna().sum()>=2]
    if lrc:
        mat=lr_pvt[lrc].T
        fig_lh=px.imshow(mat.values,x=xticks,y=lrc,
            color_continuous_scale='RdYlGn_r',zmin=0,zmax=1.2,aspect='auto',
            title="Heatmap Loss Ratio (rojo = cartera en problema ese mes)")
        fig_lh.update_layout(height=max(280,len(lrc)*32+80),**LAYOUT)
        st.plotly_chart(fig_lh, use_container_width=True)

    rows_lr=[]
    for c in carteras:
        if c not in lr_pvt.columns: continue
        s=lr_pvt[c].dropna()
        if len(s)<1: continue
        bpct_val=df_ult[df_ult['Cartera']==c]['LR_Bud_Pct'].mean()
        sobre=(s>lr_umbral).mean()*100
        rows_lr.append({'Cartera':c,'Meses':len(s),
            'LR Prom.':s.mean(),'LR Máx.':s.max(),'LR Mín.':s.min(),
            'vs Ppto %':bpct_val,'% Meses sobre umbral':sobre,
            'Estado':'🔴 CRÍTICO' if s.mean()>0.90 else ('🟡 REVISAR' if s.mean()>lr_umbral else '🟢 OK')})
    if rows_lr:
        df_lr_t=pd.DataFrame(rows_lr).sort_values('LR Prom.',ascending=False)
        def hl_lr(v):
            if isinstance(v,float):
                if v>0.90: return "background:#fdecea;font-weight:bold"
                if v>lr_umbral: return "background:#fff8e1"
            return ""
        st.dataframe(df_lr_t.style.map(hl_lr,subset=['LR Prom.','LR Máx.'])
            .format({'LR Prom.':'{:.3f}','LR Máx.':'{:.3f}','LR Mín.':'{:.3f}',
                     'vs Ppto %':'{:+.1f}%','% Meses sobre umbral':'{:.0f}%'},na_rep="—"),
            use_container_width=True, hide_index=True)

    st.markdown('<div class="sec">Gross Profit Fee For Service</div>', unsafe_allow_html=True)
    fig_fee=go.Figure()
    for i,c in enumerate(carteras):
        if c not in fee_pvt.columns or fee_pvt[c].notna().sum()<2: continue
        s=fee_pvt[c].dropna()
        fig_fee.add_trace(go.Scatter(
            x=[mes_disp.get(m,m) for m in s.index],y=s.values,
            mode='lines+markers',name=c,line=dict(width=2,color=PAL[i%len(PAL)]),
            hovertemplate=f"<b>{c}</b><br>${{y:,.0f}}<extra></extra>"))
    fig_fee.update_layout(title="GP Fee For Service por Cartera ($)",
        xaxis_title="Mes",yaxis_title="USD",height=380,
        xaxis=dict(categoryorder='array',categoryarray=xticks),
        hovermode='x unified',legend=dict(orientation='h',y=-0.28),**LAYOUT)
    st.plotly_chart(fig_fee, use_container_width=True)

    st.markdown('<div class="sec">Señales de Acción por Cartera</div>', unsafe_allow_html=True)
    for c in sorted(carteras):
        lr_s =lr_pvt[c].dropna()  if c in lr_pvt.columns  else pd.Series(dtype=float)
        avg_s=avg_pvt[c].dropna() if c in avg_pvt.columns else pd.Series(dtype=float)
        cl_s =cl_pvt[c].dropna()  if c in cl_pvt.columns  else pd.Series(dtype=float)
        fr_s =freq_pvt[c].dropna()if c in freq_pvt.columns else pd.Series(dtype=float)
        n_m=df[df['Cartera']==c]['Mes'].nunique()
        nueva=n_m<12; tag=f" · 🆕 {n_m}m" if nueva else f" · {n_m}m"
        if lr_s.empty:
            cat="🔵 FEE FOR SERVICE";cls="box-info"
            accion="Modelo Fee for Service — sin Loss Ratio. Monitorear revenue y clientes."
            lr_prom=None; trend=""
        else:
            lr_prom=lr_s.mean()
            trend="📈" if len(lr_s)>=3 and lr_s.iloc[-1]>lr_s.iloc[-3] else "📉"
            if lr_prom>0.90: cat="🔴 CRÍTICA";cls="box-danger";accion=f"LR {lr_prom:.2f} — márgenes nulos. Repricing urgente."
            elif lr_prom>lr_umbral: cat="🟡 REVISAR";cls="box-warn";accion=f"LR {lr_prom:.3f} supera umbral {lr_umbral:.0%}. Evaluar en renovación."
            elif lr_prom<=0.55 and (lr_s>lr_umbral).mean()<0.2: cat="🟢 SANA";cls="box-ok";accion=f"LR {lr_prom:.3f} — rentable. Candidata a mayor participación."
            else: cat="🔵 MONITOREAR";cls="box-info";accion=f"LR {lr_prom:.3f}. Dentro del umbral, vigilar."
        extras=[]
        if len(avg_s)>=2 and (avg_s.iloc[-1]-avg_s.iloc[0])/avg_s.iloc[0]>0.15:
            extras.append(f"costo/svc +{(avg_s.iloc[-1]-avg_s.iloc[0])/avg_s.iloc[0]*100:.0f}%")
        if len(cl_s)>=2 and (cl_s.iloc[-1]-cl_s.iloc[0])/cl_s.iloc[0]>0.20:
            extras.append(f"clientes +{(cl_s.iloc[-1]-cl_s.iloc[0])/cl_s.iloc[0]*100:.0f}%")
        if len(cl_s)>=2 and (cl_s.iloc[-1]-cl_s.iloc[0])/cl_s.iloc[0]<-0.10:
            extras.append(f"pérdida clientes {(cl_s.iloc[-1]-cl_s.iloc[0])/cl_s.iloc[0]*100:.0f}%")
        if len(fr_s)>0 and fr_s.iloc[-1]>freq_alerta:
            extras.append(f"frecuencia alta {fr_s.iloc[-1]*1000:.1f}‰")
        ex_str="  |  "+" · ".join(extras) if extras else ""
        badge=(' <span style="background:#fef3c7;color:#92400e;padding:2px 6px;border-radius:4px;font-size:0.76rem">🆕 preliminar</span>' if nueva else "")
        st.markdown(
            f'<div class="{cls}"><b>{c}</b>{tag} · {cat} · '
            f'{"LR: <b>"+f"{lr_prom:.3f}</b> {trend}" if lr_prom is not None else "Fee for Service"}'
            f'{ex_str}{badge}<br><small>{accion}</small></div>',
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# M5 — MARKOWITZ
# ══════════════════════════════════════════════════════════
elif modulo == "📈 Markowitz":
    st.markdown('<div class="sec">Optimización del Portafolio · Frontera Eficiente</div>', unsafe_allow_html=True)
    st.markdown('<div class="box-info">💡 Variable: <b>(1 − Loss Ratio)</b> = cuánto queda de cada peso de revenue tras el costo. Mayor = más rentable.</div>', unsafe_allow_html=True)
    rent_pvt=1-lr_pvt
    mk_carts=[c for c in carteras if c in rent_pvt.columns
              and rent_pvt[c].notna().sum()>=min_meses_mk and rent_pvt[c].std()>0]
    excl=[c for c in carteras if c in rent_pvt.columns
          and 0<rent_pvt[c].notna().sum()<min_meses_mk]
    if excl:
        st.markdown(f'<div class="box-warn">📅 Excluidas por &lt;{min_meses_mk} meses: <b>{", ".join(excl)}</b></div>', unsafe_allow_html=True)
    if len(mk_carts)<2:
        st.warning(f"⚠️ Se necesitan ≥2 carteras con {min_meses_mk}+ meses de Loss Ratio.")
    else:
        mu_mk=rent_pvt[mk_carts].mean(); sig_mk=rent_pvt[mk_carts].std()
        cov_mk=rent_pvt[mk_carts].cov().values
        fig_mapa=go.Figure()
        for i,c in enumerate(mk_carts):
            fig_mapa.add_trace(go.Scatter(x=[sig_mk[c]],y=[mu_mk[c]],
                mode='markers+text',text=[c],textposition='top center',
                marker=dict(size=18,color=PAL[i%len(PAL)],line=dict(color='white',width=1.5)),
                name=c,hovertemplate=f"<b>{c}</b><br>Rent: {mu_mk[c]:.1%}<br>σ: {sig_mk[c]:.4f}<extra></extra>"))
        fig_mapa.add_hline(y=(1-lr_umbral),line_dash='dash',line_color='#f15b2b',
            annotation_text=f"Objetivo {1-lr_umbral:.0%}",annotation_font=dict(color='#f15b2b',size=9))
        fig_mapa.add_vline(x=sig_mk.median(),line_dash='dot',line_color='#aaa',line_width=1)
        fig_mapa.add_hline(y=mu_mk.median(),line_dash='dot',line_color='#aaa',line_width=1)
        fig_mapa.update_layout(title="Mapa Riesgo–Rentabilidad (superior izquierda = ideal ⭐)",
            xaxis_title="Riesgo (σ)",yaxis_title="Rentabilidad (1−LR)",
            yaxis=dict(tickformat='.0%'),height=420,showlegend=False,**LAYOUT)
        st.plotly_chart(fig_mapa, use_container_width=True)

        df_sim,opt,minr=monte_carlo(tuple(mu_mk.values),tuple(cov_mk.flatten()),
            len(mk_carts),n_sim,tuple(mk_carts))
        fig_fr=go.Figure()
        fig_fr.add_trace(go.Scatter(x=df_sim['Risk'],y=df_sim['Rent'],mode='markers',
            marker=dict(color=df_sim['Sharpe'],colorscale='Viridis',size=3,opacity=0.5,
                        colorbar=dict(title='Sharpe',thickness=12,len=0.7)),
            name='Simulaciones',hovertemplate='σ: %{x:.4f}<br>Rent: %{y:.1%}<extra></extra>'))
        fig_fr.add_trace(go.Scatter(x=[minr['Risk']],y=[minr['Rent']],mode='markers',
            marker=dict(symbol='diamond',size=18,color='#1976d2',line=dict(color='white',width=1.5)),
            name='🔵 Mínimo Riesgo'))
        fig_fr.add_trace(go.Scatter(x=[opt['Risk']],y=[opt['Rent']],mode='markers',
            marker=dict(symbol='star',size=24,color='#e53935',line=dict(color='white',width=1.5)),
            name='⭐ Portafolio Óptimo'))
        rev_loc=rev_pvt.mean(); cc=[c for c in mk_carts if c in rev_loc.index]
        if cc:
            wa=np.array([rev_loc.get(c,0) for c in cc]); wa=wa/wa.sum() if wa.sum()>0 else wa
            ra=float(np.dot(wa,np.array([mu_mk[c] for c in cc])))
            ca=rent_pvt[cc].cov().values; va=float(np.sqrt(wa@ca@wa))
            fig_fr.add_trace(go.Scatter(x=[va],y=[ra],mode='markers',
                marker=dict(symbol='square',size=16,color='#f15b2b',line=dict(color='white',width=1.5)),
                name='🟠 Distribución Actual'))
        fig_fr.update_layout(title=f"Frontera Eficiente · {n_sim:,} simulaciones",
            xaxis_title="Riesgo (σ)",yaxis_title="Rentabilidad (1−LR)",
            yaxis=dict(tickformat='.0%'),height=500,
            legend=dict(orientation='h',y=-0.18),**LAYOUT)
        st.plotly_chart(fig_fr, use_container_width=True)

        m1,m2,m3=st.columns(3)
        m1.metric("📈 Rentabilidad Esperada",f"{opt['Rent']:.1%}")
        m2.metric("⚡ Riesgo (σ)",f"{opt['Risk']:.4f}")
        m3.metric("🏆 Sharpe Ratio",f"{opt['Sharpe']:.1f}")
        st.markdown("---")

        rev_tot_loc=rev_loc.sum()
        part_mk={c:rev_loc.get(c,0)/rev_tot_loc*100 for c in mk_carts}
        pesos_opt={c:opt[c] for c in mk_carts}
        df_asig=pd.DataFrame({
            'Cartera':mk_carts,
            'Peso Óptimo %':[pesos_opt[c]*100 for c in mk_carts],
            '% Actual':[part_mk.get(c,0) for c in mk_carts],
            'Cambio pp':[pesos_opt[c]*100-part_mk.get(c,0) for c in mk_carts],
            'Rentabilidad (1-LR)':[mu_mk[c] for c in mk_carts],
            'Volatilidad σ':[sig_mk[c] for c in mk_carts],
            'LR Promedio':[lr_pvt[c].mean() if c in lr_pvt.columns else None for c in mk_carts],
        }).sort_values('Peso Óptimo %',ascending=False).reset_index(drop=True)
        ca1,ca2=st.columns([1.2,1])
        with ca1:
            st.dataframe(df_asig.style
                .format({'Peso Óptimo %':'{:.1f}%','% Actual':'{:.1f}%','Cambio pp':'{:+.1f}',
                         'Rentabilidad (1-LR)':'{:.1%}','Volatilidad σ':'{:.4f}','LR Promedio':'{:.3f}'},na_rep="—")
                .background_gradient(subset=['Peso Óptimo %'],cmap='Greens')
                .background_gradient(subset=['Rentabilidad (1-LR)'],cmap='Blues'),
                use_container_width=True, hide_index=True)
        with ca2:
            fig_dona=go.Figure(go.Pie(labels=df_asig['Cartera'],values=df_asig['Peso Óptimo %'],
                hole=0.45,textinfo='label+percent',marker=dict(colors=PAL[:len(df_asig)])))
            fig_dona.update_layout(title="Distribución Óptima",height=340,showlegend=False,
                margin=dict(t=40,b=10,l=10,r=10),**LAYOUT)
            st.plotly_chart(fig_dona, use_container_width=True)

        fig_bar=go.Figure()
        fig_bar.add_trace(go.Bar(name='% Actual',x=mk_carts,
            y=[part_mk.get(c,0) for c in mk_carts],marker_color='#001d3d',
            text=[f"{part_mk.get(c,0):.1f}%" for c in mk_carts],textposition='outside'))
        fig_bar.add_trace(go.Bar(name='% Óptimo',x=mk_carts,
            y=[pesos_opt[c]*100 for c in mk_carts],marker_color='#f15b2b',
            text=[f"{pesos_opt[c]*100:.1f}%" for c in mk_carts],textposition='outside'))
        fig_bar.add_hline(y=umbral_conc,line_dash='dot',line_color='red',
            annotation_text=f"Umbral {umbral_conc}%",annotation_font=dict(color='red',size=9))
        fig_bar.update_layout(title="Distribución Actual vs Óptima",
            barmode='group',height=420,legend=dict(orientation='h',y=-0.22),**LAYOUT)
        st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")
st.caption("Connect Assistance México · Herramienta de Análisis de Carteras · Ingresos · Costos · KPI")
