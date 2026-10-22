"""Confere que todo commit do intervalo usa a identidade neutra da organização.

Uso (na raiz do site):
  python tools/verificar_autoria.py                    # intervalo padrão origin/main..HEAD
  python tools/verificar_autoria.py BASE..HEAD         # intervalo explícito (no CI: SHA base..SHA head do PR)
  python tools/verificar_autoria.py --so-autor BASE..HEAD   # só o autor (push em main, onde o committer pode variar)

Falha (código 1) se autor ou committer de algum commit for diferente de
Cesta Previa <contato@cestaprevia.com.br>.

Atenção: atualizar a branch pelo botão "Update branch" do GitHub cria um merge com committer
"GitHub <noreply@github.com>", que esta checagem recusa. Atualize localmente (rebase ou merge)
com a identidade da organização.
"""

from __future__ import annotations

import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

PERMITIDO = ("Cesta Previa", "contato@cestaprevia.com.br")
SEP = "\x1f"
INTERVALO = re.compile(r"[0-9a-fA-F]{7,40}\.\.[0-9a-fA-F]{7,40}|[\w./-]+\.\.[\w./-]+")


def main() -> int:
    args = sys.argv[1:]
    so_autor = "--so-autor" in args
    args = [a for a in args if a != "--so-autor"]
    intervalo = args[0] if args else "origin/main..HEAD"
    if intervalo.startswith("-") or not INTERVALO.fullmatch(intervalo):
        print(f"intervalo inválido: {intervalo!r} (use BASE..HEAD)", file=sys.stderr)
        return 2
    fmt = SEP.join(["%h", "%an", "%ae", "%cn", "%ce", "%s"])
    try:
        saida = subprocess.run(["git", "log", f"--format={fmt}", intervalo, "--"], capture_output=True, text=True,
                               encoding="utf-8", check=True).stdout
    except subprocess.CalledProcessError as exc:
        print(f"git log falhou para {intervalo}: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    commits = [linha.split(SEP) for linha in saida.splitlines() if linha.strip()]
    ruins = []
    for h, an, ae, cn, ce, assunto in commits:
        if (an, ae) != PERMITIDO or (not so_autor and (cn, ce) != PERMITIDO):
            ruins.append(f"{h} autor={an} <{ae}> committer={cn} <{ce}>  {assunto}")
    print(f"{len(commits)} commit(s) em {intervalo}")
    if ruins:
        print("Identidade fora do permitido (esperado Cesta Previa <contato@cestaprevia.com.br>):")
        for r in ruins:
            print(" -", r)
        return 1
    print("Autoria OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
