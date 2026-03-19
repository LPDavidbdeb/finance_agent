import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { fetchMerchants, updateMerchantAccount } from '../api/client';
import { AccountTree } from '../components/AccountTree';
import { useToast } from '../components/ui/use-toast';

interface Merchant {
  id: number;
  name: string;
  default_account_id?: number;
  default_account_name?: string;
}

export const MerchantManager: React.FC = () => {
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingMerchant, setEditingMerchant] = useState<Merchant | null>(null);
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
        title: "Category Updated",
        description: `Successfully assigned ${account.name} to ${editingMerchant.name}.`,
      });
      setEditingMerchant(null);
      loadMerchants();
    } catch (err: any) {
      toast({
        variant: "destructive",
        title: "Update Failed",
        description: err.message || "Could not update category.",
      });
    }
  };

  if (loading) return <div className="text-center p-8">Loading merchants...</div>;
  if (error) return <div className="text-center p-8 text-destructive">{error}</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Merchants</h1>
          <p className="text-slate-500 mt-1">
            Manage the default accounting categories for your identified merchants.
          </p>
        </div>
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
                  <th className="px-4 py-3 text-left font-medium text-slate-700">Current Category</th>
                  <th className="px-4 py-3 text-right font-medium text-slate-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 bg-white">
                {merchants.length === 0 && (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan={3}>
                      No merchants identified yet. Create a rule from a staged transaction to get started.
                    </td>
                  </tr>
                )}
                {merchants.map((merchant) => (
                  <tr key={merchant.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 text-slate-900 font-medium">{merchant.name}</td>
                    <td className="px-4 py-3">
                      {merchant.default_account_name ? (
                        <span className="text-slate-700">{merchant.default_account_name}</span>
                      ) : (
                        <Badge variant="destructive" className="bg-red-100 text-red-800 border-red-200">
                          Category Missing
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => setEditingMerchant(merchant)}
                      >
                        Edit Category
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
              <CardTitle>Select Category for {editingMerchant.name}</CardTitle>
              <CardDescription>
                Choose the default accounting post for this merchant.
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
