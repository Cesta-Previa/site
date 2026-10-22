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
      return t.nome + ': sem estimativa neste mês, porque o modelo não superou a média dos mesmos meses em anos anteriores. No exemplo, só o atacado aparece para este item.';
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
    var aviso = document.getElementById('aviso-edicao');
    if (aviso) { aviso.textContent = P.data(d.edicao); aviso.setAttribute('datetime', d.edicao); }

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
      ' no IPCA (índice oficial de inflação do IBGE) da Região Metropolitana do Rio, com faixa de incerteza de 80% calculada pelo erro dos meses anteriores.' }));
    var ulT = el('ul');
    d.tendencia.forEach(function (t) {
      var g = t.st === 'estimativa' ? glifo(t.prev) : el('span', { class: 'seta seta-estavel', 'aria-hidden': 'true', text: '○' });
      ulT.appendChild(el('li', null, [g, el('span', { text: frase(t) })]));
    });
    corpo.appendChild(ulT);

    corpo.appendChild(el('p', { class: 'muted', text: 'Faixa larga quer dizer incerteza alta. A estimativa não é garantia de preço.' }));
    corpo.appendChild(el('p', { class: 'muted', text: 'Se o projeto for contratado, as edições trarão uma nota sobre alimentos da estação, organizada por grupo alimentar e revisada por nutricionista. Este exemplo não traz isso.' }));
    corpo.appendChild(el('p', { class: 'muted', text: 'Fontes: boletins da CEASA-RJ e modelo PRÉVIA.' }));

    // Conferência: posição do realizado em relação à faixa, calculada pelo sinal (acima ou abaixo)
    document.getElementById('cap-conf').textContent = 'Tendência estimada em ' + P.data(d.edicao) +
      ' e variação realizada no IPCA da Região Metropolitana do Rio em ' + P.mesLongo(d.mes) + '.';
    var pubs = d.tendencia.filter(function (t) { return t.st === 'estimativa'; });
    var divulgados = d.tendencia.filter(function (t) { return temReal(t); });
    var nomes = function (lst, pos) {
      return lst.filter(function (t) { return posicao(t) === pos; }).map(function (t) { return t.nome.toLowerCase(); });
    };
    var intro;
    if (!divulgados.length) {
      intro = 'Na data da edição de exemplo, o IPCA de ' + P.mesLongo(d.mes) + ' ainda não tinha sido divulgado.';
    } else {
      var ant = divulgados[0].ant;
      intro = 'O IPCA de ' + P.mesLongo(d.mes) + ' saiu em ' + P.data(P.somarDias(d.edicao, ant)) + ', ' + ant + ' dias depois desta edição. ';
      var acima = nomes(pubs, 'acima'), abaixo = nomes(pubs, 'abaixo'), partes = [];
      if (acima.length) partes.push('A variação realizada de ' + juntar(acima) + ' ficou acima da faixa.');
      if (abaixo.length) partes.push('A variação realizada de ' + juntar(abaixo) + ' ficou abaixo da faixa.');
      if (partes.length) intro += partes.join(' ') + ' O erro fica publicado do mesmo jeito que os acertos.';
      else if (nomes(pubs, 'dentro').length) intro += 'Todos os itens com estimativa e realizado divulgado ficaram dentro da faixa.';
      var pend = nomes(d.tendencia, 'pendente');
      if (pend.length) intro += ' O realizado de ' + juntar(pend) + ' ainda não foi divulgado.';
    }
    document.getElementById('conf-intro').textContent = intro;

    var RESULTADO = { dentro: 'Dentro da faixa', acima: 'Acima da faixa', abaixo: 'Abaixo da faixa', pendente: 'Aguardando o IPCA' };
    var tb = document.getElementById('corpo-conf');
    tb.textContent = '';
    d.tendencia.forEach(function (t) {
      var pub = t.st === 'estimativa';
      var pos = posicao(t);
      tb.appendChild(el('tr', null, [
        el('th', { scope: 'row', text: t.nome }),
        el('td', null, [pub ? P.variacao(t.prev) : el('span', { text: 'Não publicada' })]),
        el('td', { class: 'n', text: pub ? P.pct(t.lo) + ' a ' + P.pct(t.hi) : '—' }),
        el('td', null, [temReal(t) ? P.variacao(t.real) : el('span', { text: 'Ainda não divulgado' })]),
        el('td', { class: pub && pos === 'dentro' ? 'destaque-ok' : null, text: pub ? RESULTADO[pos] : 'Só monitoramento' })
      ]));
    });
  }

  function temReal(t) { return t.real !== null && t.real !== undefined && !isNaN(t.real); }

  /* 'dentro' | 'acima' | 'abaixo' | 'pendente' (realizado ainda não divulgado) */
  function posicao(t) {
    if (!temReal(t)) return 'pendente';
    if (t.real > t.hi) return 'acima';
    if (t.real < t.lo) return 'abaixo';
    return 'dentro';
  }

  function juntar(lst) {
    return lst.length < 2 ? lst.join('') : lst.slice(0, -1).join(', ') + ' e ' + lst[lst.length - 1];
  }

  function iniciar() {
    P.carregarJSON('../data/boletim.json').then(render).catch(function (err) {
      P.mostrarErro(document.getElementById('boletim-corpo'), 'Não foi possível carregar o exemplo (' + err.message + ').');
      document.getElementById('edicao-data').textContent = 'Edição indisponível.';
      document.getElementById('conf-intro').textContent = 'Conferência indisponível: o exemplo não carregou.';
      var tb = document.getElementById('corpo-conf');
      tb.textContent = '';
      tb.appendChild(el('tr', null, [el('td', { colspan: '5', class: 'estado estado-erro', text: 'Dados indisponíveis.' })]));
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
