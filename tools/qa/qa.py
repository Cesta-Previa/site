"""QA do site cestaprevia.com.br (fora do deploy; ver .vercelignore).

Uso (na raiz do site):
  python tools/qa/qa.py                         # sobe um servidor próprio com os cabeçalhos do vercel.json (CSP inclusa)
  python tools/qa/qa.py --url http://127.0.0.1:8000   # usa um servidor já no ar (ex.: python -m http.server 8000)

Abre cada página no Chromium headless (desktop 1366x900 e celular 390x844), salva screenshots de página
inteira em tools/qa/_saida/ e falha (código 1) se encontrar:
- requisição a outro domínio, erro de console/CSP/rede, HTTP diferente de 200;
- termo proibido no texto renderizado ou nos arquivos publicados (lista genérica + QA_PROIBIDOS_EXTRA);
- data fixa (dd/mm/aaaa) no HTML, [data-site] sem preencher, rodapé diferente entre as páginas;
- canonical/Open Graph/twitter:card incompletos, sitemap ou robots inconsistentes, JSON-LD inválido;
- contraste de texto abaixo de AA, borda de campo abaixo de 3:1, elemento focável sem indicador de foco;
- estouro horizontal no celular, imagem quebrada, link interno quebrado, ?v= ausente em CSS/JS;
- regressão funcional da demo, da acurácia e do boletim (inclui acima/abaixo e realizado nulo).

Termos extras (nomes, siglas) vêm da variável de ambiente QA_PROIBIDOS_EXTRA, um regex com alternativas
separadas por |. No CI ela vem de um secret; localmente, de uma linha QA_PROIBIDOS_EXTRA=... no arquivo .env
na raiz do site (ignorado pelo git e pelo deploy).
"""

from __future__ import annotations

import argparse
import copy
import functools
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = Path(__file__).resolve().parent / "_saida"
URL_PUBLICA = "https://cestaprevia.com.br"

# Termos genéricos: jargão de edital, conselho de momento de compra, promessa vaga
PROIBIDOS = re.compile(
    r"em breve|m[eê]s 6|banca|Fase 2|conta exclusiva|bolsista|proponente|compre agora|hora de comprar|estoc|"
    r"sem[aá]foro|antecipar|adiar|melhor momento",
    re.IGNORECASE,
)


def _extra():
    valor = os.environ.get("QA_PROIBIDOS_EXTRA", "").strip()
    env = RAIZ / ".env"
    if not valor and env.is_file():
        for linha in env.read_text(encoding="utf-8").splitlines():
            if linha.startswith("QA_PROIBIDOS_EXTRA="):
                valor = linha.split("=", 1)[1].strip().strip('"')
    return re.compile(valor, re.IGNORECASE) if valor else None


PROIBIDOS_EXTRA = _extra()


CONTAGEM = {"generica": 0, "extra": 0}


def proibidos(txt: str) -> list[str]:
    """Descrição de cada achado. Termos da lista extra nunca são impressos (a lista é sigilosa)."""
    achados = [f"'{m.group(0)}'" for m in PROIBIDOS.finditer(txt)]
    CONTAGEM["generica"] += len(achados)
    if PROIBIDOS_EXTRA:
        n = sum(1 for _ in PROIBIDOS_EXTRA.finditer(txt))
        CONTAGEM["extra"] += n
        achados += ["termo da lista extra"] * n
    return achados
DATA_FIXA = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")

INDEXAVEIS = [("index", "/"), ("demo", "/demo/"), ("acuracia", "/acuracia/"), ("boletim", "/boletim/"),
              ("metodologia", "/metodologia/"), ("contato", "/contato/"), ("privacidade", "/privacidade/"),
              ("termos", "/termos/")]
PAGINAS = INDEXAVEIS + [("404", "/404.html")]
COM_NOSCRIPT = {"index.html", "demo/index.html", "acuracia/index.html", "boletim/index.html", "metodologia/index.html"}
VIEWPORTS = {"desktop": {"width": 1366, "height": 900}, "mobile": {"width": 390, "height": 844}}
EXT_PUBLICADAS = {".html", ".css", ".js", ".json", ".txt", ".xml", ".webmanifest"}
FORA_DO_DEPLOY = {"tools", ".github", "docs", ".git"}

REGRAS = [(re.compile("^" + r["source"] + "$"), {h["key"]: h["value"] for h in r["headers"]})
          for r in json.loads((RAIZ / "vercel.json").read_text(encoding="utf-8"))["headers"]]


def cabecalhos(caminho: str) -> dict:
    """Cabeçalhos do vercel.json que valem para o caminho (regra posterior sobrescreve a anterior)."""
    saida = {}
    for rx, hs in REGRAS:
        if rx.match(caminho):
            saida.update(hs)
    return saida


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".webmanifest": "application/manifest+json", ".woff2": "font/woff2", ".json": "application/json"}

    def end_headers(self):
        for k, v in cabecalhos(self.path.split("?")[0]).items():
            self.send_header(k, v)
        super().end_headers()

    def log_message(self, *args):
        pass


def servidor():
    handler = functools.partial(Handler, directory=str(RAIZ))
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


JS_CONTRASTE = r"""
() => {
  function rgb(s){const m=s.match(/rgba?\(([^)]+)\)/); if(!m) return null; const p=m[1].split(',').map(x=>parseFloat(x)); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
  function lum(c){const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);}
  function fundo(el){let e=el; while(e){const c=rgb(getComputedStyle(e).backgroundColor); if(c&&c.a>0.9) return c; e=e.parentElement;} return {r:255,g:255,b:255,a:1};}
  function razao(a,b){const L1=lum(a),L2=lum(b); return (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);}
  const falhas=[]; const vistos=new Set();
  document.querySelectorAll('body *').forEach(el=>{
    if (el.closest('svg,[aria-hidden="true"],.sr-only,script,style,option,noscript')) return;
    const temTexto=[...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim().length>0);
    if(!temTexto) return;
    const r=el.getBoundingClientRect(); if(r.width===0||r.height===0) return;
    const cs=getComputedStyle(el); if(cs.visibility==='hidden'||cs.display==='none') return;
    const fg=rgb(cs.color), bg=fundo(el); if(!fg) return;
    const ratio=razao(fg,bg);
    const tam=parseFloat(cs.fontSize), peso=parseInt(cs.fontWeight)||400;
    const grande= tam>=24 || (tam>=18.66 && peso>=700);
    const minimo= grande?3:4.5;
    if(ratio<minimo){const chave=el.tagName+'|'+cs.color+'|'+cs.backgroundColor+'|'+el.className; if(!vistos.has(chave)){vistos.add(chave); falhas.push({tipo:'texto',tag:el.tagName,classe:el.className,texto:el.textContent.trim().slice(0,50),ratio:Math.round(ratio*100)/100});}}
  });
  document.querySelectorAll('select, input').forEach(el=>{
    const cs=getComputedStyle(el); if(cs.display==='none') return;
    const borda=rgb(cs.borderTopColor), bg=fundo(el.parentElement);
    if(!borda) return;
    const ratio=razao(borda,bg);
    if(ratio<3 && !vistos.has('campo|'+cs.borderTopColor)){vistos.add('campo|'+cs.borderTopColor); falhas.push({tipo:'borda de campo',tag:el.tagName,classe:el.className,texto:el.id,ratio:Math.round(ratio*100)/100});}
  });
  return falhas;
}
"""

JS_FOCO = r"""
() => {
  const a = document.activeElement;
  if (!a || a === document.body) return null;
  function rgb(s){const m=(s||'').match(/rgba?\(([^)]+)\)/); if(!m) return null; const p=m[1].split(',').map(x=>parseFloat(x)); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
  function lum(c){const f=v=>{v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4)};return 0.2126*f(c.r)+0.7152*f(c.g)+0.0722*f(c.b);}
  function fundo(el){let e=el; while(e){const c=rgb(getComputedStyle(e).backgroundColor); if(c&&c.a>0.9) return c; e=e.parentElement;} return {r:255,g:255,b:255,a:1};}
  function razao(x,y){const L1=lum(x),L2=lum(y); return (Math.max(L1,L2)+0.05)/(Math.min(L1,L2)+0.05);}
  const cs = getComputedStyle(a);
  const bg = fundo(a.parentElement);
  let melhor = 0;
  if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) { const c = rgb(cs.outlineColor); if (c) melhor = Math.max(melhor, razao(c, bg)); }
  if (cs.boxShadow && cs.boxShadow !== 'none') { const c = rgb(cs.boxShadow); if (c) melhor = Math.max(melhor, razao(c, bg)); }
  return {ok: melhor >= 3, ratio: Math.round(melhor * 100) / 100,
          descr: a.tagName + (a.id ? '#' + a.id : '') + ' ' + (a.textContent || a.getAttribute('aria-label') || '').trim().slice(0, 40)};
}
"""


def publicados() -> list[Path]:
    return [p for p in RAIZ.rglob("*") if p.is_file() and p.suffix in EXT_PUBLICADAS
            and not (FORA_DO_DEPLOY & set(p.relative_to(RAIZ).parts)) and p.name != "README.md"]


def html_fontes() -> dict[str, str]:
    arqs = ["index.html", "404.html"] + [f"{r.strip('/')}/index.html" for _, r in INDEXAVEIS if r != "/"]
    return {a: (RAIZ / a).read_text(encoding="utf-8").replace("\r\n", "\n") for a in arqs}


def checar_arquivos(falhas: list[str]) -> int:
    arqs = publicados()
    for arq in arqs:
        txt = arq.read_text(encoding="utf-8")
        for m in proibidos(txt):
            falhas.append(f"termo proibido {m} em {arq.relative_to(RAIZ)}")

    fontes = html_fontes()
    rodapes = {}
    for nome, txt in fontes.items():
        for m in DATA_FIXA.finditer(txt):
            falhas.append(f"data fixa '{m.group(0)}' em {nome}")
        m = re.search(r'<footer class="rodape">.*?</footer>', txt, re.S)
        rodapes[nome] = m.group(0) if m else None
        if nome in COM_NOSCRIPT and "<noscript>" not in txt:
            falhas.append(f"{nome}: sem <noscript>")
        for ref in re.findall(r'(?:href|src)="([^"]*assets/(?:css/site\.css|js/[a-z0-9_-]+\.js)[^"]*)"', txt):
            if not re.search(r"\?v=\d{8}$", ref):
                falhas.append(f"{nome}: referência sem ?v=AAAAMMDD: {ref}")
        if re.search(r"fonts\.(googleapis|gstatic)\.com", txt):
            falhas.append(f"{nome}: ainda referencia Google Fonts")
    modelo = rodapes.get("index.html")
    for nome, rod in rodapes.items():
        if rod is None:
            falhas.append(f"{nome}: sem rodapé")
        elif rod != modelo:
            falhas.append(f"{nome}: rodapé diferente do da página inicial")
    if 'data-site="versao"' not in (modelo or ""):
        falhas.append("rodapé sem <time data-site=\"versao\">")

    # robots e sitemap
    robots = (RAIZ / "robots.txt").read_text(encoding="utf-8")
    if not re.search(r"(?im)^User-agent:\s*\*\s*$", robots) or not re.search(r"(?im)^Allow:\s*/\s*$", robots) \
            or f"Sitemap: {URL_PUBLICA}/sitemap.xml" not in robots:
        falhas.append("robots.txt incompleto (User-agent, Allow ou Sitemap)")
    locs = re.findall(r"<loc>([^<]+)</loc>", (RAIZ / "sitemap.xml").read_text(encoding="utf-8"))
    esperado = {URL_PUBLICA + r for _, r in INDEXAVEIS}
    if set(locs) != esperado or len(locs) != len(esperado):
        falhas.append(f"sitemap.xml difere das páginas indexáveis: {sorted(set(locs) ^ esperado)}")
    man = json.loads((RAIZ / "site.webmanifest").read_text(encoding="utf-8"))
    if not any(i.get("src", "").endswith("icone-192.png") for i in man.get("icons", [])):
        falhas.append("site.webmanifest sem icone-192.png")
    return len(arqs)


def checar_meta(pg, nome, rota, falhas):
    pref = f"[meta {rota}]"
    meta = pg.evaluate("""() => {
      const m = s => { const e = document.querySelector(s); return e ? (e.getAttribute('content') || e.getAttribute('href')) : null; };
      return {title: document.title, canonical: m('link[rel=canonical]'), ogurl: m('meta[property="og:url"]'),
        site: m('meta[property="og:site_name"]'), locale: m('meta[property="og:locale"]'), type: m('meta[property="og:type"]'),
        image: m('meta[property="og:image"]'), ogtitle: m('meta[property="og:title"]'), ogdesc: m('meta[property="og:description"]'),
        card: m('meta[name="twitter:card"]'), desc: m('meta[name=description]'), robots: m('meta[name=robots]'),
        ld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => s.textContent)};
    }""")
    if nome == "404":
        if meta["robots"] != "noindex":
            falhas.append(f"{pref} 404 sem noindex")
        return
    url = URL_PUBLICA + rota
    if not meta["title"].endswith(" · Cesta Prévia"):
        falhas.append(f"{pref} <title> fora do padrão 'Página · Cesta Prévia': {meta['title']}")
    for chave, esperado in [("canonical", url), ("ogurl", url), ("site", "Cesta Prévia"), ("locale", "pt_BR"),
                            ("card", "summary_large_image"), ("image", URL_PUBLICA + "/assets/img/og-previa.png")]:
        if meta[chave] != esperado:
            falhas.append(f"{pref} {chave} = {meta[chave]!r}, esperado {esperado!r}")
    for chave in ("type", "ogtitle", "ogdesc", "desc"):
        if not meta[chave]:
            falhas.append(f"{pref} sem {chave}")
    if nome == "index":
        try:
            ld = json.loads(meta["ld"][0])
            ok = (ld.get("@context") == "https://schema.org" and ld.get("@type") == "Organization" and ld.get("name") == "Cesta Prévia"
                  and ld.get("alternateName") == "PRÉVIA" and ld.get("url") and ld.get("logo")
                  and ld.get("contactPoint", {}).get("email") == "contato@cestaprevia.com.br")
            if not ok:
                falhas.append(f"{pref} JSON-LD Organization incompleto: {ld}")
        except (IndexError, ValueError) as exc:
            falhas.append(f"{pref} JSON-LD ausente ou inválido ({exc})")


def checar_foco(pg, rota, falhas, limite=160):
    pg.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0); }")
    pg.mouse.click(1, 1)
    vistos, sem = 0, []
    primeiro = None
    for _ in range(limite):
        pg.keyboard.press("Tab")
        r = pg.evaluate(JS_FOCO)
        if r is None:
            continue
        if r["descr"] == primeiro:
            break
        primeiro = primeiro or r["descr"]
        vistos += 1
        if not r["ok"]:
            sem.append(f'{r["descr"]} (anel {r["ratio"]}:1 contra o fundo)')
    for s in sorted(set(sem)):
        falhas.append(f"[foco {rota}] indicador ausente ou abaixo de 3:1: {s}")
    return vistos


def checar_funcional(pg, nome, falhas):
    if nome == "demo":
        linhas = pg.locator("#corpo-itens tr").count()
        if linhas != 9:
            falhas.append(f"demo: tabela com {linhas} linhas (esperado 9)")
        if pg.locator("#corpo-itens .status-estimativa").count() != 7:
            falhas.append("demo: mês mais recente deveria ter 7 séries com estimativa")
        if pg.locator("#grafico svg path").count() < 4:
            falhas.append("demo: gráfico sem linhas")
        if "R$" not in pg.inner_text("#resultado-cesta"):
            falhas.append("demo: Minha Cesta sem resultado")
        if pg.get_attribute("#resultado-cesta", "aria-live") is not None:
            falhas.append("demo: #resultado-cesta não deveria ser região viva")
        if pg.get_attribute("#resumo-cesta", "aria-live") != "polite":
            falhas.append("demo: #resumo-cesta sem aria-live=polite")
        pg.select_option("#sel-mes", "2023-12")
        if pg.locator("#corpo-itens .status-sem_recomendacao").count() != 9:
            falhas.append("demo: dez/2023 (histórico curto) deveria mostrar 'sem recomendação' nas 9 séries")
        if not re.search(r"Parcela do gasto com estimativa\s+0%", pg.inner_text("#resultado-cesta")):
            falhas.append("demo: em dez/2023 a cobertura da Minha Cesta deveria ser 0%")
        pg.select_option("#sel-mes", "2026-09")
        campo = "#cesta-linhas .cesta-linha:first-child input[inputmode=decimal]"
        pg.fill(campo, "abc")
        if pg.get_attribute(campo, "aria-invalid") != "true":
            falhas.append("demo: entrada inválida não marcada com aria-invalid")
        pg.click("#restaurar")
        pg.fill(campo, "130")
        pg.wait_for_timeout(250)
        if pg.inner_text("#resumo-cesta").strip() and "130" in pg.inner_text("#resumo-cesta"):
            falhas.append("demo: resumo anunciado antes dos 600 ms")
        pg.wait_for_timeout(700)
        if "Custo estimado do mês" not in pg.inner_text("#resumo-cesta"):
            falhas.append("demo: #resumo-cesta não foi atualizado após 600 ms")
        pg.click("#restaurar")
        pg.click("#add-item")
        if pg.locator("#cesta-linhas .cesta-linha").count() != 8:
            falhas.append("demo: adicionar item não criou linha")
        pg.click("#restaurar")
        pg.select_option("#sel-serie", "ipca:ovo")
        if "Ovo" not in pg.inner_text("#t-comp-serie"):
            falhas.append("demo: troca de série não atualizou componentes")
        pg.select_option("#sel-serie", "ipca:tomate")
    elif nome == "acuracia":
        if pg.locator("#corpo-placar tr").count() != 3:
            falhas.append("acuracia: placar deveria ter 3 horizontes")
        if pg.locator("#corpo-metricas tr").count() != 9:
            falhas.append("acuracia: tabela h=1 deveria ter 9 linhas")
        pg.select_option("#sel-h", "todos")
        if pg.locator("#corpo-metricas tr").count() != 27:
            falhas.append("acuracia: tabela 'todos' deveria ter 27 linhas")
        pg.select_option("#sel-h", "1")
        if pg.locator("#placar").count() != 1:
            falhas.append("acuracia: âncora #placar ausente")
        n_img = pg.evaluate("async () => { const imgs=[...document.images]; for (const i of imgs){ i.loading='eager'; i.scrollIntoView(); await i.decode().catch(()=>{}); } return imgs.filter(i=>i.naturalWidth>0).length; }")
        if n_img != 5:
            falhas.append(f"acuracia: {n_img} de 5 figuras carregadas")
        pg.evaluate("() => window.scrollTo(0, 0)")
    elif nome == "boletim":
        if pg.locator("#boletim-corpo li").count() != 12:
            falhas.append("boletim: esperado 6 itens de atacado + 6 de tendência")
        if pg.locator("#corpo-conf tr").count() != 6:
            falhas.append("boletim: conferência deveria ter 6 linhas")
        bol = json.loads((RAIZ / "data" / "boletim.json").read_text(encoding="utf-8"))
        d, m, a = bol["edicao"][8:10], bol["edicao"][5:7], bol["edicao"][:4]
        if f"{d}/{m}/{a}" not in pg.inner_text(".aviso-exemplo"):
            falhas.append("boletim: data do aviso não veio de boletim.json")
        if f"{d}/{m}/{a}" not in pg.inner_text("#cap-conf"):
            falhas.append("boletim: legenda da conferência não veio de boletim.json")
        if "acima da faixa" not in pg.inner_text("#conf-intro"):
            falhas.append("boletim: com os dados reais (tomate e batata acima), a frase deveria dizer 'acima da faixa'")
    elif nome == "index":
        if pg.evaluate("() => !!document.querySelector('.hero-nota').closest('[aria-hidden=\"true\"]')"):
            falhas.append("index: .hero-nota dentro de aria-hidden")


def cenarios_boletim(ctx, base, falhas):
    """Conferência do boletim: item abaixo da faixa escreve 'abaixo'; realizado nulo escreve 'ainda não divulgado' sem erro."""
    original = json.loads((RAIZ / "data" / "boletim.json").read_text(encoding="utf-8"))

    def abaixo(d):
        t = d["tendencia"][2]  # cebola
        t["real"] = t["lo"] - 5
        return d, ["abaixo da faixa", t["nome"].lower()]

    def nulo(d):
        d["tendencia"][0]["real"] = None
        return d, ["ainda não divulgado"]

    def todos_nulos(d):
        for t in d["tendencia"]:
            t["real"] = None
        return d, ["ainda não tinha sido divulgado"]

    for rotulo, mexer in [("abaixo", abaixo), ("real nulo", nulo), ("todos nulos", todos_nulos)]:
        dados, esperados = mexer(copy.deepcopy(original))
        pg = ctx.new_page()
        erros = []
        pg.on("pageerror", lambda exc, e=erros: e.append(str(exc)))
        pg.route("**/data/boletim.json", lambda route, _req, corpo=json.dumps(dados): route.fulfill(
            status=200, content_type="application/json", body=corpo))
        pg.goto(base + "/boletim/", wait_until="networkidle")
        texto = (pg.inner_text("#conf-intro") + " " + pg.inner_text("#corpo-conf")).lower()
        for e in esperados:
            if e not in texto:
                falhas.append(f"boletim ({rotulo}): esperado '{e}' na conferência; obtido: {texto[:200]}")
        if rotulo == "abaixo" and "acima da faixa" not in texto:
            falhas.append("boletim (abaixo): tomate e batata deveriam continuar 'acima da faixa'")
        if pg.locator("#corpo-conf tr").count() != 6:
            falhas.append(f"boletim ({rotulo}): conferência deveria ter 6 linhas")
        for e in erros:
            falhas.append(f"boletim ({rotulo}): erro de página: {e}")
        pg.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="base de um servidor já no ar (sem a CSP do vercel.json)")
    args = ap.parse_args()

    falhas: list[str] = []
    avisos: list[str] = []
    SAIDA.mkdir(parents=True, exist_ok=True)
    n_arq = checar_arquivos(falhas)
    print(f"Arquivos publicados verificados: {n_arq}")
    if not PROIBIDOS_EXTRA:
        msg = "QA_PROIBIDOS_EXTRA ausente: só a lista genérica de termos foi aplicada"
        if os.environ.get("CI") == "true" and os.environ.get("GITHUB_REF") == "refs/heads/main":
            falhas.append(msg + " (obrigatória em main)")
        else:
            print(f"::warning::{msg}")

    httpd = None
    if args.url:
        base = args.url.rstrip("/")
        avisos.append(f"servidor externo {base}: a CSP do vercel.json não é aplicada nesta rodada")
    else:
        httpd, base = servidor()

    externas: set[str] = set()
    with sync_playwright() as pw:
        nav = pw.chromium.launch(headless=True)
        for vp_nome, vp in VIEWPORTS.items():
            ctx = nav.new_context(viewport=vp, device_scale_factor=1, locale="pt-BR",
                                  is_mobile=vp_nome == "mobile", has_touch=vp_nome == "mobile")
            for nome, rota in PAGINAS:
                pg = ctx.new_page()
                erros = []
                pg.on("console", lambda m, e=erros: e.append(f"console.{m.type}: {m.text}") if m.type in ("error", "warning") else None)
                pg.on("pageerror", lambda exc, e=erros: e.append(f"pageerror: {exc}"))
                pg.on("requestfailed", lambda req, e=erros: e.append(f"falha de rede: {req.url} {req.failure}"))
                pg.on("request", lambda req: externas.add(req.url) if not req.url.startswith((base, "data:", "blob:", "about:")) else None)
                resp = pg.goto(base + rota, wait_until="networkidle")
                if not resp or resp.status != 200:
                    falhas.append(f"{rota}: HTTP {resp.status if resp else '?'}")
                pg.wait_for_timeout(300)
                pref = f"[{vp_nome} {rota}]"

                texto = pg.inner_text("body")
                for m in proibidos(texto):
                    falhas.append(f"{pref} termo proibido no texto renderizado: {m}")
                if "Carregando" in texto:
                    falhas.append(f"{pref} ainda mostra 'Carregando'")
                vazios = pg.evaluate("() => [...document.querySelectorAll('[data-site]')].filter(e => !e.textContent.trim() || e.textContent.trim() === '—' || e.textContent.trim() === 'data indisponível').map(e => e.getAttribute('data-site'))")
                if vazios:
                    falhas.append(f"{pref} [data-site] sem preencher: {vazios}")

                largura = pg.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
                if largura[0] > largura[1] + 1:
                    falhas.append(f"{pref} estouro horizontal: scrollWidth {largura[0]} > {largura[1]}")

                quebradas = pg.evaluate("() => [...document.images].filter(i => i.loading !== 'lazy' && !(i.complete && i.naturalWidth > 0)).map(i => i.src)")
                if quebradas:
                    falhas.append(f"{pref} imagens quebradas: {quebradas}")

                for c in pg.evaluate(JS_CONTRASTE):
                    falhas.append(f"{pref} contraste ({c['tipo']}) {c['ratio']}:1 em <{c['tag']} class='{c['classe']}'> '{c['texto']}'")

                if vp_nome == "mobile" and nome == "demo":
                    # a faixa fixa não pode cobrir o elemento focado ao voltar com Shift+Tab
                    pg.focus("#restaurar")
                    pg.keyboard.press("Shift+Tab")
                    topo, fim_faixa, pos = pg.evaluate("() => { const f = document.querySelector('.faixa-demo'); return [document.activeElement.getBoundingClientRect().top, f.getBoundingClientRect().bottom, getComputedStyle(f).position]; }")
                    if pos == "sticky" and topo < fim_faixa:
                        falhas.append(f"{pref} foco coberto pela faixa fixa (topo {topo:.0f} < {fim_faixa:.0f})")

                if vp_nome == "desktop":
                    checar_meta(pg, nome, rota, falhas)
                    n_foco = checar_foco(pg, rota, falhas)
                    print(f"  foco {rota}: {n_foco} elementos percorridos com Tab")
                    pg.goto(base + rota, wait_until="networkidle")
                    pg.wait_for_timeout(200)
                    checar_funcional(pg, nome, falhas)

                for e in erros:
                    falhas.append(f"{pref} {e}")

                pg.evaluate("() => window.scrollTo(0, 0)")
                pg.wait_for_timeout(150)
                pg.screenshot(path=str(SAIDA / f"{nome}_{vp_nome}.png"), full_page=True)
                pg.close()
            if vp_nome == "desktop":
                cenarios_boletim(ctx, base, falhas)
                # foco sobre navy (hero e rodapé) para revisão visual
                pg = ctx.new_page()
                pg.goto(base + "/", wait_until="networkidle")
                pg.focus(".hero .botao-principal")
                pg.keyboard.press("Shift+Tab")
                pg.keyboard.press("Tab")
                pg.locator(".hero").screenshot(path=str(SAIDA / "foco_hero.png"))
                pg.focus(".rodape a[href='/metodologia/']")
                pg.keyboard.press("Shift+Tab")
                pg.keyboard.press("Tab")
                pg.locator(".rodape").screenshot(path=str(SAIDA / "foco_rodape.png"))
                pg.goto(base + "/demo/", wait_until="networkidle")
                pg.keyboard.press("Tab")
                pg.screenshot(path=str(SAIDA / "foco_pular.png"), clip={"x": 0, "y": 0, "width": 700, "height": 160})
                pg.focus(".nav a[aria-current]")
                pg.keyboard.press("Shift+Tab")
                pg.keyboard.press("Tab")
                pg.locator(".topo").screenshot(path=str(SAIDA / "foco_nav_atual.png"))
                pg.close()
            ctx.close()

        # links internos
        pg = nav.new_page()
        hrefs = set()
        for _, rota in PAGINAS:
            pg.goto(base + rota, wait_until="domcontentloaded")
            hrefs.update(pg.evaluate("() => [...document.querySelectorAll('a[href], link[href]')].map(a => a.href).filter(h => h.startsWith(location.origin))"))
        for h in sorted(hrefs):
            try:
                urllib.request.urlopen(h.split("#")[0], timeout=5)
            except Exception as exc:  # noqa: BLE001
                falhas.append(f"link interno quebrado: {h} ({exc})")
        print(f"Links internos verificados: {len(hrefs)}")
        nav.close()
    if httpd:
        httpd.shutdown()

    for u in sorted(externas):
        falhas.append(f"requisição a outro domínio: {u}")

    print(f"Termos proibidos encontrados: lista genérica {CONTAGEM['generica']}, lista extra {CONTAGEM['extra']}"
          f"{'' if PROIBIDOS_EXTRA else ' (lista extra não carregada)'}")
    for a in avisos:
        print("AVISO", a)
    print(f"Screenshots em {SAIDA}")
    if falhas:
        print(f"\n{len(falhas)} FALHA(S):")
        for f in falhas:
            print(" -", f)
        sys.exit(1)
    print("\nQA OK: nenhuma falha.")


if __name__ == "__main__":
    main()
