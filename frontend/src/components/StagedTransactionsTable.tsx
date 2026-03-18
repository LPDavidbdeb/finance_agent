import React, { useState, useEffect } from 'react';
import { fetchStagedTransactions, approveTransaction, rerunCategorization } from '../api/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { useToast } from './ui/use-toast';
import { Badge } from './ui/badge';
import { Loader2, RefreshCw } from 'lucide-react';

interface StagedTransaction {
  id: number;
  bank_date: string;
  raw_description: string;
  clean_description?: string;
  amount: number;
  status: string;
  predicted_account_id?: number;
  predicted_account_name?: string;
  statement_import_id: number;
}

interface StagedTransactionsTableProps {
  productId: number;
  refreshTrigger?: number;
}

export const StagedTransactionsTable: React.FC<StagedTransactionsTableProps> = ({
  productId,
  refreshTrigger = 0,
}) => {
  const [transactions, setTransactions] = useState<StagedTransaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [recategorizing, setRecategorizing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState<Record<number, boolean>>({});
  const { toast } = useToast();

  const loadTransactions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchStagedTransactions(productId);
      setTransactions(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch staged transactions';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (productId) {
      loadTransactions();
    }
  }, [productId, refreshTrigger]);

  const handleRerunCategorization = async () => {
    // Get unique statement import IDs from the current transactions
    const importIds = Array.from(new Set(transactions.map(tx => tx.statement_import_id)));
    
    if (importIds.length === 0) return;

    setRecategorizing(true);
    try {
      let totalUpdated = 0;
      // Re-run categorization for each unique statement import
      for (const importId of importIds) {
        const result = await rerunCategorization(importId);
        totalUpdated += result.updated_count;
      }
      
      toast({
        title: "Categorization Complete",
        description: `Updated ${totalUpdated} transaction(s) with new rules.`,
      });
      
      await loadTransactions();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to re-run categorization';
      toast({
        variant: "destructive",
        title: "Re-categorization Failed",
        description: errorMessage,
      });
    } finally {
      setRecategorizing(false);
    }
  };

  const handleApprove = async (transactionId: number, targetAccountId?: number) => {
    if (!targetAccountId) {
      toast({
        variant: "destructive",
        title: "Approval Failed",
        description: "No predicted account to approve this transaction.",
      });
      return;
    }
    setApproving(prev => ({ ...prev, [transactionId]: true }));
    try {
      await approveTransaction(productId, transactionId, targetAccountId);
      toast({
        title: "Success",
        description: "Transaction approved and reconciled.",
      });
      loadTransactions(); // Refresh the list
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Approval failed';
      toast({
        variant: "destructive",
        title: "Approval Failed",
        description: errorMessage,
      });
    } finally {
      setApproving(prev => ({ ...prev, [transactionId]: false }));
    }
  };

  if (loading) {
    return <div className="text-center text-slate-500">Loading staged transactions...</div>;
  }

  if (error) {
    return <div className="text-center text-destructive">{error}</div>;
  }

  if (transactions.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Extracted Transactions</CardTitle>
          <CardDescription>Review transactions extracted from your statement</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-slate-500 font-medium">No pending transactions to review.</p>
            <p className="text-slate-400 text-sm mt-1">Upload a PDF statement to extract transactions.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <div>
          <CardTitle>Extracted Transactions</CardTitle>
          <CardDescription>Review {transactions.length} transaction(s) extracted from your statement</CardDescription>
        </div>
        <Button 
          variant="outline" 
          size="sm" 
          onClick={handleRerunCategorization}
          disabled={recategorizing || transactions.length === 0}
          className="flex items-center gap-2"
        >
          {recategorizing ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
          Re-run Categorization
        </Button>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto border border-slate-200 rounded-md">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-700">Date</th>
                <th className="px-4 py-3 text-left font-medium text-slate-700">Description</th>
                <th className="px-4 py-3 text-left font-medium text-slate-700">Account / Category</th>
                <th className="px-4 py-3 text-right font-medium text-slate-700">Amount</th>
                <th className="px-4 py-3 text-right font-medium text-slate-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-slate-700 whitespace-nowrap">
                    {new Date(tx.bank_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-slate-700">
                    <div>{tx.clean_description || tx.raw_description}</div>
                    {tx.clean_description && <div className="text-xs text-slate-400">{tx.raw_description}</div>}
                  </td>
                  <td className="px-4 py-3">
                    {tx.predicted_account_name ? (
                      <Badge variant="secondary" className="bg-green-100 text-green-800">
                        Predicted: {tx.predicted_account_name}
                      </Badge>
                    ) : (
                      <span className="text-slate-400">Uncategorized</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-900 font-mono text-right">
                    {`$${Math.abs(tx.amount).toFixed(2)}`}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button 
                      size="sm"
                      onClick={() => handleApprove(tx.id, tx.predicted_account_id)}
                      disabled={approving[tx.id] || !tx.predicted_account_id}
                    >
                      {approving[tx.id] ? 'Approving...' : 'Approve'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};
