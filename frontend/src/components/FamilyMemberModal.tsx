import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';

interface FamilyMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: any) => Promise<void>;
  initialData?: any;
}

export const FamilyMemberModal: React.FC<FamilyMemberModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  initialData
}) => {
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    date_of_birth: '',
    sex: 'M',
    role: 'CHILD',
    expected_age_at_retirement: 65,
    expected_age_at_death: 99,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Populate form if editing
  useEffect(() => {
    if (initialData) {
      setFormData({
        first_name: initialData.first_name || '',
        last_name: initialData.last_name || '',
        date_of_birth: initialData.date_of_birth || '',
        sex: initialData.sex || 'M',
        role: initialData.role || 'CHILD',
        expected_age_at_retirement: initialData.expected_age_at_retirement || 65,
        expected_age_at_death: initialData.expected_age_at_death || 99,
      });
    } else {
      // Reset form
      setFormData({
        first_name: '',
        last_name: '',
        date_of_birth: '',
        sex: 'M',
        role: 'CHILD',
        expected_age_at_retirement: 65,
        expected_age_at_death: 99,
      });
    }
    setError(null);
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: type === 'number' ? Number(value) : value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await onSubmit(formData);
      onClose(); // Close on success
    } catch (err: any) {
      setError(err.message || 'Failed to save family member.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <Card className="w-full max-w-md mx-auto max-h-[90vh] overflow-y-auto">
        <CardHeader>
          <CardTitle>{initialData ? 'Edit' : 'Add'} Family Member</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="first_name">First Name</Label>
                <Input id="first_name" name="first_name" value={formData.first_name} onChange={handleChange} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="last_name">Last Name</Label>
                <Input id="last_name" name="last_name" value={formData.last_name} onChange={handleChange} required />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="date_of_birth">Date of Birth</Label>
              <Input id="date_of_birth" name="date_of_birth" type="date" value={formData.date_of_birth} onChange={handleChange} required />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sex">Sex</Label>
                <select 
                  id="sex" 
                  name="sex" 
                  value={formData.sex} 
                  onChange={handleChange}
                  className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  <option value="M">Male</option>
                  <option value="F">Female</option>
                  <option value="O">Other</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role</Label>
                <select 
                  id="role" 
                  name="role" 
                  value={formData.role} 
                  onChange={handleChange}
                  className="flex h-10 w-full rounded-md border border-slate-300 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
                >
                  <option value="PARENT">Parent</option>
                  <option value="CHILD">Child</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="expected_age_at_retirement">Retirement Age</Label>
                <Input id="expected_age_at_retirement" name="expected_age_at_retirement" type="number" min="0" max="120" value={formData.expected_age_at_retirement} onChange={handleChange} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="expected_age_at_death">End of Plan Age</Label>
                <Input id="expected_age_at_death" name="expected_age_at_death" type="number" min="0" max="120" value={formData.expected_age_at_death} onChange={handleChange} required />
              </div>
            </div>

            {error && <p className="text-destructive text-sm">{error}</p>}
            
            <div className="flex justify-end space-x-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading}>
                {loading ? 'Saving...' : 'Save'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};