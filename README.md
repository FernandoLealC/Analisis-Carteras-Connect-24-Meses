# Herramienta de Análisis de Carteras · Ingresos · Costos · KPI
**Connect Assistance México**

Herramienta Streamlit para análisis operativo del portafolio de clientes.
Lee archivos KPI mensuales de Sage Intacct (.xlsx) y genera análisis multi-KPI.

---

## 🚀 Deploy en Streamlit Cloud

1. Sube estos 4 archivos a tu repo GitHub (en este orden exacto, uno por uno):
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `README.md`
   - `app.py`
2. En [share.streamlit.io](https://share.streamlit.io): New app → selecciona repo → `app.py`
3. Sube los archivos KPI desde el sidebar de la app

---

## 📂 Archivos del repo

```
app.py                    ← Aplicación principal (no modificar)
requirements.txt          ← Dependencias con versiones fijas
.streamlit/config.toml    ← Tema Connect (claro, navy + naranja)
README.md                 ← Este archivo
data/                     ← Carpeta vacía (no subir archivos .xlsx aquí)
```

---

## 📊 Módulos

| Módulo | Contenido |
|--------|-----------|
| 📊 Resumen Ejecutivo | Scorecard 🟢🟡🔴 vs presupuesto, semáforo por cartera, concentración de revenue |
| 👥 Clientes & Volumen | Evolución de clientes, detección "crece clientes / baja uso", heatmap servicios, frecuencia |
| 💰 Revenue | Barras apiladas, Actual vs Budget por cartera, total del portafolio, revenue por cliente |
| ⚙️ Costo & Eficiencia | Costo promedio por servicio + tendencia, inflación operativa, GP At Risk |
| 📉 Rentabilidad | Loss Ratio vs umbral + budget punteado, heatmap LR, GP Fee For Service, señales de acción |
| 📈 Markowitz | Mapa riesgo-rentabilidad, frontera eficiente Monte Carlo, distribución actual vs óptima |

---

## 📁 Archivos KPI compatibles

El parser detecta automáticamente **5 variantes de estructura** (2024 vs 2025 vs 2026):

| Período | Estructura |
|---------|-----------|
| Jun-Dic 2024 | Actual \| Forecast \| FcDiff \| Fc%Var \| \| Actual_YTD \| Budget_YTD |
| Ene-Mar 2025 | Actual \| FcDiff \| Fc%Var \| \| Actual_YTD \| Budget_YTD |
| Abr-Jun 2025 | Actual \| Forecast \| BudDiff \| Bud%Var \| \| Actual_YTD \| Budget_YTD |
| Jul-Sep 2025 | Actual \| Forecast \| FcDiff \| Fc%Var \| \| Actual_YTD \| Budget_YTD |
| Oct 2025 – May 2026 | Actual \| Budget \| BudDiff \| Bud%Var \| \| Actual_YTD \| Budget_YTD |

**Nombre de archivo sugerido:** `MMAA__KPI.xlsx` (ej: `0326__KPI.xlsx` = Marzo 2026)

---

## ⚙️ Dependencias

```
streamlit==1.32.0
pandas==2.2.1
numpy==1.26.4
plotly==5.19.0
openpyxl==3.1.2
xlrd==2.0.1
```

---

## 🔧 Configuración sidebar

- **Umbral Loss Ratio:** % máximo aceptable (default 65%)
- **Alerta frecuencia:** ‰ servicios/cliente (default 12‰)
- **Concentración máx.:** % de revenue por cartera (default 25%)
- **Simulaciones Markowitz:** número de portfolios simulados (default 5,000)
- **Meses mínimos Markowitz:** mínimo de datos para incluir cartera (default 6)

---

*Connect Assistance México · Uso interno*
