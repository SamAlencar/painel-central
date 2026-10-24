#!/usr/bin/env python3
"""Valida modulos/*.json contra o schema e o filtro público."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from sanitizar import problemas_publicos

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schema" / "modulo.schema.json").read_text(encoding="utf-8"))
ORDEM = json.loads((ROOT / "config" / "ordem.json").read_text(encoding="utf-8"))
MODULOS = ROOT / "modulos"
VALIDADOR = Draft202012Validator(SCHEMA, format_checker=Draft202012Validator.FORMAT_CHECKER)


def _caminho(erro) -> str:
    partes = []
    for p in erro.absolute_path:
        partes.append(f"[{p}]" if isinstance(p, int) else f".{p}")
    return "$" + "".join(partes) if partes else "$"


def mensagens(doc, nome: str = "modulo") -> list[str]:
    saida = []
    for erro in sorted(VALIDADOR.iter_errors(doc), key=lambda e: list(e.absolute_path)):
        saida.append(f"{nome}: {_caminho(erro)}: {erro.message}")
    for caminho in problemas_publicos(doc):
        saida.append(f"{nome}: conteúdo não público em {caminho} (o valor não é impresso)")
    if not isinstance(doc, dict):
        return saida
    exemplo = doc.get("exemplo")
    fonte = (doc.get("fonte") or {}).get("tipo")
    resumo = doc.get("resumo") or ""
    if exemplo is True and "Exemplo" not in resumo:
        saida.append(f"{nome}: módulo de exemplo precisa da palavra Exemplo no resumo")
    if exemplo is True and fonte != "exemplo":
        saida.append(f"{nome}: exemplo true exige fonte.tipo exemplo")
    if exemplo is False and fonte == "exemplo":
        saida.append(f"{nome}: fonte exemplo não pode estar marcada como dado real")
    vistos = set()
    for item in doc.get("aguardando_samuel") or []:
        iid = item.get("id")
        if iid in vistos:
            saida.append(f"{nome}: id repetido na fila: {iid}")
        vistos.add(iid)
    projetos = set()
    for projeto in doc.get("projetos") or []:
        pid = projeto.get("id")
        if pid in projetos:
            saida.append(f"{nome}: projeto repetido: {pid}")
        projetos.add(pid)
        for bloco in (projeto.get("progresso"),):
            if isinstance(bloco, dict) and bloco.get("feitos", 0) > bloco.get("total", 0):
                saida.append(f"{nome}: {pid} tem mais feitos do que o total")
        for frente in projeto.get("frentes") or []:
            if frente.get("feitos", 0) > frente.get("total", 0):
                saida.append(f"{nome}: frente {frente.get('nome')} passa do total")
    return saida


def validar_arquivos() -> list[str]:
    global ORDEM
    ORDEM = json.loads((ROOT / "config" / "ordem.json").read_text(encoding="utf-8"))
    arquivos = sorted(MODULOS.glob("*.json"))
    ids = []
    erros = []
    if not arquivos:
        return ["nenhum arquivo em modulos/"]
    for arq in arquivos:
        try:
            doc = json.loads(arq.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            erros.append(f"{arq.name}: JSON inválido ({exc})")
            continue
        if isinstance(doc, dict) and doc.get("id") != arq.stem:
            erros.append(f"{arq.name}: id {doc.get('id')!r} não bate com o arquivo")
        erros.extend(mensagens(doc, arq.name))
        if isinstance(doc, dict) and doc.get("id"):
            ids.append(doc["id"])
    if set(ids) != set(ORDEM) or len(ids) != len(ORDEM):
        faltam = [i for i in ORDEM if i not in ids]
        sobram = [i for i in ids if i not in ORDEM]
        if faltam:
            erros.append("faltam módulos de config/ordem.json: " + ", ".join(faltam))
        if sobram:
            erros.append("módulos fora de config/ordem.json: " + ", ".join(sobram))
        if len(ids) != len(set(ids)):
            erros.append("há ids de módulo repetidos")
    return erros


def main() -> int:
    erros = validar_arquivos()
    if erros:
        for linha in erros:
            print(linha, file=sys.stderr)
        print(f"{len(erros)} problema(s).", file=sys.stderr)
        return 1
    print(f"{len(ORDEM)} módulos válidos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
