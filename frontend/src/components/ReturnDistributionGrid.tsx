import React, { useMemo } from 'react';
import { ScenarioMetrics } from '../api/client';

interface ReturnDistributionGridProps {
  scenarios: ScenarioMetrics[];
}

const ReturnDistributionGrid: React.FC<ReturnDistributionGridProps> = ({ scenarios }) => {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-6">Return Distributions</h2>

      <div className="space-y-8">
        {scenarios.map((scenario, idx) => (
          <div key={idx} className="pb-6 border-b border-slate-100 last:border-b-0">
            <h3 className="text-md font-semibold text-slate-800 mb-4">
              {scenario.horizon_years}-Year Horizon
            </h3>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Lump Sum */}
              <DistributionPanel
                title="Lump Sum"
                data={scenario.lump_sum}
              />

              {/* DCA */}
              <DistributionPanel
                title="Dollar-Cost Averaging"
                data={scenario.dca}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

interface DistributionPanelProps {
  title: string;
  data: {
    count: number;
    stats: any;
    histogram_edges: number[];
    histogram_counts: number[];
    kde_x: number[];
    kde_y: number[];
  };
}

const DistributionPanel: React.FC<DistributionPanelProps> = ({ title, data }) => {
  const { stats, histogram_edges, histogram_counts, kde_x, kde_y } = data;

  // Create SVG paths for histogram and KDE
  const svgWidth = 400;
  const svgHeight = 250;
  const padding = 40;

  // Find max count for scaling
  const maxCount = Math.max(...histogram_counts, 1);
  const minReturn = Math.min(...histogram_edges);
  const maxReturn = Math.max(...histogram_edges);
  const returnRange = maxReturn - minReturn;

  // Histogram bars
  const histogramBars = histogram_counts.map((count, i) => {
    const x0 = histogram_edges[i];
    const x1 = histogram_edges[i + 1];
    const xMid = (x0 + x1) / 2;
    const xPct = (xMid - minReturn) / returnRange;
    const xPos = padding + xPct * (svgWidth - 2 * padding);
    const barWidth = (histogram_edges[1] - histogram_edges[0]) / returnRange * (svgWidth - 2 * padding) * 0.8;
    const barHeight = (count / maxCount) * (svgHeight - 2 * padding);
    const yPos = svgHeight - padding - barHeight;

    return (
      <rect
        key={`bar-${i}`}
        x={xPos - barWidth / 2}
        y={yPos}
        width={barWidth}
        height={barHeight}
        fill="#cbd5e1"
        opacity="0.6"
      />
    );
  });

  // KDE curve
  let kdePath = '';
  if (kde_x.length > 0 && kde_y.length > 0) {
    const maxDensity = Math.max(...kde_y, 1);
    kdePath = kde_x
      .map((x, i) => {
        const xPct = (x - minReturn) / returnRange;
        const xPos = padding + xPct * (svgWidth - 2 * padding);
        const yPct = (kde_y[i] / maxDensity);
        const yPos = svgHeight - padding - yPct * (svgHeight - 2 * padding);
        return `${i === 0 ? 'M' : 'L'} ${xPos} ${yPos}`;
      })
      .join(' ');
  }

  // Axes
  const xAxis = `M ${padding} ${svgHeight - padding} L ${svgWidth - padding} ${svgHeight - padding}`;
  const yAxis = `M ${padding} ${padding} L ${padding} ${svgHeight - padding}`;

  return (
    <div className="bg-slate-50 rounded-lg p-4">
      <h4 className="text-sm font-semibold text-slate-800 mb-3">{title}</h4>

      {/* Chart */}
      <svg
        width={svgWidth}
        height={svgHeight}
        className="mb-3 border border-slate-200 rounded bg-white"
      >
        {/* Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((pct) => (
          <line
            key={`grid-${pct}`}
            x1={padding + pct * (svgWidth - 2 * padding)}
            y1={padding}
            x2={padding + pct * (svgWidth - 2 * padding)}
            y2={svgHeight - padding}
            stroke="#e2e8f0"
            strokeWidth="0.5"
          />
        ))}

        {/* Axes */}
        <path d={xAxis} stroke="#475569" strokeWidth="1" fill="none" />
        <path d={yAxis} stroke="#475569" strokeWidth="1" fill="none" />

        {/* Histogram bars */}
        {histogramBars}

        {/* KDE curve */}
        {kdePath && (
          <path
            d={kdePath}
            stroke="#3b82f6"
            strokeWidth="2"
            fill="none"
          />
        )}

        {/* Mean line */}
        {stats.mean !== undefined && (
          <>
            <line
              x1={padding + ((stats.mean - minReturn) / returnRange) * (svgWidth - 2 * padding)}
              y1={padding}
              x2={padding + ((stats.mean - minReturn) / returnRange) * (svgWidth - 2 * padding)}
              y2={svgHeight - padding}
              stroke="#10b981"
              strokeWidth="2"
              strokeDasharray="4,4"
              opacity="0.7"
            />
          </>
        )}
      </svg>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-slate-600">Scenarios:</span>
          <span className="font-mono font-semibold text-slate-900 ml-2">{data.count}</span>
        </div>
        <div>
          <span className="text-slate-600">Mean:</span>
          <span className="font-mono font-semibold text-green-600 ml-2">
            {(stats.mean * 100).toFixed(2)}%
          </span>
        </div>
        <div>
          <span className="text-slate-600">Std Dev:</span>
          <span className="font-mono font-semibold text-slate-900 ml-2">
            {(stats.std * 100).toFixed(2)}%
          </span>
        </div>
        <div>
          <span className="text-slate-600">Median:</span>
          <span className="font-mono font-semibold text-blue-600 ml-2">
            {(stats.percentile_50 * 100).toFixed(2)}%
          </span>
        </div>
        <div>
          <span className="text-slate-600">5th %ile:</span>
          <span className="font-mono font-semibold text-red-600 ml-2">
            {(stats.percentile_5 * 100).toFixed(2)}%
          </span>
        </div>
        <div>
          <span className="text-slate-600">95th %ile:</span>
          <span className="font-mono font-semibold text-green-600 ml-2">
            {(stats.percentile_95 * 100).toFixed(2)}%
          </span>
        </div>
      </div>
    </div>
  );
};

export default ReturnDistributionGrid;
