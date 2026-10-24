"""Filtro do que pode ir para o painel público.

Espelhe as mesmas regras em src/sanitizar.js. O validador recusa o JSON se
algum texto ainda casar com estes padrões; o site também redacta na hora de
exibir, para um commit ruim não pintar segredo na página.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTA = ROOT / "config" / "nao_publicar.txt"

# Padrões que derrubam o item inteiro. Não são palavras soltas: "cliente",
# "processo" e "token" aparecem em títulos já públicos de engenharia e ficam.
RISCO = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:ghp_|gho_|ghu_|ghs_|github_pat_|xox[baprs]-|sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16})"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|senha|password|token|bearer)\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"),
    re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"),
    re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"),
    re.compile(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"),
    re.compile(r"(?i)R\$\s?\d"),
    re.compile(r"(?i)\bUS\$\s?\d"),
    re.compile(r"€\s?\d"),
    re.compile(r"\b\d{1,3}(?:\.\d{3})+,\d{2}\b"),
    re.compile(r"(?i)\b(?:honorários|honorarios|fatura|saldo|pix)\b.{0,40}\d"),
    re.compile(r"(?:\+?55\s?)?\(\d{2}\)\s?\d{4,5}-\d{4}"),
    # "cliente João Silva" ou "cliente: Oficina Norte". Não casa "com o cliente" nem "cliente do Tekto".
    re.compile(r"\b[Cc]lientes?\s*[:\-]\s*[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ú]{2,}"),
    re.compile(
        r"\b[Cc]lientes?\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ú]{2,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ú]{2,})+"
    ),
]


def termos_bloqueados() -> list[str]:
    if not LISTA.exists():
        return []
    termos = []
    for linha in LISTA.read_text(encoding="utf-8").splitlines():
        t = linha.strip()
        if not t or t.startswith("#") or len(t) < 3:
            continue
        termos.append(t.casefold())
    return termos


def arriscado(texto: str, termos: list[str] | None = None) -> bool:
    if any(p.search(texto) for p in RISCO):
        return True
    bloco = termos_bloqueados() if termos is None else termos
    baixo = texto.casefold()
    return any(t in baixo for t in bloco)


def texto_publico(valor, limite: int = 500, termos: list[str] | None = None):
    """Texto limpo, string vazia se não havia nada, ou None se o item deve sair."""
    if valor is None:
        return None
    if not isinstance(valor, str):
        return None
    t = re.sub(r"\s+", " ", valor).strip()
    if not t:
        return ""
    if arriscado(t, termos):
        return None
    if len(t) > limite:
        t = t[: limite - 1].rstrip() + "…"
    return t


def url_publica(valor, termos: list[str] | None = None):
    t = texto_publico(valor, limite=400, termos=termos)
    if not t:
        return None
    if not re.match(r"https?://", t):
        return None
    if re.search(r"(?i)(token|key|secret|senha|password)=", t):
        return None
    return t


def problemas_publicos(valor, caminho: str = "$") -> list[str]:
    achados = []
    if isinstance(valor, str):
        if arriscado(valor):
            achados.append(caminho)
    elif isinstance(valor, dict):
        for chave, item in valor.items():
            achados.extend(problemas_publicos(item, f"{caminho}.{chave}"))
    elif isinstance(valor, list):
        for i, item in enumerate(valor):
            achados.extend(problemas_publicos(item, f"{caminho}[{i}]"))
    return achados
