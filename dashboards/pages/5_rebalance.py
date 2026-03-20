"""Página de Rebalanceamento — recomendações e simulação."""

import streamlit as st

st.set_page_config(page_title="Rebalanceamento", page_icon="🔄", layout="wide")
st.title("🔄 Rebalanceamento")

try:
    from carteira_auto.data.storage import SnapshotStore

    store = SnapshotStore()
    snapshots = store.list_snapshots()

    if not snapshots:
        st.info("Nenhum snapshot disponível. Execute `carteira run rebalance`.")
        st.stop()

    latest = store.load_metadata(snapshots[-1])
    if not latest:
        st.warning("Snapshot sem dados.")
        st.stop()

    # Métricas atuais
    total_value = latest.get("total_value", 0)
    allocations = latest.get("allocations", {})

    if not allocations:
        st.info("Sem dados de alocação. Execute `carteira run analyze` primeiro.")
        st.stop()

    st.metric("Patrimônio Total", f"R$ {total_value:,.2f}")

    # Simulação "e se invisto X?"
    st.subheader("Simulação de Aporte")
    aporte = st.number_input(
        "Valor do aporte (R$)",
        min_value=0.0,
        value=1000.0,
        step=100.0,
    )

    if aporte > 0 and allocations:
        st.markdown("**Distribuição recomendada do aporte:**")

        import pandas as pd

        rows = []
        for classe, data in allocations.items():
            target = data["target_pct"]
            current = data["current_pct"]
            deviation = data["deviation"]

            # Classes abaixo da meta recebem mais
            if deviation < 0:
                # Proporcional ao desvio negativo
                weight = abs(deviation)
            else:
                weight = 0

            rows.append(
                {
                    "Classe": classe,
                    "Atual (%)": f"{current * 100:.1f}",
                    "Meta (%)": f"{target * 100:.1f}",
                    "Desvio (p.p.)": f"{deviation * 100:+.1f}",
                    "Peso": weight,
                }
            )

        df = pd.DataFrame(rows)
        total_weight = df["Peso"].sum()

        if total_weight > 0:
            df["Aporte (R$)"] = df["Peso"].apply(
                lambda w: f"R$ {(w / total_weight * aporte):,.2f}"
            )
        else:
            # Todas as classes no alvo — distribuir pela meta
            for i, row in enumerate(rows):
                meta_pct = allocations[row["Classe"]]["target_pct"]
                df.loc[i, "Aporte (R$)"] = f"R$ {(meta_pct * aporte):,.2f}"

        st.dataframe(
            df[["Classe", "Atual (%)", "Meta (%)", "Desvio (p.p.)", "Aporte (R$)"]],
            use_container_width=True,
            hide_index=True,
        )

    # Tabela de desvios
    st.subheader("Desvios de Alocação")
    import plotly.graph_objects as go

    labels = list(allocations.keys())
    deviations = [v["deviation"] * 100 for v in allocations.values()]
    colors = ["#2ca02c" if d >= 0 else "#d62728" for d in deviations]

    fig = go.Figure(data=[go.Bar(x=labels, y=deviations, marker_color=colors)])
    fig.update_layout(yaxis_title="Desvio (p.p.)", height=350)
    st.plotly_chart(fig, use_container_width=True)

except Exception as e:
    st.error(f"Erro: {e}")
