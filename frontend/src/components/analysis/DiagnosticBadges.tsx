import React from "react";
import { Badge } from "@/components/ui/badge";

export type ProcessType = "DETERMINISTIC" | "STOCHASTIC" | "EPISODIC";

interface DiagnosticBadgesProps {
  type: ProcessType;
}

const DiagnosticBadges: React.FC<DiagnosticBadgesProps> = ({ type }) => {
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

  return (
    <Badge variant="outline" className={`font-semibold px-2.5 py-0.5 rounded ${config.className}`}>
      {config.label}
    </Badge>
  );
};

export default DiagnosticBadges;
