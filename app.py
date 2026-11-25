"""
app.py - Streamlit host
=======================
Run:  streamlit run app.py      (from inside the pipingsizing folder, or
      streamlit run pipingsizing/app.py from the repo root)

Architecture (everything lives in this one folder):
  index.html    interactive builder (canvas, forms, results, profile chart)
       |  postMessage  (Streamlit custom-component protocol, no npm build)
  app.py        receives the network JSON, calls the engines, sends results back
       |
  hydraulics.py continuity, Reynolds, friction factor, Darcy-Weisbach, Bernoulli
  thermal.py    heat loss through insulation + Joule-Thomson / friction heating
"""
import io
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import hydraulics

HERE = os.path.dirname(os.path.abspath(__file__))
st.set_page_config(page_title="Piping Hydraulics & Temperature Drop", page_icon="🛠️", layout="wide")

# index.html in this folder IS the component (served as a static file)
piping_builder = components.declare_component("piping_builder", path=HERE)


@st.cache_data
def get_catalog():
    return hydraulics.catalog()


ss = st.session_state
ss.setdefault("results", None)
ss.setdefault("network", None)
ss.setdefault("last_nonce", None)
ss.setdefault("restore", None)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Project")
    up = st.file_uploader("Load network (.json)", type=["json"])
    if up is not None:
        raw = up.getvalue()
        rid = str(hash(raw))
        if not ss.restore or ss.restore.get("id") != rid:
            try:
                ss.restore = {"id": rid, "network": json.loads(raw), "force": True}
                ss.results = None
                st.success("Network loaded into the builder.")
            except Exception as e:
                st.error(f"Invalid file: {e}")
    if ss.network:
        st.download_button("Save current network (.json)", json.dumps(ss.network, indent=2),
                           file_name="piping_network.json", mime="application/json")
    st.caption("Engine: " + ("CoolProp + built-in" if hydraulics.HAS_COOLPROP else "built-in correlations"))
    st.markdown("**How to use**\n1. Set inlet, medium, units\n2. Click a green **+** and add segments\n"
                "3. Tees create two ends - close every end with an **Outlet**\n4. Press **Calculate**")

# ------------------------------------------------------------------ builder (index.html)
restore = ss.restore or ({"id": "session", "network": ss.network, "force": False} if ss.network else None)
value = piping_builder(catalog=get_catalog(), results=ss.results, restore=restore,
                       key="builder", default=None)

if value and value.get("nonce") and value.get("nonce") != ss.last_nonce:
    ss.last_nonce = value["nonce"]
    if value.get("action") == "calculate":
        ss.network = value["network"]
        res = hydraulics.solve(value["network"])
        res["nonce"] = value["nonce"]
        ss.results = res
        ss.restore = None
        st.rerun()  # push results back into index.html

# ------------------------------------------------------------------ report (Streamlit side)
res = ss.results
if res and res.get("ok"):
    sm = res["summary"]
    st.subheader("Report")
    if not sm["feasible"]:
        st.error("ΔP NOT FEASIBLE\n\n" + "\n".join(f"- {m}" for m in res["infeasible"]))
    for w in res["warnings"]:
        st.warning(w)

    cols = st.columns(min(4, 1 + len(res["outlets"])))
    cols[0].metric(sm["inlet_label"], f"{sm['P_in']:.3f} {sm['P_unit']}", f"{sm['m_kgh']:.0f} kg/h", delta_color="off")
    for i, o in enumerate(res["outlets"]):
        cols[(i + 1) % len(cols)].metric(o["label"], f"{o['P']:.3f} {sm['P_unit']}",
                                         f"-{o['dP_total']:.3f} {sm['dP_unit']}", delta_color="inverse")

    t1, t2, t3 = st.tabs(["Axial pressure profile", "Temperature & elevation", "Segment table"])
    with t1:
        fig = go.Figure()
        for p in res["profiles"]:
            fig.add_trace(go.Scatter(x=[q["x"] for q in p["points"]], y=[q["P"] for q in p["points"]],
                                     mode="lines", name=p["outlet"], customdata=[q["seg"] for q in p["points"]],
                                     hovertemplate="%{customdata}<br>x=%{x:.1f}<br>P=%{y:.4f}<extra>%{fullData.name}</extra>"))
        for o in res["outlets"]:
            if o.get("Pmin") not in (None, ""):
                fig.add_hline(y=float(o["Pmin"]), line_dash="dash", annotation_text=f"Min P {o['label']}")
        fig.update_layout(xaxis_title=f"Axial distance [{sm['len_unit']}]", yaxis_title=f"Pressure [{sm['P_unit']}]",
                          height=420, margin=dict(l=10, r=10, t=30, b=10), legend_title="Path to")
        st.plotly_chart(fig, use_container_width=True)
    with t2:
        c1, c2 = st.columns(2)
        for col, key, lbl in ((c1, "T", f"Temperature [{sm['T_unit']}]"), (c2, "z", "Elevation [m]")):
            f2 = go.Figure()
            for p in res["profiles"]:
                f2.add_trace(go.Scatter(x=[q["x"] for q in p["points"]], y=[q[key] for q in p["points"]],
                                        mode="lines", name=p["outlet"]))
            f2.update_layout(xaxis_title=f"Axial distance [{sm['len_unit']}]", yaxis_title=lbl, height=340,
                             margin=dict(l=10, r=10, t=30, b=10))
            col.plotly_chart(f2, use_container_width=True)
    with t3:
        df = pd.DataFrame(res["rows"])
        st.dataframe(df, use_container_width=True, hide_index=True)
        c1, c2 = st.columns(2)
        c1.download_button("Download segment table (CSV)", df.to_csv(index=False).encode(),
                           file_name="piping_results.csv", mime="text/csv")
        buf = io.StringIO()
        json.dump({"network": ss.network, "results": res}, buf, indent=2, default=str)
        c2.download_button("Download full report (JSON)", buf.getvalue(), file_name="piping_report.json",
                           mime="application/json")
elif res and res.get("errors"):
    st.error("Calculation blocked:\n\n" + "\n".join(f"- {e}" for e in res["errors"]))
