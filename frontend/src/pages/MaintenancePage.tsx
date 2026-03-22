import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { runMaintenanceCommand } from '../api/client';
import { Loader2, Terminal, ShieldAlert, Play, CheckCircle2, AlertCircle } from 'lucide-react';
import { useToast } from '../components/ui/use-toast';

export const MaintenancePage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<string>('');
  const [lastStatus, setLastStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const { toast } = useToast();

  const handleRunCommand = async (command: string, args: string[] = [], label: string) => {
    if (command === 'ledger_reset' && args.includes('--confirm')) {
      if (!window.confirm("WARNING: This is a destructive operation. It will wipe all Journal Entries and Transaction Lines. Are you absolutely sure?")) {
        return;
      }
    }

    setLoading(true);
    setLastStatus('idle');
    setLogs(prev => prev + `\n> Executing: ${label}...\n`);
    
    try {
      const result = await runMaintenanceCommand(command, args);
      setLogs(prev => prev + result.output + (result.error ? `\nERROR:\n${result.error}` : ''));
      
      if (result.success) {
        setLastStatus('success');
        toast({ title: "Command Completed", description: `${label} finished successfully.` });
      } else {
        setLastStatus('error');
        toast({ variant: "destructive", title: "Command Failed", description: result.error || "Check logs for details." });
      }
    } catch (err: any) {
      setLastStatus('error');
      setLogs(prev => prev + `\nSYSTEM ERROR: ${err.message}\n`);
      toast({ variant: "destructive", title: "Network Error", description: err.message });
    } finally {
      setLoading(false);
    }
  };

  const clearLogs = () => setLogs('');

  return (
    <div className="space-y-8 max-w-5xl mx-auto w-full pb-20">
      <div>
        <h1 className="text-3xl font-black tracking-tighter text-slate-900 uppercase">System Maintenance</h1>
        <p className="text-slate-500 font-medium">Restricted zone for ledger integrity and data repair.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Control Panel */}
        <div className="space-y-6">
          <Card className="border-amber-100 bg-amber-50/20 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2 text-amber-800">
                <ShieldAlert size={16} /> Ledger Reset
              </CardTitle>
              <CardDescription className="text-xs">Safe-mode first, then execution.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                variant="outline" 
                className="w-full justify-start gap-2 border-amber-200 text-amber-900 hover:bg-amber-100" 
                onClick={() => handleRunCommand('ledger_reset', ['--dry-run'], 'Ledger Reset (Dry Run)')}
                disabled={loading}
              >
                <Terminal size={14} /> Dry Run (Preview)
              </Button>
              <Button 
                variant="destructive" 
                className="w-full justify-start gap-2" 
                onClick={() => handleRunCommand('ledger_reset', ['--confirm'], 'Ledger Reset (Destructive)')}
                disabled={loading}
              >
                <AlertCircle size={14} /> Reset Ledger (Confirm)
              </Button>
            </CardContent>
          </Card>

          <Card className="shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2 text-blue-800">
                <Play size={16} /> Data Rebuild
              </CardTitle>
              <CardDescription className="text-xs">Re-extract and categorize everything.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                variant="secondary" 
                className="w-full justify-start gap-2" 
                onClick={() => handleRunCommand('reprocess_all_statements', [], 'Full Reprocess')}
                disabled={loading}
              >
                <Loader2 size={14} className={loading ? 'animate-spin' : ''} /> Reprocess Statements
              </Button>
              <Button 
                variant="outline" 
                className="w-full justify-start gap-2" 
                onClick={() => handleRunCommand('verify_ledger_integrity', [], 'Integrity Audit')}
                disabled={loading}
              >
                <CheckCircle2 size={14} /> Verify Ledger Integrity
              </Button>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Terminal size={16} /> Utilities
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Button 
                variant="ghost" 
                className="w-full justify-start gap-2 text-slate-600" 
                onClick={() => handleRunCommand('fix_inverted_transactions', [], 'Fix Inverted Transactions')}
                disabled={loading}
              >
                Fix Sign Inversions
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* Output Console */}
        <Card className="lg:col-span-2 bg-slate-950 text-emerald-400 border-none shadow-2xl overflow-hidden min-h-[500px] flex flex-col">
          <CardHeader className="border-b border-slate-800 flex flex-row items-center justify-between py-3">
            <CardTitle className="text-xs font-mono flex items-center gap-2 text-slate-400">
              <Terminal size={12} /> execution_output.log
            </CardTitle>
            <Button variant="ghost" size="sm" onClick={clearLogs} className="text-[10px] text-slate-500 hover:text-white h-6">
              Clear Console
            </Button>
          </CardHeader>
          <CardContent className="flex-1 p-0 relative">
            {loading && (
              <div className="absolute inset-0 bg-slate-950/50 backdrop-blur-[1px] flex items-center justify-center z-10">
                <div className="flex items-center gap-3 bg-slate-900 border border-slate-800 px-4 py-2 rounded-full shadow-xl">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                  <span className="text-xs font-bold text-slate-300 animate-pulse">PROCESS RUNNING...</span>
                </div>
              </div>
            )}
            <textarea
              readOnly
              className="w-full h-full bg-transparent p-6 font-mono text-xs leading-relaxed resize-none focus:outline-none scrollbar-thin scrollbar-thumb-slate-800"
              value={logs || "System idle. Ready for command input..."}
              placeholder="Waiting for execution output..."
            />
          </CardContent>
          <div className="px-6 py-3 border-t border-slate-900 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <div className={`w-2 h-2 rounded-full ${loading ? 'bg-blue-500 animate-pulse' : 'bg-slate-700'}`} />
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">Status: {loading ? 'Running' : 'Ready'}</span>
              </div>
              {lastStatus !== 'idle' && (
                <div className="flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${lastStatus === 'success' ? 'bg-emerald-500' : 'bg-red-500'}`} />
                  <span className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">Last: {lastStatus.toUpperCase()}</span>
                </div>
              )}
            </div>
            <span className="text-[10px] font-mono text-slate-600 uppercase">System Root Access Required</span>
          </div>
        </Card>
      </div>
    </div>
  );
};
