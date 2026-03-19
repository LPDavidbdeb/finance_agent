import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { createAndApplyRule, fetchMerchants } from '../api/client';
import { AccountTree } from './AccountTree';
import { Loader2 } from 'lucide-react';

interface Account {
  id: number;
  name: string;
  account_type: string;
  parent: number | null;
  children: Account[];
}

interface Merchant {
  id: number;
  name: string;
  is_unique_provider: boolean;
  default_account_id?: number;
  default_account_name?: string;
}

interface CreateRuleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (updatedCount: number) => void;
  rawDescription: string;
  institutionId?: number;
}

export const CreateRuleModal: React.FC<CreateRuleModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  rawDescription,
  institutionId
}) => {
  const [formData, setFormData] = useState({
    search_text: '',
    merchant_name: '',
    target_account_id: 0 as number | undefined,
    is_unique_provider: true,
    institution_id: undefined as number | undefined,
  });
  
  const [merchants, setMerchants] = useState<Merchant[]>([]);
  const [filteredMerchants, setFilteredMerchants] = useState<Merchant[]>([]);
  const [showMerchantSuggestions, setShowMerchantSuggestions] = useState(false);
  const [selectedMerchant, setSelectedMerchant] = useState<Merchant | null>(null);

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
        is_unique_provider: true,
        institution_id: institutionId || undefined,
      });
      setSelectedAccountName(null);
      setIsTreeOpen(false);
      setSelectedMerchant(null);
      loadMerchants();
    }
    setError(null);
  }, [isOpen, rawDescription, institutionId]);

  const loadMerchants = async () => {
    try {
      const data = await fetchMerchants();
      setMerchants(data);
    } catch (err) {
      console.error("Failed to load merchants", err);
    }
  };

  if (!isOpen) return null;

  const handleAccountSelect = (account: Account) => {
    setFormData(prev => ({ ...prev, target_account_id: account.id }));
    setSelectedAccountName(account.name);
    setIsTreeOpen(false);
  };

  const handleMerchantInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setFormData(prev => ({ ...prev, merchant_name: value }));
    
    if (value.length > 1) {
      const filtered = merchants.filter(m => 
        m.name.toLowerCase().includes(value.toLowerCase())
      );
      setFilteredMerchants(filtered);
      setShowMerchantSuggestions(true);
    } else {
      setShowMerchantSuggestions(false);
    }
    
    // Reset selection if typing
    if (selectedMerchant && value !== selectedMerchant.name) {
      setSelectedMerchant(null);
    }
  };

  const selectMerchant = (m: Merchant) => {
    setFormData(prev => ({ 
      ...prev, 
      merchant_name: m.name,
      target_account_id: m.default_account_id,
      is_unique_provider: m.is_unique_provider
    }));
    setSelectedMerchant(m);
    setSelectedAccountName(m.default_account_name || null);
    setShowMerchantSuggestions(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validation: If unique provider, must have a category
    if (formData.is_unique_provider && !formData.target_account_id && !selectedMerchant) {
      setError("Unique merchants must have a default category.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = {
        ...formData,
        target_account_id: formData.is_unique_provider ? formData.target_account_id : undefined
      };
      const result = await createAndApplyRule(payload);
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
      <Card className="w-full max-w-md mx-auto shadow-2xl">
        <CardHeader>
          <CardTitle>Create Mapping Rule</CardTitle>
          <CardDescription>Link this bank string to a clean Merchant Banner.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="search_text" className="text-xs font-bold uppercase text-slate-500">Search Text (Branch)</Label>
              <Input 
                id="search_text" 
                name="search_text" 
                value={formData.search_text} 
                onChange={(e) => setFormData(prev => ({ ...prev, search_text: e.target.value }))}
                required 
                className="font-mono text-sm"
              />
            </div>

            <div className="space-y-2 relative">
              <Label htmlFor="merchant_name" className="text-xs font-bold uppercase text-slate-500">Merchant Banner</Label>
              <Input 
                id="merchant_name" 
                name="merchant_name" 
                value={formData.merchant_name} 
                onChange={handleMerchantInputChange} 
                onFocus={() => formData.merchant_name.length > 1 && setShowMerchantSuggestions(true)}
                required 
                autoComplete="off"
                placeholder="e.g. STARBUCKS"
              />
              
              {showMerchantSuggestions && filteredMerchants.length > 0 && (
                <div className="absolute z-[60] w-full mt-1 bg-white border border-slate-200 rounded-md shadow-xl overflow-hidden">
                  {filteredMerchants.map(m => (
                    <button
                      key={m.id}
                      type="button"
                      className="w-full text-left px-4 py-2 text-sm hover:bg-slate-100 border-b border-slate-50 last:border-none"
                      onClick={() => selectMerchant(m)}
                    >
                      <div className="font-bold">{m.name}</div>
                      <div className="text-[10px] text-slate-500">
                        {m.is_unique_provider ? `Category: ${m.default_account_name || 'None'}` : 'Multi-category Provider'}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {!selectedMerchant && (
              <>
                <div className="flex items-center space-x-2 bg-slate-50 p-3 rounded-md border border-slate-100">
                  <input 
                    type="checkbox"
                    id="is_unique"
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    checked={!formData.is_unique_provider}
                    onChange={(e) => setFormData(prev => ({ ...prev, is_unique_provider: !e.target.checked }))}
                  />
                  <Label htmlFor="is_unique" className="text-sm cursor-pointer">
                    This merchant sells multiple types of goods (e.g. Amazon, Walmart)
                  </Label>
                </div>

                {formData.is_unique_provider && (
                  <div className="space-y-2 animate-in fade-in duration-200">
                    <Label className="text-xs font-bold uppercase text-slate-500">Default Category</Label>
                    <div className="relative">
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full justify-between font-normal text-sm h-10"
                        onClick={() => setIsTreeOpen(!isTreeOpen)}
                      >
                        {selectedAccountName || "Select an account..."}
                      </Button>
                      
                      {isTreeOpen && (
                        <div className="absolute z-50 mt-2 w-full max-h-64 overflow-y-auto rounded-md border border-slate-200 bg-white p-2 shadow-2xl">
                          <AccountTree 
                            isSelectMode={true} 
                            onSelect={handleAccountSelect} 
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            )}

            {selectedMerchant && (
              <div className="bg-blue-50 p-3 rounded-md border border-blue-100 text-blue-800 text-sm">
                Linking to existing merchant: <strong>{selectedMerchant.name}</strong>
              </div>
            )}

            {error && <p className="text-destructive text-sm font-medium">{error}</p>}
            
            <div className="flex justify-end space-x-2 pt-2 border-t border-slate-100">
              <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                {loading ? 'Processing...' : 'Create & Apply'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};
