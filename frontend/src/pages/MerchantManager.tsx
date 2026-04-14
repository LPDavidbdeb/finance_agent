import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { fetchMerchants, updateMerchantAccount, updateMerchant } from '../api/client';
import { AccountTree } from '../components/AccountTree';
import { useToast } from '../components/ui/use-toast';
import { Search, History, Loader2 } from 'lucide-react';

interface Merchant {
  id: number;
  name: string;
  default_account_id?: number;
  default_account_name?: string;
  is_unique_provider: boolean;
}

export const MerchantManager: React.FC = () => {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingMerchant, setEditingMerchant] = useState<Merchant | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [processingIds, setProcessingIds] = useState<number[]>([]);
  const { toast } = useToast();

  const loadMerchants = async () => {
    try {
      setLoading(true);
      const data = await fetchMerchants();
      setMerchants(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load merchants');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMerchants();
  }, []);

  const handleAccountSelect = async (account: any) => {
    if (!editingMerchant) return;

    try {
      await updateMerchantAccount(editingMerchant.id, account.id);
      toast({
        title: "Route Updated",
        description: `Successfully assigned ${account.name} to ${editingMerchant.name}.`,
      });
      setEditingMerchant(null);
      loadMerchants();
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Update Failed",
        description: err.message || "Could not update route.",
      });
    }
  };

  const handleToggleUnique = async (merchant: Merchant, newValue: boolean) => {
    setProcessingIds(prev => [...prev, merchant.id]);
    try {
      await updateMerchant(merchant.id, { is_unique_provider: newValue });
      setMerchants(prev => prev.map(m => m.id === merchant.id ? { ...m, is_unique_provider: newValue } : m));
      toast({ title: "Updated", description: `${merchant.name} unique status updated.` });
    } catch (err: any) {
      toast({ variant: "destructive", title: "Error", description: err.message });
    } finally {
      setProcessingIds(prev => prev.filter(id => id !== merchant.id));
    }
  };

  const handleSyncHistory = async (merchant: Merchant) => {
    if (!merchant.default_account_id) return;
    setProcessingIds(prev => [...prev, merchant.id]);
    try {
      await updateMerchant(merchant.id, { 
        default_account_id: merchant.default_account_id, 
        update_history: true 
      });
      toast({ title: "History Synced", description: `Past transactions for ${merchant.name} have been updated.` });
    } catch (err: any) {
      toast({ variant: "destructive", title: "Error", description: err.message });
    } finally {
      setProcessingIds(prev => prev.filter(id => id !== merchant.id));
    }
  };

  const filteredMerchants = merchants.filter(m => 
    m.name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) return <div className="text-center p-8">Loading merchants...</div>;
  if (error) return <div className="text-center p-8 text-destructive">{error}</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Merchants</h1>
          <p className="text-slate-500 mt-1">
            Manage the default routes for your identified merchants.
          </p>
        </div>
      </div>

      <div className="relative w-full max-w-md mb-6">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
        <Input 
          placeholder="Search merchants..." 
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pl-9"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Identified Merchants</CardTitle>
          <CardDescription>
            Rules created from bank statements are anchored to these merchants.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto border border-slate-200 rounded-md">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Merchant Name</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Current Route</th>
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Unique Provider</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {filteredMerchants.length === 0 && (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan={4}>
                      No merchants found matching your search.
                    </td>
                  </tr>
                )}
                {filteredMerchants.map((merchant) => (
                  <tr key={merchant.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-slate-900 font-medium">
                      <Link to={`/dashboard/merchants/${merchant.id}`} className="hover:text-blue-600 hover:underline">
                        {merchant.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      {merchant.default_account_name ? (
                        <span className="text-slate-700">{merchant.default_account_name}</span>
                      ) : (
                        <Badge variant="destructive" className="bg-red-100 text-red-800 border-red-200">
                          Route Missing
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <input 
                        type="checkbox" 
                        checked={merchant.is_unique_provider}
                        onChange={(e) => handleToggleUnique(merchant, e.target.checked)}
                        disabled={processingIds.includes(merchant.id)}
                        className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer disabled:opacity-50"
                      />
                    </td>
                    <td className="px-4 py-3 text-right space-x-2 whitespace-nowrap">
                      <Button variant="outline" size="sm" onClick={() => setEditingMerchant(merchant)} disabled={processingIds.includes(merchant.id)}>
                        Edit Route
                      </Button>
                      <Button 
                        variant="secondary" 
                        size="sm" 
                        onClick={() => handleSyncHistory(merchant)} 
                        disabled={!merchant.default_account_id || processingIds.includes(merchant.id)}
                        title="Apply route to historical transactions"
                      >
                        {processingIds.includes(merchant.id) ? <Loader2 className="h-4 w-4 animate-spin" /> : <History className="h-4 w-4" />}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Category Selection Modal */}
      {editingMerchant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
          <Card className="w-full max-w-2xl mx-auto shadow-2xl max-h-[90vh] flex flex-col">
            <CardHeader className="border-b">
              <CardTitle>Select Route for {editingMerchant.name}</CardTitle>
              <CardDescription>
                Choose the default account route for this merchant.
              </CardDescription>
            </CardHeader>
            <CardContent className="overflow-y-auto p-6">
              <AccountTree 
                isSelectMode={true} 
                onSelect={handleAccountSelect} 
              />
              <div className="flex justify-end mt-6">
                <Button variant="outline" onClick={() => setEditingMerchant(null)}>
                  Cancel
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};
