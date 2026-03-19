import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { fetchAccountDetail } from '../api/client';
import { ArrowLeft, ChevronRight, Store, Layers, Loader2 } from 'lucide-react';

interface ChildAccount {
  id: number;
  name: string;
  account_type: string;
}

interface Merchant {
  id: number;
  name: string;
}

interface AccountDetail {
  id: number;
  name: string;
  account_type: string;
  parent_id?: number;
  children: ChildAccount[];
  merchants: Merchant[];
}

export const AccountDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [account, setAccount] = useState<AccountDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      loadAccount(Number(id));
    }
  }, [id]);

  const loadAccount = async (accountId: number) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchAccountDetail(accountId);
      setAccount(data);
    } catch (err: any) {
      setError(err.message || "Failed to load account details.");
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="flex justify-center p-20"><Loader2 className="h-8 w-8 animate-spin text-blue-600" /></div>;
  if (error || !account) return <div className="p-20 text-center text-red-500">{error || "Account not found"}</div>;

  return (
    <div className="space-y-8 max-w-5xl mx-auto w-full pb-20">
      <div className="flex items-center gap-4">
        <Button variant="ghost" onClick={() => navigate('/ledger')} size="sm" className="gap-2">
          <ArrowLeft className="h-4 w-4" /> Back to Ledger
        </Button>
        {account.parent_id && (
          <Button variant="ghost" onClick={() => navigate(`/dashboard/accounts/${account.parent_id}`)} size="sm" className="gap-2">
            Up to Parent
          </Button>
        )}
      </div>

      {/* Header */}
      <div className="bg-white p-8 rounded-xl shadow-sm border border-slate-200">
        <div className="flex items-center gap-3 mb-2">
          <Badge variant="outline" className="bg-slate-50 text-slate-500 border-slate-200 font-mono">
            {account.account_type}
          </Badge>
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">
          {account.name}
        </h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column: Sub-Accounts */}
        <Card className="shadow-sm">
          <CardHeader className="border-b border-slate-50 bg-slate-50/30">
            <CardTitle className="text-lg flex items-center gap-2">
              <Layers className="h-5 w-5 text-blue-600" />
              Sub-Accounts
            </CardTitle>
            <CardDescription>Nested accounts under this post.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {account.children.length === 0 ? (
              <div className="p-10 text-center text-slate-400 italic text-sm">
                No sub-accounts found.
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {account.children.map(child => (
                  <Link 
                    key={child.id} 
                    to={`/dashboard/accounts/${child.id}`}
                    className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors group"
                  >
                    <span className="font-medium text-slate-700 group-hover:text-blue-600">{child.name}</span>
                    <ChevronRight className="h-4 w-4 text-slate-300 group-hover:text-blue-400" />
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Right Column: Linked Banners */}
        <Card className="shadow-sm">
          <CardHeader className="border-b border-slate-50 bg-slate-50/30">
            <CardTitle className="text-lg flex items-center gap-2">
              <Store className="h-5 w-5 text-emerald-600" />
              Categorized Merchants
            </CardTitle>
            <CardDescription>Vendors linked to this accounting post.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {account.merchants.length === 0 ? (
              <div className="p-10 text-center text-slate-400 italic text-sm">
                No merchants assigned to this category.
              </div>
            ) : (
              <div className="divide-y divide-slate-50">
                {account.merchants.map(merchant => (
                  <Link 
                    key={merchant.id} 
                    to={`/dashboard/merchants/${merchant.id}`}
                    className="flex items-center justify-between p-4 hover:bg-slate-50 transition-colors group"
                  >
                    <span className="font-medium text-slate-700 group-hover:text-emerald-600">{merchant.name}</span>
                    <Badge variant="outline" className="text-[10px] uppercase opacity-0 group-hover:opacity-100 transition-opacity">
                      View Profile
                    </Badge>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
