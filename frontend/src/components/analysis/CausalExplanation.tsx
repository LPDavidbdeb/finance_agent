import React from "react";
import { ArrowUp, ArrowDown } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface CausalExplanationProps {
  volume_pct: number;
  price_pct: number;
}

const CausalExplanation: React.FC<CausalExplanationProps> = ({ volume_pct, price_pct }) => {
  const isVolumeDriven = Math.abs(volume_pct) > Math.abs(price_pct);
  const primaryDriver = isVolumeDriven ? "Volume Driven" : "Price Driven";
  
  const renderFactor = (label: string, value: number) => {
    const isPositive = value >= 0;
    const Icon = isPositive ? ArrowUp : ArrowDown;
    const colorClass = isPositive ? "text-red-600" : "text-green-600";
    
    return (
      <div className="flex items-center space-x-1">
        <span className="text-xs text-slate-500 uppercase font-medium">{label}:</span>
        <div className={`flex items-center text-sm font-bold ${colorClass}`}>
          <Icon size={14} className="mr-0.5" />
          {Math.abs(value).toFixed(1)}%
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col space-y-2 p-3 bg-slate-50 rounded-lg border border-slate-100">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Primary Driver</span>
        <Badge variant="secondary" className="text-[10px] uppercase font-bold px-2 py-0">
          {primaryDriver}
        </Badge>
      </div>
      
      <div className="flex space-x-6">
        {renderFactor("Volume", volume_pct)}
        {renderFactor("Price", price_pct)}
      </div>
    </div>
  );
};

export default CausalExplanation;
