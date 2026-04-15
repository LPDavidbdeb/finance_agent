import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import DiagnosticBadges, { ProcessType, BenchmarkClassification } from "./DiagnosticBadges";
import CausalExplanation from "./CausalExplanation";

interface InsightCardProps {
  categoryName: string;
  processType: ProcessType;
  expertSummary: string;
  volume_pct: number;
  price_pct: number;
  projected_lower_bound?: number | null;
  projected_upper_bound?: number | null;
  benchmark_classification?: BenchmarkClassification | null;
}

const InsightCard: React.FC<InsightCardProps> = ({
  categoryName,
  processType,
  expertSummary,
  volume_pct,
  price_pct,
  projected_lower_bound,
  projected_upper_bound,
  benchmark_classification,
}) => {
  // Format currency
  const formatCurrency = (val: number) => 
    new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 }).format(val);

  return (
    <Card className="w-full max-w-md shadow-sm border-slate-200">
      <CardHeader className="flex flex-col space-y-2 pb-3">
        <div className="flex flex-row items-center justify-between space-y-0">
          <CardTitle className="text-lg font-bold text-slate-900">
            {categoryName}
          </CardTitle>
        </div>
        <DiagnosticBadges 
          type={processType} 
          causalVolumePct={volume_pct}
          causalPricePct={price_pct}
          benchmarkClassification={benchmark_classification}
        />
      </CardHeader>
      
      <CardContent className="space-y-4">
        <div className="text-sm leading-relaxed text-slate-600 bg-blue-50/50 p-3 rounded-md border border-blue-100 italic">
          "{expertSummary}"
        </div>
        
        <CausalExplanation 
          volume_pct={volume_pct} 
          price_pct={price_pct} 
        />

        {/* Confidence Corridor (Epic 4.1) */}
        {projected_lower_bound !== undefined && projected_lower_bound !== null && 
         projected_upper_bound !== undefined && projected_upper_bound !== null && (
          <div className="pt-2 border-t border-slate-100">
            <div className="flex justify-between items-end">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                95% Confidence Corridor
              </span>
            </div>
            <div className="mt-1 bg-slate-100 h-2 rounded-full overflow-hidden relative">
              <div className="absolute inset-0 bg-blue-200 opacity-50" />
            </div>
            <div className="flex justify-between mt-1">
              <span className="text-xs font-medium text-slate-500">
                {formatCurrency(projected_lower_bound)}
              </span>
              <span className="text-xs font-medium text-slate-500">
                {formatCurrency(projected_upper_bound)}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default InsightCard;
