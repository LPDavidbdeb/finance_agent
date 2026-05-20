import React from 'react';
import { ScenarioMetrics } from '../api/client';

interface ScenarioHeatmapProps {
  scenarios: ScenarioMetrics[];
  heatmapData: number[][];
}

const ScenarioHeatmap: React.FC<ScenarioHeatmapProps> = ({ scenarios, heatmapData }) => {
  if (!heatmapData || heatmapData.length === 0) {
    return null;
  }

  // Flatten all values to find min/max for color scaling
  const allValues = heatmapData.flat();
  const minVal = Math.min(...allValues);
  const maxVal = Math.max(...allValues);

  // Color scale: red (negative) -> white (zero) -> green (positive)
  const getColor = (value: number): string => {
    const normalized = (value - minVal) / (maxVal - minVal);

    if (normalized < 0.5) {
      // Red to white gradient
      const intensity = normalized * 2; // 0 to 1
      const r = 255;
      const g = Math.round(200 + intensity * 55); // 200 to 255
      const b = Math.round(200 + intensity * 55);
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      // White to green gradient
      const intensity = (normalized - 0.5) * 2; // 0 to 1
      const r = Math.round(255 - intensity * 100); // 255 to 155
      const g = 255;
      const b = Math.round(255 - intensity * 100);
      return `rgb(${r}, ${g}, ${b})`;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-4">Return Heatmap</h2>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200">
              <th className="text-left py-2 px-3 font-medium text-slate-700">Horizon</th>
              <th className="text-center py-2 px-3 font-medium text-slate-700">Lump Sum</th>
              <th className="text-center py-2 px-3 font-medium text-slate-700">DCA</th>
            </tr>
          </thead>
          <tbody>
            {scenarios.map((scenario, idx) => (
              <tr key={idx} className="border-b border-slate-100 hover:bg-slate-50">
                <td className="py-3 px-3 font-medium text-slate-900">{scenario.horizon_years} years</td>
                <td className="py-3 px-3">
                  <div
                    className="rounded px-3 py-2 text-center text-white font-mono font-semibold transition-all"
                    style={{ backgroundColor: getColor(heatmapData[idx][0]) }}
                  >
                    {(heatmapData[idx][0] * 100).toFixed(2)}%
                  </div>
                </td>
                <td className="py-3 px-3">
                  <div
                    className="rounded px-3 py-2 text-center text-white font-mono font-semibold transition-all"
                    style={{ backgroundColor: getColor(heatmapData[idx][1]) }}
                  >
                    {(heatmapData[idx][1] * 100).toFixed(2)}%
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="mt-4 flex items-center gap-4 text-xs text-slate-600">
        <div className="flex items-center gap-2">
          <div
            className="w-6 h-4 rounded"
            style={{ backgroundColor: getColor(minVal) }}
          />
          <span>{(minVal * 100).toFixed(1)}%</span>
        </div>
        <div className="flex-1 h-4 rounded" style={{
          background: `linear-gradient(to right, rgb(255, 200, 200), white, rgb(155, 255, 155))`
        }} />
        <div className="flex items-center gap-2">
          <span>{(maxVal * 100).toFixed(1)}%</span>
          <div
            className="w-6 h-4 rounded"
            style={{ backgroundColor: getColor(maxVal) }}
          />
        </div>
      </div>
    </div>
  );
};

export default ScenarioHeatmap;
