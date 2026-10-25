# Decisões

- O painel é público no GitHub Pages, com `base: "./"`. Dado que não passa no filtro não entra no JSON.
- Tekto reutiliza o parser de `gerar_dados.py` quando há `gh` autenticado ou token. Sem acesso aos repos privados, os números vêm do `data.json` já publicado. VTX faz o mesmo com `data/backlog.json`, copiando só id, título, área, fase e status.
- Escopo reduzido em 24/10/2026 a Tekto (um módulo por projeto), VTX, 4med.co e Dark Channel. 4med.co e Dark Channel entram só com metadados e títulos de commit filtrados; arquivo, issue e comentário não são lidos.
- `fonte.tipo: manual` não é reescrito pelo gerador. Exemplo só é recriado com `--semear`.
- O validador e a página aplicam o mesmo filtro. O validador não imprime o trecho recusado.
- Os painéis antigos continuam no ar. Este repositório não arquiva nada.
