import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import {
  fetchMerchantDetail,
  updateMerchant,
  mergeMerchants,
  fetchMerchants,
  fetchMerchantStats,
  deleteRule,
  fetchRuleStats,
  fetchUnmappedStrings,
  fetchSchedules,
  type AnnuityScheduleListOut,
} from '../api/client';
import { AccountTree } from '../components/AccountTree';
import { CreateRuleModal } from '../components/CreateRuleModal';
import { useToast } from '../components/ui/use-toast';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
  Loader2, Edit2, Check, X, ArrowLeft, Merge, Trash2, Tag,
  History, DollarSign, TrendingUp, Calendar, ChevronRight, Search, Wand2, Link2, Link2Off
} from 'lucide-react';
import { formatRoutingRuleSuccess } from '../utils/transactionVocabulary';

interface MappingRule {
  id: number;
  search_text: string;
  institution_name: string;
  min_amount?: number;
  max_amount?: number;
}

interface MerchantDetail {
  id: number;
  name: string;
  is_unique_provider: boolean;
  default_account_id?: number;
  default_account_name?: string;
  linked_schedule_id?: number | null;
  linked_schedule_name?: string | null;
  mapping_rules: MappingRule[];
}

interface MerchantSummary {
  id: number;
  name: string;
}

export const MerchantDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [merchant, setMerchant] = useState<MerchantDetail | null>(null);
  const [allMerchants, setAllMerchants] = useState<MerchantSummary[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Rule deletion state
  const [deletingRuleId, setDeletingRuleId] = useState<number | null>(null);

  // Rule stats state
  const [expandedRuleId, setExpandedRuleId] = useState<number | null>(null);
  const [ruleStats, setRuleStats] = useState<Record<number, { year: number; total: number; count: number }[] | null>>({});
  const [ruleStatsError, setRuleStatsError] = useState<Record<number, string>>({});
  const [loadingRuleStats, setLoadingRuleStats] = useState<number | null>(null);

  // Rename state
  const [isRenaming, setIsRenaming] = useState(false);
  const [newName, setNewName] = useState('');
  const [renamingLoading, setRenamingLoading] = useState(false);

  // Category change state
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [pendingAccountId, setPendingAccountId] = useState<number | null>(null);
  const [pendingAccountName, setPendingAccountName] = useState<string>('');
  const [isConfirmHistoryOpen, setIsConfirmHistoryOpen] = useState(false);
  const [updateHistory, setUpdateHistory] = useState(true);
  const [categoryLoading, setCategoryLoading] = useState(false);

  // Merge state
  const [mergeSearch, setMergeSearch] = useState('');
  const [selectedSourceIds, setSelectedSourceIds] = useState<number[]>([]);
  const [mergeLoading, setMergeLoading] = useState(false);

  // Orphaned Transactions state
  const [orphanedSearch, setOrphanedSearch] = useState('');
  const [orphanedResults, setOrphanedResults] = useState<any[]>([]);
  const [orphanedLoading, setOrphanedLoading] = useState(false);
  const [ruleModalOpen, setRuleModalOpen] = useState(false);
  const [selectedOrphan, setSelectedOrphan] = useState<any>(null);

  // Loan Schedule association state
  const [loanSchedules, setLoanSchedules] = useState<AnnuityScheduleListOut[]>([]);
  const [selectedScheduleId, setSelectedScheduleId] = useState<string>('');
  const [scheduleLoading, setScheduleLoading] = useState(false);

  useEffect(() => {
    if (id) {
      loadData(Number(id));
    }
  }, [id]);

  const loadData = async (merchantId: number) => {
    try {
      setLoading(true);
      const [detail, others, merchantStats, schedules] = await Promise.all([
        fetchMerchantDetail(merchantId),
        fetchMerchants(),
        fetchMerchantStats(merchantId),
        fetchSchedules(),
      ]);
      setMerchant(detail);
      setNewName(detail.name);
      setAllMerchants(others.filter((m: any) => m.id !== merchantId));
      setStats(merchantStats);
      setLoanSchedules(schedules.filter(s => s.schedule_type === 'LOAN_AMORTIZATION'));
    } catch (err: any) {
      setError(err.message || "Failed to load merchant details.");
    } finally {
      setLoading(false);
    }
  };

  const handleRename = async () => {
    if (!merchant || !newName.trim()) return;
    setRenamingLoading(true);
    try {
      await updateMerchant(merchant.id, { name: newName });
      toast({ title: "Merchant renamed", description: `Banner updated to ${newName.toUpperCase()}.` });
      setIsRenaming(false);
      loadData(merchant.id);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Rename failed", description: err.message });
    } finally {
      setRenamingLoading(false);
    }
  };

  const handleAccountSelect = (account: any) => {
    setPendingAccountId(account.id);
    setPendingAccountName(account.name);
    setIsAccountModalOpen(false);
    setIsConfirmHistoryOpen(true);
  };

  const handleCategoryUpdate = async () => {
    if (!merchant || !pendingAccountId) return;
    setCategoryLoading(true);
    try {
      await updateMerchant(merchant.id, { 
        default_account_id: pendingAccountId,
        update_history: updateHistory
      });
      toast({ 
        title: "Category updated", 
        description: `Merchant assigned to ${pendingAccountName}.${updateHistory ? ' Historical transactions updated.' : ''}` 
      });
      setIsConfirmHistoryOpen(false);
      loadData(merchant.id);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Update failed", description: err.message });
    } finally {
      setCategoryLoading(false);
    }
  };

  const handleToggleRuleStats = async (ruleId: number) => {
    if (expandedRuleId === ruleId) {
      setExpandedRuleId(null);
      return;
    }
    setExpandedRuleId(ruleId);
    // Only fetch if not already loaded (null = never fetched, undefined key = never fetched)
    if (ruleStats[ruleId] === undefined) {
      setLoadingRuleStats(ruleId);
      try {
        const data = await fetchRuleStats(ruleId);
        setRuleStats(prev => ({ ...prev, [ruleId]: data.yearly }));
      } catch (err: any) {
        console.error(`Failed to load stats for rule ${ruleId}:`, err);
        setRuleStatsError(prev => ({ ...prev, [ruleId]: err.message || 'Failed to load' }));
        setRuleStats(prev => ({ ...prev, [ruleId]: null }));
      } finally {
        setLoadingRuleStats(null);
      }
    }
  };

  const handleDeleteRule = async (ruleId: number) => {
    if (!window.confirm('Delete this routing rule? All transactions matched by it will be re-routed to Uncategorized Expenses.')) return;
    setDeletingRuleId(ruleId);
    try {
      await deleteRule(ruleId);
      toast({ title: "Routing rule deleted", description: "Matched transactions have been moved to Uncategorized Expenses." });
      if (merchant) loadData(merchant.id);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Delete failed", description: err.message });
    } finally {
      setDeletingRuleId(null);
    }
  };

  const handleMerge = async () => {
    if (!merchant || selectedSourceIds.length === 0) return;
    if (!window.confirm(`Are you sure you want to merge ${selectedSourceIds.length} merchants into ${merchant.name}? This cannot be undone.`)) return;

    setMergeLoading(true);
    try {
      const result = await mergeMerchants(merchant.id, selectedSourceIds);
      toast({ 
        title: "Merge successful", 
        description: `Successfully merged ${result.merged_count} merchants.` 
      });
      setSelectedSourceIds([]);
      setMergeSearch('');
      loadData(merchant.id);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Merge failed", description: err.message });
    } finally {
      setMergeLoading(false);
    }
  };

  const toggleSourceSelection = (sourceId: number) => {
    setSelectedSourceIds(prev => 
      prev.includes(sourceId) ? prev.filter(id => id !== sourceId) : [...prev, sourceId]
    );
  };

  const handleLinkSchedule = async () => {
    if (!merchant || !selectedScheduleId) return;
    setScheduleLoading(true);
    try {
      await updateMerchant(merchant.id, { linked_schedule_id: Number(selectedScheduleId) });
      toast({ title: "Schedule linked", description: "Payments from this merchant will now be split into principal + interest." });
      setSelectedScheduleId('');
      loadData(merchant.id);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Link failed", description: err.message });
    } finally {
      setScheduleLoading(false);
    }
  };

  const handleUnlinkSchedule = async () => {
    if (!merchant) return;
    setScheduleLoading(true);
    try {
      await updateMerchant(merchant.id, { clear_linked_schedule: true });
      toast({ title: "Schedule unlinked", description: "Payments will no longer be split automatically." });
      loadData(merchant.id);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Unlink failed", description: err.message });
    } finally {
      setScheduleLoading(false);
    }
  };

  const handleOrphanedSearch = async () => {
    if (orphanedSearch.length < 2) return;
    setOrphanedLoading(true);
    try {
      const data = await fetchUnmappedStrings(orphanedSearch);
      setOrphanedResults(data);
    } catch (err: any) {
      toast({ variant: "destructive", title: "Search failed", description: err.message });
    } finally {
      setOrphanedLoading(false);
    }
  };

  const filteredMerchants = allMerchants.filter(m => 
    m.name.toLowerCase().includes(mergeSearch.toLowerCase()) && 
    !selectedSourceIds.includes(m.id)
  ).slice(0, 5);

  const renderMonthlyBarChart = () => {
    if (!stats?.daily_activity || stats.daily_activity.length === 0) {
      return (
        <div className="flex items-center justify-center h-48 text-sm text-slate-400 italic">
          No activity found.
        </div>
      );
    }

    // Aggregate daily activity into months
    const monthlyData: Record<string, number> = {};
    let minDateStr = '';
    let maxDateStr = '';

    stats.daily_activity.forEach((a: any) => {
      // a.date is YYYY-MM-DD
      const monthKey = a.date.substring(0, 7); // YYYY-MM
      monthlyData[monthKey] = (monthlyData[monthKey] || 0) + a.amount;
      if (!minDateStr || a.date < minDateStr) minDateStr = a.date;
      if (!maxDateStr || a.date > maxDateStr) maxDateStr = a.date;
    });

    // Create an array from the earliest month to the latest month for a continuous timeline
    const chartData = [];
    if (minDateStr) {
      const minDate = new Date(minDateStr + 'T00:00:00Z');
      const maxDate = new Date(maxDateStr + 'T00:00:00Z');
      const today = new Date();
      const endDate = maxDate > today ? maxDate : today;

      let currentDate = new Date(Date.UTC(minDate.getUTCFullYear(), minDate.getUTCMonth(), 1));
      const endMonthDate = new Date(Date.UTC(endDate.getUTCFullYear(), endDate.getUTCMonth(), 1));
      
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

      while (currentDate <= endMonthDate) {
        const year = currentDate.getUTCFullYear();
        const month = String(currentDate.getUTCMonth() + 1).padStart(2, '0');
        const monthKey = `${year}-${month}`;
        
        chartData.push({
          name: `${monthNames[currentDate.getUTCMonth()]} '${String(year).slice(2)}`,
          amount: monthlyData[monthKey] || 0,
        });
        
        currentDate.setUTCMonth(currentDate.getUTCMonth() + 1);
      }
    }

    return (
      <div className="h-64 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
            <XAxis dataKey="name" tick={{fill: '#64748b', fontSize: 12}} tickLine={false} axisLine={false} />
            <YAxis 
              tickFormatter={(val) => `$${val}`} 
              tick={{fill: '#64748b', fontSize: 12}} 
              tickLine={false} 
              axisLine={false} 
            />
            <Tooltip 
              formatter={(value: any) => [`$${(Number(value) || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`, 'Total']}
              cursor={{fill: '#f1f5f9'}}
              contentStyle={{ borderRadius: '8px', border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
            />
            <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} maxBarSize={50} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  };

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  if (error || !merchant) return <div className="p-20 text-center text-red-500">{error || "Merchant not found"}</div>;

  return (
    <div className="space-y-8 max-w-5xl mx-auto w-full pb-20">
      <Button variant="ghost" onClick={() => navigate('/dashboard/merchants')} className="gap-2">
        <ArrowLeft className="h-4 w-4" /> Back to Merchants
      </Button>

      {/* Header / Rename */}
      <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
          <div className="flex-1 w-full">
            {isRenaming ? (
              <div className="flex items-center gap-2 w-full max-w-lg">
                <Input 
                  value={newName} 
                  onChange={(e) => setNewName(e.target.value)} 
                  className="text-2xl font-bold h-12 uppercase" 
                  autoFocus
                />
                <Button onClick={handleRename} disabled={renamingLoading} size="icon" className="shrink-0">
                  {renamingLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                </Button>
                <Button variant="ghost" onClick={() => { setIsRenaming(false); setNewName(merchant.name); }} size="icon" className="shrink-0">
                  <X className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <div className="flex items-center gap-3 group">
                <h1 className="text-4xl font-bold tracking-tight text-slate-900 uppercase">
                  {merchant.name}
                </h1>
                <Button variant="ghost" size="icon" onClick={() => setIsRenaming(true)} className="opacity-0 group-hover:opacity-100 transition-opacity">
                  <Edit2 className="h-4 w-4 text-slate-400" />
                </Button>
              </div>
            )}
            
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <Badge variant="outline" className="bg-slate-50 py-1 px-3 text-slate-600 border-slate-200 font-normal">
                {merchant.is_unique_provider ? 'Unique Provider' : 'Multi-route Merchant'}
              </Badge>
              
              <div className="flex items-center gap-2 bg-blue-50 pl-3 pr-1 py-1 rounded-full border border-blue-100">
                <Tag className="h-3.5 w-3.5 text-blue-600" />
                <span className="text-sm font-semibold text-blue-800">
                  {merchant.default_account_name || 'Unrouted'}
                </span>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="h-6 w-6 p-0 hover:bg-blue-100 text-blue-600"
                  onClick={() => setIsAccountModalOpen(true)}
                >
                  <Edit2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="bg-white shadow-sm border-slate-200">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider flex items-center gap-2 text-slate-500">
                <DollarSign className="h-3 w-3" /> Total Volume
              </CardDescription>
              <CardTitle className="text-2xl font-black text-slate-900">
                ${stats.total_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-white shadow-sm border-slate-200">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider flex items-center gap-2 text-slate-500">
                <History className="h-3 w-3" /> Historical Avg
              </CardDescription>
              <CardTitle className="text-2xl font-black text-slate-900">
                ${stats.historical_monthly_avg.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                <span className="text-[10px] text-slate-400 ml-1">/mo</span>
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-white shadow-sm border-slate-200">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider flex items-center gap-2 text-slate-500">
                <TrendingUp className="h-3 w-3" /> Current Year Avg
              </CardDescription>
              <CardTitle className="text-2xl font-black text-blue-600">
                ${stats.current_year_monthly_avg.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                <span className="text-[10px] text-slate-400 ml-1">/mo</span>
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      {/* Monthly Bar Chart */}
      <Card className="shadow-sm">
        <CardHeader className="border-b border-slate-50 bg-slate-50/30">
          <CardTitle className="text-lg flex items-center gap-2">
            <Calendar className="h-5 w-5 text-blue-600" />
            Monthly Transaction History
          </CardTitle>
          <CardDescription>Aggregate volume of all historical transactions.</CardDescription>
        </CardHeader>
        <CardContent className="p-6">
          {renderMonthlyBarChart()}
        </CardContent>
      </Card>

      {/* Loan Schedule Association */}
      <Card className="shadow-sm border-indigo-100 bg-indigo-50/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-indigo-900">
            <Link2 className="h-5 w-5" />
            Loan Schedule
          </CardTitle>
          <CardDescription>
            Link an amortization schedule so payments are automatically split into principal + interest instead of a single expense.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {merchant.linked_schedule_id ? (
            <div className="flex items-center justify-between bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3">
              <div>
                <p className="text-sm font-semibold text-indigo-900">{merchant.linked_schedule_name}</p>
                <p className="text-xs text-indigo-600 mt-0.5">Payments will be split into principal + interest on approval.</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleUnlinkSchedule}
                disabled={scheduleLoading}
                className="border-indigo-200 text-indigo-700 hover:bg-indigo-100 gap-1.5 shrink-0"
              >
                {scheduleLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Link2Off className="h-3.5 w-3.5" />}
                Unlink
              </Button>
            </div>
          ) : (
            <div className="flex gap-2">
              <select
                className="flex-1 border border-slate-200 rounded-md px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                value={selectedScheduleId}
                onChange={(e) => setSelectedScheduleId(e.target.value)}
              >
                <option value="">Select a loan schedule…</option>
                {loanSchedules.map(s => (
                  <option key={s.id} value={s.id}>
                    {s.name} — ${s.computed_payment.toLocaleString(undefined, { minimumFractionDigits: 2 })}/{s.payment_frequency.toLowerCase()}
                  </option>
                ))}
              </select>
              <Button
                onClick={handleLinkSchedule}
                disabled={!selectedScheduleId || scheduleLoading}
                className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5 shrink-0"
              >
                {scheduleLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Link2 className="h-4 w-4" />}
                Link
              </Button>
            </div>
          )}
          {loanSchedules.length === 0 && !merchant.linked_schedule_id && (
            <p className="mt-3 text-xs text-slate-400 italic">No committed loan schedules found. Create one via <strong>Simulate → Commit</strong>.</p>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Rules List */}
        <Card className="lg:col-span-2 shadow-sm">
          <CardHeader>
            <CardTitle>Mapping Rules</CardTitle>
            <CardDescription>Bank strings that automatically map to this merchant.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-y border-slate-100">
                <tr>
                  <th className="px-6 py-3 text-left font-medium text-slate-500 uppercase tracking-wider">Search Pattern</th>
                  <th className="px-6 py-3 text-left font-medium text-slate-500 uppercase tracking-wider">Institution</th>
                  <th className="px-6 py-3 text-left font-medium text-slate-500 uppercase tracking-wider">Amount Range</th>
                  <th className="px-6 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {merchant.mapping_rules.length === 0 && (
                  <tr><td colSpan={4} className="px-6 py-10 text-center text-slate-400 italic">No rules defined.</td></tr>
                )}
                {merchant.mapping_rules.map(rule => (
                  <React.Fragment key={rule.id}>
                    <tr
                      className="hover:bg-blue-50/30 cursor-pointer group transition-colors"
                      onClick={() => handleToggleRuleStats(rule.id)}
                    >
                      <td className="px-6 py-4 font-mono text-xs text-slate-700 flex items-center gap-2">
                        <ChevronRight className={`h-3 w-3 text-slate-400 transition-transform ${expandedRuleId === rule.id ? 'rotate-90' : ''}`} />
                        {rule.search_text}
                      </td>
                      <td className="px-6 py-4 text-slate-600">{rule.institution_name}</td>
                      <td className="px-6 py-4 font-mono text-xs text-slate-500">
                        {rule.min_amount != null || rule.max_amount != null ? (
                          <span>
                            {rule.min_amount != null ? `$${rule.min_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
                            {' → '}
                            {rule.max_amount != null ? `$${rule.max_amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}` : '—'}
                          </span>
                        ) : (
                          <span className="text-slate-300 italic">any</span>
                        )}
                      </td>
                      <td className="px-4 py-4 text-right">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteRule(rule.id); }}
                          disabled={deletingRuleId === rule.id}
                          className="p-1.5 rounded hover:bg-red-50 text-slate-300 hover:text-red-500 transition-colors disabled:opacity-50"
                          title="Delete rule"
                        >
                          {deletingRuleId === rule.id
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <Trash2 className="h-3.5 w-3.5" />}
                        </button>
                      </td>
                    </tr>
                    {expandedRuleId === rule.id && (
                      <tr>
                        <td colSpan={4} className="px-0 py-0 bg-slate-50 border-b border-blue-100">
                          {loadingRuleStats === rule.id ? (
                            <div className="flex items-center gap-2 px-10 py-4 text-slate-400 text-xs">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading...
                            </div>
                          ) : ruleStats[rule.id] === null ? (
                            <p className="px-10 py-4 text-xs text-red-400 italic">
                              {ruleStatsError[rule.id] || 'Failed to load stats.'}
                            </p>
                          ) : ruleStats[rule.id] === undefined ? (
                            <div className="flex items-center gap-2 px-10 py-4 text-slate-400 text-xs">
                              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading...
                            </div>
                          ) : (ruleStats[rule.id]!).length === 0 ? (
                            <p className="px-10 py-4 text-xs text-slate-400 italic">No reconciled transactions found for this rule.</p>
                          ) : (
                            <table className="w-full text-xs">
                              <thead>
                                <tr className="text-slate-400 border-b border-slate-200">
                                  <th className="px-10 py-2 text-left font-bold uppercase tracking-wider">Year</th>
                                  <th className="px-4 py-2 text-center font-bold uppercase tracking-wider">Transactions</th>
                                  <th className="px-6 py-2 text-right font-bold uppercase tracking-wider">Total</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {(ruleStats[rule.id]!).slice().sort((a, b) => b.year - a.year).map(row => (
                                  <tr key={row.year} className="hover:bg-white transition-colors">
                                    <td className="px-10 py-2.5 font-black text-slate-700">{row.year}</td>
                                    <td className="px-4 py-2.5 text-center text-slate-500">{row.count}</td>
                                    <td className="px-6 py-2.5 text-right font-mono font-black text-slate-900">
                                      ${row.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          )}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>

        {/* Orphaned Transactions Search */}
        <Card className="lg:col-span-2 shadow-sm border-purple-100 bg-purple-50/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-purple-900">
              <Search className="h-5 w-5" />
              Orphaned Transactions
            </CardTitle>
            <CardDescription>
              Find unmapped bank strings and pull them into {merchant.name}.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input 
                  placeholder="Search unmapped descriptions (e.g. 'tax')..." 
                  value={orphanedSearch}
                  onChange={(e) => setOrphanedSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleOrphanedSearch()}
                  className="bg-white border-purple-200 focus:ring-purple-500 pl-10"
                />
                <Search className="absolute left-3 top-3 h-4 w-4 text-purple-400" />
              </div>
              <Button 
                onClick={handleOrphanedSearch} 
                disabled={orphanedLoading || orphanedSearch.length < 2}
                className="bg-purple-600 hover:bg-purple-700 text-white"
              >
                {orphanedLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
              </Button>
            </div>

            {orphanedResults.length > 0 && (
              <div className="border rounded-lg overflow-hidden bg-white">
                <table className="w-full text-sm">
                  <thead className="bg-purple-50/50 border-b border-purple-100">
                    <tr className="text-[10px] font-black uppercase text-purple-700">
                      <th className="px-4 py-2 text-left">Bank String</th>
                      <th className="px-4 py-2 text-center">Occurrences</th>
                      <th className="px-4 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-purple-50">
                    {orphanedResults.map((res, idx) => (
                      <tr key={idx} className="hover:bg-purple-50/30 transition-colors group">
                        <td className="px-4 py-3 font-mono text-xs text-slate-700">{res.raw_description}</td>
                        <td className="px-4 py-3 text-center">
                          <Badge variant="secondary" className="bg-purple-100 text-purple-700 rounded-full">
                            {res.count}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-8 text-purple-600 hover:text-purple-700 hover:bg-purple-100 gap-1"
                            onClick={() => {
                              setSelectedOrphan(res);
                              setRuleModalOpen(true);
                            }}
                          >
                            <Wand2 className="h-3.5 w-3.5" />
                            <span className="text-[10px] font-bold uppercase">Create Rule</span>
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {orphanedResults.length === 0 && !orphanedLoading && orphanedSearch.length >= 2 && (
              <p className="text-center py-6 text-slate-400 text-xs italic">No unmapped transactions found matching "{orphanedSearch}".</p>
            )}
          </CardContent>
        </Card>

        {/* Merge Tool */}
        <div className="space-y-6">
          <Card className="shadow-md border-orange-100 bg-orange-50/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-orange-800">
                <Merge className="h-5 w-5" />
                Merge Tool
              </CardTitle>
              <CardDescription className="text-orange-700/70">
                Consolidate duplicate merchants into this one.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="merchant-search" className="text-xs font-bold text-orange-800 uppercase">Find Duplicates</Label>
                <Input 
                  id="merchant-search"
                  placeholder="Search banners..." 
                  value={mergeSearch}
                  onChange={(e) => setMergeSearch(e.target.value)}
                  className="bg-white border-orange-200 focus:ring-orange-500"
                />
                
                {mergeSearch.length > 1 && filteredMerchants.length > 0 && (
                  <div className="mt-1 bg-white border border-orange-100 rounded-md shadow-lg overflow-hidden animate-in fade-in zoom-in-95 duration-100">
                    {filteredMerchants.map(m => (
                      <button
                        key={m.id}
                        className="w-full text-left px-4 py-2 text-sm hover:bg-orange-50 transition-colors"
                        onClick={() => toggleSourceSelection(m.id)}
                      >
                        {m.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {selectedSourceIds.length > 0 && (
                <div className="space-y-2">
                  <Label className="text-[10px] font-bold text-orange-800 uppercase">Selected to Merge</Label>
                  <div className="flex flex-wrap gap-2">
                    {selectedSourceIds.map(sid => {
                      const m = allMerchants.find(am => am.id === sid);
                      return (
                        <Badge key={sid} variant="secondary" className="bg-orange-100 text-orange-800 flex items-center gap-1 pl-2 pr-1">
                          {m?.name}
                          <button onClick={() => toggleSourceSelection(sid)} className="hover:bg-orange-200 rounded-full p-0.5">
                            <X className="h-3 w-3" />
                          </button>
                        </Badge>
                      );
                    })}
                  </div>
                  <Button 
                    onClick={handleMerge} 
                    disabled={mergeLoading}
                    className="w-full mt-4 bg-orange-600 hover:bg-orange-700 text-white gap-2"
                  >
                    {mergeLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Merge className="h-4 w-4" />}
                    Merge into {merchant.name}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-red-100 bg-red-50/30">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-bold text-red-800">Danger Zone</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-red-700 mb-4 leading-relaxed">
                Deleting this merchant will remove all its mapping rules. This cannot be undone.
              </p>
              <Button variant="outline" size="sm" className="w-full border-red-200 text-red-600 hover:bg-red-100 gap-2">
                <Trash2 className="h-4 w-4" /> Delete Merchant
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Account Selection Modal */}
      {isAccountModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <Card className="w-full max-w-2xl mx-auto shadow-2xl max-h-[90vh] flex flex-col">
            <CardHeader className="border-b">
              <CardTitle>Select Accounting Category</CardTitle>
              <CardDescription>
                Choose the default account for {merchant.name}.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-y-auto p-6">
              <AccountTree 
                isSelectMode={true} 
                onSelect={handleAccountSelect} 
              />
              <div className="flex justify-end mt-6">
                <Button variant="outline" onClick={() => setIsAccountModalOpen(false)}>
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* History Confirmation Modal */}
      {isConfirmHistoryOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <Card className="w-full max-w-md mx-auto shadow-2xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <History className="h-5 w-5 text-blue-600" />
                Update History?
              </CardTitle>
              <CardDescription>
                You've selected <strong>{pendingAccountName}</strong> for this merchant.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-start space-x-3 bg-slate-50 p-4 rounded-lg border border-slate-100">
                <input 
                  type="checkbox" 
                  id="update-history"
                  className="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  checked={updateHistory}
                  onChange={(e) => setUpdateHistory(e.target.checked)}
                />
                <Label htmlFor="update-history" className="text-sm leading-relaxed cursor-pointer">
                  <span className="block font-bold text-slate-900">Apply to historical transactions</span>
                  <span className="text-slate-500 text-xs">
                    This will automatically update the category for all past {merchant.name} transactions in your ledger.
                  </span>
                </Label>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setIsConfirmHistoryOpen(false)}>Cancel</Button>
                <Button onClick={handleCategoryUpdate} disabled={categoryLoading}>
                  {categoryLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Check className="h-4 w-4 mr-2" />}
                  Save Correction
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {ruleModalOpen && selectedOrphan && (
        <CreateRuleModal 
          isOpen={ruleModalOpen}
          onClose={() => {
            setRuleModalOpen(false);
            setSelectedOrphan(null);
          }}
          onSuccess={(count) => {
            toast({ 
              title: "Routing rule created",
              description: formatRoutingRuleSuccess(count)
            });
            loadData(Number(id));
            setOrphanedSearch('');
            setOrphanedResults([]);
          }}
          rawDescription={selectedOrphan.raw_description}
          institutionId={selectedOrphan.institution_id}
          preselectedMerchant={merchant}
        />
      )}
    </div>
  );
};
