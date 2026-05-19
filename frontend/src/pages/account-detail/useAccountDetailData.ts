import { useEffect, useMemo, useState } from 'react';
import { fetchAccountDetail, fetchAccountTransactions, fetchAccountsFlat, fetchMerchants } from '../../api/client';
import { AccountDetailRecord, AccountTransactionRecord } from './types';
import { RerouteMerchant } from '../../components/InlineReroutePanel';

export const useAccountDetailData = (accountId: number | null, year: number) => {
  const currentYear = new Date().getFullYear();
  const [account, setAccount] = useState<AccountDetailRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<AccountTransactionRecord[]>([]);
  const [txLoading, setTxLoading] = useState(false);
  const [flatAccounts, setFlatAccounts] = useState<any[]>([]);
  const [merchants, setMerchants] = useState<RerouteMerchant[]>([]);

  const allowedYears = useMemo(() => {
    if (account?.historical_trends?.length) {
      return account.historical_trends.map(trend => trend.year).sort((a, b) => b - a);
    }

    const years: number[] = [];
    for (let i = currentYear; i >= currentYear - 5; i -= 1) years.push(i);
    return years;
  }, [account, currentYear]);

  useEffect(() => {
    if (!accountId) return;

    let cancelled = false;

    const loadAccount = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await fetchAccountDetail(accountId, year);
        if (!cancelled) setAccount(data);
      } catch (err: any) {
        if (!cancelled) setError(err.message || 'Failed to load account details.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadAccount();

    return () => {
      cancelled = true;
    };
  }, [accountId, year]);

  useEffect(() => {
    if (!accountId) return;

    let cancelled = false;

    const loadTransactions = async () => {
      try {
        setTxLoading(true);
        const data = await fetchAccountTransactions(accountId, year);
        if (!cancelled) setTransactions(data);
      } catch {
        if (!cancelled) setTransactions([]);
      } finally {
        if (!cancelled) setTxLoading(false);
      }
    };

    loadTransactions();

    return () => {
      cancelled = true;
    };
  }, [accountId, year]);

  useEffect(() => {
    let cancelled = false;

    const loadLookups = async () => {
      try {
        const [accounts, merchantList] = await Promise.all([
          fetchAccountsFlat(),
          fetchMerchants(),
        ]);
        if (!cancelled) {
          setFlatAccounts(accounts);
          setMerchants(merchantList);
        }
      } catch {
        if (!cancelled) {
          setFlatAccounts([]);
          setMerchants([]);
        }
      }
    };

    loadLookups();

    return () => {
      cancelled = true;
    };
  }, []);

  const updateTransaction = (entryId: number, updated: Partial<AccountTransactionRecord>) => {
    setTransactions(previous => previous.map(transaction => (
      transaction.journal_entry_id === entryId
        ? { ...transaction, ...updated }
        : transaction
    )));
  };

  const refreshTransactions = async () => {
    if (!accountId) return;
    const data = await fetchAccountTransactions(accountId, year).catch(() => []);
    setTransactions(data);
  };

  return {
    account,
    loading,
    error,
    transactions,
    txLoading,
    flatAccounts,
    merchants,
    allowedYears,
    updateTransaction,
    refreshTransactions,
  };
};
