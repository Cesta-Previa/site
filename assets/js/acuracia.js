/* PRÉVIA, página de acurácia. Lê data/metricas.json (gerado por build_data.py). */
(function () {
  'use strict';
  var P = window.PREVIA;
  var el = P.el;
  var dados = null;

  function relP(rel, p) {
    var txt = P.numero(rel, 2) + ' (' + (p < 0.01 ? '<0,01' : P.numero(p, 2)) + ')';
    return el('td', { class: 'n' + (rel < 1 && p < 0.05 ? ' destaque-ok' : ''), text: txt });
  }

  function renderPlacar() {
    var corpo = document.getElementById('corpo-placar');
    corpo.textContent = '';
    dados.placar_e1.forEach(function (x) {
      corpo.appendChild(el('tr', null, [
        el('th', { scope: 'row', text: x.h === 1 ? '1 mês (corrente)' : x.h + ' meses' }),
        el('td', { class: 'n', text: x.vence_rw + ' de ' + x.n_alvos + ' (' + x.vence_rw_p05 + ')' }),
        el('td', { class: 'n', text: x.vence_mb + ' de ' + x.n_alvos + ' (' + x.vence_mb_p05 + ')' }),
        el('td', { class: 'n', text: P.numero(x.rel_rw_med, 2) }),
        el('td', { class: 'n', text: P.numero(x.rel_mb_med, 2) }),
        el('td', { class: 'n', text: P.numero(x.dir_med, 0) + '%' })
      ]));
    });
    var c = dados.cobertura_faixa;
    document.getElementById('nota-faixa').textContent =
      'Faixa de incerteza usada na demonstração: estimativa ± 1,28 vez o RMSE (raiz do erro quadrático médio, que mede o erro típico) dos meses anteriores (nível nominal de 80%). ' +
      'No backtest, ela conteve o realizado em ' + c.dentro + ' de ' + c.n + ' meses-série (' + P.numero(c.pct, 1) + '%).';
  }

  function renderMetricas(h) {
    var corpo = document.getElementById('corpo-metricas');
    corpo.textContent = '';
    var anterior = null;
    dados.e1.filter(function (x) { return h === 'todos' || String(x.h) === h; }).forEach(function (x) {
      var nova = anterior !== null && anterior !== x.serie;
      anterior = x.serie;
      corpo.appendChild(el('tr', { class: nova && h === 'todos' ? 'linha-grupo' : null }, [
        el('th', { scope: 'row' }, [x.nome, el('span', { class: 'sub', text: x.fonte })]),
        el('td', { class: 'n', text: String(x.h) }),
        el('td', { class: 'n', text: String(x.n) }),
        el('td', { class: 'n', text: P.numero(x.rmse_pp, 1) }),
        relP(x.rel_rw, x.p_rw),
        el('td', { text: x.melhor_baseline }),
        relP(x.rel_mb, x.p_mb),
        el('td', { class: 'n', text: P.numero(x.dir, 0) + '%' }),
        el('td', { class: 'n', text: P.numero(x.mape, 1) + '%' }),
        el('td', { class: 'n', text: String(x.ant_med) })
      ]));
    });
  }

  function iniciar() {
    var sel = document.getElementById('sel-h');
    P.carregarJSON('../data/metricas.json').then(function (d) {
      dados = d;
      renderPlacar();
      renderMetricas(sel.value);
      sel.addEventListener('change', function () { renderMetricas(sel.value); });
    }).catch(function (err) {
      P.mostrarErro(document.querySelector('#corpo-placar td'), 'Não foi possível carregar as métricas (' + err.message + ').');
      P.mostrarErro(document.querySelector('#corpo-metricas td'), 'Métricas indisponíveis.');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar);
  else iniciar();
})();
