#!/usr/bin/env bash
# Atualiza os módulos que vêm do GitHub e reescreve o PAINEL.md.
# Não faz commit. Com gh autenticado, Tekto e VTX são lidos nos repositórios;
# sem token, o gerador usa o espelho público.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/gerar.py "$@"
