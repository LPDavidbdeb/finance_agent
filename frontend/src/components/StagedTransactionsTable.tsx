import React, { useState, useEffect } from 'react';
import { fetchStagedTransactions } from '../api/client';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';

interface StagedTransaction {
  id: number;
  bank_date: string;
  raw_description: string;
  amount: number;
  status: string;
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
  const [error, setError] = useState<string | null>(null);

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
    loadTransactions();
  }, [productId, refreshTrigger]);

  if (loading) {
    return (
      <div className="text-center text-slate-500">Loading staged transactions...</div>
    );
  }

  if (error) {
    return (
      <div className="text-center text-destructive">{error}</div>
    );
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
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-slate-300 mb-4"
            >
              <path d="M12 2v20M2 12h20" />
            </svg>
            <p className="text-slate-500 font-medium">No pending transactions to review.</p>
            <p className="text-slate-400 text-sm mt-1">Upload a PDF statement to extract transactions.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Extracted Transactions</CardTitle>
        <CardDescription>Review {transactions.length} transaction(s) extracted from your statement</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto border border-slate-200 rounded-md">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-700">Date</th>
                <th className="px-4 py-3 text-left font-medium text-slate-700">Merchant / Description</th>
                <th className="px-4 py-3 text-right font-medium text-slate-700">Amount</th>
                <th className="px-4 py-3 text-left font-medium text-slate-700">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {transactions.map((tx) => (
                <tr key={tx.id} className="hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-3 text-slate-700 whitespace-nowrap">
                    {new Date(tx.bank_date).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-slate-700">{tx.raw_description}</td>
                  <td className="px-4 py-3 text-slate-900 font-mono text-right">
                    {typeof tx.amount === 'number'
                      ? `$${Math.abs(tx.amount).toFixed(2)}`
                      : `$${tx.amount}`}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
                      Pending Review
                    </span>
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

