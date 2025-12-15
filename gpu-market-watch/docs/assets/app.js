async function loadData() {
  const response = await fetch('../data/gpu_prices.json?_=1765777328.008774');
  const data = await response.json();
  return data;
}

function renderSummary(prices) {
  const container = document.getElementById('summary');
  const offers = prices.length;
  const providers = new Set(prices.map(p => p.provider_id)).size;
  container.innerHTML = `<section><h2>Snapshot</h2><p>${offers} offers across ${providers} providers.</p></section>`;
}

function renderTable(prices) {
  const container = document.getElementById('table');
  const providers = [...new Set(prices.map(p => p.provider_id))];
  container.innerHTML = `
  <section>
    <h2>Offers</h2>
    <label>Filter GPU <input id="gpu-filter" placeholder="e.g. A100" /></label>
    <label>Provider <select id="provider-filter"><option value="">All</option>${providers.map(p => `<option>${p}</option>`).join('')}</select></label>
    <table>
      <thead><tr><th>GPU</th><th>USD/hr</th><th>Provider</th><th>Region</th><th>SKU</th></tr></thead>
      <tbody></tbody>
    </table>
  </section>`;
  const tbody = container.querySelector('tbody');
  function applyFilters() {
    const gpu = document.getElementById('gpu-filter').value.toLowerCase();
    const provider = document.getElementById('provider-filter').value;
    tbody.innerHTML = prices
      .filter(p => (!gpu || p.gpu.toLowerCase().includes(gpu)) && (!provider || p.provider_id === provider))
      .map(p => `<tr><td>${p.gpu}</td><td>${p.usd_per_hour.toFixed(4)}</td><td>${p.provider_id}</td><td>${p.region || ''}</td><td>${p.sku || ''}</td></tr>`)
      .join('');
  }
  document.getElementById('gpu-filter').addEventListener('input', applyFilters);
  document.getElementById('provider-filter').addEventListener('change', applyFilters);
  applyFilters();
}

function renderChart(prices) {
  const container = document.getElementById('chart');
  const cheapest = Object.values(prices.reduce((acc, offer) => {
    if (!acc[offer.gpu] || acc[offer.gpu].usd_per_hour > offer.usd_per_hour) {
      acc[offer.gpu] = offer;
    }
    return acc;
  }, {}));
  cheapest.sort((a, b) => a.usd_per_hour - b.usd_per_hour);
  container.innerHTML = `<section><h2>Min $/hr by GPU</h2><div class="chart"></div></section>`;
  const chart = container.querySelector('.chart');
  chart.style.display = 'grid';
  chart.style.gap = '0.5rem';
  cheapest.forEach(item => {
    const row = document.createElement('div');
    const label = document.createElement('div');
    label.textContent = `${item.gpu} (${item.provider_id})`;
    const bar = document.createElement('div');
    bar.style.height = '16px';
    bar.style.background = '#38bdf8';
    bar.style.width = `${Math.max(item.usd_per_hour * 40, 5)}px`;
    const value = document.createElement('span');
    value.textContent = `$${item.usd_per_hour.toFixed(4)}/hr`;
    value.style.marginLeft = '0.5rem';
    const wrapper = document.createElement('div');
    wrapper.style.display = 'flex';
    wrapper.style.alignItems = 'center';
    wrapper.appendChild(bar);
    wrapper.appendChild(value);
    row.appendChild(label);
    row.appendChild(wrapper);
    row.style.display = 'grid';
    row.style.gridTemplateColumns = '200px 1fr';
    chart.appendChild(row);
  });
}

(async function init() {
  try {
    const prices = await loadData();
    renderSummary(prices);
    renderTable(prices);
    renderChart(prices);
  } catch (error) {
    console.error('Failed to load dashboard data', error);
  }
})();
