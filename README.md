# Painel Central

Painel público e estático com os projetos tocados pelos agentes do Samuel: **Tekto**, **VTX**, **4med.co** e **Dark Channel**. Visual inspirado no [painel da VTX](https://samalencar.github.io/vtx_painel/): cartões de resumo, barras de progresso, roscas e gráfico de tarefas por projeto.

Publicado em <https://samalencar.github.io/painel-central/>.

## Módulos (`config/ordem.json`)

| Módulo | Frente | Fonte |
| --- | --- | --- |
| `tekto-calc`, `tekto-docs`, `tekto-model`, `tekto-studio`, `tek-team`, `tek-hunter` | Tekto (um módulo por projeto) | Backlogs lidos via GitHub (`gh`); sem token, espelho do `tekto-calc-painel` |
| `vtx` | VTX | Backlog do `vtx-core` via GitHub; sem ele, espelho do `vtx_painel` |
| `4medco` | 4med.co | Metadados dos repositórios `4medco-*` + títulos de commit filtrados |
| `dark-channel` | Dark Channel | Metadados de `dark-channel-playbook` e `engenharia-explicada` + títulos de commit filtrados |

Se uma fonte não estiver acessível, o gerador usa uma semente marcada como **Exemplo** (`exemplo: true`), exibida com aviso no site.

## Sanitização

O repositório é público. Tudo passa por `scripts/sanitizar.py` (e de novo por `src/sanitizar.js` na hora de pintar): sem nomes de clientes, valores, documentos, e-mails ou segredos.

## Comandos

| Comando | O que faz |
| --- | --- |
| `python3 scripts/gerar.py` | Atualiza todos os módulos e reescreve `PAINEL.md` |
| `python3 scripts/validar.py` | Valida `modulos/*.json` contra o schema e o filtro público |
| `python3 scripts/testar.py` | Testes do gerador e do filtro |
| `npm ci && npm run build && python3 scripts/checar_build.py` | Build do site em `dist/` |


`scripts/atualizar.sh` é o mesmo `gerar.py`, sem commit e sem push.

## Publicar no GitHub Pages

O painel é **público**, como o Tekto e a VTX hoje. O build usa `base: "./"` para funcionar tanto na raiz quanto em `https://<usuário>.github.io/<repo>/`.

1. O repositório precisa ser **público**. No plano gratuito, Pages de repositório privado não fica disponível (e este JSON não deve ir para um lugar que alguém trate como cofre).
2. Envie a branch `main`.
3. No GitHub: Settings → Pages → Build and deployment → Source: **GitHub Actions**.
4. O workflow `.github/workflows/pages.yml` valida, testa, gera `dist/` e publica a cada push na `main`. Também dá para disparar à mão em Actions → Publicar no GitHub Pages.
5. Na primeira vez o GitHub pode pedir aprovação do ambiente `github-pages`. A URL aparece no final do job de deploy e em Settings → Pages. No padrão fica `https://samalencar.github.io/<nome-do-repo>/`.
6. Se o workflow falhar com página ainda não criada, confirme o passo 3 e rode de novo.

O que o workflow não faz: não lê repositório privado e não reescreve `modulos/`. Quem atualiza número de Tekto/VTX roda o gerador localmente (com token, se quiser a fonte direta) e commita o JSON. Assim um cron não precisa de segredo com permissão de escrita.

Pull requests passam por `.github/workflows/validar.yml` (schema, filtro público, testes e build). O validador impede o deploy, mas um commit que já foi para um repositório público continua visível no histórico. Rode `python3 scripts/validar.py` antes do push.

## Se um dia o painel deixar de ser público

Não coloque o dado sensível neste repositório enquanto o Pages estiver ligado. Caminhos sem custo, se a decisão mudar:
