import React, { useState, useEffect } from 'react';
import { TrendingUp, Download, Loader } from 'lucide-react';
import {
  computePortfolioScenarios,
  PortfolioScenariosResponse,
  AllocationResult,
  ScenarioMetrics,
} from '../api/client';
import ScenarioHeatmap from '../components/ScenarioHeatmap';
import ReturnDistributionGrid from '../components/ReturnDistributionGrid';

const PortfolioScenariosPage: React.FC = () => {
  const [tickers, setTickers] = useState<string>('XIU.TO, XWD.TO, XEU.TO');
  const [horizons, setHorizons] = useState<string>('2, 5, 10, 15, 25');
  const [monthlyDca, setMonthlyDca] = useState<string>('1000');
  const [result, setResult] = useState<PortfolioScenariosResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompute = async () => {
    try {
      setError(null);
      setLoading(true);

      const tickerList = tickers
        .split(',')
        .map((t) => t.trim().toUpperCase())
        .filter((t) => t.length > 0);

      if (tickerList.length === 0) {
        setError('Please enter at least one ticker.');
        setLoading(false);
        return;
      }

      const horizonList = horizons
        .split(',')
        .map((h) => parseInt(h.trim(), 10))
        .filter((h) => !isNaN(h) && h > 0);

      if (horizonList.length === 0) {
        setError('Please enter at least one valid horizon (in years).');
        setLoading(false);
        return;
      }

      const dca = parseFloat(monthlyDca);
      if (isNaN(dca) || dca <= 0) {
        setError('Monthly DCA amount must be a positive number.');
        setLoading(false);
        return;
      }

      const response = await computePortfolioScenarios(tickerList, horizonList, dca);
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCSV = () => {
    if (!result) return;

    const rows: string[] = [];
    rows.push('Portfolio Scenario Analysis');
    rows.push('');
    rows.push(`Analysis Period: ${result.optimization.period_start} to ${result.optimization.period_end}`);
    rows.push('');

    // Optimization results
    rows.push('OPTIMIZATION RESULTS');
    rows.push(`Optimal Allocation: ${result.optimization.optimal.label}`);
    result.optimization.optimal.weights.forEach((w) => {
      rows.push(`,${w.ticker},${(w.weight * 100).toFixed(1)}%`);
    });
    rows.push(`Expected Return,${result.optimization.optimal.expected_return.toFixed(4)}`);
    rows.push(`Volatility,${result.optimization.optimal.volatility.toFixed(4)}`);
    rows.push(`Sharpe Ratio,${result.optimization.optimal.sharpe_ratio.toFixed(4)}`);
    rows.push('');

    // Scenarios
    rows.push('SCENARIO RESULTS');
    rows.push('Horizon (years),Pattern,Mean Return,Std Dev,5th %ile,25th %ile,Median,75th %ile,95th %ile');
    result.scenarios.forEach((s) => {
      const lumpSumStats = s.lump_sum.stats;
      rows.push(
        `${s.horizon_years},Lump Sum,${lumpSumStats.mean.toFixed(4)},${lumpSumStats.std.toFixed(4)},${lumpSumStats.percentile_5.toFixed(4)},${lumpSumStats.percentile_25.toFixed(4)},${lumpSumStats.percentile_50.toFixed(4)},${lumpSumStats.percentile_75.toFixed(4)},${lumpSumStats.percentile_95.toFixed(4)}`
      );

      const dcaStats = s.dca.stats;
      rows.push(
        `${s.horizon_years},DCA,${dcaStats.mean.toFixed(4)},${dcaStats.std.toFixed(4)},${dcaStats.percentile_5.toFixed(4)},${dcaStats.percentile_25.toFixed(4)},${dcaStats.percentile_50.toFixed(4)},${dcaStats.percentile_75.toFixed(4)},${dcaStats.percentile_95.toFixed(4)}`
      );
    });

    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', 'portfolio-scenarios.csv');
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <TrendingUp className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-slate-900">Portfolio Scenarios</h1>
        </div>
        <p className="text-slate-600">
          Analyze return distributions across multiple horizons and investment patterns.
        </p>
      </div>

      {/* Input Section */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Configuration</h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
          {/* Tickers */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Tickers (comma-separated)
            </label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="XIU.TO, XWD.TO, XEU.TO"
            />
            <p className="text-xs text-slate-500 mt-1">e.g., XIU.TO, XWD.TO, XEU.TO, VPL, EEM</p>
          </div>

          {/* Horizons */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Horizons (years, comma-separated)
            </label>
            <input
              type="text"
              value={horizons}
              onChange={(e) => setHorizons(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="2, 5, 10, 15, 25"
            />
            <p className="text-xs text-slate-500 mt-1">Investment periods to analyze</p>
          </div>

          {/* Monthly DCA */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              Monthly DCA ($)
            </label>
            <input
              type="number"
              value={monthlyDca}
              onChange={(e) => setMonthlyDca(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="1000"
              step="100"
            />
            <p className="text-xs text-slate-500 mt-1">Dollar-cost averaging amount</p>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Compute Button */}
        <button
          onClick={handleCompute}
          disabled={loading}
          className="w-full px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-400 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader className="w-4 h-4 animate-spin" />
              Computing...
            </>
          ) : (
            'Compute Scenarios'
          )}
        </button>
      </div>

      {/* Results Section */}
      {result && (
        <div className="space-y-6">
          {/* Optimization Summary */}
          <div className="bg-white rounded-lg border border-slate-200 p-6">
            <h2 className="text-lg font-semibold text-slate-900 mb-4">Optimal Allocation</h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
              {/* Weights */}
              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-3">Weights</h3>
                <div className="space-y-2">
                  {result.optimization.optimal.weights.map((w) => (
                    <div key={w.ticker} className="flex justify-between text-sm">
                      <span className="text-slate-600">{w.ticker}</span>
                      <span className="font-mono font-semibold text-slate-900">
                        {(w.weight * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Metrics */}
              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-3">Metrics</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Expected Return</span>
                    <span className="font-mono font-semibold text-green-600">
                      {(result.optimization.optimal.expected_return * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Volatility</span>
                    <span className="font-mono font-semibold text-slate-900">
                      {(result.optimization.optimal.volatility * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Sharpe Ratio</span>
                    <span className="font-mono font-semibold text-blue-600">
                      {result.optimization.optimal.sharpe_ratio.toFixed(3)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Period */}
              <div>
                <h3 className="text-sm font-medium text-slate-700 mb-3">Analysis Period</h3>
                <div className="text-sm space-y-1">
                  <div className="text-slate-600">
                    <span className="font-medium">Start:</span> {result.optimization.period_start}
                  </div>
                  <div className="text-slate-600">
                    <span className="font-medium">End:</span> {result.optimization.period_end}
                  </div>
                  <div className="text-slate-600">
                    <span className="font-medium">Lookback:</span> 5 years
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Heatmap */}
          {result.heatmap_data && (
            <ScenarioHeatmap
              scenarios={result.scenarios}
              heatmapData={result.heatmap_data}
            />
          )}

          {/* Distribution Grids */}
          <ReturnDistributionGrid scenarios={result.scenarios} />

          {/* Download Button */}
          <div className="flex justify-end">
            <button
              onClick={handleDownloadCSV}
              className="px-4 py-2 bg-slate-600 hover:bg-slate-700 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PortfolioScenariosPage;
