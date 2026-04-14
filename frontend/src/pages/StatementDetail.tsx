import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { fetchStatementImport, fetchStatementImportTransactions, fetchAccountsFlat, fetchMerchants, approveTransaction, BASE_URL } from '../api/client';
import { Loader2, ArrowLeft, FileText, Download, ExternalLink, AlertCircle, CheckCircle2, Clock, ChevronUp, ChevronDown, PlusCircle, Tag, ArrowRightLeft } from 'lucide-react';
import { CreateRuleModal } from '../components/CreateRuleModal';
import { AccountTree } from '../components/AccountTree';
import { InlineReroutePanel, FlatAccount, RerouteMerchant } from '../components/InlineReroutePanel';
import { useToast } from '../components/ui/use-toast';
import { StagedTransactionView } from '../types/transactions';
import { TRANSACTION_ROUTE_LABEL, TRANSACTION_ROUTED_LABEL, TRANSACTION_ROUTED_TO_LABEL } from '../utils/transactionVocabulary';

interface StatementImport {
  id: number;
  upload_date: string;
  document_date?: string;
  file_name: string;
  file_url?: string;
  status: string;
  processed_by_ai: boolean;
  processed_by_python: boolean;
}

export const StatementDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const highlightId = searchParams.get('highlight');
  const highlightTransactionId = searchParams.get('highlight_transaction');

  const [statement, setStatement] = useState<StatementImport | null>(null);
  const [transactions, setTransactions] = useState<StagedTransactionView[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [routingTxId, setRoutingTxId] = useState<number | null>(null);
  const [isRoutingModalOpen, setIsRoutingModalOpen] = useState(false);
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [ruleRawDescription, setRuleRawDescription] = useState('');
  const [ruleInstitutionId, setRuleInstitutionId] = useState<number | null>(null);
  const [routeLoading, setRouteLoading] = useState<Record<number, boolean>>({});
  const [reroutingEntryId, setReroutingEntryId] = useState<number | null>(null);
  const [flatAccounts, setFlatAccounts] = useState<FlatAccount[]>([]);
  const [merchants, setMerchants] = useState<RerouteMerchant[]>([]);
  const { toast } = useToast();

  const [sortConfig, setSortConfig] = useState<{ key: keyof StagedTransactionView; direction: 'asc' | 'desc' }>({
    key: 'bank_date',
    direction: 'asc'
  });
  
  const highlightedRef = useRef<HTMLTableRowElement>(null);

  useEffect(() => {
    if (id) {
      loadData(Number(id));
    }
  }, [id]);

  useEffect(() => {
    const loadRoutingContext = async () => {
      try {
        const [accounts, merchantList] = await Promise.all([
          fetchAccountsFlat(),
          fetchMerchants(),
        ]);
        setFlatAccounts(Array.isArray(accounts) ? (accounts as FlatAccount[]) : []);
        setMerchants(Array.isArray(merchantList) ? (merchantList as RerouteMerchant[]) : []);
      } catch {
        // Non-fatal: routing modal remains unavailable until data can be fetched.
      }
    };
    loadRoutingContext();
  }, []);

  useEffect(() => {
    if (!loading && highlightId && highlightedRef.current) {
      highlightedRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [loading, highlightId]);

  const loadData = async (importId: number) => {
    try {
      setLoading(true);
      const [stmt, txs] = await Promise.all([
        fetchStatementImport(importId),
        fetchStatementImportTransactions(importId)
      ]);
      setStatement(stmt);
      setTransactions(txs);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load statement details.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleSort = (key: keyof StagedTransactionView) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const openRoutingModal = (txId: number) => {
    setRoutingTxId(txId);
    setIsRoutingModalOpen(true);
  };

  const openRuleModal = (rawDescription: string, institutionId?: number) => {
    if (!institutionId) {
      toast({
        variant: 'destructive',
        title: 'Routing rule unavailable',
        description: 'Institution context is missing for this transaction.',
      });
      return;
    }
    setRuleRawDescription(rawDescription);
    setRuleInstitutionId(institutionId);
    setIsRuleModalOpen(true);
  };

  const handleRoute = async (tx: StagedTransactionView, targetAccountId: number) => {
    if (!tx.financial_product_id) {
      toast({
        variant: 'destructive',
        title: 'Route Failed',
        description: 'No linked product found for this transaction.',
      });
      return;
    }

    setRouteLoading((prev) => ({ ...prev, [tx.id]: true }));
    try {
      await approveTransaction(tx.financial_product_id, tx.id, targetAccountId);
      toast({ title: 'Success', description: 'Transaction routed and reconciled.' });
      await loadData(Number(id));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Route failed';
      toast({ variant: 'destructive', title: 'Route Failed', description: message });
    } finally {
      setRouteLoading((prev) => ({ ...prev, [tx.id]: false }));
      setIsRoutingModalOpen(false);
      setRoutingTxId(null);
    }
  };

  const handleRerouteSuccess = async () => {
    setReroutingEntryId(null);
    toast({ title: 'Success', description: 'Transaction re-routed.' });
    if (id) {
      await loadData(Number(id));
    }
  };

  const sortedTransactions = React.useMemo(() => {
    const sorted = [...transactions];
    sorted.sort((a, b) => {
      let aValue: string | number | Date | undefined;
      let bValue: string | number | Date | undefined;

      // Special case for description: Sort by the DISPLAY string (Merchant > Raw)
      if (sortConfig.key === 'raw_description') {
        aValue = (a.merchant_name || a.raw_description || '').trim().toLowerCase();
        bValue = (b.merchant_name || b.raw_description || '').trim().toLowerCase();
      } else {
        aValue = a[sortConfig.key];
        bValue = b[sortConfig.key];
      }

      if (aValue === undefined || bValue === undefined) return 0;

      // Numeric comparison for amount
      if (sortConfig.key === 'amount') {
        return sortConfig.direction === 'asc' 
          ? Number(aValue) - Number(bValue)
          : Number(bValue) - Number(aValue);
      }

      // Default string comparison
      if (aValue < bValue) return sortConfig.direction === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortConfig.direction === 'asc' ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [transactions, sortConfig]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
        <p className="text-slate-500 font-medium italic">Retrieving document and ledger entries...</p>
      </div>
    );
  }

  if (error || !statement) {
    return (
      <div className="p-8">
        <Button variant="ghost" onClick={() => navigate(-1)} className="mb-6">
          <ArrowLeft className="h-4 w-4 mr-2" /> Back
        </Button>
        <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-red-900 mb-2">Error Loading Statement</h2>
          <p className="text-red-700">{error || "Statement not found."}</p>
        </div>
      </div>
    );
  }

  const getStatusIcon = (status: string) => {
    switch (status.toUpperCase()) {
      case 'COMPLETED': return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
      case 'STAGED': return <Clock className="h-4 w-4 text-blue-500" />;
      case 'FAILED': return <AlertCircle className="h-4 w-4 text-red-500" />;
      default: return null;
    }
  };

  const pdfUrl = statement.file_url 
    ? (statement.file_url.startsWith('http') ? statement.file_url : `${BASE_URL}${statement.file_url}`)
    : null;

  const SortIcon = ({ column }: { column: keyof StagedTransactionView }) => {
    if (sortConfig.key !== column) return null;
    return sortConfig.direction === 'asc' 
      ? <ChevronUp className="h-3 w-3 ml-1 inline-block" /> 
      : <ChevronDown className="h-3 w-3 ml-1 inline-block" />;
  };

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] overflow-hidden">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between sticky top-0 z-20">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate(-1)} className="rounded-full">
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-black uppercase tracking-tight text-slate-900">
                Statement: {statement.file_name}
              </h1>
              <Badge variant="secondary" className="text-[10px] font-bold gap-1">
                {getStatusIcon(statement.status)}
                {statement.status}
              </Badge>
            </div>
            <p className="text-xs text-slate-500 font-medium">
              Imported on {new Date(statement.upload_date).toLocaleDateString()} • {transactions.length} transactions detected
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {pdfUrl && (
            <>
              <Button variant="outline" size="sm">
                <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className="flex items-center">
                  <ExternalLink className="h-4 w-4 mr-2" /> Open Original
                </a>
              </Button>
              <Button variant="outline" size="sm">
                <a href={pdfUrl} download className="flex items-center">
                  <Download className="h-4 w-4 mr-2" /> Download
                </a>
              </Button>
            </>
          )}
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Left: Transaction List */}
        <div className="w-1/2 overflow-y-auto border-r bg-slate-50/30 p-6">
          <div className="space-y-6">
            <h3 className="text-sm font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
              <FileText className="h-4 w-4" /> System Representation
            </h3>
            
            <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 border-b text-slate-500">
                  <tr>
                    <th 
                      className="px-4 py-3 text-left font-bold uppercase text-[10px] cursor-pointer hover:bg-slate-100 transition-colors select-none"
                      onClick={() => handleSort('bank_date')}
                    >
                      Date <SortIcon column="bank_date" />
                    </th>
                    <th 
                      className="px-4 py-3 text-left font-bold uppercase text-[10px] cursor-pointer hover:bg-slate-100 transition-colors select-none"
                      onClick={() => handleSort('raw_description')}
                    >
                      Description <SortIcon column="raw_description" />
                    </th>
                    <th 
                      className="px-4 py-3 text-right font-bold uppercase text-[10px] cursor-pointer hover:bg-slate-100 transition-colors select-none"
                      onClick={() => handleSort('amount')}
                    >
                      Amount <SortIcon column="amount" />
                    </th>
                    <th className="px-4 py-3 text-left font-bold uppercase text-[10px]">Routing / Account</th>
                    <th className="px-4 py-3 text-right font-bold uppercase text-[10px]">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {sortedTransactions.map((tx) => {
                    const isHighlighted = Boolean(
                      (highlightTransactionId && tx.id === Number(highlightTransactionId)) ||
                      (highlightId && tx.journal_entry_id === Number(highlightId)),
                    );
                    return (
                      <React.Fragment key={tx.id}>
                      <tr 
                        ref={isHighlighted ? highlightedRef : null}
                        className={`transition-colors ${
                          isHighlighted 
                            ? 'bg-blue-50 ring-2 ring-inset ring-blue-500 relative z-10' 
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="px-4 py-3 font-mono text-xs text-slate-500">
                          {tx.bank_date}
                        </td>
                        <td className="px-4 py-3">
                          <p className="font-bold text-slate-800 uppercase tracking-tight text-xs">
                            {tx.merchant_name || tx.raw_description}
                          </p>
                          {tx.merchant_name && (
                            <p className="text-[10px] text-slate-400 font-mono truncate max-w-[200px]">
                              {tx.raw_description}
                            </p>
                          )}
                        </td>
                        <td className={`px-4 py-3 text-right font-mono font-black ${tx.amount < 0 ? 'text-red-600' : 'text-slate-900'}`}>
                          ${tx.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-3">
                          <Badge 
                            variant={tx.status === 'RECONCILED' ? 'outline' : 'secondary'} 
                            className={`text-[9px] font-bold uppercase ${
                              tx.status === 'RECONCILED' ? 'border-emerald-200 text-emerald-700 bg-emerald-50/50' : ''
                            }`}
                          >
                            {tx.reconciled_account_name || (tx.predicted_account_name ? `${TRANSACTION_ROUTED_TO_LABEL}: ${tx.predicted_account_name}` : 'UNROUTED')}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right space-x-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => openRuleModal(tx.raw_description, tx.institution_id)}
                            disabled={tx.status === 'RECONCILED'}
                            title="Create routing rule for this description"
                          >
                            <PlusCircle className="h-3.5 w-3.5 mr-1" />
                            Create routing rule
                          </Button>
                          {tx.status === 'RECONCILED' ? (
                            <>
                              <Button size="sm" disabled>
                                {TRANSACTION_ROUTED_LABEL}
                              </Button>
                              {tx.journal_entry_id && (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setReroutingEntryId((prev) => (prev === tx.journal_entry_id ? null : tx.journal_entry_id!))}
                                  title="Re-route transaction"
                                >
                                  <ArrowRightLeft className="h-3.5 w-3.5 mr-1" />
                                  Re-route
                                </Button>
                              )}
                            </>
                          ) : (
                            <Button
                              size="sm"
                              onClick={() => openRoutingModal(tx.id)}
                              disabled={routeLoading[tx.id]}
                            >
                              <Tag className="h-3.5 w-3.5 mr-1" />
                              {TRANSACTION_ROUTE_LABEL}
                            </Button>
                          )}
                        </td>
                      </tr>
                      {tx.journal_entry_id && reroutingEntryId === tx.journal_entry_id && (
                        <tr>
                          <td colSpan={5} className="px-6 py-3 bg-blue-50 border-l-4 border-blue-400">
                            <InlineReroutePanel
                              entryId={tx.journal_entry_id}
                              flatAccounts={flatAccounts}
                              merchants={merchants}
                              onSuccess={() => {
                                handleRerouteSuccess();
                              }}
                              onCancel={() => setReroutingEntryId(null)}
                            />
                          </td>
                        </tr>
                      )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Right: PDF Viewer */}
        <div className="w-1/2 bg-slate-100 p-6 flex flex-col">
          <div className="flex-1 bg-white rounded-xl border shadow-lg overflow-hidden relative">
            {pdfUrl ? (
              <iframe 
                src={`${pdfUrl}#toolbar=0&navpanes=0`} 
                className="w-full h-full border-none"
                title="Statement PDF"
              />
            ) : (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 p-12 text-center">
                <AlertCircle className="h-12 w-12 mb-4 opacity-20" />
                <p className="font-medium italic">Document binary is not available for preview.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {isRuleModalOpen && ruleInstitutionId !== null && (
        <CreateRuleModal
          isOpen={isRuleModalOpen}
          onClose={() => setIsRuleModalOpen(false)}
          onSuccess={async () => {
            setIsRuleModalOpen(false);
            await loadData(Number(id));
          }}
          rawDescription={ruleRawDescription}
          institutionId={ruleInstitutionId}
        />
      )}

      {isRoutingModalOpen && routingTxId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <div className="w-full max-w-2xl">
            <div className="bg-white rounded-lg shadow-2xl border overflow-hidden">
              <div className="border-b px-6 py-4">
                <h3 className="text-base font-semibold">Route Transaction</h3>
                <p className="text-sm text-slate-500">Select the destination account route for this transaction.</p>
              </div>
              <div className="p-6 max-h-[70vh] overflow-y-auto">
                <AccountTree
                  isSelectMode={true}
                  onSelect={(account: { id: number }) => {
                    const tx = transactions.find((candidate) => candidate.id === routingTxId);
                    if (!tx) {
                      return;
                    }
                    handleRoute(tx, account.id);
                  }}
                />
                <div className="flex justify-end mt-6">
                  <Button variant="outline" onClick={() => { setIsRoutingModalOpen(false); setRoutingTxId(null); }}>
                    Cancel
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
