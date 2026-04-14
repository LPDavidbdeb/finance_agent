import React, { useState, useEffect, useRef } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { triggerAnalyticsEngine, getEngineStatus, EngineStatus } from "@/api/client";
import { 
  RefreshCw, 
  Database, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  Activity
} from "lucide-react";

interface EngineControlPanelProps {
  lastComputedAt: string | Date;
  totalFactsCached: number;
  onRefresh?: () => void;
}

const EngineControlPanel: React.FC<EngineControlPanelProps> = ({
  lastComputedAt: initialLastComputed,
  totalFactsCached: initialTotalFacts,
  onRefresh
}) => {
  const [status, setStatus] = useState<EngineStatus>({
    status: "idle",
    last_computed_at: initialLastComputed.toString(),
    total_facts: initialTotalFacts
  });
  const [showSuccess, setShowSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);

  const isSyncing = status.status === "syncing";

  const stopPolling = () => {
    if (pollingInterval.current) {
      clearInterval(pollingInterval.current);
      pollingInterval.current = null;
    }
  };

  const startPolling = () => {
    stopPolling();
    pollingInterval.current = setInterval(async () => {
      try {
        const currentStatus = await getEngineStatus();
        setStatus(currentStatus);
        
        if (currentStatus.status === "idle") {
          stopPolling();
          setShowSuccess(true);
          if (onRefresh) onRefresh();
          setTimeout(() => setShowSuccess(false), 5000);
        }
      } catch (err: any) {
        console.error("Polling error:", err);
        setError("Lost connection to engine status.");
        stopPolling();
      }
    }, 2000);
  };

  const handleRunEngine = async () => {
    setError(null);
    setShowSuccess(false);
    try {
      await triggerAnalyticsEngine();
      setStatus(prev => ({ ...prev, status: "syncing" }));
      startPolling();
    } catch (err: any) {
      setError(err.message || "Failed to trigger engine.");
    }
  };

  useEffect(() => {
    // Cleanup polling on unmount
    return () => stopPolling();
  }, []);

  const formattedDate = new Date(status.last_computed_at).toLocaleString();

  return (
    <Card className="w-full border-slate-200 shadow-sm overflow-hidden bg-white">
      <CardContent className="p-0">
        <div className="flex flex-col md:flex-row">
          {/* Status Section */}
          <div className="flex-1 p-6 flex items-center space-x-6 border-b md:border-b-0 md:border-r border-slate-100">
            <div className={`p-3 rounded-full ${isSyncing ? 'bg-blue-50 text-blue-600 animate-pulse' : 'bg-green-50 text-green-600'}`}>
              {isSyncing ? <Activity size={24} /> : <CheckCircle2 size={24} />}
            </div>
            
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Pipeline Status</span>
                <Badge variant={isSyncing ? "secondary" : "outline"} className={isSyncing ? "bg-blue-100 text-blue-700 border-none" : "bg-green-50 text-green-700 border-green-200"}>
                  {isSyncing ? "Syncing..." : "Idle / Ready"}
                </Badge>
              </div>
              <h3 className="text-xl font-bold text-slate-900">
                Inference Engine ETL
              </h3>
            </div>
          </div>

          {/* Metrics Section */}
          <div className="flex-1 p-6 grid grid-cols-2 gap-4 bg-slate-50/50">
            <div className="space-y-1">
              <div className="flex items-center text-slate-400 space-x-1.5">
                <Clock size={14} />
                <span className="text-[10px] font-bold uppercase">Last Computation</span>
              </div>
              <p className="text-sm font-medium text-slate-700">{formattedDate}</p>
            </div>
            
            <div className="space-y-1">
              <div className="flex items-center text-slate-400 space-x-1.5">
                <Database size={14} />
                <span className="text-[10px] font-bold uppercase">Facts Cached</span>
              </div>
              <p className="text-sm font-medium text-slate-700">{status.total_facts.toLocaleString()}</p>
            </div>
          </div>

          {/* Action Section */}
          <div className="p-6 flex flex-col justify-center bg-slate-50 border-t md:border-t-0 md:border-l border-slate-100 min-w-[240px]">
            <Button 
              onClick={handleRunEngine} 
              disabled={isSyncing}
              className={`w-full font-bold shadow-md transition-all ${isSyncing ? 'bg-slate-400' : 'bg-blue-600 hover:bg-blue-700'}`}
            >
              {isSyncing ? (
                <RefreshCw size={18} className="mr-2 animate-spin" />
              ) : (
                <RefreshCw size={18} className="mr-2" />
              )}
              {isSyncing ? "Processing..." : "Run Analytics Engine"}
            </Button>
            
            {showSuccess && (
              <div className="mt-3 flex items-center justify-center text-green-600 text-xs font-bold animate-in fade-in slide-in-from-top-1">
                <CheckCircle2 size={12} className="mr-1" />
                Rebuild successful
              </div>
            )}

            {error && (
              <div className="mt-3 flex items-center justify-center text-red-600 text-xs font-bold">
                <AlertCircle size={12} className="mr-1" />
                {error}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default EngineControlPanel;
