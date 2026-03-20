"""Página de Alocação — atual vs meta, breakdown por classe/setor."""

import streamlit as st

st.set_page_config(page_title="Alocação", page_icon="🥧", layout="wide")
st.title("🥧 Alocação")

try:
    from carteira_auto.data.storage import SnapshotStore

    store = SnapshotStore()
    snapshots = store.list_snapshots()

    if not snapshots:
        st.info("Nenhum snapshot disponível. Execute `carteira run analyze`.")
        st.stop()

    latest = store.load_metadata(snapshots[-1])
    if not latest:
        st.warning("Snapshot sem dados.")
        st.stop()

    allocations = latest.get("allocations", {})
    if not allocations:
        st.info("Sem dados de alocação no snapshot.")
        st.stop()

    import plotly.graph_objects as go

    labels = list(allocations.keys())
    current_pcts = [v["current_pct"] * 100 for v in allocations.values()]
    target_pcts = [v["target_pct"] * 100 for v in allocations.values()]
    deviations = [v["deviation"] * 100 for v in allocations.values()]

    # Pie charts lado a lado
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Alocação Atual")
        fig = go.Figure(data=[go.Pie(labels=labels, values=current_pcts, hole=0.4)])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Meta de Alocação")
        fig = go.Figure(data=[go.Pie(labels=labels, values=target_pcts, hole=0.4)])
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Desvios
    st.subheader("Desvios (Atual - Meta)")
    colors = ["#2ca02c" if d >= 0 else "#d62728" for d in deviations]
    fig = go.Figure(data=[go.Bar(x=labels, y=deviations, marker_color=colors)])
    fig.update_layout(
        yaxis_title="Desvio (p.p.)",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabela detalhada
    st.subheader("Detalhes")
    import pandas as pd

    df = pd.DataFrame(
        {
            "Classe": labels,
            "Atual (%)": [f"{p:.1f}" for p in current_pcts],
            "Meta (%)": [f"{p:.1f}" for p in target_pcts],
            "Desvio (p.p.)": [f"{d:+.1f}" for d in deviations],
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro: {e}")
