let chartInstance = null;

const PERIODO_LABELS = {
  '1mo': '1 mês', '3mo': '3 meses', '6mo': '6 meses',
  '1y': '1 ano', '2y': '2 anos', '5y': '5 anos'
};

async function carregarGrafico() {
  const ticker  = document.getElementById('g-ticker').value.trim();
  const mercado = document.getElementById('g-mercado').value;
  const periodo = document.getElementById('g-periodo').value;
  if (!ticker) return;

  const container = document.getElementById('chart-container');
  const loading   = document.getElementById('chart-loading');
  const header    = document.getElementById('chart-header');

  loading.textContent = 'Carregando...';
  loading.style.display = 'block';
  container.style.display = 'none';
  header.style.display = 'none';

  try {
    const res = await fetch(`/history/${ticker}?mercado=${mercado}&periodo=${periodo}`);
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Erro ao buscar dados'); }
    const data = await res.json();

    if (chartInstance) { chartInstance.remove(); chartInstance = null; }

    container.style.display = 'block';
    loading.style.display = 'none';

    document.getElementById('chart-ticker').textContent = data.ticker;
    document.getElementById('chart-periodo').textContent = PERIODO_LABELS[periodo] || periodo;
    if (data.cache) document.getElementById('chart-cache-badge').style.display = 'inline';
    else document.getElementById('chart-cache-badge').style.display = 'none';
    header.style.display = 'flex';

    chartInstance = LightweightCharts.createChart(container, {
      width: container.clientWidth,
      height: 420,
      layout: { background: { color: '#ffffff' }, textColor: '#1A1814' },
      grid: {
        vertLines: { color: '#F5F3EE' },
        horzLines: { color: '#F5F3EE' },
      },
      timeScale: { borderColor: '#DDD9D0', timeVisible: false },
      rightPriceScale: { borderColor: '#DDD9D0' },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    });

    const candleSeries = chartInstance.addCandlestickSeries({
      upColor: '#1E6E3A', downColor: '#8B1A1A',
      borderVisible: false,
      wickUpColor: '#1E6E3A', wickDownColor: '#8B1A1A',
    });
    candleSeries.setData(data.candles);

    const volumeSeries = chartInstance.addHistogramSeries({
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });
    volumeSeries.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    volumeSeries.setData(data.candles.map((c, i) => ({
      time:  c.time,
      value: data.volumes[i]?.value || 0,
      color: c.close >= c.open ? '#CEE8D6' : '#F5D0D0',
    })));

    chartInstance.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (chartInstance) chartInstance.applyOptions({ width: container.clientWidth });
    });
    ro.observe(container);

  } catch (e) {
    loading.textContent = 'Erro: ' + e.message;
    loading.style.display = 'block';
    container.style.display = 'none';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('g-ticker');
  if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter') carregarGrafico(); });
});
