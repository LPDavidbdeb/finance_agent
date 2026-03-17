import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { fetchInstitutions, createFinancialProduct } from '../api/client';

interface AddProductModalProps {
  isOpen: boolean;
  onClose: () => void;
  memberId: number | null;
  onSuccess: () => void;
}

export const AddProductModal: React.FC<AddProductModalProps> = ({ isOpen, onClose, memberId, onSuccess }) => {
  const [institutions, setInstitutions] = useState<any[]>([]);
  const [formData, setFormData] = useState({
    institution_id: '',
    product_type: 'CHECKING',
    product_name: '',
  });
  const [loading, setLoading] = useState(false);
  const [fetchingInstitutions, setFetchingInstitutions] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadInstitutions();
      setFormData({
        institution_id: '',
        product_type: 'CHECKING',
        product_name: '',
      });
      setError(null);
    }
  }, [isOpen]);

  const loadInstitutions = async () => {
    try {
      setFetchingInstitutions(true);
      const data = await fetchInstitutions();
      setInstitutions(data);
      if (data.length > 0) {
        setFormData(prev => ({ ...prev, institution_id: String(data[0].id) }));
      }
    } catch (err: any) {
      setError('Failed to load institutions.');
    } finally {
      setFetchingInstitutions(false);
    }
  };

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memberId) {
      setError("No family member selected.");
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const payload = {
        institution_id: Number(formData.institution_id),
        product_type: formData.product_type,
        product_name: formData.product_name,
        owner_id: memberId
      };
      
      await createFinancialProduct(payload);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to create financial product.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-md mx-auto">
        <CardHeader>
          <CardTitle>Add Financial Product</CardTitle>
          <CardDescription>Link a bank account or credit card to this member.</CardDescription>
        </CardHeader>
        <CardContent>
          {fetchingInstitutions ? (
            <p className="text-sm text-slate-500">Loading institutions...</p>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              
              <div className="space-y-2">
                <Label htmlFor="institution_id">Institution</Label>
                <select 
                  id="institution_id" 
                  name="institution_id" 
                  value={formData.institution_id} 
                  onChange={handleChange}
                  required
                  className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  <option value="" disabled>Select Institution</option>
                  {institutions.map(inst => (
                    <option key={inst.id} value={inst.id}>{inst.name}</option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="product_type">Product Type</Label>
                <select 
                  id="product_type" 
                  name="product_type" 
                  value={formData.product_type} 
                  onChange={handleChange}
                  required
                  className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  <option value="CHECKING">Checking Account</option>
                  <option value="SAVINGS">Savings Account</option>
                  <option value="CREDIT_CARD">Credit Card</option>
                  <option value="LOAN">Loan / Mortgage</option>
                  <option value="INVESTMENT">Investment Account</option>
                  <option value="REGISTERED">Registered Account (TFSA, RRSP)</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="product_name">Product Name</Label>
                <Input 
                  id="product_name" 
                  name="product_name" 
                  placeholder='e.g., "CashBack Visa" or "Everyday Checking"' 
                  value={formData.product_name} 
                  onChange={handleChange} 
                  required 
                />
              </div>

              {error && <p className="text-destructive text-sm">{error}</p>}
              
              <div className="flex justify-end space-x-2 pt-4">
                <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
                  Cancel
                </Button>
                <Button type="submit" disabled={loading || !formData.institution_id}>
                  {loading ? 'Adding...' : 'Add Product'}
                </Button>
              </div>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
};