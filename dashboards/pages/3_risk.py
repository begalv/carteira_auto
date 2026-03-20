"""Página de Risco — volatilidade, VaR, Sharpe, drawdown."""

import streamlit as st

st.set_page_config(page_title="Risco", page_icon="⚠️", layout="wide")
st.title("⚠️ Risco")

try:
    from carteira_auto.data.storage import SnapshotStore

    store = SnapshotStore()
    snapshots = store.list_snapshots()

    if not snapshots:
        st.info("Nenhum snapshot disponível. Execute `carteira run risk`.")
        st.stop()

    latest = store.load_metadata(snapshots[-1])
    if not latest or "risk" not in latest:
        st.info("Sem dados de risco no último snapshot. Execute `carteira run risk`.")
        st.stop()

    risk = latest["risk"]

    # Métricas principais
    col1, col2, col3, col4 = st.columns(4)

    vol = risk.get("volatility")
    sharpe = risk.get("sharpe_ratio")
    var95 = risk.get("var_95")
    max_dd = risk.get("max_drawdown")
    beta = risk.get("beta")

    col1.metric("Volatilidade (a.a.)", f"{vol:.2%}" if vol else "N/A")
    col2.metric("Sharpe Ratio", f"{sharpe:.2f}" if sharpe else "N/A")
    col3.metric("VaR 95%", f"{var95:.2%}" if var95 else "N/A")
    col4.metric("Max Drawdown", f"{max_dd:.2%}" if max_dd else "N/A")

    st.markdown("---")

    # Detalhes
    st.subheader("Detalhes")
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Métrica": "Volatilidade (anualizada)",
                "Valor": f"{vol:.4f}" if vol else "N/A",
            },
            {"Métrica": "VaR 95%", "Valor": f"{var95:.4f}" if var95 else "N/A"},
            {"Métrica": "VaR 99%", "Valor": f"{risk.get('var_99', 'N/A')}"},
            {"Métrica": "Sharpe Ratio", "Valor": f"{sharpe:.4f}" if sharpe else "N/A"},
            {"Métrica": "Max Drawdown", "Valor": f"{max_dd:.4f}" if max_dd else "N/A"},
            {"Métrica": "Beta (vs IBOV)", "Valor": f"{beta:.4f}" if beta else "N/A"},
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"Erro: {e}")
