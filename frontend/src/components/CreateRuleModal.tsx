import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { createAndApplyRule } from '../api/client';
import { AccountTree } from './AccountTree';

interface Account {
  id: number;
  name: string;
  account_type: string;
  parent: number | null;
  children: Account[];
}

interface CreateRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedCount: number) => void;
  rawDescription: string;
}

export const CreateRuleModal: React.FC<CreateRuleModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  rawDescription
}) => {
  const [formData, setFormData] = useState({
    search_text: '',
    merchant_name: '',
    target_account_id: 0,
  });
  const [selectedAccountName, setSelectedAccountName] = useState<string | null>(null);
  const [isTreeOpen, setIsTreeOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setFormData({
        search_text: rawDescription,
        merchant_name: '',
        target_account_id: 0,
      });
      setSelectedAccountName(null);
      setIsTreeOpen(false);
    }
    setError(null);
  }, [isOpen, rawDescription]);

  if (!isOpen) return null;

  const handleAccountSelect = (account: Account) => {
    setFormData(prev => ({ ...prev, target_account_id: account.id }));
    setSelectedAccountName(account.name);
    setIsTreeOpen(false);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (formData.target_account_id === 0) {
      setError("Please select an accounting post.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await createAndApplyRule(formData);
      onSuccess(result.updated_count);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create rule.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <Card className="w-full max-w-md mx-auto">
        <CardHeader>
          <CardTitle>Create Mapping Rule</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="search_text">Search Text (Branch)</Label>
              <Input 
                id="search_text" 
                name="search_text" 
                value={formData.search_text} 
                onChange={handleChange} 
                required 
                placeholder="e.g. MCDONALDS"
              />
              <p className="text-[10px] text-slate-500">Transactions containing this text will be matched.</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="merchant_name">Merchant Name (Banner)</Label>
              <Input 
                id="merchant_name" 
                name="merchant_name" 
                value={formData.merchant_name} 
                onChange={handleChange} 
                required 
                placeholder="e.g. McDonald's"
              />
            </div>

            <div className="space-y-2">
              <Label>Accounting Post</Label>
              <div className="relative">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full justify-between font-normal"
                  onClick={() => setIsTreeOpen(!isTreeOpen)}
                >
                  {selectedAccountName || "Select an account..."}
                </Button>
                
                {isTreeOpen && (
                  <div className="absolute z-50 mt-2 w-full max-h-60 overflow-y-auto rounded-md border border-slate-200 bg-white p-2 shadow-lg">
                    <AccountTree 
                      isSelectMode={true} 
                      onSelect={handleAccountSelect} 
                    />
                  </div>
                )}
              </div>
              <p className="text-[10px] text-slate-500">Choose the destination for these transactions.</p>
            </div>

            {error && <p className="text-destructive text-sm">{error}</p>}
            
            <div className="flex justify-end space-x-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Processing...' : 'Create & Apply'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};
