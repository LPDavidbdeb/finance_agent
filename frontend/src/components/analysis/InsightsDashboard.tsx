import React, { useState, useMemo } from "react";
import { Button } from "@/components/ui/button";
import InsightCard from "./InsightCard";
import { ProcessType } from "./DiagnosticBadges";
import { SlidersHorizontal, ArrowDownWideZap, Percent } from "lucide-react";

export interface InsightData {
  id: string;
  categoryName: string;
  insight_score: number;
  materiality_pct: number;
  processType: ProcessType;
  expertSummary: string;
  causal_volume_pct: number | null;
  causal_price_pct: number | null;
}

interface InsightsDashboardProps {
  data: InsightData[];
}

type SortMethod = "SEVERITY" | "MATERIALITY";

const InsightsDashboard: React.FC<InsightsDashboardProps> = ({ data }) => {
  const [sortMethod, setSortMethod] = useState<SortMethod>("SEVERITY");

  const sortedData = useMemo(() => {
    const dataCopy = [...data];
    if (sortMethod === "SEVERITY") {
      return dataCopy.sort((a, b) => b.insight_score - a.insight_score);
    } else {
      return dataCopy.sort((a, b) => b.materiality_pct - a.materiality_pct);
    }
  }, [data, sortMethod]);

  return (
    <div className="w-full space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight">
            Top Financial Insights
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            Statistically significant trends identified across your household accounts.
          </p>
        </div>

        <div className="flex items-center bg-slate-50 p-1 rounded-lg border border-slate-200 self-start sm:self-auto">
          <Button
            variant={sortMethod === "SEVERITY" ? "default" : "ghost"}
            size="sm"
            onClick={() => setSortMethod("SEVERITY")}
            className="flex items-center gap-2 h-8 px-3 text-xs"
          >
            <ArrowDownWideZap size={14} />
            Severity
          </Button>
          <Button
            variant={sortMethod === "MATERIALITY" ? "default" : "ghost"}
            size="sm"
            onClick={() => setSortMethod("MATERIALITY")}
            className="flex items-center gap-2 h-8 px-3 text-xs"
          >
            <Percent size={14} />
            Materiality
          </Button>
        </div>
      </div>

      {/* Results Grid */}
      {sortedData.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sortedData.map((insight) => (
            <div key={insight.id} className="flex justify-center md:justify-start">
              <InsightCard
                categoryName={insight.categoryName}
                processType={insight.processType}
                expertSummary={insight.expertSummary}
                volume_pct={insight.causal_volume_pct ?? 0}
                price_pct={insight.causal_price_pct ?? 0}
              />
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-20 text-slate-400 bg-slate-50/50 rounded-xl border border-dashed border-slate-200">
          <SlidersHorizontal size={40} className="mb-4 opacity-20" />
          <p className="text-sm font-medium">No significant insights detected for this window.</p>
        </div>
      )}
    </div>
  );
};

export default InsightsDashboard;
