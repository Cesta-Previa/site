"""Gera os dados e as imagens da demo publica da PREVIA a partir do backtest real.

Uso (a partir de qualquer pasta):
    python build_data.py            # dados (data/*.json) + imagens (assets/img/)
    python build_data.py --so-dados # so os JSON

Entradas (somente leitura):
    ../backtest/resultados/previsoes.csv
    ../backtest/resultados/metricas_item_horizonte_modelo.csv
    ../backtest/resultados/resumo_por_horizonte.csv
    ../backtest/resultados/figuras/*.png
    ../backtest/dados/processados/ceasa_rj_*.csv
    Logo.png da identidade visual (Fase 1)

Saidas:
    data/previsoes.json  -> painel de demonstracao (tabela, grafico, Minha Cesta, componentes)
    data/metricas.json   -> pagina de acuracia
    data/boletim.json    -> exemplo do Boletim PREVIA de precos
    assets/img/...       -> figuras em WebP, favicon e simbolo

Regras aplicadas (sem olhar o futuro):
    - Faixa de incerteza de cada mes usa so os erros dos meses-alvo anteriores (realizado ja
      divulgado no dia 15). Faixa de 80%: estimativa +- 1,2816 x RMSE dos erros passados, em log.
    - Status do mes tambem usa so o passado: "estimativa" se o RMSE do modelo ficou abaixo do da
      media sazonal ate aquela data; "monitoramento" se nao; "sem_recomendacao" se faltou o boletim
      CEASA-RJ da 1a semana (dado vencido) ou se ha menos de 8 meses de erro avaliado.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
BACKTEST = AQUI.parent / "backtest"
RES = BACKTEST / "resultados"
PROC = BACKTEST / "dados" / "processados"
LOGO = (AQUI.parents[2] / "01_Fase1_Ideias_Inovadoras" / "Projeto1_PREVIA_Cesta_Basica"
        / "identidade" / "Logo.png")
DATA = AQUI / "data"
IMG = AQUI / "assets" / "img"

MODELO = "ARX atacado + nowcast"
Z80 = 1.2816
MIN_ERROS = 8
VERSAO = "2026-10-22"

# (alvo, item, nome exibido, fonte, unidade do nivel, coluna CEASA)
SERIES = [
    ("ipca:tomate", "tomate", "Tomate", "IPCA RM Rio", "índice", "tomate"),
    ("dieese:tomate", "tomate", "Tomate", "DIEESE Rio", "R$/kg", "tomate"),
    ("ipca:batata", "batata", "Batata", "IPCA RM Rio", "índice", "batata"),
    ("dieese:batata", "batata", "Batata", "DIEESE Rio", "R$/kg", "batata"),
    ("ipca:cebola", "cebola", "Cebola", "IPCA RM Rio", "índice", "cebola"),
    ("ipca:cenoura", "cenoura", "Cenoura", "IPCA RM Rio", "índice", "cenoura"),
    ("ipca:banana_prata", "banana", "Banana-prata", "IPCA RM Rio", "índice", "banana_prata"),
    ("dieese:banana", "banana", "Banana", "DIEESE Rio", "R$/dúzia", "banana_prata"),
    ("ipca:ovo", "ovo", "Ovo", "IPCA RM Rio", "índice", "ovo"),
]

CEASA_EMB = {
    "tomate": "tomate extra AA, caixa de 18 kg",
    "batata": "batata lisa especial, saco de 25 kg",
    "cebola": "cebola nacional branca, saco de 20 kg",
    "cenoura": "cenoura extra A, caixa de 20 kg",
    "banana_prata": "banana-prata extra, caixa de 20 kg",
    "ovo": "ovo branco extra, caixa de 30 dúzias",
}
CEASA_NOME = {"tomate": "Tomate", "batata": "Batata", "cebola": "Cebola", "cenoura": "Cenoura",
              "banana_prata": "Banana-prata", "ovo": "Ovo"}

# Minha Cesta: cada item usa a serie IPCA RM Rio (unica fonte com os 6 itens)
CESTA = [
    {"item": "tomate", "nome": "Tomate", "serie": "ipca:tomate", "unidade": "kg"},
    {"item": "batata", "nome": "Batata", "serie": "ipca:batata", "unidade": "kg"},
    {"item": "cebola", "nome": "Cebola", "serie": "ipca:cebola", "unidade": "kg"},
    {"item": "cenoura", "nome": "Cenoura", "serie": "ipca:cenoura", "unidade": "kg"},
    {"item": "banana", "nome": "Banana-prata", "serie": "ipca:banana_prata", "unidade": "kg"},
    {"item": "ovo", "nome": "Ovo", "serie": "ipca:ovo", "unidade": "dúzia"},
]

BASELINE_NOME = {"MediaSazonal": "média sazonal", "MediaMovel3": "média móvel 3 meses",
                 "SazonalNaive": "naive sazonal", "RW": "preço estável"}


def r(x, nd=2):
    """Arredonda para JSON; NaN/inf viram None."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(xf) or math.isinf(xf):
        return None
    return round(xf, nd)


def mes_anterior(m: str) -> str:
    return str(pd.Period(m, freq="M") - 1)


def carregar_ceasa():
    fw = pd.read_csv(PROC / "ceasa_rj_modal_primeira_semana.csv").set_index("mes")
    mm = pd.read_csv(PROC / "ceasa_rj_modal_media_mensal.csv").set_index("mes")
    bol = pd.read_csv(PROC / "ceasa_rj_boletins_amostra.csv")
    return fw, mm, bol


def ceasa_valor(df, mes, col):
    if mes in df.index and col in df.columns:
        v = df.at[mes, col]
        if pd.notna(v):
            return float(v)
    return None


def montar_previsoes(prev, met, fw, mm):
    e1 = prev[(prev.experimento == "E1") & (prev.h == 1)]
    wide = e1.pivot_table(index=["alvo", "mes_alvo"], columns="modelo", values="prev").reset_index()
    info = (e1[e1.modelo == MODELO][["alvo", "mes_alvo", "origem", "real", "nivel_origem",
                                    "nivel_real", "data_emissao", "antecedencia_dias"]])
    wide = wide.merge(info, on=["alvo", "mes_alvo"], how="inner")

    met1 = met[(met.experimento == "E1") & (met.modelo == MODELO)]
    series_out = []
    cobertura_hits, cobertura_n = 0, 0
    for alvo, item, nome, fonte, unidade, col in SERIES:
        g = wide[wide.alvo == alvo].sort_values("mes_alvo").reset_index(drop=True)
        if g.empty:
            raise SystemExit(f"serie ausente no backtest: {alvo}")
        err = g[MODELO] - g["real"]
        err_ms = g["MediaSazonal"] - g["real"]
        pontos = []
        for i, row in g.iterrows():
            passado, passado_ms = err.iloc[:i], err_ms.iloc[:i]
            n_err = int(len(passado))
            rmse = float(np.sqrt((passado ** 2).mean())) if n_err else None
            rmse_ms = float(np.sqrt((passado_ms ** 2).mean())) if n_err else None
            rel_ms = (rmse / rmse_ms) if (n_err and rmse_ms) else None
            nc = float(row[MODELO])
            lo = hi = None
            if n_err >= MIN_ERROS:
                lo = math.expm1(nc - Z80 * rmse) * 100
                hi = math.expm1(nc + Z80 * rmse) * 100
            m = row["mes_alvo"]
            ceasa_ok = ceasa_valor(fw, m, col) is not None
            p1 = ceasa_valor(fw, m, col)
            media_ant = ceasa_valor(mm, mes_anterior(m), col)
            atac = (p1 / media_ant - 1) * 100 if (p1 is not None and media_ant) else None

            if not ceasa_ok:
                st, mot = "sem_recomendacao", "Sem boletim CEASA-RJ da 1ª semana neste mês: o dado de atacado estaria vencido."
            elif n_err < MIN_ERROS:
                st, mot = "sem_recomendacao", f"Só {n_err} meses de erro avaliado até esta data (mínimo: {MIN_ERROS})."
            elif rel_ms is not None and rel_ms >= 1:
                st, mot = "monitoramento", "Até esta data, o modelo não superou a média sazonal nesta série."
            else:
                st, mot = "estimativa", "Até esta data, o modelo superou a média sazonal nesta série."

            real = float(row["real"])
            dentro = None
            if lo is not None:
                dentro = bool(lo <= math.expm1(real) * 100 <= hi)
                cobertura_n += 1
                cobertura_hits += int(dentro)

            pontos.append({
                "m": m, "o": row["origem"], "e": row["data_emissao"], "ant": int(row["antecedencia_dias"]),
                "prev": r(math.expm1(nc) * 100), "lo": r(lo), "hi": r(hi),
                "real": r(math.expm1(real) * 100),
                "nc": r(nc * 100), "ar": r(float(row["AR (controle)"]) * 100),
                "ms": r(float(row["MediaSazonal"]) * 100),
                "ms_pct": r(math.expm1(float(row["MediaSazonal"])) * 100),
                "n_err": n_err, "rmse": r(rmse * 100 if rmse is not None else None),
                "rel_ms": r(rel_ms, 3),
                "ceasa": ceasa_ok, "atac": r(atac, 1), "dentro": dentro,
                "niv_o": r(row["nivel_origem"], 2), "niv_r": r(row["nivel_real"], 2),
                "st": st, "mot": mot,
            })

        mets = {}
        for h in (1, 2, 3):
            mr = met1[(met1.alvo == alvo) & (met1.h == h)]
            if mr.empty:
                continue
            x = mr.iloc[0]
            mets[f"h{h}"] = {
                "n": int(x.n_origens), "rmse_pp": r(x.rmse_pp), "rel_rw": r(x.rmse_rel_rw, 3),
                "p_rw": r(x.p_dm_rw, 3), "melhor_baseline": BASELINE_NOME.get(x.melhor_baseline, x.melhor_baseline),
                "rel_mb": r(x.rmse_rel_melhor_baseline, 3), "p_mb": r(x.p_dm_melhor_baseline, 3),
                "dir": r(x.acerto_direcao_pct, 1), "mape": r(x.mape_nivel_pct, 1),
                "ant_med": r(x.antecedencia_dias_mediana, 0),
            }
        h1 = mets["h1"]
        series_out.append({
            "id": alvo, "item": item, "nome": nome, "fonte": fonte, "unidade": unidade,
            "ceasa_item": col, "ceasa_emb": CEASA_EMB[col],
            "status_backtest": "estimativa" if h1["rel_mb"] < 1 else "monitoramento",
            "metricas": mets, "pontos": pontos,
        })

    meses = sorted({p["m"] for s in series_out for p in s["pontos"]})
    cobertura = {"nivel": 80, "n": cobertura_n, "dentro": cobertura_hits,
                 "pct": r(100 * cobertura_hits / cobertura_n, 1) if cobertura_n else None}
    return {
        "versao": VERSAO,
        "modelo": "Transmissão atacado-varejo com o 1º boletim CEASA-RJ do mês (Ridge linear), h = 1",
        "faixa": {"nivel": 80, "z": Z80, "min_erros": MIN_ERROS},
        "cobertura_faixa": cobertura,
        "meses": meses,
        "series": series_out,
        "cesta": CESTA,
    }


def montar_metricas(met, resumo, dados_prev):
    m1 = met[(met.experimento == "E1") & (met.modelo == MODELO)].copy()
    ordem = {s[0]: i for i, s in enumerate(SERIES)}
    m1["ordem"] = m1.alvo.map(ordem)
    linhas = []
    for _, x in m1.sort_values(["ordem", "h"]).iterrows():
        s = next(s for s in SERIES if s[0] == x.alvo)
        linhas.append({
            "serie": x.alvo, "nome": s[2], "fonte": s[3], "h": int(x.h), "n": int(x.n_origens),
            "rmse_pp": r(x.rmse_pp, 1), "rel_rw": r(x.rmse_rel_rw, 2), "p_rw": r(x.p_dm_rw, 3),
            "melhor_baseline": BASELINE_NOME.get(x.melhor_baseline, x.melhor_baseline),
            "rel_mb": r(x.rmse_rel_melhor_baseline, 2), "p_mb": r(x.p_dm_melhor_baseline, 3),
            "dir": r(x.acerto_direcao_pct, 0), "mape": r(x.mape_nivel_pct, 1),
            "ant_med": r(x.antecedencia_dias_mediana, 0), "ant_min": r(x.antecedencia_dias_min, 0),
        })

    def placar(exp, modelo):
        out = []
        for _, x in resumo[(resumo.experimento == exp) & (resumo.modelo == modelo)].sort_values("h").iterrows():
            out.append({"h": int(x.h), "n_alvos": int(x.n_alvos), "vence_rw": int(x.vence_rw),
                        "vence_rw_p05": int(x.vence_rw_p05), "vence_mb": int(x.vence_melhor_baseline),
                        "vence_mb_p05": int(x.vence_melhor_baseline_p05),
                        "rel_rw_med": r(x.rmse_rel_rw_mediana, 3),
                        "rel_mb_med": r(x.rmse_rel_melhor_base_mediana, 3), "dir_med": r(x.dir_mediana, 1)})
        return out

    return {
        "versao": VERSAO,
        "e1": linhas,
        "placar_e1": placar("E1", MODELO),
        "placar_e1_media_sazonal": placar("E1", "MediaSazonal"),
        "placar_e2_ridge": placar("E2", "Ridge drivers"),
        "placar_e2_gbm": placar("E2", "GBM drivers"),
        "placar_e3_ridge": placar("E3", "Ridge drivers"),
        "cobertura_faixa": dados_prev["cobertura_faixa"],
    }


def montar_boletim(dados_prev, bol, mm):
    """Exemplo de boletim semanal para a edicao de 15/09/2026, so com dados ate essa data."""
    edicao = "2026-09-15"
    mes = "2026-09"
    b = bol[(bol.mes_pagina == mes) & (bol.data < edicao)].sort_values("data")
    datas = sorted(b.data.unique())
    if len(datas) < 2:
        raise SystemExit("boletins CEASA-RJ insuficientes para o exemplo")
    d1, d2 = datas[0], datas[-1]
    atacado = []
    for col in ["tomate", "batata", "cebola", "cenoura", "banana_prata", "ovo"]:
        v1 = b[(b.data == d1) & (b.item == col)].modal
        v2 = b[(b.data == d2) & (b.item == col)].modal
        media_ant = ceasa_valor(mm, mes_anterior(mes), col)
        p1 = float(v1.iloc[0]) if len(v1) else None
        p2 = float(v2.iloc[0]) if len(v2) else None
        atacado.append({
            "item": col, "nome": CEASA_NOME[col], "emb": CEASA_EMB[col],
            "media_mes_ant": r(media_ant, 2), "p1": r(p1, 2), "p2": r(p2, 2),
            "var1": r((p1 / media_ant - 1) * 100, 0) if (p1 and media_ant) else None,
            "var2": r((p2 / media_ant - 1) * 100, 0) if (p2 and media_ant) else None,
        })
    tendencia = []
    for c in CESTA:
        s = next(s for s in dados_prev["series"] if s["id"] == c["serie"])
        p = next(p for p in s["pontos"] if p["m"] == mes)
        tendencia.append({"nome": c["nome"], "serie": s["id"], "fonte": s["fonte"], "st": p["st"],
                          "mot": p["mot"], "prev": p["prev"], "lo": p["lo"], "hi": p["hi"],
                          "real": p["real"], "dentro": p["dentro"], "ant": p["ant"]})
    return {"versao": VERSAO, "edicao": edicao, "mes": mes, "boletim_1": d1, "boletim_2": d2,
            "mes_anterior": mes_anterior(mes), "atacado": atacado, "tendencia": tendencia}


def conferir_afirmacoes(met):
    """Confere os numeros fixos do texto do site contra o backtest. Falha se divergirem."""
    m1 = met[(met.experimento == "E1") & (met.modelo == MODELO) & (met.h == 1)]
    rel_rw = float(np.median(m1.rmse_rel_rw))
    rel_mb = float(np.median(m1.rmse_rel_melhor_baseline))
    vence = int((m1.rmse_rel_melhor_baseline < 1).sum())
    sig = int((m1.p_dm_melhor_baseline < 0.05).sum())
    direcao = float(np.median(m1.acerto_direcao_pct))
    ant_ipca = float(np.median(m1[m1.fonte == "ipca"].antecedencia_dias_mediana))
    checks = [
        ("RMSE -24% vs preço estável", round((1 - rel_rw) * 100), 24),
        ("RMSE -11% vs média sazonal", round((1 - rel_mb) * 100), 11),
        ("7 de 9 séries vencem a média sazonal", vence, 7),
        ("0 séries com significância a 5% vs média sazonal", sig, 0),
        ("acerto de direção mediano 72%", round(direcao), 72),
        ("26 dias antes do IPCA (mediana)", round(ant_ipca), 26),
        ("9 séries", len(m1), 9),
    ]
    ok = True
    for nome, obtido, esperado in checks:
        flag = "OK " if obtido == esperado else "ERRO"
        ok &= obtido == esperado
        print(f"  [{flag}] {nome}: obtido {obtido}, texto {esperado}")
    if not ok:
        raise SystemExit("Números do site divergem do backtest. Revise index.html antes de publicar.")


def gerar_imagens():
    from PIL import Image

    fig_dir = IMG / "figuras"
    fig_dir.mkdir(parents=True, exist_ok=True)
    figuras = ["fig4_E1_ganho_vs_rw", "fig4b_E1_ganho_vs_melhor_baseline", "fig1_E1_previsto_vs_realizado_h1",
               "fig7_acerto_direcao", "fig0_atacado_antecede_varejo"]
    for f in figuras:
        im = Image.open(RES / "figuras" / f"{f}.png").convert("RGB")
        if im.width > 1600:
            im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
        im.save(fig_dir / f"{f}.webp", "WEBP", quality=86, method=6)
        print(f"  figura {f}.webp {im.size}")

    logo = Image.open(LOGO).convert("RGB")
    logo.resize((512, 512), Image.LANCZOS).save(IMG / "logo-previa.png", optimize=True)
    simbolo = logo.crop((300, 180, 1000, 860))  # cesta + linha + ponto ambar, sem o wordmark
    for tam, nome in [(32, "favicon-32.png"), (180, "apple-touch-icon.png"), (192, "icone-192.png")]:
        simbolo.resize((tam, tam), Image.LANCZOS).save(IMG / nome, optimize=True)
    print("  logo, favicon e icones gerados")


def main():
    so_dados = "--so-dados" in sys.argv
    DATA.mkdir(exist_ok=True)
    prev = pd.read_csv(RES / "previsoes.csv")
    met = pd.read_csv(RES / "metricas_item_horizonte_modelo.csv")
    met = met.drop(columns=["item"])  # coluna corrompida no CSV (repr de metodo pandas); usar 'alvo'
    resumo = pd.read_csv(RES / "resumo_por_horizonte.csv")
    fw, mm, bol = carregar_ceasa()

    print("Conferência dos números citados no site:")
    conferir_afirmacoes(met)

    dados_prev = montar_previsoes(prev, met, fw, mm)
    dados_met = montar_metricas(met, resumo, dados_prev)
    dados_bol = montar_boletim(dados_prev, bol, mm)

    for nome, obj in [("previsoes.json", dados_prev), ("metricas.json", dados_met), ("boletim.json", dados_bol)]:
        caminho = DATA / nome
        caminho.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"  {caminho.relative_to(AQUI)}: {caminho.stat().st_size / 1024:.1f} KB")

    cob = dados_prev["cobertura_faixa"]
    print(f"Cobertura da faixa de 80%: {cob['dentro']}/{cob['n']} = {cob['pct']}%")
    ult = dados_prev["meses"][-1]
    print(f"Último mês-alvo: {ult}")
    for s in dados_prev["series"]:
        p = s["pontos"][-1]
        print(f"  {s['id']:<18} {p['st']:<17} prev {p['prev']:>7} faixa [{p['lo']}, {p['hi']}] real {p['real']}")

    if not so_dados:
        gerar_imagens()


if __name__ == "__main__":
    main()
