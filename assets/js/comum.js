/* PRÉVIA, utilitários compartilhados (sem dependências). Todo texto entra via textContent. */
(function () {
  'use strict';

  var MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto',
    'setembro', 'outubro', 'novembro', 'dezembro'];
  var MESES_CURTOS = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  var MENOS = '−';

  function numero(v, casas) {
    return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas });
  }

  function pct(v, casas, comSinal) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    casas = casas === undefined ? 1 : casas;
    var abs = numero(Math.abs(v), casas);
    var zero = Number(abs.replace(/\./g, '').replace(',', '.')) === 0;
    var sinal = zero ? '' : (v < 0 ? MENOS : (comSinal === false ? '' : '+'));
    return sinal + abs + '%';
  }

  function pontos(v, casas) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    var abs = numero(Math.abs(v), casas === undefined ? 1 : casas);
    return (v < 0 ? MENOS : (v > 0 ? '+' : '')) + abs;
  }

  var fmtBRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  function brl(v) { return fmtBRL.format(v); }

  function mesLongo(m) {
    var p = m.split('-');
    return MESES[Number(p[1]) - 1] + ' de ' + p[0];
  }
  function mesCurto(m) {
    var p = m.split('-');
    return MESES_CURTOS[Number(p[1]) - 1] + '/' + p[0].slice(2);
  }
  function mesAnterior(m) {
    var p = m.split('-');
    var a = Number(p[0]), mm = Number(p[1]) - 1;
    if (mm === 0) { a -= 1; mm = 12; }
    return a + '-' + (mm < 10 ? '0' : '') + mm;
  }
  function data(iso) {
    var p = iso.split('-');
    return p[2] + '/' + p[1] + '/' + p[0];
  }
  function somarDias(iso, dias) {
    var p = iso.split('-');
    var d = new Date(Date.UTC(Number(p[0]), Number(p[1]) - 1, Number(p[2]) + dias));
    return d.toISOString().slice(0, 10);
  }

  /* Cria elemento: el('td', {class: 'n'}, ['texto', outroNo]) */
  function el(tag, attrs, filhos) {
    var no = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (attrs[k] === null || attrs[k] === undefined || attrs[k] === false) return;
        if (k === 'text') no.textContent = attrs[k];
        else no.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
      });
    }
    (filhos || []).forEach(function (f) {
      if (f === null || f === undefined) return;
      no.appendChild(typeof f === 'string' ? document.createTextNode(f) : f);
    });
    return no;
  }

  var SVGNS = 'http://www.w3.org/2000/svg';
  function svg(tag, attrs) {
    var no = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') no.textContent = attrs[k];
      else no.setAttribute(k, attrs[k]);
    });
    return no;
  }

  /* Variação com glifo: cor nunca é o único portador da informação */
  function variacao(v, casas) {
    var classe = 'seta-estavel', glifo = '■';
    if (v > 1) { classe = 'seta-alta'; glifo = '▲'; }
    else if (v < -1) { classe = 'seta-queda'; glifo = '▼'; }
    return el('span', { class: 'var' }, [
      el('span', { class: 'seta ' + classe, 'aria-hidden': 'true', text: glifo }),
      pct(v, casas === undefined ? 1 : casas)
    ]);
  }

  var STATUS = {
    estimativa: 'Estimativa + faixa',
    monitoramento: 'Só monitoramento',
    sem_recomendacao: 'Sem recomendação'
  };
  function status(st) {
    return el('span', { class: 'status status-' + st, text: STATUS[st] || st });
  }

  function carregarJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error('HTTP ' + r.status + ' em ' + url);
      return r.json();
    });
  }

  function mostrarErro(alvo, msg) {
    if (!alvo) return;
    alvo.textContent = '';
    alvo.appendChild(el('p', { class: 'estado estado-erro', role: 'alert',
      text: msg + ' Recarregue a página.' }));
  }

  /* Datas do site vêm de data/site.json (nenhuma data fixa no HTML).
     <time data-site="versao"> recebe "22/10/2026"; chave AAAA-MM vira "setembro de 2026"; aceita caminho com ponto. */
  function valorSite(obj, caminho) {
    return caminho.split('.').reduce(function (o, k) { return o && o[k] !== undefined ? o[k] : null; }, obj);
  }
  function formatarSite(v) {
    if (typeof v !== 'string') return null;
    if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return data(v);
    if (/^\d{4}-\d{2}$/.test(v)) return mesLongo(v);
    return v;
  }
  function preencherSite(site) {
    var alvos = document.querySelectorAll('[data-site]');
    for (var i = 0; i < alvos.length; i++) {
      var no = alvos[i];
      var bruto = valorSite(site, no.getAttribute('data-site'));
      var txt = formatarSite(bruto);
      if (txt === null) continue;
      no.textContent = txt;
      if (no.tagName === 'TIME') no.setAttribute('datetime', bruto);
    }
    return site;
  }
  var site = carregarJSON('/data/site.json').catch(function () { return null; });
  function aplicarSite() { site.then(function (s) { if (s) preencherSite(s); }); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aplicarSite);
  else aplicarSite();

  window.PREVIA = {
    pct: pct, pontos: pontos, numero: numero, brl: brl, mesLongo: mesLongo, mesCurto: mesCurto,
    mesAnterior: mesAnterior, data: data, somarDias: somarDias, el: el, svg: svg,
    variacao: variacao, status: status, STATUS: STATUS, carregarJSON: carregarJSON, mostrarErro: mostrarErro,
    site: site
  };
})();
