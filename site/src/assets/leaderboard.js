(async function () {
  const { $, $$, esc } = CT;
  const [R, charts] = await Promise.all([CT.ratings(), CT.json('data/charts.json')]);
  const ms = R.models.slice().sort((a, b) => b.combined - a.combined);
  const words = ['Zero', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen'];
  $('#lb-lede').textContent = `${words[ms.length] || ms.length} models released in 2026, ${R.games} rated games. Every model plays both sides.`;

  // The newest model, in one line above the table.
  const newest = R.models.slice().sort((a, b) => b.date.localeCompare(a.date))[0], rank = ms.indexOf(newest) + 1;
  if ($('#lb-news')) $('#lb-news').innerHTML = `<b>Newest:</b> <a href="games.html?model=${encodeURIComponent(newest.id)}">${esc(CT.name(R, newest.id))}</a>, released ${CT.fmtDate(newest.date)}, rates <b>${newest.combined}</b> (90%: ${newest.c90[0]}–${newest.c90[1]}) after ${newest.good_games + newest.evil_games} games: ${['', 'first', 'second', 'third', 'fourth', 'fifth'][rank] || '#' + rank} of ${ms.length}.`;

  // Ranked table: the script sheet (CT.board in site.js).
  CT.board($('#table'), R);

  // Rating by date, with a metric switch.
  const host = $('#chart-date');
  const trendCap = (m) => {
    const t = R.trend_per_year[{ combined: 'c', detection: 'd', deception: 'v' }[m]];
    $('#trend-cap').textContent = `Trend: +${t[0]} Elo per year (90%: ${t[1][0]} to ${t[1][1]}).`;
  };
  CT.chartByDate(host, R, 'combined'); trendCap('combined');
  $$('#metric button').forEach((b) => b.addEventListener('click', () => {
    $$('#metric button').forEach((x) => x.setAttribute('aria-pressed', x === b));
    const fresh = host.cloneNode(false); $('#chart-date').replaceWith(fresh);  // a fresh node drops the old resize hook
    CT.chartByDate(fresh, R, b.dataset.m); trendCap(b.dataset.m);
  }));

  CT.chartSplit($('#chart-split'), R);

  CT.h2h($('#h2h'), R, 'both');
  $$('#h2h-mode button').forEach((b) => b.addEventListener('click', () => {
    $$('#h2h-mode button').forEach((x) => x.setAttribute('aria-pressed', x === b));
    CT.h2h($('#h2h'), R, b.dataset.m);
  }));
  window.addEventListener('ct-theme', () => CT.h2h($('#h2h'), R, ($$('#h2h-mode button').find((b) => b.getAttribute('aria-pressed') === 'true') || {}).dataset?.m || 'both'));

  CT.chartBelief($('#chart-belief'), charts.demon_belief);
  if (charts.evil_tilt) {
    $('#card-tilt').hidden = false;
    CT.chartTilt($('#chart-tilt'), charts.evil_tilt);
    $('#tilt-cap').textContent = `Catching a liar gets easier faster than lying does (in ${Math.round(charts.evil_tilt.p_good_gains * 100)}% of bootstrap resamples).`;
  }
  if (charts.mixed) {
    $('#card-mixed').hidden = false;
    const drawMixed = (k) => {
      const fresh = $('#chart-mixed').cloneNode(false); $('#chart-mixed').replaceWith(fresh);
      CT.chartMixed(fresh, charts.mixed, R, k);
      const d = charts.mixed[k], label = { combined: 'Overall', detection: 'As good', deception: 'As evil' }[k];
      $('#mixed-cap').textContent = `${label}: mixed team ${d.mixed[0]} vs members' average ${d.members_mean[0]}. ${k === 'deception' ? 'Mixed evil teams won 4 of 66 games; this is the one split whose interval excludes zero.' : 'The interval includes zero: a small effect at most.'}`;
    };
    drawMixed('deception');
    $$('#mixed-mode button').forEach((b) => b.addEventListener('click', () => {
      $$('#mixed-mode button').forEach((x) => x.setAttribute('aria-pressed', x === b)); drawMixed(b.dataset.m);
    }));
  }
  const se = R.setup_effects;
  $('#setup').innerHTML = '<tbody>' + [['Good-side advantage', R.good_advantage], ['Spy in play', se['Spy']], ['Baron in play', se['Baron']], ['Scarlet Woman in play', se['Scarlet Woman']], ['11 players', se['11 players']], ['12 players', se['12 players']], ['Evil wins overall', Math.round(R.evil_win_rate * 100) + '%']]
    .map(([k, v]) => `<tr><td>${k}</td><td class="num">${typeof v === 'number' && v > 0 ? '+' + v : v}</td></tr>`).join('') + '</tbody>';
})();
