"""Testes para ConfigService — leitura de config, prioridades e salvamento."""
import pytest
from app.services.config_service import ConfigService
from app.models import Configuration


@pytest.fixture()
def config_svc(db_session, config_patch):
    return ConfigService(db_session)


@pytest.fixture()
def config_svc_no_save(db_session, config_patch, monkeypatch):
    """ConfigService com _save_file neutralizado para não tocar no arquivo real."""
    monkeypatch.setattr(ConfigService, "_save_file", lambda self: None)
    return ConfigService(db_session)


class TestGetProductionConfig:
    def test_retorna_valores_padrão(self, config_svc):
        cfg = config_svc.get_production_config()
        assert cfg["daily_production_target"] == 40_000_000.0
        assert cfg["effective_hours_per_day"] == 8.0

    def test_override_via_banco_substitui_valor(self, db_session, config_patch):
        db_session.add(Configuration(
            key="production.daily_production_target",
            value="50000000",
            category="production",
        ))
        db_session.commit()
        svc = ConfigService(db_session)
        cfg = svc.get_production_config()
        assert cfg["daily_production_target"] == 50_000_000.0

    def test_override_inválido_mantém_padrão(self, db_session, config_patch):
        db_session.add(Configuration(
            key="production.effective_hours_per_day",
            value="não_é_número",
            category="production",
        ))
        db_session.commit()
        svc = ConfigService(db_session)
        cfg = svc.get_production_config()
        assert cfg["effective_hours_per_day"] == 8.0

    def test_override_de_chave_inexistente_é_ignorado(self, db_session, config_patch):
        db_session.add(Configuration(
            key="production.chave_fantasma",
            value="99",
            category="production",
        ))
        db_session.commit()
        svc = ConfigService(db_session)
        cfg = svc.get_production_config()
        assert "chave_fantasma" not in cfg


class TestGetProductionRates:
    def test_taxas_consistentes(self, config_svc):
        rates = config_svc.get_production_rates()
        # 40M / (8h * 60min) = 83333.333.../min
        expected = 40_000_000.0 / (8.0 * 60)
        assert rates["per_minute"] == pytest.approx(expected, rel=1e-4)

    def test_taxa_por_dia_igual_ao_target(self, config_svc):
        rates = config_svc.get_production_rates()
        assert rates["per_day"] == 40_000_000.0


class TestSaveProductionConfig:
    def test_salva_novo_valor_no_banco(self, db_session, config_patch, monkeypatch):
        monkeypatch.setattr(ConfigService, "_save_file", lambda self: None)
        svc = ConfigService(db_session)
        svc.save_production_config({"daily_production_target": 50_000_000.0})
        rec = db_session.query(Configuration).filter_by(
            key="production.daily_production_target"
        ).first()
        assert rec is not None
        assert rec.value == "50000000.0"

    def test_atualiza_registro_existente(self, db_session, config_patch, monkeypatch):
        monkeypatch.setattr(ConfigService, "_save_file", lambda self: None)
        db_session.add(Configuration(
            key="production.effective_hours_per_day",
            value="8.0",
            category="production",
        ))
        db_session.commit()
        svc = ConfigService(db_session)
        svc.save_production_config({"effective_hours_per_day": 7.5})
        rec = db_session.query(Configuration).filter_by(
            key="production.effective_hours_per_day"
        ).first()
        assert rec.value == "7.5"


class TestPrioritiesAndStatuses:
    def test_get_priorities_retorna_p1_a_p4(self, config_svc):
        p = config_svc.get_priorities()
        assert set(p.keys()) == {"P1", "P2", "P3", "P4"}

    def test_get_statuses_retorna_lista(self, config_svc):
        s = config_svc.get_statuses()
        assert "Aberto" in s
        assert "Resolvido" in s

    def test_get_priority_color_p1(self, config_svc):
        assert config_svc.get_priority_color("P1") == "#DC2626"

    def test_get_priority_color_desconhecida_usa_fallback(self, config_svc):
        assert config_svc.get_priority_color("P9") == "#6B7280"

    def test_get_priority_sla_p1_é_60min(self, config_svc):
        assert config_svc.get_priority_sla("P1") == 60

    def test_get_priority_sla_desconhecida_retorna_alto_valor(self, config_svc):
        assert config_svc.get_priority_sla("PX") == 9999
