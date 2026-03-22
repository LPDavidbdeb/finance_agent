import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { fetchDrillDown } from '../api/client';
import { Loader2, X, FileText, List, ArrowRight, Store, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { Link } from 'react-router-dom';

interface DrillDownModalProps {
  isOpen: boolean;
  onClose: () => void;
  dimension: string;
  period: string; // YYYY-MM
}

export const DrillDownModal: React.FC<DrillDownModalProps> = ({ isOpen, onClose, dimension, period }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && dimension && period) {
      loadDrillDown();
    }
  }, [isOpen, dimension, period]);

  const loadDrillDown = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await fetchDrillDown(dimension, period);
      setData(result);
    } catch (err: any) {
      setError(err.message || "Failed to load drill-down data.");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 overflow-hidden">
      <Card className="w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl animate-in zoom-in-95 duration-200">
        <CardHeader className="flex flex-row items-center justify-between border-b bg-slate-50/50 sticky top-0 z-10">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <FileText className="h-5 w-5 text-blue-600" />
              Investigation: {dimension.replace('-', ' ').toUpperCase()} ({period})
            </CardTitle>
            <CardDescription>Deep-dive into individual categories and banners.</CardDescription>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} className="rounded-full">
            <X className="h-5 w-5" />
          </Button>
        </CardHeader>

        <CardContent className="flex-1 overflow-y-auto p-6 space-y-8">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
              <Loader2 className="h-10 w-10 animate-spin text-blue-600" />
              <p className="text-slate-500 font-medium italic">Sifting through the ledger...</p>
            </div>
          ) : error ? (
            <div className="text-center py-20 text-red-500 font-medium">{error}</div>
          ) : (
            <>
              {/* Category Breakdown */}
              <section className="space-y-4">
                <h3 className="text-sm font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
                  <List className="h-4 w-4" /> Category Performance vs. Average
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {data.category_breakdown.map((cat: any) => {
                    const diff = cat.balance - cat.average_monthly_balance;
                    const percentDiff = cat.average_monthly_balance > 0 
                      ? (diff / cat.average_monthly_balance) * 100 
                      : 0;
                    const isOver = diff > 0;

                    return (
                      <div key={cat.id} className="bg-white border rounded-xl p-4 shadow-sm flex flex-col group hover:border-blue-200 transition-colors">
                        <div className="flex justify-between items-start mb-2">
                          <p className="text-[10px] font-black text-slate-400 uppercase tracking-tighter">{cat.name}</p>
                          <Link 
                            to={`/dashboard/accounts/${cat.id}?year=${period.split('-')[0]}`}
                            className="p-1.5 bg-slate-50 rounded-full text-slate-400 group-hover:text-blue-600 group-hover:bg-blue-50 transition-all"
                          >
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        </div>
                        <div className="flex items-baseline gap-2">
                          <p className="text-2xl font-black text-slate-900">${cat.balance.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</p>
                          <div className={`flex items-center text-[10px] font-bold ${isOver ? 'text-red-500' : 'text-emerald-500'}`}>
                            {isOver ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}
                            {Math.abs(percentDiff).toFixed(0)}%
                          </div>
                        </div>
                        <p className="text-[10px] text-slate-400 font-medium mt-1">
                          vs. ${cat.average_monthly_balance.toLocaleString(undefined, { maximumFractionDigits: 0 })} monthly avg
                        </p>
                      </div>
                    );
                  })}
                </div>
              </section>

              {/* Banners Table */}
              <section className="space-y-4">
                <h3 className="text-sm font-black uppercase tracking-widest text-slate-400 flex items-center gap-2">
                  <Store className="h-4 w-4" /> Banners Grouped
                </h3>
                <div className="border rounded-xl overflow-hidden shadow-sm">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b text-slate-500">
                      <tr>
                        <th className="px-4 py-3 text-left font-bold uppercase text-[10px]">Merchant Banner</th>
                        <th className="px-4 py-3 text-left font-bold uppercase text-[10px]">Category</th>
                        <th className="px-4 py-3 text-center font-bold uppercase text-[10px]">Hits</th>
                        <th className="px-4 py-3 text-right font-bold uppercase text-[10px]">Total Amount</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y bg-white">
                      {data.banners.length === 0 ? (
                        <tr><td colSpan={4} className="p-10 text-center text-slate-400 italic">No activity found in this period.</td></tr>
                      ) : (
                        data.banners.map((b: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-50/50 transition-colors group">
                            <td className="px-4 py-3">
                              <span className="font-black text-slate-700 uppercase tracking-tight">{b.name}</span>
                            </td>
                            <td className="px-4 py-3 text-slate-500">
                              <Badge variant="outline" className="text-[10px] font-bold bg-slate-50/50 uppercase">
                                {b.category}
                              </Badge>
                            </td>
                            <td className="px-4 py-3 text-center">
                              <Badge variant="secondary" className="text-[10px] rounded-full px-2">
                                {b.count}
                              </Badge>
                            </td>
                            <td className={`px-4 py-3 text-right font-mono font-black ${b.amount < 0 ? 'text-red-600' : 'text-slate-900'}`}>
                              ${b.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </CardContent>
        <div className="p-4 border-t bg-slate-50/50 flex justify-end">
          <Button onClick={onClose}>Close Investigation</Button>
        </div>
      </Card>
    </div>
  );
};
