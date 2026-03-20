"""Página Macro — indicadores BCB, trajetória Selic, IPCA, câmbio."""

import streamlit as st

st.set_page_config(page_title="Macro", page_icon="🏦", layout="wide")
st.title("🏦 Macro")

try:
    from carteira_auto.data.storage import SnapshotStore

    store = SnapshotStore()
    snapshots = store.list_snapshots()

    if not snapshots:
        st.info("Nenhum snapshot disponível. Execute `carteira run macro`.")
        st.stop()

    latest = store.load_metadata(snapshots[-1])
    if not latest or "macro" not in latest:
        st.info("Sem dados macro no último snapshot. Execute `carteira run macro`.")
        st.stop()

    macro = latest["macro"]

    # Indicadores principais
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Selic", f"{macro.get('selic', 'N/A')}% a.a.")
    col2.metric("IPCA (12m)", f"{macro.get('ipca', 'N/A')}%")
    col3.metric("Câmbio (USD)", f"R$ {macro.get('cambio', 'N/A')}")
    col4.metric("PIB", f"{macro.get('pib_growth', 'N/A')}%")

    st.markdown("---")

    # Busca dados históricos em tempo real
    st.subheader("Séries Históricas (BCB)")

    try:
        from carteira_auto.data.fetchers import BCBFetcher

        bcb = BCBFetcher()

        tab1, tab2, tab3, tab4 = st.tabs(["Selic", "IPCA", "PTAX", "CDI"])

        import plotly.express as px

        with tab1:
            df = bcb.get_selic(period_days=730)
            if not df.empty:
                fig = px.line(df, x="data", y="valor", title="Taxa Selic (% a.a.)")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        with tab2:
            df = bcb.get_ipca(period_days=730)
            if not df.empty:
                fig = px.bar(df, x="data", y="valor", title="IPCA mensal (%)")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        with tab3:
            df = bcb.get_ptax(period_days=365)
            if not df.empty:
                fig = px.line(df, x="data", y="valor", title="PTAX USD (R$)")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

        with tab4:
            df = bcb.get_cdi(period_days=365)
            if not df.empty:
                fig = px.line(df, x="data", y="valor", title="CDI (% a.d.)")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"Falha ao buscar dados BCB em tempo real: {e}")

except Exception as e:
    st.error(f"Erro: {e}")
