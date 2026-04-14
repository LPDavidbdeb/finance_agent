import React, { useState, useEffect, useCallback } from 'react';
import { approveTransaction } from '../api/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { useToast } from './ui/use-toast';
import { Badge } from './ui/badge';
import { CreateRuleModal } from './CreateRuleModal';
import { AccountTree } from './AccountTree';
import {
  TRANSACTION_ROUTE_LABEL,
  TRANSACTION_ROUTED_LABEL,
  TRANSACTION_ROUTED_TO_LABEL,
  formatRoutingRuleSuccess,
} from '../utils/transactionVocabulary';
import { PlusCircle, Tag, Loader2 } from 'lucide-react';
import { StagedTransactionView } from '../types/transactions';

interface TransactionListTableProps {
  productId: number;
  institutionId: number;
  title: string;
  description: string;
  fetchFn: () => Promise<StagedTransactionView[]>;
  onDataChange?: () => void;
  refreshTrigger?: number;
}

export const TransactionListTable: React.FC<TransactionListTableProps> = ({
  productId,
  institutionId,
  title,
  description,
  fetchFn,
  onDataChange,
  refreshTrigger = 0,
}) => {
  const [transactions, setTransactions] = useState<StagedTransactionView[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [approving, setApproving] = useState<Record<number, boolean>>({});
  
  // Rule Modal State
  const [isRuleModalOpen, setIsRuleModalOpen] = useState(false);
  const [selectedRawDescription, setSelectedRawDescription] = useState('');

  // Inline Categorization State
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);
  const [categorizingTxId, setCategorizingTxId] = useState<number | null>(null);

  const { toast } = useToast();

  const loadTransactions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchFn();
      setTransactions(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch routed transactions';
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  useEffect(() => {
    loadTransactions();
  }, [loadTransactions, refreshTrigger]);

  const handleRoute = async (transactionId: number, targetAccountId?: number) => {
    if (!targetAccountId) {
      toast({
        variant: "destructive",
        title: "Route Failed",
        description: "No target account selected to route this transaction.",
      });
      return;
    }
    setApproving(prev => ({ ...prev, [transactionId]: true }));
    try {
      await approveTransaction(productId, transactionId, targetAccountId);
      toast({
        title: "Success",
        description: "Transaction routed and reconciled.",
      });
      if (onDataChange) onDataChange();
      loadTransactions(); // Refresh the list
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Route failed';
      toast({
        variant: "destructive",
        title: "Route Failed",
        description: errorMessage,
      });
    } finally {
      setApproving(prev => ({ ...prev, [transactionId]: false }));
    }
  };

  const handleCreateRuleClick = (rawDescription: string) => {
    setSelectedRawDescription(rawDescription);
    setIsRuleModalOpen(true);
  };

  const handleRuleCreated = (updatedCount: number) => {
    toast({
      title: 'Routing rule created',
      description: formatRoutingRuleSuccess(updatedCount),
    });
    if (onDataChange) onDataChange();
    loadTransactions(); // Refresh the list
  };

  const handleAssignCategoryClick = (txId: number) => {
    setCategorizingTxId(txId);
    setIsAccountModalOpen(true);
  };

  const handleAccountSelect = async (account: { id: number }) => {
    if (categorizingTxId) {
      await handleRoute(categorizingTxId, account.id);
      setIsAccountModalOpen(false);
      setCategorizingTxId(null);
    }
  };

  if (loading && transactions.length === 0) {
    return (
      <div className="p-12 text-center text-slate-500 flex flex-col items-center gap-2">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        <p>Fetching ledger records...</p>
      </div>
    );
  }

  if (error) {
    return <div className="text-center text-destructive p-8">{error}</div>;
  }

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        {transactions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <p className="text-slate-500 font-medium">No transactions to display.</p>
          </div>
        ) : (
          <div className="overflow-x-auto border border-slate-200 rounded-md">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Date</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Description</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Routing / Account</th>
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
                      <div>{tx.merchant_name || tx.raw_description}</div>
                      {tx.merchant_name && <div className="text-xs text-slate-400">{tx.raw_description}</div>}
                    </td>
                    <td className="px-4 py-3">
                      {tx.status === 'RECONCILED' ? (
                        <Badge className="bg-blue-600 text-white border-none font-normal">
                           {tx.reconciled_account_name || TRANSACTION_ROUTED_LABEL}
                        </Badge>
                      ) : tx.predicted_account_name ? (
                        <Badge variant="secondary" className="bg-green-100 text-green-800">
                           {TRANSACTION_ROUTED_TO_LABEL}: {tx.predicted_account_name}
                        </Badge>
                      ) : (
                        <Button 
                          variant="outline" 
                          size="sm" 
                          className="h-7 text-[10px] gap-1 border-dashed"
                          onClick={() => handleAssignCategoryClick(tx.id)}
                        >
                          <Tag className="h-3 w-3" />
                           {TRANSACTION_ROUTE_LABEL}
                        </Button>
                      )}
                    </td>
                    <td className={`px-4 py-3 text-right font-mono font-semibold ${tx.amount < 0 ? 'text-red-600' : 'text-slate-900'}`}>
                      {`$${Math.abs(tx.amount).toFixed(2)}`}
                    </td>
                    <td className="px-4 py-3 text-right space-x-2">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleCreateRuleClick(tx.raw_description)}
                        title="Create routing rule for this description"
                        disabled={tx.status === 'RECONCILED'}
                      >
                        <PlusCircle className="h-4 w-4 mr-1" />
                        Create routing rule
                      </Button>
                      <Button 
                        size="sm"
                        onClick={() => handleRoute(tx.id, tx.predicted_account_id)}
                        disabled={approving[tx.id] || !tx.predicted_account_id || tx.status === 'RECONCILED'}
                      >
                        {tx.status === 'RECONCILED' ? TRANSACTION_ROUTED_LABEL : TRANSACTION_ROUTE_LABEL}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>

      <CreateRuleModal 
        isOpen={isRuleModalOpen}
        onClose={() => setIsRuleModalOpen(false)}
        onSuccess={handleRuleCreated}
        rawDescription={selectedRawDescription}
        institutionId={institutionId}
      />

      {/* Manual Routing Modal */}
      {isAccountModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <Card className="w-full max-w-2xl mx-auto shadow-2xl max-h-[90vh] flex flex-col">
            <CardHeader className="border-b">
              <CardTitle>Route Transaction</CardTitle>
              <CardDescription>
                Select the destination account route for this transaction.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-y-auto p-6">
              <AccountTree 
                isSelectMode={true} 
                onSelect={handleAccountSelect} 
              />
              <div className="flex justify-end mt-6">
                <Button variant="outline" onClick={() => { setIsAccountModalOpen(false); setCategorizingTxId(null); }}>
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </Card>
  );
};
