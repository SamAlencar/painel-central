// Mesmas regras de scripts/sanitizar.py. A página redacta de novo na hora
// de pintar, caso um JSON ruim passe do validador.

const RISCO = [
  /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /\b(?:ghp_|gho_|ghu_|ghs_|github_pat_|xox[baprs]-|sk-[A-Za-z0-9]{10,}|AKIA[0-9A-Z]{16})/,
  /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/,
  /\b(api[_-]?key|secret|senha|password|token|bearer)\b\s*[:=]\s*\S+/i,
  /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i,
  /\b\d{3}\.\d{3}\.\d{3}-\d{2}\b/,
  /\b\d{2}\.\d{3}\.\d{3}\/\d{4}-\d{2}\b/,
  /\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b/,
  /R\$\s?\d/i,
  /\bUS\$\s?\d/i,
  /€\s?\d/,
  /\b\d{1,3}(?:\.\d{3})+,\d{2}\b/,
  /\b(?:honorários|honorarios|fatura|saldo|pix)\b.{0,40}\d/i,
  /(?:\+?55\s?)?\(\d{2}\)\s?\d{4,5}-\d{4}/,
  /\b[Cc]lientes?\s*[:\-]\s*[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ú]{2,}/,
  /\b[Cc]lientes?\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ú]{2,}(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕ][\wÀ-ú]{2,})+/,
]

export function publico(valor, limite = 500) {
  if (valor == null) return ""
  const t = String(valor).replace(/\s+/g, " ").trim()
  if (!t) return ""
  if (RISCO.some((p) => p.test(t))) return null
  if (t.length > limite) return `${t.slice(0, limite - 1).trimEnd()}…`
  return t
}

export function mostrar(valor, limite) {
  const t = publico(valor, limite)
  if (t == null) return "Conteúdo omitido na versão pública."
  return t
}

export function esc(valor) {
  return String(valor ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]))
}

export function hrefSeguro(url) {
  const t = publico(url, 400)
  if (!t) return null
  try {
    const u = new URL(t)
    if (u.protocol !== "https:" && u.protocol !== "http:") return null
    if (/[?&](token|key|secret|senha|password)=/i.test(u.href)) return null
    return u.href
  } catch {
    return null
  }
}
