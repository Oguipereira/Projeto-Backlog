"""Popula o banco com dados de exemplo para demonstração."""
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.init_db import init_db
from app.database import get_db_session
from app.models import System, IncidentType, Incident
from app.services.incident_service import IncidentService

random.seed(42)

SYSTEMS = [
    ("ERP (SAP)",          "Planejamento de Recursos Empresariais",   "alta"),
    ("CRM",                "Gestão de Relacionamento com Cliente",     "alta"),
    ("Portal de Vendas",   "E-commerce e pedidos B2B",                "alta"),
    ("Linha de Produção A","Controle da linha de produção principal",  "alta"),
    ("Linha de Produção B","Controle da linha de produção secundária", "alta"),
    ("WMS",                "Sistema de Gerenciamento de Armazém",      "media"),
    ("MES",                "Sistema de Execução de Manufatura",        "alta"),
    ("E-mail Corporativo", "Exchange / Microsoft 365",                 "baixa"),
    ("VPN Corporativa",    "Acesso remoto seguro",                     "media"),
    ("Active Directory",   "Autenticação e diretório corporativo",     "alta"),
]

INCIDENT_TYPES = [
    ("Falha de Hardware",    "Problemas físicos em servidores ou equipamentos"),
    ("Falha de Software",    "Bugs, crashes ou erros em aplicações"),
    ("Falha de Rede",        "Problemas de conectividade ou infraestrutura"),
    ("Falha de Energia",     "Quedas de energia ou problemas no nobreak"),
    ("Erro de Configuração", "Mudanças incorretas de configuração"),
    ("Sobrecarga de Sistema","Alta utilização de CPU, memória ou disco"),
    ("Falha de Integração",  "Problemas na comunicação entre sistemas"),
    ("Atualização/Patch",    "Problemas decorrentes de atualizações"),
]

TITLES = {
    "P1": [
        "Parada total do {system} — produção paralisada",
        "Falha crítica no {system} — sistema indisponível",
        "Interrupção completa no {system}",
        "{system} fora do ar — impacto imediato na operação",
    ],
    "P2": [
        "Degradação severa de performance no {system}",
        "Erros recorrentes impedindo operação no {system}",
        "Instabilidade grave detectada no {system}",
        "{system} respondendo com falhas intermitentes graves",
    ],
    "P3": [
        "Performance reduzida no {system}",
        "Funcionalidade parcialmente indisponível no {system}",
        "Intermitências reportadas no {system}",
        "{system} com lentidão moderada",
    ],
    "P4": [
        "Lentidão pontual reportada no {system}",
        "Funcionalidade menor indisponível no {system}",
        "Alerta de monitoramento no {system}",
        "Pequena anomalia detectada no {system}",
    ],
}

ROOT_CAUSES = [
    "Falha em disco do servidor de aplicação",
    "Atualização automática causou incompatibilidade",
    "Pico de carga inesperado sobrecarregou o servidor",
    "Erro na última implantação de código",
    "Problema de conectividade com o datacenter",
    "Certificado SSL expirado",
    "Falta de espaço em disco no servidor de banco de dados",
    "Configuração incorreta após manutenção programada",
    "Falha no balanceador de carga",
    "Queda de energia no rack principal",
]

RESOLUTION_NOTES = [
    "Servidor reiniciado e monitoramento ativado.",
    "Rollback realizado para versão anterior estável.",
    "Capacidade de hardware aumentada.",
    "Configuração corrigida e serviço reiniciado.",
    "Certificado renovado e serviço normalizado.",
    "Espaço em disco liberado; purge de logs executado.",
    "Redundância ativada; causa raiz investigada.",
    "Patch de emergência aplicado com sucesso.",
    "Equipe de rede restabeleceu a conectividade.",
    "Grupo de disponibilidade de banco de dados comutado.",
]


def seed():
    init_db()
    db = get_db_session()

    # Limpa dados anteriores (reseed seguro)
    if db.query(System).count() > 0:
        print("Dados já existem. Pulando seed.")
        db.close()
        return

    # Sistemas
    systems = []
    for name, desc, crit in SYSTEMS:
        s = System(name=name, description=desc, criticality=crit)
        db.add(s)
        systems.append(s)
    db.commit()

    # Tipos de incidente
    types = []
    for name, desc in INCIDENT_TYPES:
        t = IncidentType(name=name, description=desc)
        db.add(t)
        types.append(t)
    db.commit()

    # Incidentes
    service = IncidentService(db)

    priorities = ["P1", "P2", "P3", "P4"]
    p_weights = [0.08, 0.20, 0.40, 0.32]
    dur_ranges = {"P1": (45, 480), "P2": (20, 240), "P3": (5, 120), "P4": (5, 60)}
    statuses = ["Aberto", "Em Andamento", "Resolvido"]
    s_weights = [0.04, 0.04, 0.92]

    end_ref = datetime(2026, 4, 26, 18, 0)
    start_ref = datetime(2025, 10, 26, 7, 0)
    date_range_seconds = int((end_ref - start_ref).total_seconds())

    for _ in range(85):
        priority = random.choices(priorities, weights=p_weights)[0]
        status = random.choices(statuses, weights=s_weights)[0]
        system = random.choice(systems)
        itype = random.choice(types)

        # Open/in-progress incidents are always recent (last 48h) to avoid
        # accumulating unrealistic 6-month durations in KPI calculations.
        if status in ("Aberto", "Em Andamento"):
            hours_ago = random.randint(1, 47)
            started_at = end_ref - timedelta(hours=hours_ago)
            started_at = started_at.replace(minute=random.choice([0, 15, 30, 45]), second=0)
        else:
            offset_secs = random.randint(0, date_range_seconds)
            started_at = start_ref + timedelta(seconds=offset_secs)
            started_at = started_at.replace(
                hour=random.randint(6, 22),
                minute=random.choice([0, 15, 30, 45]),
                second=0,
            )

        ended_at = None
        if status == "Resolvido":
            min_d, max_d = dur_ranges[priority]
            duration_min = random.randint(min_d, max_d)
            ended_at = started_at + timedelta(minutes=duration_min)
            if ended_at > end_ref:
                ended_at = end_ref - timedelta(minutes=random.randint(5, 30))

        title = random.choice(TITLES[priority]).format(system=system.name)

        data = {
            "title": title,
            "description": (
                f"Incidente registrado no sistema {system.name}. "
                f"Tipo: {itype.name}. Prioridade: {priority}."
            ),
            "system_id": system.id,
            "incident_type_id": itype.id,
            "priority": priority,
            "status": status,
            "started_at": started_at,
            "ended_at": ended_at,
            "affected_users": random.randint(50, 500) if priority in ("P1", "P2") else random.randint(1, 80),
            "root_cause": random.choice(ROOT_CAUSES) if status == "Resolvido" else "",
            "resolution_notes": random.choice(RESOLUTION_NOTES) if status == "Resolvido" else "",
        }
        service.create(data)

    print(f"Seed concluído: {len(systems)} sistemas, {len(types)} tipos, 85 incidentes.")
    db.close()


if __name__ == "__main__":
    seed()
