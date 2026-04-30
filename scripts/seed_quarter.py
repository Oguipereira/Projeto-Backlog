"""
Adiciona 85 incidentes fictícios cobrindo Q1 2026 (Jan–Mar).
Usa sistemas e tipos já cadastrados no banco.
"""
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.database  # inicializa engine antes dos models
from app.database import get_db_session
from app.models import System, IncidentType
from app.services.incident_service import IncidentService

random.seed(99)

TITLES = {
    "P1": [
        "Parada total do {system} — produção paralisada",
        "Falha crítica no {system} — sistema indisponível",
        "Interrupção completa no {system}",
        "{system} fora do ar — impacto imediato na operação",
        "Queda total do {system} durante horário de pico",
    ],
    "P2": [
        "Degradação severa de performance no {system}",
        "Erros recorrentes impedindo operação no {system}",
        "Instabilidade grave detectada no {system}",
        "{system} respondendo com falhas intermitentes graves",
        "Lentidão crítica afetando múltiplos usuários no {system}",
    ],
    "P3": [
        "Performance reduzida no {system}",
        "Funcionalidade parcialmente indisponível no {system}",
        "Intermitências reportadas no {system}",
        "{system} com lentidão moderada",
        "Relatórios com atraso no {system}",
    ],
    "P4": [
        "Lentidão pontual reportada no {system}",
        "Funcionalidade menor indisponível no {system}",
        "Alerta de monitoramento no {system}",
        "Pequena anomalia detectada no {system}",
        "Timeout ocasional no {system}",
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
    "Vazamento de memória identificado no processo principal",
    "Deadlock em queries de longa duração",
    "Expiração de token de integração entre sistemas",
    "Backup noturno consumiu I/O excessivo",
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
    "Processo reiniciado e heap memory limpa.",
    "Query otimizada e índice recriado.",
    "Token renovado e pipeline de integração reativado.",
    "Janela de backup reposicionada para fora do horário comercial.",
]

# Q1 2026: 1 Jan → 31 Mar
Q_START = datetime(2026, 1, 1, 7, 0)
Q_END   = datetime(2026, 3, 31, 18, 0)
Q_RANGE_SECS = int((Q_END - Q_START).total_seconds())

PRIORITIES  = ["P1", "P2", "P3", "P4"]
P_WEIGHTS   = [0.07, 0.18, 0.42, 0.33]
DUR_RANGES  = {"P1": (60, 480), "P2": (20, 240), "P3": (10, 120), "P4": (5, 60)}
STATUSES    = ["Aberto", "Em Andamento", "Resolvido"]
# Q1 já encerrou — quase tudo resolvido
S_WEIGHTS   = [0.02, 0.02, 0.96]


def run():
    db = get_db_session()
    try:
        systems = db.query(System).filter(System.active.is_(True)).all()
        types   = db.query(IncidentType).filter(IncidentType.active.is_(True)).all()

        if not systems or not types:
            print("Nenhum sistema ou tipo encontrado. Execute seed_data.py primeiro.")
            return

        svc = IncidentService(db)
        count = 0

        for _ in range(85):
            priority = random.choices(PRIORITIES, weights=P_WEIGHTS)[0]
            status   = random.choices(STATUSES, weights=S_WEIGHTS)[0]
            system   = random.choice(systems)
            itype    = random.choice(types)

            offset   = random.randint(0, Q_RANGE_SECS)
            started  = Q_START + timedelta(seconds=offset)
            started  = started.replace(
                hour=random.randint(6, 21),
                minute=random.choice([0, 15, 30, 45]),
                second=0,
            )

            ended_at = None
            if status == "Resolvido":
                lo, hi   = DUR_RANGES[priority]
                dur_min  = random.randint(lo, hi)
                ended_at = started + timedelta(minutes=dur_min)
                if ended_at > Q_END:
                    ended_at = Q_END - timedelta(minutes=random.randint(5, 30))

            title = random.choice(TITLES[priority]).format(system=system.name)

            svc.create({
                "title":            title,
                "description":      (
                    f"Incidente registrado no {system.name} durante Q1 2026. "
                    f"Tipo: {itype.name}. Prioridade: {priority}."
                ),
                "system_id":        system.id,
                "incident_type_id": itype.id,
                "priority":         priority,
                "status":           status,
                "started_at":       started,
                "ended_at":         ended_at,
                "affected_users":   (
                    random.randint(50, 600) if priority in ("P1", "P2")
                    else random.randint(1, 100)
                ),
                "root_cause":       random.choice(ROOT_CAUSES) if status == "Resolvido" else "",
                "resolution_notes": random.choice(RESOLUTION_NOTES) if status == "Resolvido" else "",
                "created_by":       "seed_quarter",
            })
            count += 1

        print(f"OK: {count} incidentes do Q1 2026 adicionados com sucesso.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
