# Cesta Prévia · site (cestaprevia.com.br)

Site estático da Cesta Prévia, empresa em constituição que desenvolve a PRÉVIA: estimativa da variação do preço de varejo dos alimentos na Região Metropolitana do Rio, a partir do atacado da CEASA-RJ, com faixa de incerteza e erro publicado.

HTML, CSS e JavaScript puro. Sem build, sem framework, sem dependência JS externa, sem cookies e sem requisição a outro domínio (fontes servidas do próprio site).

## Rodar localmente

`fetch()` não funciona com `file://`; sirva a pasta por HTTP:

```bash
python -m http.server 8000
# abrir http://localhost:8000
```

## QA

```bash
python -m pip install -r tools/requirements.txt
python -m playwright install chromium

python tools/qa/qa.py                              # servidor próprio com os cabeçalhos do vercel.json (CSP inclusa)
python tools/qa/qa.py --url http://127.0.0.1:8000  # contra um servidor já no ar
python tools/verificar_autoria.py origin/main..HEAD
python tools/bump_versao.py --checar
```

Termos proibidos além da lista genérica (nomes, siglas) vêm de `QA_PROIBIDOS_EXTRA`: secret no CI, linha `QA_PROIBIDOS_EXTRA=...` num `.env` local (ignorado pelo git e pelo deploy).

O QA abre as 9 páginas em desktop e celular, salva screenshots em `tools/qa/_saida/` (fora do git) e falha com requisição externa, termo proibido, data fixa no HTML, rodapé divergente, metadados incompletos, contraste abaixo de AA, foco invisível, link quebrado ou regressão funcional. O CI (`.github/workflows/qa.yml`) roda o mesmo em todo PR, com Lighthouse e axe como informativos.

## Publicar

O deploy é feito pelo GitHub Actions com a CLI do Vercel (`.github/workflows/deploy.yml`), não pela integração Git do Vercel:

- PR deste repositório: preview, com a URL comentada no PR;
- push em `main`: produção.

Secrets necessários: `VERCEL_TOKEN` e `VERCEL_ORG_ID` (o ID do projeto vem da variável `VERCEL_PROJECT_ID`, com valor padrão no workflow). Sem eles, o preview avisa e não publica; em `main`, o job de produção falha. A produção roda no environment `production` do GitHub, onde o dono do repositório configura a aprovação obrigatória.

Antes de publicar uma mudança de CSS ou JS, atualize a versão dos assets:

```bash
python tools/bump_versao.py          # ?v=AAAAMMDD de hoje em todas as páginas
```

Toda publicação passa por QA, revisão de design, de texto e de fatos, e aprovação humana. Todo commit usa a identidade `Cesta Previa <contato@cestaprevia.com.br>`; o CI recusa outra. Não use o botão "Update branch" do GitHub: o merge criado lá tem committer GitHub e é recusado; atualize a branch localmente. O merge em `main` também é feito localmente, com a identidade da organização, e enviado por push (nunca pelo botão de merge do GitHub). No push em `main` o CI confere só o autor dos commits.

## Estrutura

| Caminho | O que é |
|---|---|
| `index.html` | Página inicial |
| `demo/` | Painel de demonstração com os dados do backtest e a Minha Cesta |
| `acuracia/` | Método, placar, métricas, figuras, o que não funcionou |
| `boletim/` | Edição de exemplo do boletim e conferência com o IPCA |
| `metodologia/` | Fontes, cálculos, limitações, versão dos dados, como citar, perguntas |
| `contato/`, `privacidade/`, `termos/` | Contato e encarregado, política de privacidade, termos de uso |
| `404.html` | Página de erro |
| `assets/css/site.css` | Estilos e tokens de cor |
| `assets/js/` | `comum.js` (utilitários e datas de `data/site.json`), `demo.js`, `acuracia.js`, `boletim.js` |
| `assets/fonts/` | Inter e Space Grotesk em WOFF2 (OFL; origem em `LICENSE.txt`) |
| `assets/img/` | Ícones, logo, imagem de compartilhamento e figuras do backtest |
| `data/` | JSON publicados: `previsoes.json`, `metricas.json`, `boletim.json`, `site.json` (datas) |
| `robots.txt`, `sitemap.xml`, `site.webmanifest` | Indexação e manifesto |
| `vercel.json` | Cabeçalhos de segurança (CSP, HSTS, COOP) e cache |
| `tools/` | QA, autoria, versão de assets, imagem de compartilhamento (fora do deploy) |

`build_data.py` é legado e fica fora do deploy; os JSON passam a ser gerados fora deste repositório.

## Licença

- Dados derivados publicados em `data/` (estimativas, faixas, erros e métricas): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br). Valores originais da CEASA-RJ, do IBGE e do DIEESE seguem os termos de cada instituição.
- Código do site, textos, marca PRÉVIA e logotipo: todos os direitos reservados à Cesta Prévia.
- Fontes tipográficas: SIL Open Font License 1.1 (`assets/fonts/LICENSE.txt`).
