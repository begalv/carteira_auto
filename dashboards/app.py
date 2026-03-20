"""Dashboard principal — Carteira Auto.

Execução:
    streamlit run dashboards/app.py
    ou
    carteira dashboard
"""

import streamlit as st

st.set_page_config(
    page_title="Carteira Auto",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Carteira Auto")
st.markdown("---")

# Sidebar
st.sidebar.title("Navegação")
st.sidebar.info(
    "Use o menu lateral para navegar entre as páginas.\n\n"
    "Cada página busca dados em tempo real dos fetchers configurados."
)

# Página inicial — visão geral rápida
st.header("Visão Geral")

col1, col2, col3, col4 = st.columns(4)

# Tenta carregar último snapshot
try:
    from carteira_auto.data.storage import SnapshotStore

    store = SnapshotStore()
    snapshots = store.list_snapshots()

    if snapshots:
        latest = store.load_metadata(snapshots[-1])
        if latest:
            col1.metric("Patrimônio", f"R$ {latest.get('total_value', 0):,.2f}")
            col2.metric("Retorno", f"{latest.get('total_return_pct', 0):.2%}")
            col3.metric("Dividend Yield", f"{latest.get('dividend_yield', 0):.2%}")

            macro = latest.get("macro", {})
            col4.metric("Selic", f"{macro.get('selic', 'N/A')}%")

            st.markdown("---")

            # Alocação
            allocations = latest.get("allocations", {})
            if allocations:
                st.subheader("Alocação por Classe")
                import plotly.graph_objects as go

                labels = list(allocations.keys())
                current = [v["current_pct"] * 100 for v in allocations.values()]
                target = [v["target_pct"] * 100 for v in allocations.values()]

                fig = go.Figure()
                fig.add_trace(
                    go.Bar(name="Atual", x=labels, y=current, marker_color="#1f77b4")
                )
                fig.add_trace(
                    go.Bar(name="Meta", x=labels, y=target, marker_color="#ff7f0e")
                )
                fig.update_layout(
                    barmode="group",
                    yaxis_title="Alocação (%)",
                    height=400,
                )
                st.plotly_chart(fig, use_container_width=True)

            # Info do snapshot
            st.caption(f"Último snapshot: {snapshots[-1]}")
        else:
            st.info("Snapshot encontrado mas sem dados.")
    else:
        st.info(
            "Nenhum snapshot encontrado. "
            "Execute `carteira run analyze` para gerar dados."
        )
except ImportError:
    st.warning("Módulo carteira_auto não encontrado no PYTHONPATH.")
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
