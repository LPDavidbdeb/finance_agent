import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { createAndApplyRule, fetchMerchants } from '../api/client';
import { AccountTree } from './AccountTree';
import { Loader2 } from 'lucide-react';
import { TRANSACTION_ROUTING_RULE_LABEL } from '../utils/transactionVocabulary';

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
  institutionId: number;
  preselectedMerchant?: Merchant | null;
}

export const CreateRuleModal: React.FC<CreateRuleModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  rawDescription,
  institutionId,
  preselectedMerchant
}) => {
  const [formData, setFormData] = useState({
    search_text: '',
    merchant_name: '',
    target_account_id: 0 as number | undefined,
    is_unique_provider: true,
    institution_id: undefined as number | undefined,
    min_amount: '' as string,
    max_amount: '' as string,
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
        search_text: rawDescription.trim(),
        merchant_name: preselectedMerchant ? preselectedMerchant.name : '',
        target_account_id: preselectedMerchant?.default_account_id || 0,
        is_unique_provider: preselectedMerchant ? preselectedMerchant.is_unique_provider : true,
        institution_id: institutionId,
        min_amount: '',
        max_amount: '',
      });

      if (preselectedMerchant) {
        setSelectedMerchant(preselectedMerchant);
        setSelectedAccountName(preselectedMerchant.default_account_name || null);
      } else {
        setSelectedAccountName(null);
        setSelectedMerchant(null);
      }

      setIsTreeOpen(false);
      loadMerchants();
    }
    setError(null);
  }, [isOpen, rawDescription, institutionId, preselectedMerchant]);

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

    if (!formData.institution_id) {
      setError("System Error: No financial institution context found for this product.");
      return;
    }

    // Validation: If unique provider, must have a route
    if (formData.is_unique_provider && !formData.target_account_id && !selectedMerchant) {
      setError("Unique merchants must have a default route.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const payload = {
        ...formData,
        search_text: formData.search_text.trim(),
        target_account_id: formData.is_unique_provider ? formData.target_account_id : undefined,
        min_amount: formData.min_amount ? parseFloat(formData.min_amount) : undefined,
        max_amount: formData.max_amount ? parseFloat(formData.max_amount) : undefined,
      };
      const result = await createAndApplyRule(payload);
      onSuccess(result.updated_count);
      onClose();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create routing rule.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <Card className="w-full max-w-5xl mx-auto shadow-2xl">
        <CardHeader className="border-b border-slate-200">
          <CardTitle>{TRANSACTION_ROUTING_RULE_LABEL}</CardTitle>
          <CardDescription>Define transaction matching criteria and route it to an account.</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="grid grid-cols-2 gap-0 min-h-[600px]">
            {/* Left Column: Form */}
            <div className="p-6 overflow-y-auto border-r border-slate-200">
              <form onSubmit={handleSubmit} className="space-y-5">
                <div className="space-y-2">
                  <Label htmlFor="search_text" className="text-xs font-bold uppercase text-slate-500">
                    Search Text (Routing Description)
                  </Label>
                  <Input
                    id="search_text"
                    name="search_text"
                    value={formData.search_text}
                    onChange={(e) => setFormData(prev => ({ ...prev, search_text: e.target.value }))}
                    required
                    className="font-mono text-sm"
                    placeholder="e.g. STARBUCKS COFFEE #1234"
                  />
                </div>

                <div className="space-y-2 relative">
                  <Label htmlFor="merchant_name" className="text-xs font-bold uppercase text-slate-500">
                    Merchant Banner
                  </Label>
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
                            {m.is_unique_provider ? `Route: ${m.default_account_name || 'None'}` : 'Multi-route Provider'}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {/* Amount Range Section */}
                <div className="bg-slate-50 p-4 rounded-md border border-slate-200">
                  <Label className="text-xs font-bold uppercase text-slate-500 block mb-3">
                    Optional: Amount Range
                  </Label>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label htmlFor="min_amount" className="text-xs text-slate-600">
                        Min Amount ($)
                      </Label>
                      <Input
                        id="min_amount"
                        name="min_amount"
                        type="number"
                        step="0.01"
                        min="0"
                        value={formData.min_amount}
                        onChange={(e) => setFormData(prev => ({ ...prev, min_amount: e.target.value }))}
                        placeholder="e.g. 10.00"
                        className="text-sm"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="max_amount" className="text-xs text-slate-600">
                        Max Amount ($)
                      </Label>
                      <Input
                        id="max_amount"
                        name="max_amount"
                        type="number"
                        step="0.01"
                        min="0"
                        value={formData.max_amount}
                        onChange={(e) => setFormData(prev => ({ ...prev, max_amount: e.target.value }))}
                        placeholder="e.g. 50.00"
                        className="text-sm"
                      />
                    </div>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-2">
                    Use these to distinguish recurring transactions with similar descriptions (e.g., home vs. auto insurance)
                  </p>
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
                        Multi-route provider (e.g. Amazon, Walmart)
                      </Label>
                    </div>

                    {formData.is_unique_provider && (
                      <div className="space-y-2 animate-in fade-in duration-200">
                        <Label className="text-xs font-bold uppercase text-slate-500">Default Route</Label>
                        <Button
                          type="button"
                          variant="outline"
                          className="w-full justify-between font-normal text-sm h-10"
                          onClick={() => setIsTreeOpen(!isTreeOpen)}
                        >
                          {selectedAccountName || "Select an account (use tree on right)..."}
                        </Button>
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

                <div className="flex justify-end space-x-2 pt-4 border-t border-slate-200">
                  <Button type="button" variant="ghost" onClick={onClose} disabled={loading}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={loading}>
                    {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    {loading ? 'Processing...' : 'Create & Apply'}
                  </Button>
                </div>
              </form>
            </div>

            {/* Right Column: Account Tree */}
            <div className="p-6 overflow-y-auto bg-slate-50">
              <div className="space-y-3">
                <div>
                  <Label className="text-xs font-bold uppercase text-slate-500">Account Hierarchy</Label>
                  <p className="text-xs text-slate-600 mt-1">
                    {formData.is_unique_provider ? 'Click to select a route' : 'N/A for multi-route providers'}
                  </p>
                </div>

                {formData.is_unique_provider && (
                  <div className="bg-white border border-slate-200 rounded-md p-3 max-h-[520px] overflow-y-auto">
                    <AccountTree
                      isSelectMode={true}
                      onSelect={handleAccountSelect}
                    />
                  </div>
                )}

                {!formData.is_unique_provider && (
                  <div className="bg-white border border-slate-200 rounded-md p-4 text-center text-slate-500 h-[520px] flex items-center justify-center">
                    <p className="text-sm">Multi-route providers don't require a default account.</p>
                  </div>
                )}

                {selectedAccountName && (
                  <div className="bg-green-50 p-3 rounded-md border border-green-200 text-green-800 text-sm">
                    ✓ Selected: <strong>{selectedAccountName}</strong>
                  </div>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
