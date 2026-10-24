#!/usr/bin/env python3
"""Testes locais, sem rede: parser, filtro público, schema dos exemplos."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gerar import mapear_tekto, mapear_vtx, semente
from sanitizar import texto_publico
from tekto_parse import parse_backlog, parse_duvidas
from validar import mensagens

TZ = ZoneInfo("America/Sao_Paulo")
FIX = ROOT / "scripts" / "fixtures"


def test_parser():
    tarefas = parse_backlog((FIX / "backlog.md").read_text(encoding="utf-8"))
    assert len(tarefas) == 4, tarefas
    assert sum(t["feito"] for t in tarefas) == 2, tarefas
    abertas = parse_duvidas((FIX / "duvidas.md").read_text(encoding="utf-8"))
    assert len(abertas) == 1, abertas
    assert "Edição vigente" in abertas[0]["texto"]


def test_filtro():
    assert texto_publico("economia de tokens e entrevista com o cliente")
    assert texto_publico("Processo periódico de revisão")
    assert texto_publico("cliente do Tekto Calc")
    assert texto_publico("R$ 10,00") is None
    assert texto_publico("1.234,56") is None
    assert texto_publico("0001234-56.2026.8.26.0100") is None
    assert texto_publico("contato fulano@example.com") is None
    assert texto_publico("ghp_abc1234567890ABCDEF") is None
    assert texto_publico("cliente João Silva") is None
    assert texto_publico("senha=abc123") is None
    assert texto_publico("CPF 123.456.789-09") is None


def test_exemplos():
    for mid in ("4medco", "dark-channel"):
        doc = semente(mid)
        erros = mensagens(doc, mid)
        assert not erros, erros
        assert doc["exemplo"] is True
        assert "Exemplo" in doc["resumo"]


def test_mapear_tekto():
    hoje = datetime(2026, 10, 24, 18, tzinfo=TZ)
    dados = {
        "atualizado_em": "2026-10-24T15:57:00-03:00",
        "projetos": [{
            "slug": "calc",
            "nome": "Tekto Calc",
            "descricao": "Rotinas de cálculo",
            "estado": "ativo",
            "repo_encontrado": True,
            "total": 2,
            "feitos": 1,
            "areas": [{"nome": "Concreto", "total": 2, "feitos": 1}],
            "proximas": [{"id": "TC-002", "titulo": "Viga contínua"}],
            "entregas": [
                {"numero": 3, "titulo": "Pilar retangular", "data": "2026-10-24T10:00:00-03:00"},
                {"numero": 4, "titulo": "Nota de R$ 50,00", "data": "2026-10-24T09:00:00-03:00"},
            ],
            "ultima_entrega": "2026-10-24T10:00:00-03:00",
            "duvidas": [
                {"texto": "D-001 — Edição vigente da norma"},
                {"texto": "D-009 — escrever para fulano@example.com"},
                {"texto": "Verificação"},
            ],
            "previsao": {
                "situacao": "ativo",
                "ritmo_planejado": 1,
                "ritmo_texto": "1 tarefa/dia",
                "rotina": "diária",
                "planejada": {"data": "2026-10-25", "dias": 1, "concluido": False},
                "real": {"disponivel": False},
            },
        }],
    }
    doc = mapear_tekto(dados, "espelho", hoje)
    erros = mensagens(doc, "tekto")
    assert not erros, erros
    assert [d["id"] for d in doc["aguardando_samuel"]] == ["calc-D-001"]
    assert len(doc["atividade"]) == 1
    assert "50,00" not in json_blob(doc)
    assert doc["fonte"]["tipo"] == "espelho"
    assert any("omitidos" in a for a in doc["avisos"])


def test_mapear_vtx():
    hoje = datetime(2026, 10, 24, 18, tzinfo=TZ)
    dados = {
        "gerado_em": "2026-10-24T13:06:12+00:00",
        "projeto": {
            "nome": "Base de conhecimento",
            "fases": [{"id": "F0", "nome": "Fundação"}],
            "tarefas": [
                {"id": "VTX-001", "titulo": "Fundar o repositório", "fase": "F0", "area": "Base", "status": "concluído", "segredo": "não copiar"},
                {"id": "VTX-002", "titulo": "Próxima tarefa pública", "fase": "F0", "area": "Base", "status": "a fazer"},
                {"id": "VTX-003", "titulo": "Pagar R$ 9,00", "fase": "F0", "area": "Base", "status": "a fazer"},
            ],
        },
        "dias": [{"data": "2026-10-24", "tarefas": [
            {"id": "VTX-001", "titulo": "Fundar o repositório", "status": "concluído"},
        ]}],
    }
    doc = mapear_vtx(dados, "espelho", hoje)
    erros = mensagens(doc, "vtx")
    assert not erros, erros
    assert doc["aguardando_samuel"] == []
    assert doc["projetos"][0]["progresso"]["feitos"] == 1
    assert doc["projetos"][0]["progresso"]["total"] == 2
    blob = json_blob(doc)
    assert "não copiar" not in blob
    assert "R$" not in blob
    assert "segredo" not in blob


def json_blob(doc) -> str:
    import json
    return json.dumps(doc, ensure_ascii=False)


if __name__ == "__main__":
    test_parser()
    test_filtro()
    test_exemplos()
    test_mapear_tekto()
    test_mapear_vtx()
    print("testes ok")
