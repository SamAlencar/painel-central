import "./style.css"
import ordem from "../config/ordem.json"
import { esc, hrefSeguro, mostrar } from "./sanitizar.js"

const brutos = import.meta.glob("../modulos/*.json", { eager: true, import: "default" })
const porId = Object.fromEntries(Object.values(brutos).map((m) => [m.id, m]))
const modulos = ordem.filter((id) => porId[id]).map((id) => porId[id])

const GRUPOS = [
  { id: "tekto", nome: "Tekto", sub: "Engenharia: cálculo, documentos, modelo e estúdio", cor: "#38bdf8", ids: ["tekto-calc", "tekto-docs", "tekto-model", "tekto-studio", "tek-team", "tek-hunter"] },
  { id: "vtx", nome: "VTX", sub: "Empresa de TI operada por agentes de IA", cor: "#a78bfa", ids: ["vtx"] },
  { id: "4medco", nome: "4med.co", sub: "Produtos e base de conhecimento", cor: "#34d399", ids: ["4medco"] },
  { id: "dark", nome: "Dark Channel", sub: "Canal educacional Engenharia Explicada", cor: "#f472b6", ids: ["dark-channel"] },
]
const STATUS = { saudavel: ["Saudável", "ok"], atencao: ["Atenção", "and"], bloqueado: ["Bloqueado", "bad"], parado: ["Parado", "fz"], planejado: ["Planejado", "fz"] }
const FONTE = { github: "Lido do GitHub", espelho: "Espelho do painel público", manual: "Atualizado pelo agente", exemplo: "Exemplo" }

const estado = { grupo: "", busca: "" }
const app = document.querySelector("#app")
const t = (v, l) => esc(mostrar(v, l))
const n = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0)
const pctTxt = (x) => (Number.isInteger(n(x)) ? String(n(x)) : n(x).toFixed(1).replace(".", ","))
function dataCurta(iso) {
  if (!iso) return "sem data"
  const [a, m, d] = String(iso).slice(0, 10).split("-")
  return `${d}/${m}/${a}`
}
function link(url, rotulo) {
  const h = hrefSeguro(url)
  return h ? `<a href="${esc(h)}" target="_blank" rel="noopener">${rotulo}</a>` : rotulo
}
function totais(mods) {
  let feitos = 0, total = 0, duvidas = 0, repos = 0
  for (const m of mods) {
    for (const p of m.projetos || []) {
      repos++
      if (p.progresso) { feitos += n(p.progresso.feitos); total += n(p.progresso.total) }
    }
    if (!m.exemplo) duvidas += (m.aguardando_samuel || []).filter((i) => i.tipo !== "exemplo").length
  }
  return { feitos, total, duvidas, repos, pct: total ? (feitos / total) * 100 : 0 }
}
function barra(pct, cor, alto = 8) {
  return `<div class="progress" style="height:${alto}px"><div style="width:${Math.min(100, n(pct))}%;${cor ? `background:linear-gradient(90deg,${cor},var(--ok))` : ""}"></div></div>`
}
function rosca(pct, cor) {
  const r = 34, c = 2 * Math.PI * r, v = (Math.min(100, n(pct)) / 100) * c
  return `<svg viewBox="0 0 90 90" class="rosca" aria-hidden="true"><circle cx="45" cy="45" r="${r}" stroke="#334155" stroke-width="10" fill="none"/><circle cx="45" cy="45" r="${r}" stroke="${cor}" stroke-width="10" fill="none" stroke-linecap="round" stroke-dasharray="${v} ${c}" transform="rotate(-90 45 45)"/><text x="45" y="50" text-anchor="middle">${Math.round(n(pct))}%</text></svg>`
}
function grafico(mods) {
  const itens = mods.flatMap((m) => (m.projetos || []).filter((p) => p.progresso).map((p) => ({ nome: p.nome, ...p.progresso, cor: GRUPOS.find((g) => g.ids.includes(m.id))?.cor })))
  if (!itens.length) return ""
  const max = Math.max(...itens.map((i) => i.total))
  return `<section class="bloco"><h2 class="sec">Tarefas por projeto</h2><div class="chart">${itens.map((i) => `
    <div class="linha"><span class="rot">${t(i.nome, 40)}</span>
      <div class="trilho"><div class="tot" style="width:${(i.total / max) * 100}%"><div class="fe" style="width:${i.total ? (i.feitos / i.total) * 100 : 0}%;background:${i.cor}"></div></div></div>
      <span class="num">${i.feitos}/${i.total}</span></div>`).join("")}</div>
    <p class="legenda"><i style="background:#38bdf8"></i>concluídas <i style="background:#334155"></i>restantes</p></section>`
}
function cartaoProjeto(m, g) {
  const p = (m.projetos || [])[0] || {}
  const [st, cls] = STATUS[m.status] || ["—", "fz"]
  const prog = p.progresso
  const fila = m.exemplo ? [] : (m.aguardando_samuel || []).filter((i) => i.tipo !== "exemplo")
  const frentes = (p.frentes || []).slice(0, 8)
  const extras = (m.projetos || []).slice(1)
  const repos = (m.projetos || []).length > 1 ? m.projetos : []
  const prazo = (m.prazos || []).find((x) => x.data)
  return `<article class="proj-card" style="--g:${g.cor}">
    <div class="topo">
      <div><h3>${link(p.url || (m.links || [])[0]?.url, t(m.nome, 60))}</h3><p class="mut">${t(repos.length ? m.resumo : p.descricao, 220)}</p></div>
      <span class="st st-${cls}">${st}</span>
    </div>
    ${m.exemplo ? `<p class="exemplo">Exemplo — dados ilustrativos, sem fonte ligada.</p>` : ""}
    ${prog ? `<div class="prog-row">${rosca(prog.percentual, g.cor)}<div class="prog-info">
        <div class="progress-label"><span>${prog.feitos} de ${prog.total} tarefas</span><strong>${pctTxt(prog.percentual)}%</strong></div>
        ${barra(prog.percentual, g.cor, 10)}
        <div class="mini"><span>❓ ${fila.length} dúvidas</span><span>🕒 ${dataCurta(p.ultima_atividade || m.atualizado_em)}</span>${prazo ? `<span>🎯 previsão ${dataCurta(prazo.data)}</span>` : ""}</div>
      </div></div>` : ""}
    ${repos.length ? `<div class="repos">${repos.map((r) => { const [s, c] = STATUS[r.saude] || ["—", "fz"]; return `<div class="repo">${link(r.url, t(r.nome, 50))}<span class="st st-${c}">${s}</span><small>push ${dataCurta(r.ultima_atividade)}</small></div>` }).join("")}</div>` : ""}
    ${frentes.length ? `<details><summary>Progresso por frente <span>${frentes.length} frentes</span></summary>${frentes.map((f) => `
      <div class="fase"><div class="cab">${t(f.nome, 60)}<span>${f.feitos}/${f.total} · ${pctTxt(f.percentual)}%</span></div>${barra(f.percentual, g.cor)}</div>`).join("")}</details>` : ""}
    ${(p.destaques || []).length ? `<div class="prox"><small>Próximas tarefas</small>${p.destaques.slice(0, 3).map((d) => `<div class="tarefa"><span class="id">${t(d.id || "", 20)}</span><span class="t">${t(d.texto, 140)}</span><span class="st st-fazer">a fazer</span></div>`).join("")}</div>` : ""}
    ${(m.atividade || []).length ? `<details><summary>Atividade recente <span>${m.atividade.length}</span></summary>${m.atividade.slice(0, 8).map((a) => `<div class="tarefa"><span class="id">${dataCurta(a.quando)}</span><span class="t">${t(a.resumo, 200)}</span><span class="st st-ok">feito</span></div>`).join("")}</details>` : ""}
    ${fila.length ? `<details><summary>Aguardando você <span>${fila.length}</span></summary>${fila.slice(0, 15).map((i) => `<div class="tarefa"><span class="id">${t(i.id, 20)}</span><span class="t">${t(i.titulo, 180)}</span></div>`).join("")}${fila.length > 15 ? `<p class="mut">… e mais ${fila.length - 15}.</p>` : ""}</details>` : ""}
    <p class="fonte">${FONTE[m.fonte?.tipo] || ""} · atualizado ${dataCurta(m.atualizado_em)}</p>
  </article>`
}
function casa(m) {
  const q = estado.busca.toLowerCase()
  if (!q) return true
  return JSON.stringify([m.nome, m.resumo, m.projetos?.map((p) => [p.nome, p.descricao, p.destaques])]).toLowerCase().includes(q)
}
function render() {
  const geral = totais(modulos)
  const grupos = GRUPOS.filter((g) => !estado.grupo || g.id === estado.grupo)
  app.innerHTML = `
  <header><div class="wrap">
    <h1>Painel Central <span>· Projetos dos agentes</span></h1>
    <p class="sub">Tekto, VTX, 4med.co e Dark Channel em um só lugar</p>
  </div></header>
  <main class="wrap" id="miolo">
    <section class="cards">
      <div class="card"><div class="n">${geral.repos}</div><div class="l">Projetos</div></div>
      <div class="card"><div class="n" style="color:var(--ok)">${geral.feitos}</div><div class="l">Tarefas concluídas</div></div>
      <div class="card"><div class="n" style="color:var(--and)">${geral.total - geral.feitos}</div><div class="l">Tarefas restantes</div></div>
      <div class="card"><div class="n" style="color:var(--acc)">${geral.duvidas}</div><div class="l">Dúvidas aguardando você</div></div>
    </section>
    <section><div class="progress-label"><span>Progresso geral (projetos com backlog)</span><strong>${pctTxt(geral.pct.toFixed(1))}%</strong></div>${barra(geral.pct, null, 12)}</section>
    <section class="gcards">${GRUPOS.map((g) => { const tt = totais(g.ids.map((i) => porId[i]).filter(Boolean)); return `
      <button class="gcard ${estado.grupo === g.id ? "ativo" : ""}" data-g="${g.id}" style="--g:${g.cor}">
        <strong>${g.nome}</strong><small>${tt.repos} repositório(s)</small>
        ${tt.total ? `${barra(tt.pct, g.cor)}<small>${tt.feitos}/${tt.total} · ${pctTxt(tt.pct.toFixed(1))}%</small>` : `<small>sem backlog medido</small>`}
      </button>` }).join("")}</section>
    ${grafico(modulos)}
    <section class="filtros">
      <label>Frente <select id="f-grupo"><option value="">Todas</option>${GRUPOS.map((g) => `<option value="${g.id}" ${estado.grupo === g.id ? "selected" : ""}>${g.nome}</option>`).join("")}</select></label>
      <label>Busca <input id="f-busca" type="search" value="${esc(estado.busca)}" placeholder="projeto, tarefa…"></label>
    </section>
    ${grupos.map((g) => { const mods = g.ids.map((i) => porId[i]).filter(Boolean).filter(casa); if (!mods.length) return ""; return `
      <section class="grupo"><h2 class="gtit" style="--g:${g.cor}">${g.nome} <span>${g.sub}</span></h2>
        <div class="grid">${mods.map((m) => cartaoProjeto(m, g)).join("")}</div></section>` }).join("")}
    <p class="rodape">Só resumos filtrados: sem nomes de clientes, valores ou segredos. Os painéis antigos (Tekto Calc e VTX) seguem no ar.</p>
  </main>`
  app.querySelectorAll(".gcard").forEach((b) => b.addEventListener("click", () => { estado.grupo = estado.grupo === b.dataset.g ? "" : b.dataset.g; render() }))
  app.querySelector("#f-grupo").addEventListener("change", (e) => { estado.grupo = e.target.value; render() })
  const busca = app.querySelector("#f-busca")
  busca.addEventListener("input", (e) => { estado.busca = e.target.value; render(); const b = app.querySelector("#f-busca"); b.focus(); b.setSelectionRange(b.value.length, b.value.length) })
}
render()
