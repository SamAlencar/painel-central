# Painel Central

Painel público único das frentes que os agentes do Grok Bot tocam para o Samuel (GitHub [SamAlencar](https://github.com/SamAlencar)). Substitui, quando a migração fechar, o [tekto-calc-painel](https://github.com/SamAlencar/tekto-calc-painel) e o [vtx_painel](https://github.com/SamAlencar/vtx_painel). A visão de portfólio, saúde e fila de aprovação vem de `vtx-acompanhamento` (`docs/visao.md`); esse repositório é privado e não entrou nesta leitura.

O site é estático. Cada frente é um JSON em `modulos/<id>.json`, validado por `schema/modulo.schema.json`. O `PAINEL.md` repete o resumo para quem abre o repositório sem hospedagem.

## O que está ligado agora

| Módulo | Agente | Fonte | O que dá para confiar |
| --- | --- | --- | --- |
| Tekto | Eng/Tek | Espelho público do tekto-calc-painel | Contagens, dúvidas de backlog, previsões de ritmo e PRs já publicados naquele painel. Seis repos: tekto-calc, tekto-docs, tekto-model, tekto-studio, tek-team, tek-hunter. |
| VTX | Vix | Espelho público do vtx_painel | Progresso e títulos já publicados do vtx-core. A fila de aprovação do Samuel ainda não vem marcada no backlog. |
| Pub | Pub | API pública do GitHub | Só metadados de `SamAlencar/pub-policy` (último push). O HTML da política não é copiado. |
| 4medco | Bil | Exemplo | Prefixo `4medco-*` não apareceu na listagem pública. |
| Dar | Dar | Exemplo | `dark-channel-playbook` e `engenharia-explicada` não apareceram na listagem pública. |
| Jur, Fin/Pow, Stu, Mar, Sys, Tzu | Jur, Fin/Pow, Stu, Mar, Sys, Tzu | Exemplo | Sem repositório ligado, de propósito. |

Nada aqui foi arquivado. Os dois painéis antigos continuam no ar.

### O que falta para dado real

1. **Tekto e VTX direto da fonte.** Numa máquina com `gh auth login` ou com `GITHUB_TOKEN` / `GH_TOKEN` que leia os repositórios privados, `python3 scripts/gerar.py` troca o espelho pela API. A Tekto relê `docs/BACKLOG.md`, `docs/DUVIDAS.md` e PRs mesclados (a mesma lógica de `gerar_dados.py`). A VTX procura `data/backlog.json` em `SamAlencar/vtx-core` e só copia id, título, área, fase e status.
2. **4medco e Dar.** Quando esses repositórios aparecerem para o token, o gerador grava nome, descrição e data de push. Não lê arquivo, issue nem comentário.
3. **Jur, Fin/Pow, Stu, Mar, Sys, Tzu.** O agente da frente edita o JSON e abre commit ou PR. Não há coleta automática: e-mail, agenda, processo, extrato e nota de aluno não devem ser puxados para um site público.
4. **Nomes de clientes.** Se um nome próprio não pode aparecer nem em título de tarefa, acrescente uma linha em `config/nao_publicar.txt`.

## Como cada agente atualiza o próprio módulo

Módulos manuais: `jur`, `fin`, `stu`, `mar`, `sys`, `tzu`. Também vale para qualquer frente que você queira tirar do gerador.

1. Edite `modulos/<id>.json`. O id é o nome do arquivo e precisa estar em `config/ordem.json`.
2. Siga `schema/modulo.schema.json`. Campos: agente, status, projetos, prazos, rotinas (`nome`, `frequencia`, `ultima_execucao`), `aguardando_samuel` e `links`.
3. Quando o conteúdo for real, mude `exemplo` para `false`, `fonte.tipo` para `manual` e tire a palavra "Exemplo" do resumo. O gerador **não reescreve** `fonte.tipo: manual`.
4. Escreva só resumo. Sem valor, conta, processo, parte, nome de cliente, remetente, assunto de e-mail, matrícula, host ou segredo. Se a pendência for sensível, diga o tipo ("conciliação periódica pendente") e pare.
5. Rode `python3 scripts/validar.py`. Se um texto casar com o filtro, o validador recusa e **não imprime o valor**.
6. Abra o PR ou o commit. O workflow de pull request valida de novo.

Tekto, VTX e Pub são gerados. Não edite esses JSON à mão: o próximo `scripts/gerar.py` cobre o arquivo. Ajuste o backlog no repositório de origem ou o próprio gerador.

`--semear` reescreve só módulos que ainda estão como exemplo. Não mexe em `manual`.

## Rodar localmente

Requisitos: Node 22, Python 3.12 e pip. Tudo gratuito.

```bash
python3 -m pip install -r requirements.txt
python3 scripts/testar.py
python3 scripts/gerar.py          # opcional: refresca Tekto, VTX e Pub
npm install
npm run dev
```

Abre em <http://127.0.0.1:4471>. `npm run build` valida os JSON e gera `dist/`. `npm run preview` serve esse build na mesma porta.

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

- Ler só o `PAINEL.md` num repositório privado, sem Pages.
- Cloudflare Pages no plano gratuito, com Cloudflare Access na frente (o Access gratuito cobre um grupo pequeno de usuários).

Enquanto a decisão for a atual, o site é o Pages público e o filtro abaixo é obrigatório.

## Sanitização

O gerador só grava campos de uma lista branca. O validador recusa, em qualquer string do JSON, o que parecer:

- valor em real, dólar ou euro, inclusive no formato `1.234,56`
- CPF, CNPJ, telefone com DDD, e-mail
- número de processo no padrão CNJ
- token (`ghp_`, `github_pat_`, `sk-`, chave AWS, JWT, `senha=` / `token=`)
- nome próprio depois de "cliente" (`cliente João Silva`, `cliente: Oficina`)

"Cliente" sozinho, "contrato" de API e "valores da NBR" continuam, porque já são o vocabulário público dos backlogs de engenharia. Termos extras ficam em `config/nao_publicar.txt`, uma expressão por linha.

A página aplica o mesmo filtro de novo na hora de desenhar. Um JSON que escapasse ainda assim não seria pintado por inteiro.

Jurídico, financeiro e pessoal (Jur, Fin/Pow, Tzu) não têm coleta. O exemplo deixa explícito que o conteúdo foi omitido.

## Schema

`schema/modulo.schema.json` (JSON Schema 2020-12) descreve cada campo. Resumo:

- `agente` — quem responde pela frente
- `status` — `saudavel`, `atencao`, `bloqueado`, `parado`, `planejado`
- `projetos[]` — repo, progresso, saúde, frentes e próximas tarefas
- `prazos[]` — data e tipo (`previsao` é ritmo calculado, não compromisso)
- `rotinas[]` — `nome`, `frequencia`, `ultima_execucao`, `status`
- `aguardando_samuel[]` — título curto, urgência e tipo (`duvida`, `aprovacao`, `leitura`, `rotina`, `exemplo`)
- `atividade[]` — o que o agente fez
- `links[]` — rótulo e URL `http(s)`
- `exemplo` — `true` tira o módulo da fila real

`python3 scripts/validar.py` confere os onze arquivos de `config/ordem.json`.

## Migração

Rodar as duas gerações em paralelo por uma ou duas semanas:

1. Este painel no ar, ao lado de <https://samalencar.github.io/tekto-calc-painel/> e <https://samalencar.github.io/vtx_painel/>.
2. Conferir se os números da Tekto (179/625 na leitura de 24/10/2026) e da VTX (36/142) batem com os painéis antigos.
3. Cada agente passa a gravar o próprio módulo aqui.
4. Só depois disso, arquivar `tekto-calc-painel` e `vtx_painel` no GitHub. **Não arquivar agora.** Este repositório não faz isso.

## Comandos

| Comando | Efeito |
| --- | --- |
| `python3 scripts/gerar.py` | Atualiza Tekto, VTX, Pub e a descoberta de 4medco/Dar. Reescreve `PAINEL.md`. |
| `python3 scripts/gerar.py --somente tekto,vtx` | Só essas frentes. |
| `python3 scripts/gerar.py --semear` | Recria os exemplos que ainda não viraram `manual`. |
| `python3 scripts/gerar.py --somente-painel` | Só reescreve o `PAINEL.md` a partir dos JSON. |
| `python3 scripts/validar.py` | Schema + filtro público. |
| `python3 scripts/testar.py` | Parser, filtro e exemplos, sem rede. |
| `npm run dev` / `npm run build` | Site local / `dist/` para o Pages. |
