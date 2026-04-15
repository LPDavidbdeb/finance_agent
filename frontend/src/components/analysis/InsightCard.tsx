import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import DiagnosticBadges, { ProcessType } from "./DiagnosticBadges";
import CausalExplanation from "./CausalExplanation";

interface InsightCardProps {
  categoryName: string;
  processType: ProcessType;
  expertSummary: string;
  volume_pct: number;
  price_pct: number;
}

const InsightCard: React.FC<InsightCardProps> = ({
  categoryName,
  processType,
  expertSummary,
  volume_pct,
  price_pct,
}) => {
  return (
    <Card className="w-full max-w-md shadow-sm border-slate-200">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-lg font-bold text-slate-900">
          {categoryName}
        </CardTitle>
        <DiagnosticBadges type={processType} />
      </CardHeader>
      
      <CardContent className="space-y-4">
        <div className="text-sm leading-relaxed text-slate-600 bg-blue-50/50 p-3 rounded-md border border-blue-100 italic">
          "{expertSummary}"
        </div>
        
        <CausalExplanation 
          volume_pct={volume_pct} 
          price_pct={price_pct} 
        />
      </CardContent>
    </Card>
  );
};

export default InsightCard;
