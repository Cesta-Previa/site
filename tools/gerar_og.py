"""Gera assets/img/og-previa.png (1200x630) para Open Graph e Twitter.

Uso (na raiz do site):  python tools/gerar_og.py

Wordmark PRÉVIA + linha de previsão (observado cheio, estimativa tracejada, faixa de
incerteza e o ponto âmbar no fim) sobre o papel, nas cores e fontes do guia de identidade.
Desenha em 2x e reduz (antisserrilhado), depois reduz a paleta para ficar abaixo de 80 KB.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parent.parent
FONTES = RAIZ / "assets" / "fonts"
SAIDA = RAIZ / "assets" / "img" / "og-previa.png"
LIMITE_BYTES = 80 * 1024

PAPEL = (250, 250, 247)
NAVY = (13, 43, 69)
VERDE = (27, 94, 32)
AMBAR = (245, 158, 11)
MUTED = (90, 107, 120)
LINHA = (216, 222, 220)

K = 2  # fator de supersampling
W, H = 1200 * K, 630 * K


def fonte(nome: str, tam: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / nome), tam * K)


def tracejado(d: ImageDraw.ImageDraw, p0, p1, cor, largura, traco, vao):
    (x0, y0), (x1, y1) = p0, p1
    comp = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    ux, uy = (x1 - x0) / comp, (y1 - y0) / comp
    pos = 0.0
    while pos < comp:
        fim = min(pos + traco, comp)
        d.line([(x0 + ux * pos, y0 + uy * pos), (x0 + ux * fim, y0 + uy * fim)], fill=cor, width=largura)
        pos = fim + vao


def simbolo(d: ImageDraw.ImageDraw, x: float, y: float, escala: float):
    """Cesta + linha de dado + ponto âmbar (mesmo desenho do SVG do site, viewBox 72x72)."""
    def p(px, py):
        return (x + px * escala, y + py * escala)
    lw = round(5 * escala)
    d.line([p(22, 30), p(30, 17), p(44, 17), p(50, 27)], fill=VERDE, width=lw, joint="curve")
    d.line([p(15, 30), p(57, 30), p(52, 55), p(20, 55), p(15, 30)], fill=VERDE, width=lw, joint="curve")
    d.line([p(22, 40), p(33, 30), p(41, 36), p(62, 15)], fill=NAVY, width=lw, joint="curve")
    cx, cy = p(62, 15)
    r = 6 * escala
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=AMBAR)


def gerar() -> int:
    img = Image.new("RGB", (W, H), PAPEL)
    d = ImageDraw.Draw(img, "RGBA")

    # Marca: símbolo + wordmark
    mx, my = 96 * K, 120 * K
    simbolo(d, mx, my - 18 * K, 2.2 * K)
    f_wm = fonte("space-grotesk-700.woff2", 112)
    x = mx + 175 * K
    for parte, cor in (("PRÉV", NAVY), ("I", VERDE), ("A", AMBAR)):
        d.text((x, my), parte, font=f_wm, fill=cor)
        x += d.textlength(parte, font=f_wm) + 4 * K
    f_sub = fonte("inter-600.woff2", 36)
    d.text((mx, my + 170 * K), "Estimativa do preço dos", font=f_sub, fill=NAVY)
    d.text((mx, my + 220 * K), "alimentos no Rio (demonstração)", font=f_sub, fill=NAVY)

    # Linha de previsão (canto inferior direito)
    base_y = 560 * K
    d.line([(96 * K, base_y), (1104 * K, base_y)], fill=LINHA, width=2 * K)
    obs = [(620, 470), (680, 452), (740, 478), (800, 440), (860, 456), (910, 424), (950, 414)]
    obs = [(a * K, b * K) for a, b in obs]
    hoje = obs[-1]
    fim = (1080 * K, 330 * K)
    banda = [hoje, (fim[0], 250 * K), (fim[0], 410 * K)]
    d.polygon(banda, fill=VERDE + (38,))
    d.line(obs, fill=VERDE, width=6 * K, joint="curve")
    tracejado(d, hoje, fim, VERDE, 6 * K, 16 * K, 12 * K)
    r = 13 * K
    d.ellipse([fim[0] - r, fim[1] - r, fim[0] + r, fim[1] + r], fill=AMBAR)

    f_url = fonte("inter-400.woff2", 26)
    d.text((96 * K, 578 * K), "cestaprevia.com.br", font=f_url, fill=MUTED)

    final = img.resize((1200, 630), Image.LANCZOS)
    final = final.quantize(colors=48, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    final.save(SAIDA, "PNG", optimize=True)
    tamanho = SAIDA.stat().st_size
    print(f"{SAIDA.relative_to(RAIZ)}: {final.size[0]}x{final.size[1]}, {tamanho / 1024:.1f} KB")
    if tamanho >= LIMITE_BYTES:
        print("ERRO: imagem acima de 80 KB", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(gerar())
