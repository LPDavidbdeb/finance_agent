import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { fetchMerchantDetail, updateMerchant, mergeMerchants, fetchMerchants } from '../api/client';
import { AccountTree } from '../components/AccountTree';
import { useToast } from '../components/ui/use-toast';
import { Loader2, Edit2, Check, X, ArrowLeft, Merge, Trash2, Tag, History } from 'lucide-react';

interface MappingRule {
  id: number;
  search_text: string;
  institution_name: string;
}

interface MerchantDetail {
  id: number;
  name: string;
  is_unique_provider: boolean;
  default_account_id?: number;
  default_account_name?: string;
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    if (id) {
      loadData(Number(id));
    }
  }, [id]);

  const loadData = async (merchantId: number) => {
    try {
      setLoading(true);
      const [detail, others] = await Promise.all([
        fetchMerchantDetail(merchantId),
        fetchMerchants()
      ]);
      setMerchant(detail);
      setNewName(detail.name);
      setAllMerchants(others.filter((m: any) => m.id !== merchantId));
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

  const filteredMerchants = allMerchants.filter(m => 
    m.name.toLowerCase().includes(mergeSearch.toLowerCase()) && 
    !selectedSourceIds.includes(m.id)
  ).slice(0, 5);

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
                {merchant.is_unique_provider ? 'Unique Provider' : 'Multi-category Merchant'}
              </Badge>
              
              <div className="flex items-center gap-2 bg-blue-50 pl-3 pr-1 py-1 rounded-full border border-blue-100">
                <Tag className="h-3.5 w-3.5 text-blue-600" />
                <span className="text-sm font-semibold text-blue-800">
                  {merchant.default_account_name || 'Uncategorized'}
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
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {merchant.mapping_rules.length === 0 && (
                  <tr><td colSpan={2} className="px-6 py-10 text-center text-slate-400 italic">No rules defined.</td></tr>
                )}
                {merchant.mapping_rules.map(rule => (
                  <tr key={rule.id}>
                    <td className="px-6 py-4 font-mono text-xs text-slate-700">{rule.search_text}</td>
                    <td className="px-6 py-4 text-slate-600">{rule.institution_name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
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
    </div>
  );
};
