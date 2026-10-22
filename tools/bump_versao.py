"""Atualiza o ?v=AAAAMMDD das referências a site.css e aos *.js em todas as páginas HTML.

Uso (na raiz do site):
  python tools/bump_versao.py              # usa a data de hoje
  python tools/bump_versao.py 20261022     # usa a versão informada
  python tools/bump_versao.py --checar     # só confere: toda referência tem ?v= e a mesma versão

Rodar antes de publicar qualquer mudança em CSS ou JS: o Vercel guarda assets/ por um dia
no navegador, e a versão nova na URL força o download.
"""

from __future__ import annotations

import datetime as dt
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
REF = re.compile(r'((?:href|src)="[^"]*assets/(?:css/site\.css|js/[a-z0-9_-]+\.js))(?:\?v=(\d{8}))?"')


def paginas() -> list[Path]:
    return sorted(p for p in RAIZ.rglob("*.html") if "tools" not in p.relative_to(RAIZ).parts)


def checar() -> int:
    versoes, sem = set(), []
    for p in paginas():
        for m in REF.finditer(p.read_text(encoding="utf-8")):
            if m.group(2) is None:
                sem.append(f"{p.relative_to(RAIZ)}: {m.group(1)}")
            else:
                versoes.add(m.group(2))
    for s in sem:
        print("sem ?v=", s)
    if len(versoes) > 1:
        print("versões diferentes:", sorted(versoes))
    ok = not sem and len(versoes) <= 1
    print("OK" if ok else "FALHA", sorted(versoes))
    return 0 if ok else 1


def bump(versao: str) -> int:
    if not re.fullmatch(r"\d{8}", versao):
        print("versão deve ser AAAAMMDD", file=sys.stderr)
        return 2
    total = 0
    for p in paginas():
        bruto = p.read_bytes().decode("utf-8")
        novo, n = REF.subn(lambda m: f'{m.group(1)}?v={versao}"', bruto)
        if n:
            p.write_bytes(novo.encode("utf-8"))
            total += n
            print(f"{p.relative_to(RAIZ)}: {n} referência(s)")
    print(f"{total} referências em ?v={versao}")
    return 0


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().strftime("%Y%m%d")
    sys.exit(checar() if arg == "--checar" else bump(arg))
