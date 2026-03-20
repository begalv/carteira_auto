"""Página de Performance — séries temporais e benchmarks."""

import streamlit as st

st.set_page_config(page_title="Performance", page_icon="📈", layout="wide")
st.title("📈 Performance")

try:
    from carteira_auto.data.storage import SnapshotStore

    store = SnapshotStore()
    snapshots = store.list_snapshots()

    if not snapshots:
        st.info("Nenhum snapshot disponível. Execute `carteira run analyze`.")
        st.stop()

    # Série temporal de valor total
    ts = store.get_time_series("total_value")
    if not ts.empty:
        st.subheader("Evolução do Patrimônio")
        import plotly.express as px

        fig = px.line(
            ts,
            x="date",
            y="total_value",
            labels={"total_value": "Valor (R$)", "date": "Data"},
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Série temporal de retorno
    ts_ret = store.get_time_series("total_return_pct")
    if not ts_ret.empty:
        st.subheader("Evolução do Retorno")
        import plotly.express as px

        fig = px.line(
            ts_ret,
            x="date",
            y="total_return_pct",
            labels={"total_return_pct": "Retorno (%)", "date": "Data"},
        )
        fig.update_layout(height=400, yaxis_tickformat=".1%")
        st.plotly_chart(fig, use_container_width=True)

    # Benchmarks do último snapshot
    latest = store.load_metadata(snapshots[-1])
    if latest and "market" in latest:
        st.subheader("Benchmarks (último snapshot)")
        market = latest["market"]
        col1, col2, col3 = st.columns(3)

        ibov = market.get("ibov_return")
        ifix = market.get("ifix_return")
        cdi = market.get("cdi_return")

        col1.metric("IBOV (1a)", f"{ibov:.2%}" if ibov else "N/A")
        col2.metric("IFIX (1a)", f"{ifix:.2%}" if ifix else "N/A")
        col3.metric("CDI (1a)", f"{cdi:.2%}" if cdi else "N/A")

    if ts.empty and ts_ret.empty:
        st.info(
            "Execute `carteira run analyze` em dias diferentes para gerar séries temporais."
        )

except Exception as e:
    st.error(f"Erro: {e}")
