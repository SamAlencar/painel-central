#!/usr/bin/env python3
"""Lê os backlogs da Tekto e devolve metadados de progresso.

Lógica de leitura própria do painel-central (sem depender de outro painel). Aqui não há commit
nem push: o painel-central só consome o dicionário e publica o resumo sanitizado.
"""
import json, re, subprocess
from datetime import datetime, timedelta
import math
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO — para acompanhar um novo projeto, basta acrescentar um item.
#   slug:   identificador curto usado na URL do painel (#slug)
#   nome:   nome exibido
#   repo:   repositório privado (dono/nome), lido só via gh api
#   descricao: subtítulo do cartão
#   prefixo: prefixo dos IDs de tarefa (informativo)
#   normas_escopo: (opcional) lista (código, descrição) exibida mesmo sem tarefas
#   ritmo_planejado: (opcional) tarefas/dia da rotina diária do projeto (padrão RITMO_PADRAO)
# ---------------------------------------------------------------------------
PROJETOS = [
    {
        "slug": "calc", "nome": "Tekto Calc", "repo": "SamAlencar/tek-calc", "prefixo": "TC",
        "descricao": "Rotinas de cálculo de engenharia em Python",
        "ritmo_planejado": 1.0,
        "normas_escopo": [
            ("NBR 6118", "Concreto armado e protendido"),
            ("NBR 8800", "Estruturas de aço"),
            ("NBR 14762", "Perfis de aço formados a frio"),
            ("NBR 7190", "Estruturas de madeira"),
            ("NBR 6122", "Fundações"),
            ("NBR 6120", "Ações para o cálculo de estruturas"),
            ("NBR 8681", "Ações e segurança nas estruturas"),
            ("NBR 5410", "Instalações elétricas de baixa tensão"),
            ("NBR 5626", "Água fria e água quente"),
            ("NBR 8160", "Esgoto sanitário"),
            ("NBR 10844", "Águas pluviais"),
        ],
    },
    {
        "slug": "docs", "nome": "Tekto Docs", "repo": "SamAlencar/tek-docs", "prefixo": "TD",
        "descricao": "Memoriais, especificações, laudos e fichas técnicas",
        "ritmo_planejado": 1.0,
    },
    {
        "slug": "model", "nome": "Tekto Model", "repo": "SamAlencar/tek-model", "prefixo": "TM",
        "descricao": "Modelagem e BIM",
        "ritmo_planejado": 2.0,   # rotina roda duas vezes por dia
    },
    {
        "slug": "hunter", "nome": "Tek Hunter", "repo": "SamAlencar/tek-hunter", "prefixo": "TH",
        "descricao": "Base para captação de elaboração de projetos",
        "ritmo_planejado": 2/7,   # duas etapas por semana
        "rotina": "semanal",
    },
    {
        "slug": "team", "nome": "Tek Team", "repo": "SamAlencar/tek-team", "prefixo": "TT",
        "descricao": "Equipe de agentes de IA: papéis, skills e diretrizes BIM",
        "ritmo_planejado": 1.0,   # uma etapa por dia
    },
    {
        "slug": "studio", "nome": "Tekto Studio", "repo": "SamAlencar/tek-studio", "prefixo": "TS",
        "descricao": "Plataforma de engenharia com agente de IA e núcleo determinístico",
        "ritmo_planejado": 1.0,   # um item por dia (TS-D04)
    },
    {
        "slug": "token", "nome": "Tek Token", "repo": "SamAlencar/tek-token", "prefixo": "TK-T",
        "descricao": "",
        "ritmo_planejado": 1.0,
        # Repositório previsto para 26/10/2026; até existir, descobrir() o remove sem erro.
    },
    {
        "slug": "catalog", "nome": "Tek Catalog", "repo": "SamAlencar/tek-catalog", "prefixo": "TK",
        "descricao": "Catálogo Tekto de materiais da construção civil com IFC 4.3",
        "ritmo_planejado": 1.0,
    },
]
CAMINHO_BACKLOG = "docs/BACKLOG.md"
RITMO_PADRAO = 1.0        # tarefas/dia quando o projeto não define ritmo_planejado (7 dias por semana)
JANELA_RITMO_REAL = 14    # dias usados para medir o ritmo real
MAX_REFERENCIAS = 60      # limite de chips de normas/referências por projeto
HISTORICO_MINIMO = 7      # dias de histórico do backlog antes de mostrar o ritmo real
CAMINHO_DUVIDAS = "docs/DUVIDAS.md"

TZ = ZoneInfo("America/Sao_Paulo")
_getter = None


RE_REPO_TEKTO = re.compile(r"^(tekto|tek)-[a-z0-9][a-z0-9-]*$")
IGNORAR_TEKTO = re.compile(r"-painel$")


def _slug_de(nome_repo):
    return re.sub(r"^(tekto|tek)-", "", nome_repo)


def descobrir(repos):
    """Acrescenta a PROJETOS todo repositório tek-*/tekto-* ainda não configurado.

    Devolve a lista final (configurados que existem + descobertos), na ordem de PROJETOS
    e depois por nome. Repositórios -painel (painéis legados) ficam de fora.
    """
    nomes = {(r.get("name") or "") for r in repos}
    conhecidos = {c["repo"].split("/", 1)[1] for c in PROJETOS}
    for r in sorted(repos, key=lambda r: r.get("name") or ""):
        nome = r.get("name") or ""
        if not RE_REPO_TEKTO.match(nome) or IGNORAR_TEKTO.search(nome) or nome in conhecidos:
            continue
        PROJETOS.append({
            "slug": _slug_de(nome),
            "nome": " ".join(p.capitalize() for p in nome.split("-")),
            "repo": r.get("full_name") or f"SamAlencar/{nome}",
            "descricao": r.get("description") or "",
            "ritmo_planejado": RITMO_PADRAO,
        })
        conhecidos.add(nome)
    por_nome = {(r.get("name") or ""): r for r in repos}
    for c in PROJETOS:
        r = por_nome.get(c["repo"].split("/", 1)[1])
        if r and not c.get("descricao"):
            c["descricao"] = r.get("description") or ""
    if nomes:
        PROJETOS[:] = [c for c in PROJETOS if c["repo"].split("/", 1)[1] in nomes]
    return PROJETOS


def usar_github(fn):
    """fn(path, raw=False) -> str | dict | None. None significa 404."""
    global _getter
    _getter = fn


RE_NORMA = re.compile(r"\bNBR\s*(ISO(?:/IEC)?\s*)?(\d{4,5})(?:-\d+)?(?:[:\s]*(\d{4})\b)?", re.I)
RE_ID = re.compile(r"`?\b([A-Z]{1,6}(?:[-_.][A-Z0-9]{1,6})*[-_.]?\d{1,4}(?:\.\d+)?)\b`?")
RE_CHECK = re.compile(r"^\s*[-*+]\s*\[([ xX~\-])\]\s*(.+)$")
RE_TAREFA_HEAD = re.compile(r"^\s*(?:\[[ xX]\]\s*)?`?\*{0,2}[A-Z]{1,6}(?:[-_.][A-Z0-9]{1,6})*[-_.]?\d{1,4}(?:\.\d+)?\b")
RE_CAMPO = re.compile(r"^\s*[-*+]\s*\*{0,2}([A-Za-zÀ-ú ]{3,30}?)\*{0,2}\s*:\s*\*{0,2}\s*(.*)$")
RE_HEAD = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
FEITO_TXT = re.compile(r"\[x\]|✅|✔|☑|\bfeit[oa]\b|\bconclu[ií]d[oa]\b|\bdone\b|\bok\b|\bmesclad[oa]\b", re.I)
PEND_TXT = re.compile(r"\[ \]|⬜|☐|pendente|a fazer|todo|em andamento|aberto", re.I)


def gh_api(path, raw=False):
    if _getter is not None:
        return _getter(path, raw=raw)
    cmd = ["gh", "api", path]
    if raw:
        cmd += ["-H", "Accept: application/vnd.github.raw"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        if "404" in (r.stderr + r.stdout) or "Not Found" in (r.stderr + r.stdout):
            return None
        raise RuntimeError(f"gh api {path} falhou: {r.stderr.strip()}")
    return r.stdout if raw else json.loads(r.stdout)


def limpa(t):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)  # links md -> texto
    t = re.sub(r"\*\*|__|`|(?<!\w)[*_]|[*_](?!\w)", "", t)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip(" -–—|:;")


def normas_em(t):
    out = []
    for m in RE_NORMA.finditer(t):
        n = f"NBR {'ISO ' if m.group(1) else ''}{m.group(2)}"
        if n not in out:
            out.append(n)
    return out


RE_OUTRAS = re.compile(r"\b(?:ISO(?:/IEC)?|IEC|EN|NR)[\s-]*\d{2,5}(?:-\d+)?|\bIFC\s*\d(?:\.\d)*", re.I)


def referencias_em(valor):
    """Códigos de norma do campo (NBR, ISO, IEC, NR, IFC...). Se não houver código,
    os itens curtos separados por ';' entram como texto (ex.: 'buildingSMART IDS')."""
    valor = re.sub(r"\(\s*<?https?://[^)]*\)", "", valor)   # "(https://...)" depois do nome
    valor = re.sub(r"<?https?://\S+>?", "", valor)
    out = []
    for parte in valor.split(";"):
        codigos = normas_em(parte)
        for m in RE_OUTRAS.finditer(RE_NORMA.sub(" ", parte)):
            c = re.sub(r"\s+", " ", m.group(0).upper().replace("IFC", "IFC ")).strip()
            if c not in codigos:
                codigos.append(c)
        if codigos:
            out += [c for c in codigos if c not in out]
            continue
        t = limpa(re.split(r"\.\s|,\s", parte)[0]).rstrip(". ")
        if t.count("(") != t.count(")") or re.match(r"(conferir|sem|ver|verificar|ainda|na edição|edição)\b", t, re.I):
            continue
        if 2 <= len(t) <= 50 and not re.search(r"\b(nenhum\w*|n/a|não se aplica|a definir)\b", t, re.I) and t not in out:
            out.append(t)
    return out


def separa_tarefa(texto, disciplina):
    bruto = texto
    tid = None
    m = RE_ID.search(texto[:40])
    if m and not RE_NORMA.match(texto[m.start():]) and not m.group(1).upper().startswith("NBR"):
        tid = m.group(1)
        texto = texto[:m.start()] + texto[m.end():]
    normas = normas_em(bruto)
    titulo = limpa(texto)
    # corta critério de pronto / referência longa depois de separadores
    for sep in [" — ", " – ", " | ", " -- "]:
        partes = titulo.split(sep)
        if len(partes) > 1 and len(partes[0]) >= 6:
            titulo = partes[0]
            break
    titulo = re.sub(r"\(\s*(ABNT\s*)?NBR[^)]*\)", "", titulo).strip(" -–—:;")
    return {"id": tid, "titulo": titulo[:160], "normas": normas, "disciplina": disciplina}


def parse_backlog(md):
    tarefas, disc, headers, atual = [], "Geral", None, None
    for linha in md.splitlines():
        h = RE_HEAD.match(linha)
        if h:
            nivel = len(h.group(1))
            headers, atual = None, None
            # Formato "### TC-001 — Título" (tarefa como cabeçalho, campos em bullets)
            mt = RE_TAREFA_HEAD.match(h.group(2)) if nivel >= 3 else None
            if mt:
                t = separa_tarefa(h.group(2), disc)
                t["feito"] = bool(re.search(r"\[x\]|✅|✔", h.group(2), re.I))
                t["_status_explicito"] = False
                if t["titulo"]:
                    tarefas.append(t)
                    atual = t
                continue
            if nivel >= 2:
                disc = limpa(re.sub(r"^\d+(\.\d+)*[.)]?\s*", "", h.group(2))) or disc
            continue
        if atual is not None:
            mc = RE_CAMPO.match(linha)
            if mc:
                chave, valor = limpa(mc.group(1)).lower(), mc.group(2)
                if chave.startswith(("status", "situa", "estado")):
                    atual["feito"] = bool(FEITO_TXT.search(valor)) and not re.search(r"\[ \]", valor)
                    atual["_status_explicito"] = True
                elif chave.startswith(("norma", "refer")):
                    for n in referencias_em(valor):
                        if n not in atual["normas"]:
                            atual["normas"].append(n)
                elif chave.startswith("depende"):
                    atual["depende"] = [x for x in re.findall(r"[A-Z]{1,6}-?\d{1,4}", valor)]
                continue
        c = RE_CHECK.match(linha)
        if c and not linha.startswith((" " * 4, "\t")):
            t = separa_tarefa(c.group(2), disc)
            t["feito"] = c.group(1) in "xX"
            if t["titulo"]:
                tarefas.append(t)
            continue
        s = linha.strip()
        if s.startswith("|") and s.count("|") >= 3:
            cels = [x.strip() for x in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", x) for x in cels if x):
                continue
            if headers is None:
                headers = [limpa(x).lower() for x in cels]
                continue
            row = dict(zip(headers, cels))
            def col(*nomes):
                for k, v in row.items():
                    if any(n in k for n in nomes):
                        return v
                return None
            st = col("status", "situa", "estado", "feito") or ""
            idc = col("id", "cód", "cod", "#")
            tit = col("tarefa", "título", "titulo", "descri", "item") or (cels[1] if len(cels) > 1 else cels[0])
            nor = col("norma", "refer")
            if not limpa(tit):
                continue
            if not st:
                st = " ".join(cels)
            feito = bool(FEITO_TXT.search(st)) and not re.search(r"\[ \]", st)
            t = separa_tarefa(tit, disc)
            if idc and limpa(idc):
                t["id"] = limpa(idc)
            if nor:
                t["normas"] = normas_em(nor) or t["normas"]
            t["feito"] = feito
            tarefas.append(t)
        elif s and not s.startswith("|"):
            if not RE_CHECK.match(linha) and not linha.startswith((" ", "\t")):
                headers = None
    for t in tarefas:
        t.pop("_status_explicito", None)
        t.pop("depende", None)
    return tarefas


def duvida_resolvida(st):
    if re.search(r"\[x\]|✅|✔", st, re.I):
        return True
    if re.search(r"\[ \]|parcial|em aberto|pendente", st, re.I):
        return False
    return bool(re.search(r"resolvid|respondid|fechad|encerrad", st, re.I))


def parse_duvidas(md):
    abertas, secao_fechada, atual = [], False, None
    tem_check = any(RE_CHECK.match(l) for l in md.splitlines())
    for linha in md.splitlines():
        h = RE_HEAD.match(linha)
        if h:
            nivel, txt = len(h.group(1)), limpa(h.group(2))
            if nivel <= 2 and re.search(r"resolvid|fechad|respondid|encerrad", txt, re.I):
                secao_fechada = True
                continue
            if nivel <= 2 and re.search(r"abert|pendente|em aberto", txt, re.I):
                secao_fechada = False
                continue
            if nivel >= 3 and not secao_fechada and txt:
                if re.search(r"resolvid|\[x\]|✅", h.group(2), re.I):
                    continue
                atual = {"texto": txt[:300], "normas": normas_em(txt)}
                abertas.append(atual)
            continue
        if secao_fechada:
            continue
        mc = RE_CAMPO.match(linha)
        if atual is not None and mc and limpa(mc.group(1)).lower().startswith(("status", "situa", "estado")):
            if duvida_resolvida(mc.group(2)) and atual in abertas:
                abertas.remove(atual)
            continue
        if atual is not None and mc:
            continue
        c = RE_CHECK.match(linha)
        if c and not linha.startswith((" ", "\t")):
            if c.group(1) in "xX":
                continue
            txt = limpa(c.group(2))
            if txt and not re.search(r"\bresolvid", txt, re.I):
                abertas.append({"texto": txt[:300], "normas": normas_em(txt)})
            continue
        m = re.match(r"^[-*+]\s+(.+)$", linha)
        if m and not tem_check:
            txt = limpa(m.group(1))
            if txt and atual is None and not re.search(r"\bresolvid", txt, re.I):
                abertas.append({"texto": txt[:300], "normas": normas_em(txt)})
    return abertas


def prs_mesclados(repo):
    prs = gh_api(f"repos/{repo}/pulls?state=closed&per_page=100&sort=updated&direction=desc") or []
    out = []
    for p in prs:
        if not p.get("merged_at"):
            continue
        dt = datetime.fromisoformat(p["merged_at"].replace("Z", "+00:00")).astimezone(TZ)
        out.append({"numero": p["number"], "titulo": p["title"].strip()[:200],
                    "data": dt.isoformat(timespec="minutes")})
    out.sort(key=lambda x: x["data"], reverse=True)
    return out


def previsao(pendentes, ritmo, hoje):
    """Data prevista de término com `ritmo` tarefas/dia a partir de hoje."""
    if pendentes <= 0:
        return {"data": hoje.date().isoformat(), "dias": 0, "concluido": True}
    dias = math.ceil(pendentes / ritmo)
    return {"data": (hoje + timedelta(days=dias)).date().isoformat(), "dias": dias, "concluido": False}


def ritmo_real(repo, branch, feitos_agora, hoje):
    """Tarefas concluídas por dia nos últimos JANELA_RITMO_REAL dias, medido pelo
    histórico de commits do BACKLOG.md (contagem de [x] no início da janela vs. agora)."""
    commits = gh_api(f"repos/{repo}/commits?path={CAMINHO_BACKLOG}&sha={branch}&per_page=100") or []
    if not commits:
        return {"disponivel": False, "historico_dias": 0}
    datas = [(datetime.fromisoformat(c["commit"]["committer"]["date"].replace("Z", "+00:00")), c["sha"]) for c in commits]
    datas.sort()
    primeiro = datas[0][0]
    historico = (hoje - primeiro).total_seconds() / 86400
    if historico < HISTORICO_MINIMO:
        return {"disponivel": False, "historico_dias": round(historico, 1)}
    inicio = hoje - timedelta(days=JANELA_RITMO_REAL)
    antes = [x for x in datas if x[0] <= inicio]
    base_data, base_sha = antes[-1] if antes else datas[0]
    md = gh_api(f"repos/{repo}/contents/{CAMINHO_BACKLOG}?ref={base_sha}", raw=True) or ""
    feitos_base = sum(t["feito"] for t in parse_backlog(md))
    janela = (hoje - max(base_data, inicio)).total_seconds() / 86400
    concluidas = max(0, feitos_agora - feitos_base)
    return {"disponivel": True, "historico_dias": round(historico, 1), "janela_dias": round(janela, 1),
            "concluidas_na_janela": concluidas, "tarefas_por_dia": round(concluidas / janela, 3) if janela > 0 else 0}


def ritmo_texto(cfg, ritmo):
    if cfg.get("rotina") == "semanal":
        n = round(ritmo * 7)
        return f"{n} {'etapa' if n == 1 else 'etapas'}/semana"
    n = ritmo
    nt = int(n) if float(n).is_integer() else round(n, 2)
    return f"{nt} {'tarefa' if n == 1 else 'tarefas'}/dia"


def gerar_projeto(cfg):
    repo = cfg["repo"]
    info = gh_api(f"repos/{repo}")
    branch = info["default_branch"] if info else "main"
    backlog = gh_api(f"repos/{repo}/contents/{CAMINHO_BACKLOG}?ref={branch}", raw=True) if info else None
    duvidas = gh_api(f"repos/{repo}/contents/{CAMINHO_DUVIDAS}?ref={branch}", raw=True) if info else None
    tarefas = parse_backlog(backlog) if backlog else []
    entregas = []
    sem_prs = False
    if info:
        try:
            entregas = prs_mesclados(repo)
        except Exception as exc:
            sem_prs = True
            print(f"aviso: PRs de {repo} indisponíveis ({str(exc)[:160]}); seguindo só com BACKLOG e DUVIDAS.")
    ultima_commit = None
    if info and not entregas:
        try:
            cs = gh_api(f"repos/{repo}/commits?sha={branch}&per_page=1") or []
            if cs:
                dt = datetime.fromisoformat(cs[0]["commit"]["committer"]["date"].replace("Z", "+00:00")).astimezone(TZ)
                ultima_commit = dt.isoformat(timespec="minutes")
        except Exception as exc:
            print(f"aviso: commits de {repo} indisponíveis ({str(exc)[:160]}).")

    areas = {}
    for t in tarefas:
        d = areas.setdefault(t["disciplina"], {"nome": t["disciplina"], "total": 0, "feitos": 0})
        d["total"] += 1
        d["feitos"] += t["feito"]
    for d in areas.values():
        d["percentual"] = round(100 * d["feitos"] / d["total"], 1) if d["total"] else 0

    total = len(tarefas)
    feitos = sum(t["feito"] for t in tarefas)
    escopo = cfg.get("normas_escopo", [])
    conhecidas = [n for n, _ in escopo]
    vistas = []
    for t in tarefas:
        vistas += [n for n in t["normas"] if n not in vistas and n not in conhecidas]
    normas = []
    freq = {n: sum(1 for t in tarefas if n in t["normas"]) for n in vistas}
    vistas = sorted(vistas, key=lambda n: (not RE_NORMA.search(n), -freq[n]))[:MAX_REFERENCIAS]
    for n, desc in list(escopo) + [(n, "") for n in vistas]:
        nt = sum(1 for t in tarefas if n in t["normas"])
        nf = sum(1 for t in tarefas if t["feito"] and n in t["normas"])
        estado = "coberta" if nt and nf == nt else "em_andamento" if nf else "planejada" if nt else "futura"
        normas.append({"norma": n, "descricao": desc, "tarefas": nt, "feitas": nf, "estado": estado})
    lista_duv = parse_duvidas(duvidas) if duvidas else []

    hoje = datetime.now(TZ)
    ritmo_plan = float(cfg.get("ritmo_planejado") or RITMO_PADRAO)
    pend = total - feitos
    if total:
        real = ritmo_real(repo, branch, feitos, hoje)
        prev = {"situacao": "ativo", "ritmo_planejado": ritmo_plan, "ritmo_texto": ritmo_texto(cfg, ritmo_plan),
                "rotina": cfg.get("rotina", "diária"), "pendentes": pend,
                "planejada": previsao(pend, ritmo_plan, hoje), "real": real}
        if real.get("disponivel") and real["tarefas_por_dia"] > 0:
            real["previsao"] = previsao(pend, real["tarefas_por_dia"], hoje)
    else:
        prev = {"situacao": "aguardando_backlog", "ritmo_planejado": ritmo_plan,
                "ritmo_texto": ritmo_texto(cfg, ritmo_plan), "rotina": cfg.get("rotina", "diária"), "pendentes": 0}

    return {
        "slug": cfg["slug"],
        "nome": cfg["nome"],
        "descricao": cfg.get("descricao", ""),
        "estado": "ativo" if total else "preparacao",
        "repo_encontrado": info is not None,
        "backlog_encontrado": backlog is not None,
        "duvidas_encontrado": duvidas is not None,
        "total": total,
        "feitos": feitos,
        "percentual": round(100 * feitos / total, 1) if total else 0,
        "areas": list(areas.values()),
        "proximas": [{k: t[k] for k in ("id", "titulo", "normas", "disciplina")} for t in tarefas if not t["feito"]][:8],
        "entregas": entregas[:12],
        "total_entregas": len(entregas),
        "ultima_entrega": entregas[0]["data"] if entregas else ultima_commit,
        "sem_prs": sem_prs,
        "normas": normas,
        "normas_cobertas": sorted({n for t in tarefas if t["feito"] for n in t["normas"]}),
        "duvidas": lista_duv,
        "previsao": prev,
    }


def gerar():
    projetos = [gerar_projeto(c) for c in PROJETOS]
    total = sum(p["total"] for p in projetos)
    feitos = sum(p["feitos"] for p in projetos)
    datas = [p["ultima_entrega"] for p in projetos if p["ultima_entrega"]]
    ativos = [p for p in projetos if p["previsao"]["situacao"] == "ativo"]
    prev_sis = {"aguardando": [p["nome"] for p in projetos if p["previsao"]["situacao"] != "ativo"]}
    if ativos:
        ult = max(ativos, key=lambda p: p["previsao"]["planejada"]["data"])
        prev_sis["planejada"] = dict(ult["previsao"]["planejada"], projeto=ult["nome"])
        # Projetos sem histórico suficiente não apagam o ritmo real dos demais.
        com_real = [p for p in ativos if p["previsao"]["real"].get("previsao")]
        if com_real:
            ur = max(com_real, key=lambda p: p["previsao"]["real"]["previsao"]["data"])
            prev_sis["real"] = dict(ur["previsao"]["real"]["previsao"], projeto=ur["nome"],
                                    sem_historico=[p["nome"] for p in ativos if p not in com_real])
    return {
        "painel": "Painel Tekto",
        "geral": {
            "total": total, "feitos": feitos,
            "percentual": round(100 * feitos / total, 1) if total else 0,
            "duvidas": sum(len(p["duvidas"]) for p in projetos),
            "entregas": sum(p["total_entregas"] for p in projetos),
            "ultima_entrega": max(datas) if datas else None,
            "projetos_ativos": sum(p["estado"] == "ativo" for p in projetos),
            "previsao": prev_sis,
        },
        "projetos": projetos,
    }


def coletar():
    """Mesmo miolo do antigo data.json: geral + projetos. Sem gravar arquivo."""
    return gerar()
