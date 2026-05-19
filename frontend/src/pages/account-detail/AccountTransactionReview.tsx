import React, { useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { InlineReroutePanel, RerouteMerchant } from '../../components/InlineReroutePanel';
import { CreateRuleModal } from '../../components/CreateRuleModal';
import { AccountTransactionRecord } from './types';
import { ArrowRightLeft, ArrowDown, ArrowUp, ArrowUpDown, ChevronRight, FileText, Loader2, PlusCircle, Store, X } from 'lucide-react';

type BannerSortKey = 'name' | 'count' | 'total';

interface BannerTableProps {
  transactions: AccountTransactionRecord[];
  flatAccounts: any[];
  merchants: RerouteMerchant[];
  onTransactionUpdate: (entryId: number, updated: Partial<AccountTransactionRecord>) => void;
  onRuleSuccess: () => void;
}

interface AccountTransactionReviewProps {
  year: number;
  loading: boolean;
  transactions: AccountTransactionRecord[];
  flatAccounts: any[];
  merchants: RerouteMerchant[];
  selectedMonth: string | null;
  onSelectedMonthChange: (month: string | null) => void;
  onTransactionUpdate: (entryId: number, updated: Partial<AccountTransactionRecord>) => void;
  onRuleSuccess: () => void;
}

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const BannerTable: React.FC<BannerTableProps> = ({ transactions, flatAccounts, merchants, onTransactionUpdate, onRuleSuccess }) => {
  const [txSearch, setTxSearch] = useState('');
  const [expandedBanner, setExpandedBanner] = useState<string | null>(null);
  const [reroutingEntry, setReroutingEntry] = useState<number | null>(null);
  const [ruleModalTx, setRuleModalTx] = useState<AccountTransactionRecord | null>(null);
  const [sortKey, setSortKey] = useState<BannerSortKey>('count');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  const bannerMap = useMemo(() => {
    const map = new Map<string, { txs: AccountTransactionRecord[]; total: number }>();
    transactions.forEach(transaction => {
      if (!map.has(transaction.description)) map.set(transaction.description, { txs: [], total: 0 });
      const entry = map.get(transaction.description)!;
      entry.txs.push(transaction);
      entry.total += transaction.amount;
    });
    return map;
  }, [transactions]);

  const banners = useMemo(() => Array.from(bannerMap.entries())
    .map(([name, { txs, total }]) => ({ name, txs, total, count: txs.length }))
    .sort((a, b) => {
      const direction = sortDirection === 'asc' ? 1 : -1;
      if (sortKey === 'name') return a.name.localeCompare(b.name) * direction;
      if (sortKey === 'count') return (a.count - b.count) * direction;
      return (a.total - b.total) * direction;
    })
  , [bannerMap, sortDirection, sortKey]);

  const filtered = txSearch
    ? banners.filter(banner => banner.name.toLowerCase().includes(txSearch.toLowerCase()))
    : banners;

  const toggleSort = (key: BannerSortKey) => {
    if (sortKey === key) {
      setSortDirection(previous => (previous === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setSortKey(key);
    setSortDirection(key === 'name' ? 'asc' : 'desc');
  };

  const SortIndicator = ({ column }: { column: BannerSortKey }) => {
    if (sortKey !== column) return <ArrowUpDown className="h-3 w-3 text-slate-300" />;
    return sortDirection === 'asc'
      ? <ArrowUp className="h-3 w-3 text-blue-600" />
      : <ArrowDown className="h-3 w-3 text-blue-600" />;
  };

  return (
    <>
      <div className="flex justify-end px-4 py-3 border-b border-slate-100 bg-white">
        <input
          type="text"
          value={txSearch}
          onChange={e => setTxSearch(e.target.value)}
          placeholder="Search banners..."
          className="text-xs border border-slate-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400 w-48"
        />
      </div>
      {filtered.length === 0 ? (
        <p className="text-center py-12 text-slate-400 italic text-sm">No transactions found.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="bg-slate-50/50 border-b text-slate-500 text-xs uppercase font-bold tracking-wider">
            <tr>
              <th className="px-4 py-3 w-6"></th>
              <th className="px-4 py-3 text-left">
                <button type="button" onClick={() => toggleSort('name')} className="inline-flex items-center gap-1 hover:text-blue-600">
                  Banner <SortIndicator column="name" />
                </button>
              </th>
              <th className="px-4 py-3 text-center">
                <button type="button" onClick={() => toggleSort('count')} className="inline-flex items-center gap-1 hover:text-blue-600 mx-auto">
                  Hits <SortIndicator column="count" />
                </button>
              </th>
              <th className="px-4 py-3 text-right">
                <button type="button" onClick={() => toggleSort('total')} className="inline-flex items-center gap-1 hover:text-blue-600 ml-auto">
                  Total <SortIndicator column="total" />
                </button>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y bg-white">
            {filtered.map(banner => (
              <React.Fragment key={banner.name}>
                <tr
                  className="hover:bg-blue-50/40 cursor-pointer group transition-colors"
                  onClick={() => setExpandedBanner(expandedBanner === banner.name ? null : banner.name)}
                >
                  <td className="px-4 py-3 text-slate-400 group-hover:text-blue-500">
                    <ChevronRight className={`h-3.5 w-3.5 transition-transform ${expandedBanner === banner.name ? 'rotate-90' : ''}`} />
                  </td>
                  <td className="px-4 py-3 font-black text-slate-700 uppercase tracking-tight">{banner.name}</td>
                  <td className="px-4 py-3 text-center">
                    <Badge variant="secondary" className="text-[10px] rounded-full px-2">{banner.count}</Badge>
                  </td>
                  <td className="px-4 py-3 text-right font-mono font-black text-slate-900">
                    ${banner.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </td>
                </tr>
                {expandedBanner === banner.name && (
                  <tr>
                    <td colSpan={4} className="p-0 bg-slate-50/80 border-b-2 border-blue-100">
                      <table className="w-full text-xs">
                        <thead className="border-b border-slate-200">
                          <tr className="text-slate-400">
                            <th className="px-10 py-2 text-left font-bold uppercase tracking-wider">Date</th>
                            <th className="px-4 py-2 text-left font-bold uppercase tracking-wider">From</th>
                            <th className="px-4 py-2 text-left font-bold uppercase tracking-wider">Routed To</th>
                            <th className="px-4 py-2 text-right font-bold uppercase tracking-wider">Amount</th>
                            <th className="px-4 py-2 text-center font-bold uppercase tracking-wider">Stmt</th>
                            <th className="px-4 py-2 text-right font-bold uppercase tracking-wider">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {banner.txs.map(transaction => (
                            <React.Fragment key={transaction.journal_entry_id}>
                              <tr
                                className={`hover:bg-white transition-colors ${transaction.statement_id ? 'cursor-pointer' : ''}`}
                                onClick={() => {
                                  if (transaction.statement_id) {
                                    window.open(`/dashboard/statements/${transaction.statement_id}?highlight=${transaction.journal_entry_id}`, '_blank');
                                  }
                                }}
                              >
                                <td className="px-10 py-2.5 font-mono text-slate-500">{transaction.date}</td>
                                <td className="px-4 py-2.5 text-slate-600">{transaction.source_account}</td>
                                <td className="px-4 py-2.5">
                                  <Badge variant="outline" className="text-[10px] font-bold uppercase bg-white">
                                    {transaction.routed_to}
                                  </Badge>
                                </td>
                                <td className="px-4 py-2.5 text-right font-mono font-black text-slate-900">
                                  ${transaction.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                </td>
                                <td className="px-4 py-2.5 text-center">
                                  {transaction.statement_id && (
                                    <div className="text-slate-300 group-hover:text-blue-500">
                                      <FileText className="h-3.5 w-3.5" />
                                    </div>
                                  )}
                                </td>
                                <td className="px-4 py-2.5 text-right" onClick={e => e.stopPropagation()}>
                                  <div className="flex items-center justify-end gap-1">
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="h-6 text-[10px] gap-1 px-2"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setRuleModalTx(transaction);
                                        setReroutingEntry(null);
                                      }}
                                    >
                                      <PlusCircle className="h-2.5 w-2.5" /> Routing Rule
                                    </Button>
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        setReroutingEntry(reroutingEntry === transaction.journal_entry_id ? null : transaction.journal_entry_id);
                                      }}
                                      className="p-1 rounded hover:bg-blue-100 text-slate-400 hover:text-blue-600 transition-colors border border-slate-200"
                                      title="Re-route transaction"
                                    >
                                      <ArrowRightLeft className="h-3 w-3" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                              {reroutingEntry === transaction.journal_entry_id && (
                                <tr>
                                  <td colSpan={5} className="px-10 py-3 bg-blue-50 border-l-4 border-blue-400">
                                    <InlineReroutePanel
                                      entryId={transaction.journal_entry_id}
                                      flatAccounts={flatAccounts}
                                      merchants={merchants}
                                      onSuccess={(updated) => {
                                        onTransactionUpdate(transaction.journal_entry_id, updated);
                                        setReroutingEntry(null);
                                      }}
                                      onCancel={() => setReroutingEntry(null)}
                                    />
                                  </td>
                                </tr>
                              )}
                            </React.Fragment>
                          ))}
                        </tbody>
                      </table>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
      {ruleModalTx && (
        <CreateRuleModal
          isOpen={!!ruleModalTx}
          onClose={() => setRuleModalTx(null)}
          rawDescription={ruleModalTx.description}
          institutionId={ruleModalTx.institution_id || 0}
          onSuccess={() => { setRuleModalTx(null); onRuleSuccess(); }}
        />
      )}
    </>
  );
};

export const AccountTransactionReview: React.FC<AccountTransactionReviewProps> = ({
  year,
  loading,
  transactions,
  flatAccounts,
  merchants,
  selectedMonth,
  onSelectedMonthChange,
  onTransactionUpdate,
  onRuleSuccess,
}) => {
  const monthFilteredTransactions = selectedMonth
    ? transactions.filter(transaction => MONTH_NAMES[new Date(`${transaction.date}T00:00:00`).getMonth()] === selectedMonth)
    : transactions;

  return (
    <Card className="shadow-sm">
      <CardHeader className="bg-slate-50/30 border-b border-slate-100">
        <CardTitle className="text-lg flex items-center gap-2">
          <Store className="h-5 w-5 text-blue-600" />
          Transactions - {year}
        </CardTitle>
        <CardDescription>
          Click a month bar above to drill into a specific month. Click a banner to expand, re-route or create a rule.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {loading ? (
          <div className="flex items-center justify-center py-12 gap-2 text-slate-400">
            <Loader2 className="h-5 w-5 animate-spin" /> Loading...
          </div>
        ) : (
          <BannerTable
            transactions={transactions}
            flatAccounts={flatAccounts}
            merchants={merchants}
            onTransactionUpdate={onTransactionUpdate}
            onRuleSuccess={onRuleSuccess}
          />
        )}
      </CardContent>

      {selectedMonth && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => onSelectedMonthChange(null)}
        >
          <div
            className="bg-white rounded-xl shadow-2xl w-full max-w-4xl max-h-[80vh] overflow-hidden flex flex-col"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/60">
              <div>
                <h2 className="text-lg font-black text-slate-900 uppercase tracking-tight flex items-center gap-2">
                  <Store className="h-5 w-5 text-blue-600" />
                  {selectedMonth} {year}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5">
                  {monthFilteredTransactions.length} transactions · click a banner to expand
                </p>
              </div>
              <button
                onClick={() => onSelectedMonthChange(null)}
                className="p-1.5 rounded hover:bg-slate-200 text-slate-400 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="overflow-y-auto flex-1">
              <BannerTable
                transactions={monthFilteredTransactions}
                flatAccounts={flatAccounts}
                merchants={merchants}
                onTransactionUpdate={onTransactionUpdate}
                onRuleSuccess={() => {
                  onSelectedMonthChange(null);
                  onRuleSuccess();
                }}
              />
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};
