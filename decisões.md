# Decisões

- O painel é público no GitHub Pages, com `base: "./"`, no mesmo espírito do tekto-calc-painel e do vtx_painel. Dado que não passa no filtro não entra no JSON.
- Tekto reutiliza o parser de `gerar_dados.py` quando há `gh` autenticado ou token. Sem acesso aos repos privados, os números vêm do `data.json` já publicado. VTX faz o mesmo com `data/backlog.json`, copiando só id, título, área, fase e status.
- 4medco e Dar, se um dia aparecerem na API, entram só com metadados (nome, descrição, push). Arquivo, issue e comentário não são lidos. Jur, Fin, Stu, Mar, Sys e Tzu não têm coleta: e-mail, agenda, processo e extrato não alimentam um site público.
- `fonte.tipo: manual` não é reescrito pelo gerador. Exemplo só é recriado com `--semear`.
- O validador e a página aplicam o mesmo filtro. O validador não imprime o trecho recusado.
- Os painéis antigos continuam no ar. Este repositório não arquiva nada.
