import "@fontsource/outfit/latin-400.css"
import "@fontsource/outfit/latin-500.css"
import "@fontsource/outfit/latin-600.css"
import "@fontsource/fraunces/latin-500.css"
import "@fontsource/fraunces/latin-600-italic.css"
import "./style.css"
import ordem from "../config/ordem.json"
import { esc, hrefSeguro, mostrar } from "./sanitizar.js"

const brutos = import.meta.glob("../modulos/*.json", { eager: true, import: "default" })
const porId = Object.fromEntries(Object.values(brutos).map((m) => [m.id, m]))
const modulos = [
  ...ordem.filter((id) => porId[id]).map((id) => porId[id]),
  ...Object.values(porId).filter((m) => !ordem.includes(m.id)),
]

const STATUS = {
  saudavel: "Saudável",
  atencao: "Atenção",
  bloqueado: "Bloqueado",
  parado: "Parado",
  planejado: "Planejado",
}
const ROTINA = { em_dia: "em dia", atrasada: "atrasada", desconhecida: "sem registro", pausada: "pausada" }
const ESPERA = { duvida: "Dúvida de backlog", aprovacao: "Aprovação", leitura: "Leitura", rotina: "Rotina", exemplo: "Exemplo" }
const PRAZO = { previsao: "previsão de ritmo, não é data prometida", rotina: "rotina", decisao: "decisão", exemplo: "exemplo" }
const FONTE = { github: "Lido do GitHub", espelho: "Espelho do painel público", manual: "Atualizado pelo agente", exemplo: "Exemplo" }

const estado = {
  filtro: "todas",
  busca: "",
  aberto: decodeURIComponent(location.hash.replace(/^#/, "")),
}

const app = document.querySelector("#app")

function t(valor, limite) {
  return esc(mostrar(valor, limite))
}
function n(valor) {
  const x = Number(valor)
  return Number.isFinite(x) ? x : 0
}
function dataCurta(iso) {
  if (!iso) return "sem data"
  const [ano, mes, dia] = String(iso).slice(0, 10).split("-")
  return `${dia}/${mes}/${ano}`
}
function hora(iso) {
  const m = String(iso || "").match(/T(\d{2}:\d{2})/)
  return m && m[1] !== "00:00" ? `${dataCurta(iso)} ${m[1]}` : dataCurta(iso)
}
function pctTxt(valor) {
  const x = n(valor)
  return Number.isInteger(x) ? String(x) : x.toFixed(1).replace(".", ",")
}
function filaReal(mod) {
  if (mod.exemplo) return []
  return (mod.aguardando_samuel || []).filter((item) => item.tipo !== "exemplo")
}
function progresso(mod) {
  const feitos = (mod.projetos || []).reduce((s, p) => s + n(p.progresso?.feitos), 0)
  const total = (mod.projetos || []).reduce((s, p) => s + n(p.progresso?.total), 0)
  if (!total) return null
  return { feitos, total, percentual: Math.round((1000 * feitos) / total) / 10 }
}
function casa(mod, busca) {
  if (!busca) return true
  const q = busca.toLocaleLowerCase("pt-BR")
  const pedacos = [
    mod.nome, mod.resumo, mod.agente?.nome, mod.agente?.papel, mod.status,
    ...(mod.projetos || []).map((p) => `${p.nome} ${p.descricao}`),
    ...(mod.aguardando_samuel || []).map((i) => i.titulo),
  ]
  return pedacos.join(" ").toLocaleLowerCase("pt-BR").includes(q)
}
function visivel(mod) {
  if (!casa(mod, estado.busca.trim())) return false
  if (estado.filtro === "fila") return filaReal(mod).length > 0
  if (estado.filtro === "atencao") return ["atencao", "bloqueado", "parado"].includes(mod.status)
  if (estado.filtro === "reais") return !mod.exemplo
  if (estado.filtro === "exemplos") return mod.exemplo
  return true
}
function selo(classe, texto) {
  return `<span class="selo ${esc(classe)}">${t(texto)}</span>`
}
function trilho(percentual, legenda) {
  const w = Math.max(0, Math.min(100, n(percentual)))
  return `<div class="trilho" role="img" aria-label="${esc(legenda)}"><span style="width:${w}%"></span></div>`
}
function linkExterno(url, rotulo) {
  const href = hrefSeguro(url)
  if (!href) return ""
  return `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${t(rotulo)}</a>`
}

function hero() {
  if (estado.busca.trim() || estado.filtro !== "todas") return ""
  const blocos = modulos.map((m) => ({ m, fila: filaReal(m) })).filter((x) => x.fila.length)
  if (!blocos.length) {
    return `<section class="hero"><h2>Nada na fila real</h2><p>Nenhum módulo com fonte ligada espera uma decisão. Cartões de exemplo não entram aqui.</p></section>`
  }
  const itens = []
  for (const bloco of blocos) {
    for (const item of bloco.fila) {
      itens.push({ m: bloco.m, item })
      if (itens.length === 5) break
    }
    if (itens.length === 5) break
  }
  const total = blocos.reduce((s, b) => s + b.fila.length, 0)
  const lis = itens.map(({ m, item }) => `
    <li>
      <span class="quem">${t(m.nome)} · ${t(ESPERA[item.tipo] || item.tipo)}</span>
      <span>${t(item.titulo, 180)}${item.desde ? ` <span class="quando">desde ${esc(dataCurta(item.desde))}</span>` : ""}</span>
    </li>`).join("")
  const mais = blocos.map(({ m, fila }) => `<a class="mais" href="#${esc(m.id)}">Ver ${t(m.nome)} · ${fila.length}</a>`).join(" ")
  return `<section class="hero"><h2>Espera você</h2><p>${total} itens em módulos reais. Dúvida de backlog não é, sozinha, uma aprovação formal.</p><ul class="fila">${lis}</ul>${mais}</section>`
}

function cartao(mod) {
  const prog = progresso(mod)
  const fila = filaReal(mod)
  const extra = mod.exemplo
    ? "Exemplo, fora da fila real"
    : fila.length ? `${fila.length} na fila` : "fila vazia"
  return `<a class="cartao s-${esc(mod.status)} ${mod.exemplo ? "exemplo" : ""}" href="#${esc(mod.id)}">
    <div class="selos">${selo("", mod.agente?.nome || "Agente")}${selo(mod.status, STATUS[mod.status] || mod.status)}${mod.exemplo ? selo("exemplo", "Exemplo") : ""}</div>
    <h2>${t(mod.nome)}</h2>
    <p class="clamp">${t(mod.resumo, 600)}</p>
    ${prog ? trilho(prog.percentual, `${pctTxt(prog.percentual)}% concluído`) : ""}
    <p class="meta">${prog ? `${prog.feitos}/${prog.total} · ` : ""}${esc(extra)}</p>
  </a>`
}

function lista() {
  const mods = modulos.filter(visivel)
  const corpo = mods.length
    ? `<div class="grade">${mods.map(cartao).join("")}</div>`
    : `<div class="vazio"><h2>Nenhuma frente neste recorte</h2><p class="mudo">Troque o filtro ou limpe a busca.</p></div>`
  return `${hero()}${corpo}`
}

function projeto(p) {
  const prog = p.progresso
  const frentes = (p.frentes || []).slice(0, 6).map((f) =>
    `<li><span>${t(f.nome)}</span><span class="quando">${n(f.feitos)}/${n(f.total)} · ${pctTxt(f.percentual)}%</span></li>`).join("")
  const destaques = (p.destaques || []).map((d) =>
    `<li>${d.id ? `<strong>${t(d.id)}</strong> ` : ""}${t(d.texto, 180)}</li>`).join("")
  return `<article class="projeto">
    <div class="selos">${selo(p.saude, STATUS[p.saude] || p.saude)}<span class="selo">${t(p.status)}</span></div>
    <h3>${t(p.nome)}</h3>
    <p>${t(p.descricao, 400)}</p>
    ${prog ? `<p class="meta">${prog.feitos}/${prog.total} · ${pctTxt(prog.percentual)}%</p>${trilho(prog.percentual, `${pctTxt(prog.percentual)}% de ${t(p.nome)}`)}` : `<p class="mudo">Sem contagem de tarefas.</p>`}
    <p class="meta">Última atividade: ${esc(hora(p.ultima_atividade))}</p>
    ${p.nota ? `<p class="nota">${t(p.nota, 300)}</p>` : ""}
    ${frentes ? `<h4>Frentes</h4><ul class="lista">${frentes}</ul>` : ""}
    ${destaques ? `<h4>Próximas do backlog</h4><ul class="lista">${destaques}</ul>` : ""}
    ${p.url ? `<p class="links">${linkExterno(p.url, "Repositório")}</p>` : ""}
  </article>`
}

function detalhe(mod) {
  const fila = mod.aguardando_samuel || []
  const cabeca = fila.slice(0, 6).map((item) => `
    <li>
      <span class="tipo">${t(ESPERA[item.tipo] || item.tipo)} · ${t(item.urgencia)}</span>
      <span>${t(item.titulo, 180)}</span>
      ${item.detalhe ? `<span class="quando">${t(item.detalhe, 280)}</span>` : ""}
      <span class="quando">${item.desde ? `desde ${esc(dataCurta(item.desde))}` : "sem data"}${item.projeto_id ? ` · ${t(item.projeto_id)}` : ""}</span>
    </li>`).join("")
  const resto = fila.slice(6).map((item) => `<li><span>${t(item.titulo, 180)}</span><span class="quando">${t(ESPERA[item.tipo] || "")}</span></li>`).join("")
  const rotinas = (mod.rotinas || []).map((r) => `
    <li><strong>${t(r.nome)}</strong><span class="quando">${t(r.frequencia)} · última ${esc(hora(r.ultima_execucao))} · ${t(ROTINA[r.status] || r.status)}</span>${r.nota ? `<span>${t(r.nota, 200)}</span>` : ""}</li>`).join("")
  const prazos = (mod.prazos || []).map((p) => `
    <li><strong>${esc(dataCurta(p.data))}</strong><span>${t(p.titulo, 180)}</span><span class="quando">${t(PRAZO[p.tipo] || p.tipo)}</span></li>`).join("")
  const atividade = (mod.atividade || []).map((a) => `
    <li><span class="quando">${esc(hora(a.quando))}</span><span>${t(a.resumo, 240)}</span>${a.link ? linkExterno(a.link, "Abrir") : ""}</li>`).join("")
  const links = (mod.links || []).map((l) => linkExterno(l.url, l.rotulo)).filter(Boolean).join("")
  const avisos = (mod.avisos || []).map((a) => `<p class="aviso">${t(a, 300)}</p>`).join("")
  return `<button class="voltar" type="button" data-voltar>Todas as frentes</button>
    <header class="cabeca">
      <div>
        <p class="kicker">${t(mod.agente?.nome)} · ${t(FONTE[mod.fonte?.tipo] || "")}</p>
        <h2>${t(mod.nome)}</h2>
        <p class="papel">${t(mod.agente?.papel, 120)}</p>
      </div>
      <div class="selos">${selo(mod.status, STATUS[mod.status] || mod.status)}${mod.exemplo ? selo("exemplo", "Exemplo") : ""}</div>
    </header>
    <p class="resumo">${t(mod.resumo, 600)}</p>
    <p class="meta">Fonte atualizada em ${esc(hora(mod.atualizado_em))}. ${t(mod.saude?.motivo, 400)}</p>
    ${mod.exemplo ? `<p class="tarja">Dados de exemplo. Isto não é um pedido real ao Samuel.</p>` : ""}
    ${avisos ? `<div class="avisos">${avisos}</div>` : ""}
    <div class="projetos">${(mod.projetos || []).map(projeto).join("")}</div>
    <div class="grade-2" style="margin-top:12px">
      <section class="bloco"><h3>Rotinas</h3>${rotinas ? `<ul class="lista">${rotinas}</ul>` : `<p class="mudo">Nenhuma rotina informada.</p>`}</section>
      <section class="bloco"><h3>Próximos prazos</h3>${prazos ? `<ul class="lista">${prazos}</ul>` : `<p class="mudo">Nenhum prazo informado.</p>`}</section>
    </div>
    <section class="bloco" style="margin-top:12px"><h3>Na fila do Samuel</h3>
      ${cabeca ? `<ul class="lista">${cabeca}</ul>` : `<p class="mudo">Nada aguardando o Samuel neste módulo.</p>`}
      ${resto ? `<details><summary>Mostrar os outros ${fila.length - 6}</summary><ul class="lista">${resto}</ul></details>` : ""}
    </section>
    <section class="bloco" style="margin-top:12px"><h3>O que o agente fez</h3>
      ${atividade ? `<ul class="lista">${atividade}</ul>` : `<p class="mudo">Nenhuma atividade registrada.</p>`}
    </section>
    <section class="bloco" style="margin-top:12px"><h3>Links</h3>
      ${links ? `<div class="links">${links}</div>` : `<p class="mudo">Nenhum link informado.</p>`}
    </section>`
}

function desenhar() {
  const aberto = porId[estado.aberto]
  document.title = aberto ? `Painel Central · ${mostrar(aberto.nome) || "Frente"}` : "Painel Central"
  const miolo = document.querySelector("#miolo")
  miolo.innerHTML = aberto ? detalhe(aberto) : estado.aberto ? `<div class="vazio"><h2>Frente não encontrada</h2><p class="mudo">Não há módulo “${t(estado.aberto)}”.</p></div>` : lista()
  document.querySelectorAll("[data-filtro]").forEach((b) => {
    b.setAttribute("aria-pressed", b.dataset.filtro === estado.filtro ? "true" : "false")
  })
}

function casca() {
  const reais = modulos.filter((m) => !m.exemplo).length
  const fila = modulos.reduce((s, m) => s + filaReal(m).length, 0)
  const atencao = modulos.filter((m) => ["atencao", "bloqueado", "parado"].includes(m.status)).length
  const exemplos = modulos.filter((m) => m.exemplo).length
  app.innerHTML = `
    <header class="topo">
      <div class="topo-in">
        <p class="olho">Samuel · agentes no Grok Bot</p>
        <h1>Painel <em>central</em></h1>
        <p class="lede">O que cada agente está tocando, a saúde da frente e o que espera uma decisão sua.</p>
        <p class="faixa">Painel público. Só resumos já filtrados: sem nomes de clientes, valores, dados jurídicos ou financeiros, mensagens e segredos.</p>
      </div>
    </header>
    <div class="barra">
      <p class="sumario">${modulos.length} frentes · ${reais} com fonte · ${fila} na fila real · ${atencao} pedem olhar · ${exemplos} exemplos</p>
      <label class="busca"><span>Buscar frente, agente ou pendência</span><input id="busca" type="search" placeholder="Tekto, Vix, backup…"></label>
      <div class="chips">
        <button type="button" data-filtro="todas">Todas</button>
        <button type="button" data-filtro="fila">Na fila</button>
        <button type="button" data-filtro="atencao">Atenção</button>
        <button type="button" data-filtro="reais">Com fonte</button>
        <button type="button" data-filtro="exemplos">Exemplos</button>
      </div>
    </div>
    <main id="miolo"></main>
    <footer class="rodape">Tekto e VTX repetem os painéis públicos já no ar. O restante fica marcado como exemplo até o agente gravar o próprio JSON. Os painéis antigos seguem publicados.</footer>`
  desenhar()
}

function iniciar() {
  if (!modulos.length) {
    app.innerHTML = `<p class="erro">Nenhum módulo em modulos/. Rode python3 scripts/gerar.py.</p>`
    return
  }
  casca()
  app.addEventListener("input", (ev) => {
    if (ev.target.id !== "busca") return
    estado.busca = ev.target.value
    if (estado.aberto) return
    desenhar()
  })
  app.addEventListener("click", (ev) => {
    const filtro = ev.target.closest("[data-filtro]")
    if (filtro) {
      estado.filtro = filtro.dataset.filtro
      estado.aberto = ""
      if (location.hash) location.hash = ""
      else desenhar()
      return
    }
    if (ev.target.closest("[data-voltar]")) location.hash = ""
  })
  window.addEventListener("hashchange", () => {
    estado.aberto = decodeURIComponent(location.hash.replace(/^#/, ""))
    desenhar()
    window.scrollTo(0, 0)
  })
}

try {
  iniciar()
} catch (erro) {
  console.error(erro)
  app.innerHTML = `<p class="erro">Não foi possível montar o painel.</p>`
}
