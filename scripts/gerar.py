#!/usr/bin/env python3
"""Monta modulos/*.json e o PAINEL.md.

Tekto e VTX vêm da API do GitHub quando `gh` está autenticado ou há
GITHUB_TOKEN/GH_TOKEN. Sem token, usam o espelho público já sanitizado
(tekto-calc-painel e vtx_painel). Pub usa só metadados do repositório público.

4medco e Dar, se aparecerem na listagem, entram só com nome, descrição e data
de push — o gerador não lê arquivo, issue nem comentário.

Módulos com fonte.tipo manual nunca são reescritos. Exemplos só são reescritos
com --semear, ou quando a descoberta passa a achar repositório de verdade.

Uso:
  python3 scripts/gerar.py
  python3 scripts/gerar.py --semear
  python3 scripts/gerar.py --somente tekto,vtx
  python3 scripts/gerar.py --somente-painel
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import tekto_parse
from sanitizar import texto_publico, url_publica
from validar import mensagens, validar_arquivos

ROOT = Path(__file__).resolve().parents[1]
MODULOS = ROOT / "modulos"
ORDEM = json.loads((ROOT / "config" / "ordem.json").read_text(encoding="utf-8"))
TZ = ZoneInfo("America/Sao_Paulo")
SCHEMA_REF = "../schema/modulo.schema.json"
TEKTO_ESPELHO = "https://raw.githubusercontent.com/SamAlencar/tekto-calc-painel/main/data.json"
VTX_ESPELHO = "https://raw.githubusercontent.com/SamAlencar/vtx_painel/main/data/backlog.json"
SLUG_REPO = {p["slug"]: p["repo"] for p in tekto_parse.PROJETOS}
RE_DATA = re.compile(r"\((20\d{2}-\d{2}-\d{2})\)\s*$")
RE_ID = re.compile(r"\b([A-Z]{1,6}-\d{1,4})\b")
GENERICO = re.compile(r"(?i)^(?:verifica(?:ção|cao)|geral|notas|introdução|introducao)$")


class Filtro:
    def __init__(self):
        self.omitidos = 0

    def txt(self, valor, limite=180):
        if not isinstance(valor, str) or not valor.strip():
            return None
        out = texto_publico(valor, limite=limite)
        if out is None:
            self.omitidos += 1
        return out or None

    def url(self, valor):
        if not isinstance(valor, str) or not valor.strip():
            return None
        out = url_publica(valor)
        if out is None and valor.strip():
            self.omitidos += 1
        return out


class ClienteGitHub:
    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        self.modo = "gh" if _gh_autenticado() else ("token" if self.token else "publico")
        self._repos = None

    def get(self, path: str, raw: bool = False):
        if self.modo == "gh":
            return _gh_api(path, raw)
        return _http_api(path, raw, self.token)

    def repos(self) -> list[dict]:
        if self._repos is not None:
            return self._repos
        if self.modo == "publico":
            data = self.get("users/SamAlencar/repos?per_page=100&type=owner") or []
        else:
            data = []
            for page in range(1, 11):
                batch = self.get(f"user/repos?per_page=100&page={page}&affiliation=owner") or []
                if not isinstance(batch, list) or not batch:
                    break
                data.extend(batch)
                if len(batch) < 100:
                    break
        self._repos = data if isinstance(data, list) else []
        return self._repos


def _gh_autenticado() -> bool:
    if not shutil.which("gh"):
        return False
    r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
    return r.returncode == 0


def _gh_api(path: str, raw: bool):
    cmd = ["gh", "api", path]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or "") + (r.stdout or "")
        if "404" in err or "Not Found" in err:
            return None
        raise RuntimeError(err.strip()[:400])
    if raw:
        return r.stdout
    return json.loads(r.stdout) if r.stdout.strip() else None


def _http_api(path: str, raw: bool, token: str):
    req = urllib.request.Request(
        "https://api.github.com/" + path.lstrip("/"),
        headers={
            "User-Agent": "painel-central",
            "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        detalhe = exc.read().decode("utf-8", "replace")[:180]
        raise RuntimeError(f"GitHub {exc.code} em {path}: {detalhe}") from exc
    if raw:
        return body
    return json.loads(body) if body.strip() else None


def baixar(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "painel-central"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


def instante(iso):
    if not iso:
        return None
    dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.isoformat(timespec="seconds")


def idade_dias(iso, hoje) -> float | None:
    if not iso:
        return None
    dt = datetime.fromisoformat(instante(iso))
    dias = (hoje - dt).total_seconds() / 86400
    return max(0.0, dias)


def data_curta(iso) -> str:
    if not iso:
        return "sem data"
    ano, mes, dia = str(iso)[:10].split("-")
    return f"{dia}/{mes}/{ano}"


def pct(feitos, total) -> float:
    if not total:
        return 0
    return round(100 * feitos / total, 1)


def pct_txt(n) -> str:
    if float(n).is_integer():
        return str(int(n))
    return f"{n:.1f}".replace(".", ",")


def gravar(doc: dict):
    caminho = MODULOS / f"{doc['id']}.json"
    caminho.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def carregar(mid: str):
    caminho = MODULOS / f"{mid}.json"
    if not caminho.exists():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))


def base(mid, nome, agente, resumo, exemplo, fonte_tipo, fonte_detalhe, status, motivo, atualizado, projetos, prazos, rotinas, fila, atividade, links, avisos):
    return {
        "$schema": SCHEMA_REF,
        "id": mid,
        "nome": nome,
        "agente": {"id": agente[0], "nome": agente[1], "papel": agente[2]},
        "resumo": resumo,
        "exemplo": exemplo,
        "fonte": {"tipo": fonte_tipo, "detalhe": fonte_detalhe},
        "status": status,
        "saude": {"motivo": motivo},
        "atualizado_em": atualizado,
        "projetos": projetos,
        "prazos": prazos,
        "rotinas": rotinas,
        "aguardando_samuel": fila,
        "atividade": atividade,
        "links": links,
        "avisos": avisos,
    }


def projeto_vazio(pid, nome, descricao, repo=None):
    return {
        "id": pid,
        "nome": nome,
        "repo": repo,
        "url": f"https://github.com/{repo}" if repo else None,
        "descricao": descricao,
        "status": "preparacao",
        "saude": "planejado",
        "saude_motivo": "Exemplo — fonte ainda não conectada.",
        "progresso": None,
        "ultima_atividade": None,
        "nota": "Exemplo — sem leitura de arquivos.",
        "frentes": [],
        "destaques": [],
    }


def rotina_exemplo(nome="Exemplo — rotina ainda não ligada"):
    return {
        "nome": nome,
        "frequencia": "a definir",
        "ultima_execucao": None,
        "status": "desconhecida",
        "nota": "Exemplo — nenhuma execução real.",
    }


def fila_exemplo(iid, titulo, detalhe, projeto_id):
    return {
        "id": iid,
        "titulo": titulo,
        "detalhe": detalhe,
        "desde": None,
        "projeto_id": projeto_id,
        "urgencia": "baixa",
        "tipo": "exemplo",
        "link": None,
    }


def semente(mid: str) -> dict:
    aviso = ["Dados de exemplo. Não representam pedidos reais ao Samuel."]
    comum = dict(exemplo=True, fonte_tipo="exemplo", atualizado=None, prazos=[], atividade=[], status="planejado")
    if mid == "4medco":
        return base(
            "4medco", "4medco", ("bil", "Bil", "Produtos e operação da 4medco"),
            "Exemplo — frente da 4medco sem repositórios 4medco-* visíveis nesta leitura. Nenhum dado de paciente, clínica ou contrato entra neste painel.",
            fonte_detalhe="Semente ilustrativa. O gerador troca este arquivo se a API listar repositórios com prefixo 4medco-, e mesmo assim só grava metadados.",
            motivo="Exemplo — o gerador ainda não encontrou repositórios com prefixo 4medco-.",
            projetos=[projeto_vazio("4medco", "4medco", "Exemplo — família de repositórios com prefixo 4medco-*. O conteúdo dos arquivos não é lido.")],
            rotinas=[rotina_exemplo()],
            fila=[fila_exemplo("ex-4medco-1", "Exemplo — revisão de texto institucional", "O conteúdo fica de fora de propósito: este painel não publica material de paciente, clínica ou contrato.", "4medco")],
            links=[], avisos=aviso, **comum,
        )
    if mid == "dar":
        repos = ("dark-channel-playbook", "engenharia-explicada")
        return base(
            "dar", "Dar", ("dar", "Dar", "Canais e publicação"),
            "Exemplo — canais dark-channel-playbook e engenharia-explicada sem metadados visíveis. Sem audiência, receita ou anunciante.",
            fonte_detalhe="Semente ilustrativa até a API enxergar esses repositórios. A coleta futura é só de metadados.",
            motivo="Exemplo — repositórios previstos ainda não apareceram na listagem pública.",
            projetos=[
                projeto_vazio("dark-channel-playbook", "Dark channel playbook", "Exemplo — playbook do canal. Sem números de audiência ou receita.", f"SamAlencar/{repos[0]}"),
                projeto_vazio("engenharia-explicada", "Engenharia explicada", "Exemplo — canal de engenharia explicada. Sem pauta real nem anunciante.", f"SamAlencar/{repos[1]}"),
            ],
            rotinas=[rotina_exemplo("Exemplo — pauta da semana")],
            fila=[fila_exemplo("ex-dar-1", "Exemplo — pauta ilustrativa da semana", "Sem título real de vídeo, sem métrica e sem anunciante.", "dark-channel-playbook")],
            links=[{"rotulo": f"Repositório previsto · {nome}", "url": f"https://github.com/SamAlencar/{nome}"} for nome in repos],
            avisos=aviso, **comum,
        )
    if mid == "jur":
        return base(
            "jur", "Jur", ("jur", "Jur", "Rotinas jurídicas"),
            "Exemplo — o painel público só mostra que existe rotina jurídica, nunca o conteúdo.",
            fonte_detalhe="Semente ilustrativa. Não há repositório ligado e nenhum documento é lido.",
            motivo="Exemplo — frente jurídica sem fonte automática, de propósito.",
            projetos=[projeto_vazio("rotina", "Rotina jurídica", "Exemplo — existência da rotina, sem peça, parte ou número.")],
            rotinas=[rotina_exemplo("Exemplo — leitura da fila jurídica")],
            fila=[fila_exemplo("ex-jur-1", "Exemplo — item de leitura pendente", "Peças, partes e números ficam de fora. Quando houver dado real, grave só o tipo da pendência.", "rotina")],
            links=[], avisos=aviso, **comum,
        )
    if mid == "fin":
        return base(
            "fin", "Fin / Pow", ("fin", "Fin/Pow", "Rotinas financeiras"),
            "Exemplo — o painel público não mostra valores, contas, notas nem instituições.",
            fonte_detalhe="Semente ilustrativa. Nenhum extrato ou planilha é lido.",
            motivo="Exemplo — frente financeira sem fonte automática, de propósito.",
            projetos=[projeto_vazio("rotina", "Rotina financeira", "Exemplo — existência da rotina, sem lançamento e sem valor.")],
            rotinas=[rotina_exemplo("Exemplo — conciliação periódica")],
            fila=[fila_exemplo("ex-fin-1", "Exemplo — conciliação periódica pendente", "Valores, contas e instituições ficam de fora. O painel só pode dizer que a rotina existe.", "rotina")],
            links=[], avisos=aviso, **comum,
        )
    if mid == "stu":
        return base(
            "stu", "Stu", ("stu", "Stu", "STUQUI e estudos no SESI-SENAI"),
            "Exemplo — rotina de estudo do STUQUI e do SESI-SENAI. Sem nomes de alunos, notas ou documentos.",
            fonte_detalhe="Semente ilustrativa. Nenhum boletim ou lista de presença é lido.",
            motivo="Exemplo — estudos sem fonte automática.",
            projetos=[
                projeto_vazio("stuqui", "STUQUI", "Exemplo — rotina do STUQUI, sem aluno e sem nota."),
                projeto_vazio("sesi-senai", "SESI-SENAI", "Exemplo — estudos no SESI-SENAI, sem turma real e sem documento."),
            ],
            rotinas=[rotina_exemplo("Exemplo — checkpoint de estudo")],
            fila=[fila_exemplo("ex-stu-1", "Exemplo — checkpoint ilustrativo de estudo", "Sem disciplina real, sem nota e sem nome de aluno.", "stuqui")],
            links=[], avisos=aviso, **comum,
        )
    if mid == "mar":
        return base(
            "mar", "Mar", ("mar", "Mar", "Marketing"),
            "Exemplo — calendário de peças ainda ilustrativo. Sem verba, mídia paga ou lista de contatos.",
            fonte_detalhe="Semente ilustrativa. Nenhuma campanha ou audiência é lida.",
            motivo="Exemplo — marketing sem fonte automática.",
            projetos=[projeto_vazio("calendario", "Calendário de peças", "Exemplo — calendário ilustrativo, sem campanha real.")],
            rotinas=[rotina_exemplo("Exemplo — revisão do calendário")],
            fila=[fila_exemplo("ex-mar-1", "Exemplo — peça ilustrativa aguardando um olhar", "Sem nome de campanha, sem verba e sem lista de contatos.", "calendario")],
            links=[], avisos=aviso, **comum,
        )
    if mid == "sys":
        return base(
            "sys", "Sys", ("sys", "Sys", "TI e infraestrutura"),
            "Exemplo — rotinas de casa de máquinas. Sem nomes de servidor, usuários ou credenciais.",
            fonte_detalhe="Semente ilustrativa. Inventário, log e segredo não são lidos.",
            motivo="Exemplo — TI sem fonte automática.",
            projetos=[projeto_vazio("casa", "Casa de máquinas", "Exemplo — rotina de infraestrutura, sem host e sem credencial.")],
            rotinas=[rotina_exemplo("Exemplo — checagem de backup")],
            fila=[fila_exemplo("ex-sys-1", "Exemplo — checagem ilustrativa de backup", "Sem nome de servidor, sem usuário e sem segredo.", "casa")],
            links=[], avisos=aviso, **comum,
        )
    if mid == "tzu":
        return base(
            "tzu", "Tzu", ("tzu", "Tzu", "Pessoal: e-mail, agenda e faculdade"),
            "Exemplo — e-mail, agenda e faculdade Uninter. O painel público não mostra mensagens, compromissos reais nem dados acadêmicos.",
            fonte_detalhe="Semente ilustrativa. Caixa de entrada, agenda e portal da faculdade não são lidos.",
            motivo="Exemplo — frente pessoal sem fonte automática, de propósito.",
            projetos=[
                projeto_vazio("email", "E-mail", "Exemplo — triagem da caixa. Sem remetente, assunto ou corpo."),
                projeto_vazio("agenda", "Agenda", "Exemplo — existência da agenda. Sem horário real, local ou convidado."),
                projeto_vazio("uninter", "Uninter", "Exemplo — estudos na Uninter. Sem matrícula, disciplina ou nota."),
            ],
            rotinas=[rotina_exemplo("Exemplo — triagem de e-mail e agenda")],
            fila=[
                fila_exemplo("ex-tzu-email", "Exemplo — triagem da caixa de entrada", "Sem remetente, assunto ou corpo de mensagem.", "email"),
                fila_exemplo("ex-tzu-agenda", "Exemplo — compromisso ilustrativo na agenda", "Horário, local e convidados são fictícios e não devem ser preenchidos com dado real.", "agenda"),
                fila_exemplo("ex-tzu-uninter", "Exemplo — entrega ilustrativa de estudo", "Sem disciplina, nota ou matrícula.", "uninter"),
            ],
            links=[], avisos=aviso, **comum,
        )
    raise KeyError(mid)


def saude_por_idade(iso, hoje, frase):
    dias = idade_dias(iso, hoje)
    data = data_curta(iso)
    if dias is None:
        return "planejado", "Sem data de atividade."
    if dias > 30:
        return "parado", f"{frase} em {data}."
    if dias > 7:
        return "atencao", f"{frase} em {data}."
    return "saudavel", f"{frase} em {data}."


def pior(niveis: list[str]) -> str:
    ordem = {"saudavel": 0, "planejado": 1, "atencao": 2, "parado": 3, "bloqueado": 4}
    return max(niveis, key=lambda n: ordem[n])


def status_rotina(codigo: str, ultima, hoje) -> str:
    dias = idade_dias(ultima, hoje)
    if dias is None:
        return "desconhecida"
    limite = 8 if codigo == "semanal" else 3
    return "em_dia" if dias <= limite else "atrasada"


def mapear_tekto(dados: dict, origem: str, hoje=None) -> dict:
    filtro = Filtro()
    hoje = hoje or datetime.now(TZ)
    projetos = []
    prazos = []
    rotinas = []
    fila = []
    eventos = []
    vistos = set()
    for bruto in dados.get("projetos") or []:
        slug = bruto.get("slug") or "projeto"
        repo = SLUG_REPO.get(slug)
        nome = filtro.txt(bruto.get("nome"), 80) or slug
        descricao = filtro.txt(bruto.get("descricao"), 300) or "Sem descrição publicada."
        if not bruto.get("repo_encontrado", True):
            psaude, pmotivo = "bloqueado", "Repositório não encontrado na leitura."
            estado = "indisponivel"
        elif not bruto.get("total"):
            psaude, pmotivo = "planejado", "Backlog ainda sem tarefas."
            estado = "preparacao"
        else:
            psaude, pmotivo = saude_por_idade(bruto.get("ultima_entrega"), hoje, "Entrega")
            prev = bruto.get("previsao") or {}
            real = prev.get("real") or {}
            plano = float(prev.get("ritmo_planejado") or 0)
            if psaude == "saudavel" and real.get("disponivel") and plano and float(real.get("tarefas_por_dia") or 0) < 0.5 * plano:
                psaude = "atencao"
                pmotivo = f"Ritmo medido abaixo da metade do planejado. Última entrega em {data_curta(bruto.get('ultima_entrega'))}."
            estado = "ativo" if bruto.get("estado") == "ativo" else "preparacao"
        feitos = int(bruto.get("feitos") or 0)
        total = int(bruto.get("total") or 0)
        frentes = []
        areas = sorted(bruto.get("areas") or [], key=lambda a: a.get("total") or 0, reverse=True)
        for area in areas[:12]:
            titulo = filtro.txt(area.get("nome"), 80)
            if not titulo:
                continue
            ft = int(area.get("total") or 0)
            ff = min(int(area.get("feitos") or 0), ft)
            frentes.append({"nome": titulo, "feitos": ff, "total": ft, "percentual": pct(ff, ft)})
        destaques = []
        for tarefa in bruto.get("proximas") or []:
            texto = filtro.txt(tarefa.get("titulo"), 160)
            if not texto:
                continue
            ident = filtro.txt(tarefa.get("id"), 40) if tarefa.get("id") else None
            destaques.append({"id": ident, "texto": texto})
            if len(destaques) == 4:
                break
        nota_partes = []
        prev = bruto.get("previsao") or {}
        ritmo = filtro.txt(prev.get("ritmo_texto"), 80)
        if ritmo:
            nota_partes.append(f"Ritmo planejado: {ritmo}.")
        plan = prev.get("planejada") or {}
        if plan.get("data") and not plan.get("concluido"):
            nota_partes.append(f"Previsão de término: {plan['data']}.")
            prazos.append({
                "id": f"{slug}-previsao",
                "titulo": f"Previsão de término no ritmo planejado — {nome}",
                "data": plan["data"],
                "projeto_id": slug,
                "tipo": "previsao",
            })
        freq = prev.get("rotina") or "diária"
        codigo = "semanal" if "seman" in freq else "diaria"
        if total:
            rotinas.append({
                "nome": f"Backlog do {nome}",
                "frequencia": "semanal" if codigo == "semanal" else "diária",
                "ultima_execucao": instante(bruto.get("ultima_entrega")),
                "status": status_rotina(codigo, bruto.get("ultima_entrega"), hoje),
                "nota": ritmo,
            })
        for i, duvida in enumerate(bruto.get("duvidas") or []):
            texto = (duvida.get("texto") or "").strip()
            if not texto or GENERICO.fullmatch(texto):
                continue
            desde = None
            mdata = RE_DATA.search(texto)
            if mdata:
                desde = mdata.group(1)
                texto = texto[: mdata.start()].rstrip()
            titulo = filtro.txt(texto, 180)
            if not titulo or len(titulo) < 12:
                continue
            acha = RE_ID.search(titulo)
            iid = f"{slug}-{acha.group(1) if acha else i + 1}"
            n = 2
            base_id = iid
            while iid in vistos:
                iid = f"{base_id}-{n}"
                n += 1
            vistos.add(iid)
            fila.append({
                "id": iid,
                "titulo": titulo,
                "detalhe": None,
                "desde": desde,
                "projeto_id": slug,
                "urgencia": "alta" if re.search(r"(?i)urgente|bloque", titulo) else "media",
                "tipo": "duvida",
                "link": None,
            })
        for entrega in bruto.get("entregas") or []:
            titulo = filtro.txt(entrega.get("titulo"), 160)
            if not titulo or not entrega.get("data"):
                continue
            eventos.append((entrega["data"], nome, slug, titulo, entrega.get("numero"), repo))
        projetos.append({
            "id": slug,
            "nome": nome,
            "repo": repo,
            "url": f"https://github.com/{repo}" if repo else None,
            "descricao": descricao,
            "status": estado,
            "saude": psaude,
            "saude_motivo": pmotivo,
            "progresso": {"feitos": feitos, "total": total, "percentual": pct(feitos, total)} if total else None,
            "ultima_atividade": instante(bruto.get("ultima_entrega")),
            "nota": " ".join(nota_partes) or None,
            "frentes": frentes,
            "destaques": destaques,
        })
    eventos.sort(key=lambda e: e[0], reverse=True)
    atividade = []
    for quando, nome, slug, titulo, numero, repo in eventos[:12]:
        resumo = filtro.txt(f"Mesclou em {nome}: {titulo}", 220) or f"Mesclou uma entrega em {nome}."
        link = f"https://github.com/{repo}/pull/{numero}" if repo and numero else None
        atividade.append({"quando": instante(quando), "resumo": resumo, "projeto_id": slug, "link": link})
    fila.sort(key=lambda item: ({"alta": 0, "media": 1, "baixa": 2}[item["urgencia"]], item["desde"] or "9999-99-99", item["id"]))
    prazos.sort(key=lambda item: item["data"] or "9999-99-99")
    feitos = sum((p["progresso"] or {}).get("feitos", 0) for p in projetos)
    total = sum((p["progresso"] or {}).get("total", 0) for p in projetos)
    ultima = max((p["ultima_atividade"] for p in projetos if p["ultima_atividade"]), default=None)
    niveis = [p["saude"] for p in projetos] or ["planejado"]
    status = pior(niveis)
    if len(fila) >= 15 and status == "saudavel":
        status = "atencao"
    if status == "atencao" and len(fila) >= 15:
        motivo = (
            f"Há {len(fila)} dúvidas abertas nos backlogs. "
            f"A última entrega da frente foi em {data_curta(ultima)}."
        )
    else:
        motivo = next((p["saude_motivo"] for p in projetos if p["saude"] == status), "Sem leitura de saúde.")
    resumo = (
        f"{len(projetos)} repositórios de engenharia. "
        f"{feitos} de {total} tarefas concluídas ({pct_txt(pct(feitos, total))}%). "
        f"{len(fila)} dúvidas de backlog seguem abertas."
    )
    if origem == "github":
        fonte = ("github", "Lido via API do GitHub: docs/BACKLOG.md, docs/DUVIDAS.md e PRs mesclados. Só entram contagens, títulos curtos e datas.")
    else:
        fonte = ("espelho", "Espelho do painel público tekto-calc-painel/data.json. Com gh autenticado, a leitura passa a ser direta nos repositórios.")
    avisos = []
    if origem != "github":
        avisos.append("Sem token do GitHub nesta execução. Os números vêm do painel público, que já é um resumo.")
    if any(len(p.get("areas") or []) > 12 for p in dados.get("projetos") or []):
        avisos.append("Cada projeto mostra no máximo 12 frentes, as de maior volume.")
    if filtro.omitidos:
        avisos.append(f"{filtro.omitidos} trechos omitidos pelo filtro público.")
    links = [
        {"rotulo": "Painel Tekto (legado)", "url": "https://samalencar.github.io/tekto-calc-painel/"},
        {"rotulo": "Repositório do painel legado", "url": "https://github.com/SamAlencar/tekto-calc-painel"},
    ]
    for projeto in projetos:
        if projeto["url"]:
            links.append({"rotulo": projeto["nome"], "url": projeto["url"]})
    return base(
        "tekto", "Tekto", ("tek", "Eng/Tek", "Engenharia: cálculo, documento, modelo e estúdio"),
        resumo, False, fonte[0], fonte[1], status, motivo,
        instante(dados.get("atualizado_em")) or ultima,
        projetos, prazos, rotinas, fila, atividade, links[:20], avisos,
    )


def _tarefas_vtx(dados, filtro):
    projeto = dados.get("projeto") if isinstance(dados.get("projeto"), dict) else {}
    brutas = projeto.get("tarefas") if projeto.get("tarefas") else []
    if not brutas:
        vistos = {}
        for dia in dados.get("dias") or []:
            for tarefa in dia.get("tarefas") or []:
                if isinstance(tarefa, dict) and tarefa.get("id"):
                    vistos[tarefa["id"]] = tarefa
        brutas = list(vistos.values())
    saida = []
    for tarefa in brutas:
        if not isinstance(tarefa, dict):
            continue
        titulo = filtro.txt(tarefa.get("titulo"), 160)
        if not titulo:
            continue
        status = tarefa.get("status") if tarefa.get("status") in ("a fazer", "em andamento", "concluído") else "a fazer"
        saida.append({
            "id": filtro.txt(str(tarefa.get("id") or ""), 40) or "",
            "titulo": titulo,
            "area": filtro.txt(tarefa.get("area"), 80) or "Geral",
            "fase": filtro.txt(str(tarefa.get("fase") or ""), 20) or "",
            "status": status,
        })
    fases = {}
    for fase in projeto.get("fases") or []:
        if isinstance(fase, dict) and fase.get("id"):
            nome = filtro.txt(fase.get("nome"), 80)
            if nome:
                fases[str(fase["id"])] = nome
    return saida, fases


def mapear_vtx(dados: dict, origem: str, hoje=None) -> dict:
    filtro = Filtro()
    hoje = hoje or datetime.now(TZ)
    tarefas, fases = _tarefas_vtx(dados, filtro)
    feitos = sum(t["status"] == "concluído" for t in tarefas)
    total = len(tarefas)
    grupos = {}
    for tarefa in tarefas:
        chave = fases.get(tarefa["fase"]) or tarefa["area"] or "Geral"
        g = grupos.setdefault(chave, {"nome": chave, "feitos": 0, "total": 0})
        g["total"] += 1
        g["feitos"] += tarefa["status"] == "concluído"
    frentes = []
    for grupo in sorted(grupos.values(), key=lambda g: g["total"], reverse=True)[:12]:
        frentes.append({**grupo, "percentual": pct(grupo["feitos"], grupo["total"])})
    destaques = []
    for tarefa in tarefas:
        if tarefa["status"] == "concluído":
            continue
        destaques.append({"id": tarefa["id"] or None, "texto": tarefa["titulo"]})
        if len(destaques) == 4:
            break
    dias = sorted(dados.get("dias") or [], key=lambda d: d.get("data") or "", reverse=True)
    ultima_data = dias[0]["data"] if dias else None
    gerado = instante(dados.get("gerado_em"))
    ultima = gerado if gerado and ultima_data and gerado[:10] == ultima_data else (f"{ultima_data}T12:00:00-03:00" if ultima_data else gerado)
    atividade = []
    for dia in dias:
        for tarefa in dia.get("tarefas") or []:
            if not isinstance(tarefa, dict) or tarefa.get("status") != "concluído":
                continue
            titulo = filtro.txt(tarefa.get("titulo"), 140)
            ident = filtro.txt(str(tarefa.get("id") or ""), 40)
            if not titulo:
                continue
            resumo = filtro.txt(f"Concluiu {ident + ' — ' if ident else ''}{titulo}", 220)
            if not resumo:
                continue
            atividade.append({
                "quando": f"{dia['data']}T12:00:00-03:00",
                "resumo": resumo,
                "projeto_id": "vtx-core",
                "link": None,
            })
            if len(atividade) == 12:
                break
        if len(atividade) == 12:
            break
    psaude, pmotivo = saude_por_idade(ultima, hoje, "Rotina diária")
    nome_proj = filtro.txt((dados.get("projeto") or {}).get("nome") if isinstance(dados.get("projeto"), dict) else None, 120)
    descricao = nome_proj or "Base de conhecimento e operação da VTX."
    projeto = {
        "id": "vtx-core",
        "nome": "VTX Core",
        "repo": "SamAlencar/vtx-core",
        "url": "https://github.com/SamAlencar/vtx-core",
        "descricao": descricao,
        "status": "ativo" if total else "preparacao",
        "saude": psaude,
        "saude_motivo": pmotivo,
        "progresso": {"feitos": feitos, "total": total, "percentual": pct(feitos, total)} if total else None,
        "ultima_atividade": ultima,
        "nota": "Tarefas de construir a fila de aprovação não entram como pedido ao Samuel.",
        "frentes": frentes,
        "destaques": destaques,
    }
    rotinas = []
    if ultima:
        rotinas.append({
            "nome": "Backlog diário da VTX",
            "frequencia": "diária",
            "ultima_execucao": ultima,
            "status": status_rotina("diaria", ultima, hoje),
            "nota": "Conclusões do dia no backlog público.",
        })
    if origem == "github":
        fonte = ("github", "Lido via API em SamAlencar/vtx-core. Só entram id, título, área, fase e status.")
    else:
        fonte = ("espelho", "Espelho do painel público vtx_painel/data/backlog.json. Só entram id, título, área, fase e status.")
    avisos = ["Nenhum item do backlog está marcado como aprovação pendente do Samuel."]
    if origem != "github":
        avisos.insert(0, "Sem token do GitHub nesta execução. Os números vêm do painel público, que já é um resumo.")
    if filtro.omitidos:
        avisos.append(f"{filtro.omitidos} trechos omitidos pelo filtro público.")
    resumo = (
        f"{descricao.rstrip('.')}. {feitos} de {total} tarefas concluídas. "
        f"A rotina diária tem registro em {data_curta(ultima)}."
    )
    links = [
        {"rotulo": "Painel VTX (legado)", "url": "https://samalencar.github.io/vtx_painel/"},
        {"rotulo": "Repositório do painel legado", "url": "https://github.com/SamAlencar/vtx_painel"},
        {"rotulo": "vtx-core", "url": "https://github.com/SamAlencar/vtx-core"},
    ]
    return base(
        "vtx", "VTX", ("vix", "Vix", "Operação da VTX, empresa de TI tocada por agentes"),
        resumo, False, fonte[0], fonte[1], psaude, pmotivo, gerado or ultima,
        [projeto], [], rotinas, [], atividade, links, avisos,
    )


def produzir_tekto(gh: ClienteGitHub, hoje):
    if gh.modo != "publico":
        try:
            tekto_parse.usar_github(lambda path, raw=False: gh.get(path, raw=raw))
            dados = tekto_parse.coletar()
            dados["atualizado_em"] = datetime.now(TZ).isoformat(timespec="seconds")
            if any(p.get("repo_encontrado") for p in dados.get("projetos") or []):
                return mapear_tekto(dados, "github", hoje)
        except Exception as exc:
            print(f"aviso: leitura direta da Tekto falhou ({exc}); usando o espelho público.")
    return mapear_tekto(json.loads(baixar(TEKTO_ESPELHO)), "espelho", hoje)


def produzir_vtx(gh: ClienteGitHub, hoje):
    if gh.modo != "publico":
        for caminho in ("data/backlog.json", "backlog.json", "docs/backlog.json"):
            raw = gh.get(f"repos/SamAlencar/vtx-core/contents/{caminho}", raw=True)
            if not raw:
                continue
            try:
                dados = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(dados, dict) and ("projeto" in dados or "dias" in dados):
                return mapear_vtx(dados, "github", hoje)
    return mapear_vtx(json.loads(baixar(VTX_ESPELHO)), "espelho", hoje)


def produzir_pub(gh: ClienteGitHub, hoje):
    info = gh.get("repos/SamAlencar/pub-policy")
    if not isinstance(info, dict):
        return None
    pushed = instante(info.get("pushed_at"))
    saude, motivo = saude_por_idade(pushed, hoje, "Último push")
    links = [{"rotulo": "Repositório", "url": info.get("html_url") or "https://github.com/SamAlencar/pub-policy"}]
    homepage = url_publica(info.get("homepage") or "")
    if homepage and homepage != links[0]["url"]:
        links.append({"rotulo": "Página", "url": homepage})
    projeto = {
        "id": "pub-policy",
        "nome": "Pub",
        "repo": "SamAlencar/pub-policy",
        "url": links[0]["url"],
        "descricao": "Página pública com a política de privacidade do Pub. O texto da política não é copiado para cá.",
        "status": "ativo",
        "saude": saude,
        "saude_motivo": motivo,
        "progresso": None,
        "ultima_atividade": pushed,
        "nota": "Sem backlog ligado a este painel.",
        "frentes": [],
        "destaques": [],
    }
    atividade = []
    if pushed:
        atividade.append({
            "quando": pushed,
            "resumo": "Atualizou a página pública da política de privacidade.",
            "projeto_id": "pub-policy",
            "link": links[0]["url"],
        })
    return base(
        "pub", "Pub", ("pub", "Pub", "Política de privacidade do Pub"),
        "Política de privacidade do Pub publicada no GitHub. Sem fila e sem rotina cadastradas neste painel.",
        False, "github",
        "Metadados públicos de SamAlencar/pub-policy. O HTML da política não é copiado.",
        saude, motivo, pushed, [projeto], [], [], [], atividade, links,
        ["Nenhuma rotina foi inferida: o repositório público só tem a página da política."],
    )


def produzir_descoberta(gh: ClienteGitHub, hoje, mid, nome, agente, prefixo=None, nomes=None):
    achados = []
    for repo in gh.repos():
        nome_repo = repo.get("name") or ""
        if nomes and nome_repo in nomes:
            achados.append(repo)
        elif prefixo and nome_repo.startswith(prefixo):
            achados.append(repo)
    if not achados:
        return None
    filtro = Filtro()
    projetos = []
    for repo in sorted(achados, key=lambda r: r.get("name") or ""):
        desc = filtro.txt(repo.get("description") or "", 300) or "Sem descrição pública."
        pushed = instante(repo.get("pushed_at"))
        saude, motivo = saude_por_idade(pushed, hoje, "Último push")
        full = repo.get("full_name") or f"SamAlencar/{repo.get('name')}"
        url = url_publica(repo.get("html_url") or "") or f"https://github.com/{full}"
        projetos.append({
            "id": (repo.get("name") or "repo").lower(),
            "nome": repo.get("name") or "repo",
            "repo": full,
            "url": url,
            "descricao": desc,
            "status": "ativo",
            "saude": saude,
            "saude_motivo": motivo,
            "progresso": None,
            "ultima_atividade": pushed,
            "nota": "Só metadados. Arquivo e issue não são lidos.",
            "frentes": [],
            "destaques": [],
        })
    status = pior([p["saude"] for p in projetos])
    ultima = max((p["ultima_atividade"] for p in projetos if p["ultima_atividade"]), default=None)
    lista = ", ".join(p["nome"] for p in projetos)
    return base(
        mid, nome, agente,
        f"Repositórios visíveis: {lista}. Só metadados públicos; arquivo, issue e comentário não entram no painel.",
        False, "github",
        "Listagem da API do GitHub. Conteúdo de arquivo não é lido nesta frente.",
        status,
        f"Saúde pelo push mais recente ({data_curta(ultima)})." if ultima else "Sem data de push.",
        ultima, projetos, [], [], [], [],
        [{"rotulo": p["nome"], "url": p["url"]} for p in projetos if p["url"]],
        ["Issues e arquivos não são lidos. Esta frente não leva valor, cliente nem conteúdo interno."] + (
            [f"{filtro.omitidos} descrições omitidas pelo filtro público."] if filtro.omitidos else []
        ),
    )


def produzir(mid: str, gh: ClienteGitHub, hoje):
    if mid == "tekto":
        return produzir_tekto(gh, hoje)
    if mid == "vtx":
        return produzir_vtx(gh, hoje)
    if mid == "pub":
        return produzir_pub(gh, hoje)
    if mid == "4medco":
        return produzir_descoberta(gh, hoje, "4medco", "4medco", ("bil", "Bil", "Produtos e operação da 4medco"), prefixo="4medco-")
    if mid == "dar":
        return produzir_descoberta(
            gh, hoje, "dar", "Dar", ("dar", "Dar", "Canais e publicação"),
            nomes={"dark-channel-playbook", "engenharia-explicada"},
        )
    return None


def _md(texto) -> str:
    return str(texto).replace("|", "/").replace("\n", " ").strip()


def escrever_painel(docs: list[dict]):
    linhas = [
        "# Painel Central",
        "",
        "Resumo público das frentes dos agentes de Samuel. Gerado por `scripts/gerar.py` — não edite à mão.",
        "",
        "Só entram resumos já filtrados: sem nomes de clientes, valores, dados jurídicos ou financeiros, mensagens e segredos. O site estático mostra o mesmo conteúdo.",
        "",
        "Os horários abaixo são o `atualizado_em` de cada módulo (a fonte), não o instante em que este arquivo foi escrito.",
        "",
        "## Fila do Samuel",
        "",
        "Dúvida aberta no backlog não é, sozinha, uma aprovação formal. Itens de módulos de exemplo ficam fora desta lista.",
        "",
    ]
    reais = [d for d in docs if d and not d.get("exemplo")]
    exemplos = [d for d in docs if d and d.get("exemplo")]
    houve = False
    for doc in reais:
        fila = doc.get("aguardando_samuel") or []
        if not fila:
            continue
        houve = True
        linhas.append(f"### {doc['nome']} · {doc['agente']['nome']} · {len(fila)}")
        linhas.append("")
        for item in fila[:5]:
            extra = f" — desde {data_curta(item['desde'])}" if item.get("desde") else ""
            linhas.append(f"- {_md(item['titulo'])}{extra}")
        if len(fila) > 5:
            linhas.append(f"- … e mais {len(fila) - 5} no site e em `modulos/{doc['id']}.json`")
        linhas.append("")
    if not houve:
        linhas.append("Nenhum item real na fila.")
        linhas.append("")
    linhas.append("## Frentes")
    linhas.append("")
    rotulo = {
        "saudavel": "saudável", "atencao": "atenção", "bloqueado": "bloqueado",
        "parado": "parado", "planejado": "planejado",
        "em_dia": "em dia", "atrasada": "atrasada", "desconhecida": "desconhecida", "pausada": "pausada",
    }
    for doc in reais:
        linhas.append(f"### {doc['nome']} · {doc['agente']['nome']} · {rotulo.get(doc['status'], doc['status'])}")
        linhas.append("")
        linhas.append(_md(doc["resumo"]))
        linhas.append("")
        linhas.append(f"Fonte: {doc['fonte']['tipo']}. Atualizado em: {data_curta(doc.get('atualizado_em'))}.")
        linhas.append("")
        linhas.append(_md(doc["saude"]["motivo"]))
        linhas.append("")
        linhas.append("| Projeto | Saúde | Progresso | Última atividade |")
        linhas.append("| --- | --- | --- | --- |")
        for projeto in doc["projetos"]:
            prog = projeto.get("progresso")
            prog_txt = f"{prog['feitos']}/{prog['total']} ({pct_txt(prog['percentual'])}%)" if prog else "sem contagem"
            linhas.append(
                f"| {_md(projeto['nome'])} | {rotulo.get(projeto['saude'], projeto['saude'])} | {prog_txt} | {data_curta(projeto.get('ultima_atividade'))} |"
            )
        linhas.append("")
        if doc["rotinas"]:
            linhas.append("Rotinas:")
            linhas.append("")
            for rotina in doc["rotinas"]:
                linhas.append(
                    f"- {_md(rotina['nome'])} — {rotina['frequencia']} — última {data_curta(rotina.get('ultima_execucao'))} — {rotulo.get(rotina['status'], rotina['status'])}"
                )
            linhas.append("")
        if doc["prazos"]:
            linhas.append("Prazos:")
            linhas.append("")
            for prazo in doc["prazos"]:
                linhas.append(f"- {data_curta(prazo.get('data'))} — {_md(prazo['titulo'])}")
            linhas.append("")
        if doc["avisos"]:
            for aviso in doc["avisos"]:
                linhas.append(f"> {_md(aviso)}")
            linhas.append("")
    linhas.append("## Ainda em exemplo")
    linhas.append("")
    linhas.append("Estes módulos não têm fonte ligada. Não são pedidos reais.")
    linhas.append("")
    for doc in exemplos:
        linhas.append(f"- **{doc['nome']}** ({doc['agente']['nome']}) — {_md(doc['resumo'])}")
    linhas.append("")
    linhas.append("## Migração")
    linhas.append("")
    linhas.append("Os painéis [tekto-calc-painel](https://github.com/SamAlencar/tekto-calc-painel) e [vtx_painel](https://github.com/SamAlencar/vtx_painel) continuam no ar. Este gerador não arquiva nada.")
    linhas.append("")
    (ROOT / "PAINEL.md").write_text("\n".join(linhas), encoding="utf-8")


def _checar(doc):
    erros = mensagens(doc, doc.get("id", "modulo"))
    if erros:
        for linha in erros:
            print(linha, file=sys.stderr)
        raise SystemExit(1)


def main(argv: list[str]) -> int:
    semear = "--semear" in argv
    painel_apenas = "--somente-painel" in argv
    somente = None
    if "--somente" in argv:
        somente = set(argv[argv.index("--somente") + 1].split(","))
    gh = ClienteGitHub()
    hoje = datetime.now(TZ)
    print(f"github: {gh.modo}")
    MODULOS.mkdir(exist_ok=True)
    for mid in ORDEM:
        atual = carregar(mid)
        if painel_apenas:
            if atual is None:
                print(f"erro: falta modulos/{mid}.json", file=sys.stderr)
                return 1
            continue
        if somente and mid not in somente:
            continue
        if atual and atual.get("fonte", {}).get("tipo") == "manual":
            print(f"{mid}: manual, mantido")
            continue
        try:
            novo = produzir(mid, gh, hoje)
        except Exception as exc:
            if atual:
                print(f"aviso: {mid} mantido após falha ({exc})")
                continue
            print(f"erro: {mid} falhou e não há arquivo anterior ({exc})", file=sys.stderr)
            return 1
        if novo is None:
            if atual is None or (semear and atual.get("fonte", {}).get("tipo") == "exemplo"):
                novo = semente(mid)
            else:
                print(f"{mid}: mantido ({atual['fonte']['tipo']})")
                continue
        elif atual and atual.get("fonte", {}).get("tipo") == "exemplo" and novo.get("fonte", {}).get("tipo") == "exemplo" and not semear:
            print(f"{mid}: exemplo mantido")
            continue
        _checar(novo)
        gravar(novo)
        print(f"{mid}: escrito ({novo['fonte']['tipo']}, {novo['status']})")
    docs = []
    for mid in ORDEM:
        doc = carregar(mid)
        if doc is None:
            print(f"erro: módulo {mid} ausente", file=sys.stderr)
            return 1
        docs.append(doc)
    escrever_painel(docs)
    erros = validar_arquivos()
    if erros:
        for linha in erros:
            print(linha, file=sys.stderr)
        return 1
    print("PAINEL.md escrito. validação ok.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
