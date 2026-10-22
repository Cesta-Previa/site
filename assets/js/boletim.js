/* PRÉVIA, exemplo do Boletim PRÉVIA de preços. Lê data/boletim.json (gerado por build_data.py). */
(function () {
  'use strict';
  var P = window.PREVIA;
  var el = P.el;
  var DIAS = ['domingo', 'segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado'];

  function glifo(v) {
    var classe = 'seta-estavel', g = '■';
    if (v > 1) { classe = 'seta-alta'; g = '▲'; } else if (v < -1) { classe = 'seta-queda'; g = '▼'; }
    return el('span', { class: 'seta ' + classe, 'aria-hidden': 'true', text: g });
  }

  function reais(v) { return 'R$ ' + P.numero(v, v % 1 ? 2 : 0); }

  function frase(t) {
    if (t.st !== 'estimativa') {
      return t.nome + ': sem estimativa neste mês. O modelo não superou a média sazonal para este item; acompanhamos só o atacado.';
    }
    var faixa = 'faixa de ' + P.pct(t.lo) + ' a ' + P.pct(t.hi);
    var cruza = t.lo < 0 && t.hi > 0;
    if (Math.abs(t.prev) <= 1) {
      return t.nome + ': praticamente estável (' + P.pct(t.prev) + '), ' + faixa + '.';
    }
    var sentido = t.prev > 0 ? 'alta' : 'queda';
    var oposto = t.prev > 0 ? 'queda' : 'alta';
    return t.nome + ': ' + sentido + ' estimada de ' + P.pct(t.prev, 1, false).replace('−', '') + ', ' + faixa +
      (cruza ? ', que também inclui ' + oposto + '.' : '.');
  }

  function render(d) {
    var ed = d.edicao.split('-');
    var dia = new Date(Date.UTC(Number(ed[0]), Number(ed[1]) - 1, Number(ed[2]))).getUTCDay();
    document.getElementById('edicao-data').textContent =
      'Edição de ' + DIAS[dia] + ', ' + P.data(d.edicao) + ' · Região Metropolitana do Rio';

    var corpo = document.getElementById('boletim-corpo');
    corpo.textContent = '';

    corpo.appendChild(el('h3', { text: 'No atacado da CEASA-RJ' }));
    corpo.appendChild(el('p', { class: 'muted', text: 'Preço mais comum nos boletins de ' + P.data(d.boletim_1) + ' e ' + P.data(d.boletim_2) +
      ', comparado à média de ' + P.mesLongo(d.mes_anterior).split(' de ')[0] + '.' }));
    var ulA = el('ul');
    d.atacado.forEach(function (a) {
      var emb = a.emb.split(', ')[1] || a.emb;
      var txt = a.nome + ' (' + emb + '): ' + reais(a.p1) + ' e ' + reais(a.p2) + '. Média de ' +
        P.mesLongo(d.mes_anterior).split(' de ')[0] + ': ' + reais(a.media_mes_ant) + ' (' + P.pct(a.var2, 0) + ').';
      ulA.appendChild(el('li', null, [glifo(a.var2), el('span', { text: txt })]));
    });
    corpo.appendChild(ulA);

    corpo.appendChild(el('h3', { text: 'Tendência do mês no varejo' }));
    corpo.appendChild(el('p', { class: 'muted', text: 'Estimativa para ' + P.mesLongo(d.mes).split(' de ')[0] +
      ' no IPCA da RM Rio, com faixa de incerteza de 80% calculada pelo erro dos meses anteriores.' }));
    var ulT = el('ul');
    d.tendencia.forEach(function (t) {
      var g = t.st === 'estimativa' ? glifo(t.prev) : el('span', { class: 'seta seta-estavel', 'aria-hidden': 'true', text: '○' });
      ulT.appendChild(el('li', null, [g, el('span', { text: frase(t) })]));
    });
    corpo.appendChild(ulT);

    corpo.appendChild(el('p', { class: 'muted', text: 'Faixa larga quer dizer incerteza alta. A estimativa não é garantia de preço.' }));
    corpo.appendChild(el('p', { class: 'muted', text: 'Sugestões de troca por alimentos da estação, dentro do mesmo grupo alimentar, entram só depois de revisão de nutricionista e não fazem parte deste exemplo.' }));
    corpo.appendChild(el('p', { class: 'muted', text: 'Fontes: boletins da CEASA-RJ e modelo PRÉVIA. Não é conselho de compra nem de estocagem.' }));

    // Conferência
    var ant = d.tendencia[0].ant;
    var divulg = P.somarDias(d.edicao, ant);
    var fora = d.tendencia.filter(function (t) { return t.st === 'estimativa' && t.dentro === false; }).map(function (t) { return t.nome.toLowerCase(); });
    var intro = 'O IPCA de ' + P.mesLongo(d.mes) + ' saiu em ' + P.data(divulg) + ', ' + ant + ' dias depois desta edição. ';
    intro += fora.length
      ? 'A alta de ' + fora.join(' e ') + ' passou do limite de cima da faixa. O erro fica publicado do mesmo jeito que os acertos.'
      : 'Todos os itens com estimativa ficaram dentro da faixa.';
    document.getElementById('conf-intro').textContent = intro;

    var tb = document.getElementById('corpo-conf');
    tb.textContent = '';
    d.tendencia.forEach(function (t) {
      var pub = t.st === 'estimativa';
      tb.appendChild(el('tr', null, [
        el('th', { scope: 'row', text: t.nome }),
        el('td', null, [pub ? P.variacao(t.prev) : el('span', { text: 'Não publicada' })]),
        el('td', { class: 'n', text: pub ? P.pct(t.lo) + ' a ' + P.pct(t.hi) : '—' }),
        el('td', null, [P.variacao(t.real)]),
        el('td', { class: pub && t.dentro ? 'destaque-ok' : null, text: pub ? (t.dentro ? 'Dentro da faixa' : 'Fora da faixa') : 'Só monitoramento' })
      ]));
    });
  }

  function iniciar() {
    P.carregarJSON('../data/boletim.json').then(render).catch(function (err) {
      P.mostrarErro(document.getElementById('boletim-corpo'), 'Não foi possível carregar o exemplo (' + err.message + ').');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
