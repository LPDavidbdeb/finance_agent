import React, { useState, useEffect } from "react";
import { fetchTopInsights, getEngineStatus, EngineStatus } from "@/api/client";
import InsightsDashboard, { InsightData } from "@/components/analysis/InsightsDashboard";
import EngineControlPanel from "@/components/analysis/EngineControlPanel";
import { AlertCircle, Loader2 } from "lucide-react";

const AnalysisPage: React.FC = () => {
  const [insights, setInsights] = useState<InsightData[]>([]);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadInsights = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const [insightsData, statusData] = await Promise.all([
        fetchTopInsights(),
        getEngineStatus()
      ]);
      setInsights(insightsData);
      setEngineStatus(statusData);
    } catch (err: any) {
      console.error("Error loading insights:", err);
      setError(err.message || "An unexpected error occurred while loading insights.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadInsights();
  }, []);

  return (
    <div className="container mx-auto py-8 px-4 max-w-7xl space-y-8">
      {/* Page Header Area */}
      <div className="mb-2">
        <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Financial Intelligence</h1>
        <p className="text-slate-500 mt-2">
          Advanced inference engine analysis of your household spending patterns and structural shifts.
        </p>
      </div>

      {engineStatus && (
        <EngineControlPanel 
          lastComputedAt={engineStatus.last_computed_at}
          totalFactsCached={engineStatus.total_facts}
          onRefresh={loadInsights}
        />
      )}

      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-32 space-y-4">
          <Loader2 className="h-12 w-12 text-blue-500 animate-spin" />
          <p className="text-slate-500 font-medium animate-pulse">Running inference engine...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 flex items-start space-x-4 max-w-2xl mx-auto mt-12">
          <AlertCircle className="h-6 w-6 text-red-600 mt-0.5 flex-shrink-0" />
          <div>
            <h3 className="text-red-800 font-bold text-lg">Inference Engine Error</h3>
            <p className="text-red-700 mt-1">{error}</p>
            <button 
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-red-600 text-white rounded-md text-sm font-semibold hover:bg-red-700 transition-colors"
            >
              Retry Analysis
            </button>
          </div>
        </div>
      ) : (
        <InsightsDashboard data={insights} />
      )}
    </div>
  );
};

export default AnalysisPage;
