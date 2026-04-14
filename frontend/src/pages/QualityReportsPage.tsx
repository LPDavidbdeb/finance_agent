import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Loader2, PlayCircle, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  ConsistencyReportFinding,
  ConsistencyReportRun,
  ConsistencySeverity,
  ConsistencyUnresolvedTransaction,
  fetchConsistencyFindings,
  fetchConsistencyRuns,
  fetchConsistencyUnresolvedTransactions,
  triggerConsistencyRun,
} from '../api/client';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { useToast } from '../components/ui/use-toast';

const severityBadgeClass: Record<ConsistencySeverity, string> = {
  INFO: 'bg-blue-100 text-blue-800',
  WARNING: 'bg-amber-100 text-amber-800',
  ERROR: 'bg-red-100 text-red-800',
};

export const QualityReportsPage: React.FC = () => {
  const [runs, setRuns] = useState<ConsistencyReportRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [findings, setFindings] = useState<ConsistencyReportFinding[]>([]);
  const [unresolvedTransactions, setUnresolvedTransactions] = useState<ConsistencyUnresolvedTransaction[]>([]);
  const [severityFilter, setSeverityFilter] = useState<'' | ConsistencySeverity>('');
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingFindings, setLoadingFindings] = useState(false);
  const [loadingUnresolvedTransactions, setLoadingUnresolvedTransactions] = useState(false);
  const [triggeringRun, setTriggeringRun] = useState(false);
  const { toast } = useToast();
  const toastRef = useRef(toast);
  const selectedRunIdRef = useRef<number | null>(null);

  useEffect(() => {
    toastRef.current = toast;
  }, [toast]);

  useEffect(() => {
    selectedRunIdRef.current = selectedRunId;
  }, [selectedRunId]);

  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? null,
    [runs, selectedRunId],
  );

  const loadRuns = useCallback(async (preserveSelection = true) => {
    setLoadingRuns(true);
    try {
      const nextRuns = await fetchConsistencyRuns();
      setRuns(nextRuns);

      const currentSelectedRunId = selectedRunIdRef.current;
      if (!preserveSelection || !nextRuns.some((run) => run.id === currentSelectedRunId)) {
        setSelectedRunId(nextRuns.length > 0 ? nextRuns[0].id : null);
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toastRef.current({
        variant: 'destructive',
        title: 'Failed to load runs',
        description: message,
      });
    } finally {
      setLoadingRuns(false);
    }
  }, []);

  const loadFindings = useCallback(async (runId: number, severity?: ConsistencySeverity) => {
    setLoadingFindings(true);
    try {
      const nextFindings = await fetchConsistencyFindings(runId, severity);
      setFindings(nextFindings);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toastRef.current({
        variant: 'destructive',
        title: 'Failed to load findings',
        description: message,
      });
    } finally {
      setLoadingFindings(false);
    }
  }, []);

  const loadUnresolvedTransactions = useCallback(async (runId: number) => {
    setLoadingUnresolvedTransactions(true);
    try {
      const nextTransactions = await fetchConsistencyUnresolvedTransactions(runId);
      setUnresolvedTransactions(nextTransactions);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toastRef.current({
        variant: 'destructive',
        title: 'Failed to load unresolved transactions',
        description: message,
      });
    } finally {
      setLoadingUnresolvedTransactions(false);
    }
  }, []);

  const handleTriggerRun = async () => {
    setTriggeringRun(true);
    try {
      const newRun = await triggerConsistencyRun();
      toastRef.current({
        title: 'Consistency run started',
        description: `Run #${newRun.id} completed with ${newRun.finding_count} findings.`,
      });
      await loadRuns(false);
      setSelectedRunId(newRun.id);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toastRef.current({
        variant: 'destructive',
        title: 'Run failed',
        description: message,
      });
    } finally {
      setTriggeringRun(false);
    }
  };

  useEffect(() => {
    loadRuns(false);
  }, [loadRuns]);

  useEffect(() => {
    if (!selectedRunId) {
      setFindings([]);
      setUnresolvedTransactions([]);
      return;
    }

    loadFindings(selectedRunId, severityFilter || undefined);
  }, [selectedRunId, severityFilter, loadFindings]);

  useEffect(() => {
    if (!selectedRunId) {
      setUnresolvedTransactions([]);
      return;
    }

    loadUnresolvedTransactions(selectedRunId);
  }, [selectedRunId, loadUnresolvedTransactions]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tighter text-slate-900 uppercase">Data Quality</h1>
          <p className="text-slate-500 font-medium">Consistency reports for statement ingestion and ledger integrity.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => loadRuns(true)} disabled={loadingRuns}>
            {loadingRuns ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh
          </Button>
          <Button onClick={handleTriggerRun} disabled={triggeringRun}>
            {triggeringRun ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            Run Consistency Check
          </Button>
        </div>
      </div>

      <Card className="border-blue-200 bg-blue-50/40">
        <CardHeader>
          <CardTitle className="text-lg text-slate-900">What this page is checking</CardTitle>
          <CardDescription className="text-slate-700">
            Each run is a point-in-time health check for your current family data.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-slate-700">
          <p>
            The consistency engine validates that imported statement transactions, routing outcomes, and double-entry
            journal records still align after imports, resets, and reprocessing.
          </p>
          <p>
            <span className="font-semibold text-slate-900">Run Consistency Check</span> creates a new run now. Runs
            created by system maintenance commands (like ledger reset or bulk reprocess) also appear in the history.
          </p>
          <div className="rounded-md border border-blue-100 bg-white p-3">
            <p className="font-semibold text-slate-900">How to read findings</p>
            <p>
              <span className="font-semibold">INFO</span>: expected or informational observations.
            </p>
            <p>
              <span className="font-semibold">WARNING</span>: unusual state that may need review.
            </p>
            <p>
              <span className="font-semibold">ERROR</span>: integrity issue that should be investigated quickly.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Recent Runs</CardTitle>
            <CardDescription>Latest 25 manual consistency report runs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {runs.length === 0 ? (
              <p className="text-sm text-slate-500">No runs yet.</p>
            ) : (
              runs.map((run) => (
                <button
                  key={run.id}
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left transition-colors ${
                    run.id === selectedRunId
                      ? 'border-blue-300 bg-blue-50'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                  onClick={() => setSelectedRunId(run.id)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-slate-900">Run #{run.id}</span>
                    <span className="text-xs text-slate-500">{run.status}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Findings: {run.finding_count} - {new Date(run.started_at).toLocaleString()}
                  </div>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <CardTitle>
                  Findings {selectedRun ? `for Run #${selectedRun.id}` : ''}
                </CardTitle>
                <CardDescription>
                  {selectedRun
                    ? `Status: ${selectedRun.status} | Trigger: ${selectedRun.trigger_source}`
                    : 'Select a run to inspect findings.'}
                </CardDescription>
              </div>
              <select
                value={severityFilter}
                onChange={(event) => setSeverityFilter(event.target.value as '' | ConsistencySeverity)}
                className="h-9 rounded-md border border-slate-300 bg-white px-2 text-sm"
                disabled={!selectedRunId}
              >
                <option value="">All severities</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {loadingFindings ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading findings...
              </div>
            ) : findings.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <AlertCircle className="h-4 w-4" /> No findings for this run/filter.
              </div>
            ) : (
              <div className="space-y-3">
                {findings.map((finding) => (
                  <div key={finding.id} className="rounded-md border border-slate-200 p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${severityBadgeClass[finding.severity]}`}
                      >
                        {finding.severity}
                      </span>
                      <span className="text-xs text-slate-500">{finding.category}</span>
                    </div>
                    <h3 className="mt-2 font-semibold text-slate-900">{finding.title}</h3>
                    <p className="mt-1 text-sm text-slate-600">{finding.message}</p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            Unresolved Transactions {selectedRunId ? `for Run #${selectedRunId}` : ''}
          </CardTitle>
          <CardDescription>
            These are the staged rows that remain unresolved past the fallback cutoff and can be inspected directly.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingUnresolvedTransactions ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading unresolved transactions...
            </div>
          ) : unresolvedTransactions.length === 0 ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <AlertCircle className="h-4 w-4" /> No unresolved transactions were returned for this run.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Description</th>
                    <th className="px-3 py-2">Amount</th>
                    <th className="px-3 py-2">Statement</th>
                    <th className="px-3 py-2">Age</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 bg-white">
                  {unresolvedTransactions.map((tx) => (
                    <tr key={tx.id} className="align-top">
                      <td className="px-3 py-2 whitespace-nowrap text-slate-600">{new Date(tx.bank_date).toLocaleDateString()}</td>
                      <td className="px-3 py-2 text-slate-900">
                        <div className="font-medium">{tx.raw_description}</div>
                        <div className="text-xs text-slate-500">
                          Status: {tx.status}
                          {tx.predicted_account_id ? ` • Predicted account #${tx.predicted_account_id}` : ''}
                        </div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap font-semibold text-amber-700">{tx.amount}</td>
                      <td className="px-3 py-2 whitespace-nowrap text-slate-600">
                        <Link
                          to={`/dashboard/statements/${tx.statement_import_id}?highlight_transaction=${tx.id}`}
                          className="text-blue-600 hover:underline"
                        >
                          #{tx.statement_import_id}
                        </Link>
                        <div className="text-xs text-slate-500">{tx.statement_import_label}</div>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap text-slate-600">{tx.days_past_cutoff} days past cutoff</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

