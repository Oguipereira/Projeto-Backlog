"""Testes unitários para app/utils/calculations.py — funções puras, sem DB."""
from datetime import datetime, timedelta

import pytest

from app.utils.calculations import (
    calculate_duration_minutes,
    calculate_production_loss,
    format_duration,
    format_number,
    get_production_rates,
)


class TestCalculateDurationMinutes:
    def test_duração_exata(self):
        start = datetime(2024, 1, 1, 8, 0, 0)
        end   = datetime(2024, 1, 1, 9, 30, 0)
        assert calculate_duration_minutes(start, end) == 90.0

    def test_duração_zero_quando_igual(self):
        t = datetime(2024, 1, 1, 12, 0)
        assert calculate_duration_minutes(t, t) == 0.0

    def test_não_retorna_negativo(self):
        start = datetime(2024, 1, 1, 10, 0)
        end   = datetime(2024, 1, 1,  9, 0)   # end < start
        assert calculate_duration_minutes(start, end) == 0.0

    def test_sem_end_usa_agora(self):
        start = datetime.now() - timedelta(minutes=5)
        result = calculate_duration_minutes(start)
        assert 4.5 <= result <= 5.5


class TestCalculateProductionLoss:
    def test_cálculo_simples(self):
        assert calculate_production_loss(60.0, 100.0) == 6_000.0

    def test_duração_zero(self):
        assert calculate_production_loss(0.0, 100.0) == 0.0

    def test_arredondamento_duas_casas(self):
        result = calculate_production_loss(1.0, 1.0 / 3)
        assert result == round(1.0 / 3, 2)


class TestGetProductionRates:
    def test_taxa_por_minuto(self):
        rates = get_production_rates(daily_target=480.0, effective_hours=8.0)
        # 480 / (8*60) = 1.0 por minuto
        assert rates["per_minute"] == pytest.approx(1.0)

    def test_taxa_por_hora(self):
        rates = get_production_rates(daily_target=800.0, effective_hours=8.0)
        assert rates["per_hour"] == pytest.approx(100.0)

    def test_taxa_por_dia(self):
        rates = get_production_rates(daily_target=40_000_000.0, effective_hours=8.0)
        assert rates["per_day"] == 40_000_000.0


class TestFormatDuration:
    @pytest.mark.parametrize("minutes,expected", [
        (0.5,   "30s"),
        (1.0,   "1min"),
        (59.0,  "59min"),
        (60.0,  "1h"),
        (90.0,  "1h 30min"),
        (120.0, "2h"),
        (125.0, "2h 5min"),
    ])
    def test_formatos(self, minutes, expected):
        assert format_duration(minutes) == expected


class TestFormatNumber:
    def test_inteiro_sem_decimais(self):
        assert format_number(1_000_000) == "1.000.000"

    def test_com_decimais(self):
        result = format_number(1_234.5, decimals=2)
        assert result == "1.234,50"

    def test_zero(self):
        assert format_number(0) == "0"
