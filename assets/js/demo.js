/* PRÉVIA, painel de demonstração. Lê data/previsoes.json (gerado por build_data.py a partir do backtest). */
(function () {
  'use strict';
  var P = window.PREVIA;
  var el = P.el;

  var dados = null;
  var mesSel = null;
  var serieSel = 'ipca:tomate';
  var linhasCesta = [];
  var proximoId = 1;

  var EXEMPLO = [
    { item: 'tomate', qtd: '120', preco: '6,50' },
    { item: 'batata', qtd: '150', preco: '4,80' },
    { item: 'cebola', qtd: '80', preco: '4,20' },
    { item: 'cenoura', qtd: '60', preco: '4,00' },
    { item: 'banana', qtd: '50', preco: '6,00' },
    { item: 'ovo', qtd: '40', preco: '9,50' },
    { item: 'outro', nome: 'Arroz', qtd: '100', preco: '5,20' }
  ];

  function $(id) { return document.getElementById(id); }

  function ponto(serie, mes) {
    for (var i = 0; i < serie.pontos.length; i++) if (serie.pontos[i].m === mes) return serie.pontos[i];
    return null;
  }
  function serie(id) {
    for (var i = 0; i < dados.series.length; i++) if (dados.series[i].id === id) return dados.series[i];
    return null;
  }

  /* ---------- Tabela por item ---------- */
  function renderContexto() {
    var ref = ponto(serie('ipca:tomate'), mesSel);
    var alvo = $('contexto-mes');
    alvo.textContent = '';
    var publicadas = dados.series.filter(function (s) {
      var p = ponto(s, mesSel); return p && p.st === 'estimativa';
    }).length;
    var partes = [];
    partes.push(el('strong', { text: 'Mês de referência: ' + P.mesLongo(mesSel) + '. ' }));
    if (ref) {
      partes.push('Estimativa emitida em ' + P.data(ref.e) + ' com o primeiro boletim CEASA-RJ do mês. ' +
        'O IPCA de ' + P.mesLongo(mesSel).split(' de ')[0] + ' saiu em ' + P.data(P.somarDias(ref.e, ref.ant)) +
        ', ' + ref.ant + ' dias depois. ');
    }
    partes.push('Séries com estimativa publicada: ' + publicadas + ' de ' + dados.series.length + '.');
    alvo.appendChild(el('p', null, partes));
  }

  function celulaNivel(s, valor) {
    if (s.unidade.indexOf('R$') !== 0 || valor === null || valor === undefined) return null;
    return el('span', { class: 'sub', text: P.brl(valor) + s.unidade.replace('R$', '') });
  }

  function renderTabela() {
    var corpo = $('corpo-itens');
    corpo.textContent = '';
    var itemAnterior = null;
    dados.series.forEach(function (s) {
      var p = ponto(s, mesSel);
      var tr = el('tr', { class: (itemAnterior && itemAnterior !== s.item) ? 'linha-grupo' : null });
      itemAnterior = s.item;
      tr.appendChild(el('th', { scope: 'row' }, [s.nome, el('span', { class: 'sub', text: s.fonte + (s.unidade !== 'índice' ? ', ' + s.unidade : '') })]));

      if (!p) {
        tr.appendChild(el('td', { text: '—' }));
        tr.appendChild(el('td', { text: 'Não publicada' }));
        tr.appendChild(el('td', { text: '—' }));
        tr.appendChild(el('td', { text: '—' }));
        tr.appendChild(el('td', null, [P.status('sem_recomendacao'), el('span', { class: 'motivo', text: 'Série sem previsão neste mês do backtest.' })]));
        corpo.appendChild(tr);
        return;
      }

      // Atacado
      var tdAt = el('td');
      if (p.atac !== null) {
        tdAt.appendChild(P.variacao(p.atac, 0));
      } else {
        tdAt.appendChild(el('span', { text: p.ceasa ? '—' : 'Sem boletim' }));
      }
      tr.appendChild(tdAt);

      // Estimativa
      var tdEst = el('td');
      if (p.st === 'estimativa') {
        tdEst.appendChild(P.variacao(p.prev));
        tdEst.appendChild(el('span', { class: 'faixa-txt', text: 'faixa de ' + P.pct(p.lo, 0) + ' a ' + P.pct(p.hi, 0) }));
        if (p.niv_o !== null && s.unidade.indexOf('R$') === 0) {
          tdEst.appendChild(celulaNivel(s, p.niv_o * (1 + p.prev / 100)));
        }
      } else {
        tdEst.appendChild(el('span', { text: 'Não publicada' }));
      }
      tr.appendChild(tdEst);

      // Realizado
      var tdReal = el('td');
      if (p.real !== null) {
        tdReal.appendChild(P.variacao(p.real));
        if (p.st === 'estimativa' && p.dentro !== null) {
          tdReal.appendChild(el('span', { class: 'faixa-txt' + (p.dentro ? ' destaque-ok' : ''), text: p.dentro ? 'dentro da faixa' : 'fora da faixa' }));
        }
        var niv = celulaNivel(s, p.niv_r);
        if (niv) tdReal.appendChild(niv);
      } else {
        tdReal.appendChild(el('span', { text: 'Ainda não divulgado' }));
      }
      tr.appendChild(tdReal);

      // Erro histórico
      var tdErr = el('td');
      if (p.rmse !== null) {
        tdErr.appendChild(el('span', { class: 'num', text: P.numero(p.rmse, 1) + ' pp' }));
        tdErr.appendChild(el('span', { class: 'sub', text: P.numero(p.rel_ms, 2) + ' × média sazonal · ' + p.n_err + ' meses' }));
      } else {
        tdErr.appendChild(el('span', { text: '—' }));
        tdErr.appendChild(el('span', { class: 'sub', text: 'sem histórico' }));
      }
      tr.appendChild(tdErr);

      tr.appendChild(el('td', null, [P.status(p.st), el('span', { class: 'motivo', text: p.mot })]));
      corpo.appendChild(tr);
    });
  }

  /* ---------- Gráfico previsto x realizado (SVG próprio) ---------- */
  function passoEixo(amplitude) {
    var bruto = amplitude / 5;
    var passos = [1, 2, 2.5, 5, 10, 20, 25, 50, 100];
    for (var i = 0; i < passos.length; i++) if (passos[i] >= bruto) return passos[i];
    return 100;
  }

  function renderGrafico() {
    var s = serie(serieSel);
    var pts = s.pontos;
    var estreito = $('grafico').clientWidth < 600;
    var W = estreito ? 380 : 760, H = estreito ? 300 : 330, ml = estreito ? 44 : 52, mr = 12, mt = 16, mb = 40;
    var passoX = estreito ? 6 : 3;
    var iw = W - ml - mr, ih = H - mt - mb;
    var vals = [0];
    pts.forEach(function (p) {
      [p.real, p.prev, p.lo, p.hi, p.ms_pct].forEach(function (v) { if (v !== null) vals.push(v); });
    });
    var vmin = Math.min.apply(null, vals), vmax = Math.max.apply(null, vals);
    var passo = passoEixo(vmax - vmin);
    vmin = Math.floor(vmin / passo) * passo;
    vmax = Math.ceil(vmax / passo) * passo;
    function x(i) { return ml + (pts.length === 1 ? iw / 2 : i * iw / (pts.length - 1)); }
    function y(v) { return mt + (vmax - v) / (vmax - vmin) * ih; }

    var acertos = pts.filter(function (p) { return p.dentro === true; }).length;
    var comFaixa = pts.filter(function (p) { return p.dentro !== null; }).length;
    var titulo = 'Previsto e realizado: ' + s.nome + ' (' + s.fonte + ')';
    var desc = 'Variação mensal do preço de varejo de ' + P.mesLongo(pts[0].m) + ' a ' + P.mesLongo(pts[pts.length - 1].m) +
      '. RMSE do modelo no mês corrente: ' + P.numero(s.metricas.h1.rmse_pp, 1) + ' pontos percentuais, ' +
      P.numero(s.metricas.h1.rel_mb, 2) + ' vez o da média sazonal. O realizado ficou dentro da faixa de 80% em ' +
      acertos + ' de ' + comFaixa + ' meses com faixa. Os valores estão na tabela abaixo do gráfico.';

    var raiz = P.svg('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-labelledby': 'g-tit g-desc' });
    raiz.appendChild(P.svg('title', { id: 'g-tit', text: titulo }));
    raiz.appendChild(P.svg('desc', { id: 'g-desc', text: desc }));

    // grade e eixo Y
    for (var v = vmin; v <= vmax + 1e-9; v += passo) {
      raiz.appendChild(P.svg('line', { x1: ml, x2: W - mr, y1: y(v), y2: y(v), stroke: v === 0 ? '#5A6B78' : '#E3E7E5', 'stroke-width': v === 0 ? 1.5 : 1 }));
      raiz.appendChild(P.svg('text', { x: ml - 8, y: y(v) + 4, 'text-anchor': 'end', 'font-size': 12, fill: '#5A6B78', 'font-family': 'Inter, sans-serif', text: P.pct(v, 0) }));
    }
    // eixo X
    pts.forEach(function (p, i) {
      if ((i % passoX === 0 && pts.length - 1 - i >= passoX / 2 + 1) || i === pts.length - 1) {
        raiz.appendChild(P.svg('text', { x: x(i), y: H - mb + 22, 'text-anchor': 'middle', 'font-size': 12, fill: '#5A6B78', 'font-family': 'Inter, sans-serif', text: P.mesCurto(p.m) }));
      }
    });

    // faixa (trechos contínuos com lo/hi)
    var trecho = [];
    function fecharTrecho() {
      if (trecho.length > 1) {
        var d = trecho.map(function (k, j) { return (j ? 'L' : 'M') + x(k) + ' ' + y(pts[k].hi); }).join(' ');
        d += ' ' + trecho.slice().reverse().map(function (k) { return 'L' + x(k) + ' ' + y(pts[k].lo); }).join(' ') + ' Z';
        raiz.appendChild(P.svg('path', { d: d, fill: '#1B5E20', 'fill-opacity': 0.14 }));
      }
      trecho = [];
    }
    pts.forEach(function (p, i) { if (p.lo !== null) trecho.push(i); else fecharTrecho(); });
    fecharTrecho();

    // mês selecionado
    var iSel = -1;
    pts.forEach(function (p, i) { if (p.m === mesSel) iSel = i; });
    if (iSel >= 0) {
      raiz.appendChild(P.svg('line', { x1: x(iSel), x2: x(iSel), y1: mt, y2: H - mb, stroke: '#0D2B45', 'stroke-width': 1.5, 'stroke-dasharray': '2 4' }));
    }

    function linha(chave, attrs) {
      var d = '';
      var aberto = false;
      pts.forEach(function (p, i) {
        if (p[chave] === null) { aberto = false; return; }
        d += (aberto ? 'L' : 'M') + x(i) + ' ' + y(p[chave]) + ' ';
        aberto = true;
      });
      attrs.d = d; attrs.fill = 'none';
      raiz.appendChild(P.svg('path', attrs));
    }
    linha('ms_pct', { stroke: '#5A6B78', 'stroke-width': 1.6, 'stroke-dasharray': '2 4' });
    linha('real', { stroke: '#0D2B45', 'stroke-width': 2.5, 'stroke-linejoin': 'round' });
    linha('prev', { stroke: '#1B5E20', 'stroke-width': 2.5, 'stroke-dasharray': '7 5', 'stroke-linejoin': 'round' });
    pts.forEach(function (p, i) {
      if (p.real !== null) raiz.appendChild(P.svg('circle', { cx: x(i), cy: y(p.real), r: 3.2, fill: '#0D2B45' }));
      var publicada = p.st === 'estimativa';
      raiz.appendChild(P.svg('circle', { cx: x(i), cy: y(p.prev), r: 3.6, fill: publicada ? '#1B5E20' : '#FFFFFF', stroke: '#1B5E20', 'stroke-width': 1.6 }));
    });

    var alvo = $('grafico');
    alvo.textContent = '';
    alvo.appendChild(raiz);
    alvo.appendChild(el('p', { class: 'ressalva', text: 'Ponto verde cheio: mês em que a estimativa seria publicada. Ponto vazado: mês em só monitoramento ou sem recomendação. Linha pontilhada vertical: mês de referência escolhido.' }));

    // tabela acessível
    var tb = document.querySelector('#tabela-grafico tbody');
    tb.textContent = '';
    pts.forEach(function (p) {
      tb.appendChild(el('tr', null, [
        el('th', { scope: 'row', text: P.mesCurto(p.m) }),
        el('td', { class: 'n', text: P.pct(p.prev) }),
        el('td', { class: 'n', text: p.lo !== null ? P.pct(p.lo, 0) + ' a ' + P.pct(p.hi, 0) : '—' }),
        el('td', { class: 'n', text: P.pct(p.real) }),
        el('td', { class: 'n', text: P.pct(p.ms_pct) })
      ]));
    });
  }

  /* ---------- Leitura por componente ---------- */
  function renderComponentes() {
    var s = serie(serieSel);
    var p = ponto(s, mesSel);
    var tit = $('t-comp-serie');
    var alvo = $('componentes');
    alvo.textContent = '';
    if (!p) {
      tit.textContent = s.nome + ' · ' + s.fonte + ' · ' + P.mesLongo(mesSel);
      alvo.appendChild(el('p', { class: 'estado', text: 'Sem previsão desta série neste mês do backtest.' }));
      return;
    }
    tit.textContent = s.nome + ' · ' + s.fonte + ' · ' + P.mesLongo(mesSel) +
      (p.st === 'estimativa' ? '' : ' (estimativa não publicada neste mês)');
    var itens = [
      { rot: 'Média sazonal do mês', v: p.ms },
      { rot: 'Ajuste pelo histórico recente do varejo', v: p.ar - p.ms },
      { rot: 'Ajuste pelo atacado CEASA-RJ', v: p.nc - p.ar },
      { rot: 'Estimativa (soma)', v: p.nc, total: true }
    ];
    var maximo = Math.max.apply(null, itens.map(function (c) { return Math.abs(c.v); })) || 1;
    itens.forEach(function (c) {
      var barra = el('div', { class: 'comp-barra', 'aria-hidden': 'true' }, [el('div', { class: 'eixo' })]);
      var largura = Math.abs(c.v) / maximo * 50;
      var preenche = el('div', { class: 'preenche ' + (c.v >= 0 ? 'preenche-pos' : 'preenche-neg') });
      preenche.style.width = largura + '%';
      preenche.style.left = (c.v >= 0 ? 50 : 50 - largura) + '%';
      barra.appendChild(preenche);
      alvo.appendChild(el('div', { class: 'comp-linha' + (c.total ? ' total' : '') }, [
        el('span', { text: c.rot }),
        barra,
        el('span', { class: 'num', text: P.pontos(c.v, 1) + ' pts' })
      ]));
    });
  }

  /* ---------- Minha Cesta ---------- */
  function itemCesta(chave) {
    for (var i = 0; i < dados.cesta.length; i++) if (dados.cesta[i].item === chave) return dados.cesta[i];
    return null;
  }

  function lerNumero(txt) {
    var s = String(txt || '').trim().replace(/\s/g, '').replace(/^R\$/, '');
    if (!s) return NaN;
    if (s.indexOf(',') >= 0) s = s.replace(/\./g, '').replace(',', '.');
    if (!/^\d+(\.\d+)?$/.test(s)) return NaN;
    var v = Number(s);
    return v <= 1e7 ? v : NaN;
  }

  function restaurarExemplo() {
    linhasCesta = EXEMPLO.map(function (l) {
      return { id: proximoId++, item: l.item, nome: l.nome || '', qtd: l.qtd, preco: l.preco };
    });
  }

  function renderLinhasCesta(focarId) {
    var cont = $('cesta-linhas');
    cont.textContent = '';
    linhasCesta.forEach(function (l, idx) {
      var info = itemCesta(l.item);
      var unidade = info ? info.unidade : 'unidade';
      var idItem = 'c-item-' + l.id, idQtd = 'c-qtd-' + l.id, idPreco = 'c-preco-' + l.id, idNome = 'c-nome-' + l.id;

      var sel = el('select', { id: idItem });
      dados.cesta.forEach(function (c) {
        sel.appendChild(el('option', { value: c.item, selected: c.item === l.item, text: c.nome }));
      });
      sel.appendChild(el('option', { value: 'outro', selected: l.item === 'outro', text: 'Outro item' }));
      sel.addEventListener('change', function () { l.item = sel.value; renderLinhasCesta(l.id); calcularCesta(); });

      var campoItem = el('div', { class: 'campo campo-item' }, [el('label', { for: idItem, text: 'Item ' + (idx + 1) }), sel]);
      if (l.item === 'outro') {
        var nome = el('input', { type: 'text', id: idNome, class: 'outro-nome', value: l.nome, maxlength: '40', autocomplete: 'off' });
        nome.addEventListener('input', function () { l.nome = nome.value; calcularCesta(); });
        campoItem.appendChild(el('label', { for: idNome, class: 'sr-only', text: 'Nome do item ' + (idx + 1) }));
        campoItem.appendChild(nome);
      }

      var qtd = el('input', { type: 'text', id: idQtd, inputmode: 'decimal', value: l.qtd, autocomplete: 'off', 'aria-describedby': 'erro-' + l.id });
      qtd.addEventListener('input', function () { l.qtd = qtd.value; calcularCesta(); });
      var preco = el('input', { type: 'text', id: idPreco, inputmode: 'decimal', value: l.preco, autocomplete: 'off', 'aria-describedby': 'erro-' + l.id });
      preco.addEventListener('input', function () { l.preco = preco.value; calcularCesta(); });

      var remover = el('button', { type: 'button', class: 'botao-remover', 'aria-label': 'Remover item ' + (idx + 1), text: '✕' });
      remover.addEventListener('click', function () {
        linhasCesta = linhasCesta.filter(function (x) { return x.id !== l.id; });
        renderLinhasCesta();
        calcularCesta();
        $('add-item').focus();
      });

      var linha = el('div', { class: 'cesta-linha', 'data-id': l.id }, [
        campoItem,
        el('div', { class: 'campo' }, [el('label', { for: idQtd, text: 'Quantidade (' + unidade + ')' }), qtd]),
        el('div', { class: 'campo' }, [el('label', { for: idPreco, text: 'Preço pago (R$ por ' + unidade + ')' }), preco]),
        remover,
        el('span', { class: 'erro-campo', id: 'erro-' + l.id, 'aria-live': 'polite' })
      ]);
      cont.appendChild(linha);
    });
    if (focarId) {
      var alvo = document.getElementById('c-item-' + focarId);
      if (alvo) alvo.focus();
    }
  }

  function calcularCesta() {
    var res = $('resultado-cesta');
    var base = 0, est = 0, lo = 0, hi = 0, coberto = 0;
    var detalhes = [];
    linhasCesta.forEach(function (l) {
      var q = lerNumero(l.qtd), pr = lerNumero(l.preco);
      var inQ = document.getElementById('c-qtd-' + l.id), inP = document.getElementById('c-preco-' + l.id);
      var msg = document.getElementById('erro-' + l.id);
      var qOk = !isNaN(q), pOk = !isNaN(pr);
      if (inQ) inQ.setAttribute('aria-invalid', qOk ? 'false' : 'true');
      if (inP) inP.setAttribute('aria-invalid', pOk ? 'false' : 'true');
      if (msg) msg.textContent = (qOk && pOk) ? '' : 'Use número positivo, com vírgula para centavos (ex.: 6,50). Linha fora da conta.';
      if (!qOk || !pOk) return;

      var b = q * pr;
      var info = itemCesta(l.item);
      var nome = info ? info.nome : (l.nome.trim() || 'Outro item');
      var p = info ? ponto(serie(info.serie), mesSel) : null;
      var st = p ? p.st : null;
      var e = b, a = b, z = b, rotulo;
      if (p && st === 'estimativa') {
        e = b * (1 + p.prev / 100); a = b * (1 + p.lo / 100); z = b * (1 + p.hi / 100);
        coberto += b;
        rotulo = 'estimativa ' + P.pct(p.prev);
      } else if (!info) {
        rotulo = 'sem estimativa, preço informado';
      } else {
        rotulo = P.STATUS[st || 'sem_recomendacao'].toLowerCase() + ', preço informado';
      }
      base += b; est += e; lo += a; hi += z;
      detalhes.push({ nome: nome, base: b, est: e, rotulo: rotulo });
    });

    res.textContent = '';
    if (base <= 0) {
      res.appendChild(el('p', { class: 'nota', text: 'Informe ao menos um item com quantidade e preço.' }));
      return;
    }
    var cobPct = coberto / base * 100;
    res.appendChild(el('p', { class: 'grande', text: P.brl(est) }));
    res.appendChild(el('p', { class: 'nota', text: 'Faixa: ' + P.brl(lo) + ' a ' + P.brl(hi) + ' · mês de referência: ' + P.mesLongo(mesSel) }));
    res.appendChild(el('div', { class: 'linha-res' }, [el('span', { text: 'Gasto no mês-base (' + P.mesLongo(P.mesAnterior(mesSel)) + ')' }), el('span', { text: P.brl(base) })]));
    res.appendChild(el('div', { class: 'linha-res' }, [el('span', { text: 'Variação do cenário' }), el('span', { text: P.pct((est / base - 1) * 100) })]));
    var barra = el('div', { class: 'cobertura-barra', 'aria-hidden': 'true' }, [el('div')]);
    barra.firstChild.style.width = Math.min(100, cobPct) + '%';
    res.appendChild(el('div', { class: 'linha-res' }, [el('span', { text: 'Parcela do gasto com estimativa' }), el('span', { text: P.pct(cobPct, 0, false) })]));
    res.appendChild(barra);
    detalhes.forEach(function (d) {
      res.appendChild(el('div', { class: 'linha-res' }, [
        el('span', null, [d.nome, el('span', { class: 'sub sub-escuro', text: d.rotulo })]),
        el('span', { text: P.brl(d.base) + ' → ' + P.brl(d.est) })
      ]));
    });
    res.appendChild(el('p', { class: 'nota', text: 'A faixa soma os extremos item a item, como se todos errassem para o mesmo lado, e por isso é larga. É um cenário de custo do mês, não conselho de compra.' }));
  }

  /* ---------- Montagem ---------- */
  function preencherSelects() {
    var selMes = $('sel-mes');
    selMes.textContent = '';
    dados.meses.slice().reverse().forEach(function (m) {
      selMes.appendChild(el('option', { value: m, selected: m === mesSel, text: P.mesLongo(m) }));
    });
    selMes.disabled = false;
    selMes.addEventListener('change', function () { mesSel = selMes.value; atualizar(); });

    var selSerie = $('sel-serie');
    selSerie.textContent = '';
    dados.series.forEach(function (s) {
      selSerie.appendChild(el('option', { value: s.id, selected: s.id === serieSel, text: s.nome + ' · ' + s.fonte }));
    });
    selSerie.disabled = false;
    selSerie.addEventListener('change', function () { serieSel = selSerie.value; renderGrafico(); renderComponentes(); });
    var espera = null, larguraAnterior = window.innerWidth;
    window.addEventListener('resize', function () {
      if (window.innerWidth === larguraAnterior) return;
      larguraAnterior = window.innerWidth;
      clearTimeout(espera);
      espera = setTimeout(renderGrafico, 200);
    });
  }

  function atualizar() {
    renderContexto();
    renderTabela();
    renderGrafico();
    renderComponentes();
    calcularCesta();
  }

  function iniciar() {
    P.carregarJSON('../data/previsoes.json').then(function (d) {
      dados = d;
      mesSel = dados.meses[dados.meses.length - 1];
      preencherSelects();
      restaurarExemplo();
      renderLinhasCesta();
      $('add-item').addEventListener('click', function () {
        var l = { id: proximoId++, item: 'outro', nome: '', qtd: '', preco: '' };
        linhasCesta.push(l);
        renderLinhasCesta(l.id);
        calcularCesta();
      });
      $('restaurar').addEventListener('click', function () { restaurarExemplo(); renderLinhasCesta(); calcularCesta(); });
      var cob = dados.cobertura_faixa;
      $('nota-cobertura').textContent = 'A faixa de 80% é a estimativa ± 1,28 vez o erro quadrático médio dos meses anteriores (mínimo de ' +
        dados.faixa.min_erros + ' meses). No backtest, ela conteve o realizado em ' + cob.dentro + ' de ' + cob.n +
        ' meses-série (' + P.numero(cob.pct, 1) + '%).';
      atualizar();
    }).catch(function (err) {
      P.mostrarErro($('contexto-mes'), 'Não foi possível carregar os dados (' + err.message + ').');
      P.mostrarErro(document.querySelector('#corpo-itens td'), 'Dados indisponíveis.');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
