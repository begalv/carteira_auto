"""Testes para helpers de conversão temporal de taxas."""

import numpy as np
import pytest
from carteira_auto.utils.helpers import (
    accumulate_and_annualize,
    accumulate_rates,
    convert_rate,
)


class TestConvertRate:
    """Testes para convert_rate — conversão entre a.d., a.m. e a.a."""

    def test_identidade(self):
        """Mesma unidade → retorna o mesmo valor."""
        assert convert_rate(13.75, "a.a.", "a.a.") == 13.75
        assert convert_rate(0.5, "a.m.", "a.m.") == 0.5
        assert convert_rate(0.042, "a.d.", "a.d.") == 0.042

    def test_anual_para_mensal(self):
        """Selic 13,75% a.a. → ~1,08% a.m."""
        mensal = convert_rate(13.75, "a.a.", "a.m.")
        # (1.1375)^(1/12) - 1 = 0.010794
        assert mensal == pytest.approx(1.0794, rel=1e-3)

    def test_mensal_para_anual(self):
        """Poupança 0,5% a.m. → ~6,17% a.a."""
        anual = convert_rate(0.5, "a.m.", "a.a.")
        assert anual == pytest.approx(6.1678, rel=1e-3)

    def test_diario_para_anual(self):
        """CDI 0,042% a.d. → ~11,14% a.a. (252 dias úteis)."""
        anual = convert_rate(0.042, "a.d.", "a.a.")
        assert anual == pytest.approx(11.14, rel=1e-2)

    def test_anual_para_diario(self):
        """13,75% a.a. → ~0,0512% a.d."""
        diario = convert_rate(13.75, "a.a.", "a.d.")
        assert diario == pytest.approx(0.0512, rel=1e-2)

    def test_mensal_para_diario(self):
        """1% a.m. → taxa diária (252/12 = 21 dias/mês)."""
        diario = convert_rate(1.0, "a.m.", "a.d.")
        # 1% a.m. → ~0,047% a.d. (via 252 dias)
        assert 0.04 < diario < 0.06

    def test_roundtrip_anual_mensal(self):
        """Conversão ida e volta a.a. → a.m. → a.a."""
        original = 13.75
        mensal = convert_rate(original, "a.a.", "a.m.")
        volta = convert_rate(mensal, "a.m.", "a.a.")
        assert volta == pytest.approx(original, rel=1e-10)

    def test_roundtrip_anual_diario(self):
        """Conversão ida e volta a.a. → a.d. → a.a."""
        original = 11.0
        diario = convert_rate(original, "a.a.", "a.d.")
        volta = convert_rate(diario, "a.d.", "a.a.")
        assert volta == pytest.approx(original, rel=1e-10)

    def test_taxa_zero(self):
        """Taxa zero → sempre zero."""
        assert convert_rate(0.0, "a.a.", "a.m.") == 0.0
        assert convert_rate(0.0, "a.d.", "a.a.") == 0.0


class TestAccumulateRates:
    """Testes para accumulate_rates — composição via produtório."""

    def test_serie_simples(self):
        """3 meses de IPCA: 0,38 + 0,42 + 0,35 → ~1,154%."""
        ipca = [0.38, 0.42, 0.35]
        acum = accumulate_rates(ipca, "a.m.")
        esperado = ((1.0038) * (1.0042) * (1.0035) - 1) * 100
        assert acum == pytest.approx(esperado, rel=1e-6)

    def test_serie_diaria_cdi(self):
        """252 dias de CDI a 0,042% a.d. → ~11,14% no período."""
        cdi_diario = [0.042] * 252
        acum = accumulate_rates(cdi_diario, "a.d.")
        esperado = ((1.00042) ** 252 - 1) * 100
        assert acum == pytest.approx(esperado, rel=1e-6)

    def test_serie_mensal_poupanca(self):
        """12 meses de poupança 0,5% a.m. → ~6,17%."""
        poup = [0.5] * 12
        acum = accumulate_rates(poup, "a.m.")
        esperado = ((1.005) ** 12 - 1) * 100
        assert acum == pytest.approx(esperado, rel=1e-6)

    def test_serie_vazia(self):
        """Série vazia → 0%."""
        # prod() de array vazio = 1, então (1 - 1) * 100 = 0
        acum = accumulate_rates([], "a.m.")
        assert acum == 0.0

    def test_aceita_numpy_array(self):
        """Funciona com np.ndarray."""
        arr = np.array([0.5, 0.5, 0.5])
        acum = accumulate_rates(arr, "a.m.")
        assert acum == pytest.approx(((1.005) ** 3 - 1) * 100, rel=1e-6)

    def test_aceita_pandas_series(self):
        """Funciona com pd.Series."""
        import pandas as pd

        s = pd.Series([0.042, 0.042, 0.042])
        acum = accumulate_rates(s, "a.d.")
        assert acum == pytest.approx(((1.00042) ** 3 - 1) * 100, rel=1e-6)

    def test_taxa_zero(self):
        """Taxas zero → 0% acumulado."""
        acum = accumulate_rates([0.0, 0.0, 0.0], "a.m.")
        assert acum == 0.0


class TestAccumulateAndAnnualize:
    """Testes para accumulate_and_annualize — acumulação + anualização."""

    def test_um_ano_cdi(self):
        """252 dias de CDI → taxa anualizada = taxa do período (1 ano)."""
        cdi = [0.042] * 252
        anual = accumulate_and_annualize(cdi, "a.d.")
        acum = accumulate_rates(cdi, "a.d.")
        # 252 dias = 1 ano → anualização não muda o valor
        assert anual == pytest.approx(acum, rel=1e-6)

    def test_dois_anos_cdi(self):
        """504 dias de CDI → anualização deve dar ~metade do acumulado."""
        cdi = [0.042] * 504
        anual = accumulate_and_annualize(cdi, "a.d.")
        # 504 dias = 2 anos. Anualizar: (1 + acum)^(1/2) - 1
        acum = (1.00042) ** 504 - 1
        esperado = ((1 + acum) ** 0.5 - 1) * 100
        assert anual == pytest.approx(esperado, rel=1e-6)

    def test_12_meses(self):
        """12 meses de poupança → taxa = acumulado (1 ano exato)."""
        poup = [0.5] * 12
        anual = accumulate_and_annualize(poup, "a.m.")
        acum = accumulate_rates(poup, "a.m.")
        assert anual == pytest.approx(acum, rel=1e-6)

    def test_24_meses(self):
        """24 meses → anualiza para 2 anos."""
        poup = [0.5] * 24
        anual = accumulate_and_annualize(poup, "a.m.")
        acum = (1.005) ** 24 - 1
        esperado = ((1 + acum) ** 0.5 - 1) * 100
        assert anual == pytest.approx(esperado, rel=1e-6)

    def test_serie_vazia(self):
        """Série vazia → 0%."""
        assert accumulate_and_annualize([], "a.m.") == 0.0
