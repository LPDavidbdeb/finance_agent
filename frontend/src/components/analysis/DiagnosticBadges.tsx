import React from "react";
import { Badge } from "@/components/ui/badge";

export type ProcessType = "DETERMINISTIC" | "STOCHASTIC" | "EPISODIC";
export type BenchmarkClassification = 'REAL_GROWTH' | 'INFLATION_TRACKED' | 'EFFICIENCY_GAIN';

interface DiagnosticBadgesProps {
  type: ProcessType;
  causalVolumePct?: number | null;
  causalPricePct?: number | null;
  benchmarkClassification?: BenchmarkClassification | null;
}

const DiagnosticBadges: React.FC<DiagnosticBadgesProps> = ({ 
  type, 
  causalVolumePct, 
  causalPricePct,
  benchmarkClassification
}) => {
  const getBadgeConfig = (type: ProcessType) => {
    switch (type) {
      case "DETERMINISTIC":
        return {
          label: "Deterministic",
          className: "bg-blue-100 text-blue-800 hover:bg-blue-200 border-blue-200",
        };
      case "STOCHASTIC":
        return {
          label: "Stochastic",
          className: "bg-purple-100 text-purple-800 hover:bg-purple-200 border-purple-200",
        };
      case "EPISODIC":
        return {
          label: "Episodic",
          className: "bg-orange-100 text-orange-800 hover:bg-orange-200 border-orange-200",
        };
      default:
        return {
          label: "Unknown",
          className: "bg-gray-100 text-gray-800 border-gray-200",
        };
    }
  };

  const config = getBadgeConfig(type);

  // Causal Driver Logic
  const showPriceDriver = causalPricePct && causalPricePct > 0 && (!causalVolumePct || causalPricePct > causalVolumePct);
  const showVolumeDriver = causalVolumePct && causalVolumePct > 0 && (!causalPricePct || causalVolumePct >= causalPricePct);

  // Normalization Logic
  const getNormalizationConfig = (classification: BenchmarkClassification) => {
    switch (classification) {
      case 'REAL_GROWTH':
        return { label: "REAL GROWTH 📈", className: "bg-red-100 text-red-800 border-red-200" };
      case 'INFLATION_TRACKED':
        return { label: "INFLATION TRACKED ⚖️", className: "bg-gray-100 text-gray-800 border-gray-200" };
      case 'EFFICIENCY_GAIN':
        return { label: "EFFICIENCY GAIN 🏆", className: "bg-green-100 text-green-800 border-green-200" };
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      <Badge variant="outline" className={`font-semibold px-2.5 py-0.5 rounded ${config.className}`}>
        {config.label}
      </Badge>

      {showPriceDriver && (
        <Badge variant="outline" className="bg-amber-50 text-amber-700 border-amber-200 font-medium">
          🏷️ Price-Driven
        </Badge>
      )}

      {showVolumeDriver && (
        <Badge variant="outline" className="bg-sky-50 text-sky-700 border-sky-200 font-medium">
          🛒 Volume-Driven
        </Badge>
      )}

      {benchmarkClassification && (
        <Badge variant="outline" className={`font-medium ${getNormalizationConfig(benchmarkClassification).className}`}>
          {getNormalizationConfig(benchmarkClassification).label}
        </Badge>
      )}
    </div>
  );
};

export default DiagnosticBadges;
