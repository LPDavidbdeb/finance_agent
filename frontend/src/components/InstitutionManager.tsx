import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { 
  fetchInstitutions, 
  createInstitution, 
  updateInstitution, 
  deleteInstitution 
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const InstitutionManager: React.FC = () => {
  const [institutions, setInstitutions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  
  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingInstitution, setEditingInstitution] = useState<any | null>(null);
  const [formData, setFormData] = useState({ name: '' });
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    loadInstitutions();
  }, [isAuthenticated, navigate]);

  const loadInstitutions = async () => {
    try {
      setLoading(true);
      const data = await fetchInstitutions();
      setInstitutions(data);
    } catch (err: any) {
      if (err.message === "Unauthorized") {
         navigate('/login');
      } else {
         setError(err.message || 'Failed to load institutions.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAddClick = () => {
    setEditingInstitution(null);
    setFormData({ name: '' });
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleEditClick = (inst: any) => {
    setEditingInstitution(inst);
    setFormData({ name: inst.name });
    setModalError(null);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Are you sure you want to delete this institution?")) {
      setDeleteError(null); // Clear previous errors
      try {
        await deleteInstitution(id);
        await loadInstitutions(); 
      } catch (err: any) {
        // Display the specific ProtectedError if caught
        setDeleteError(err.message || 'Failed to delete institution.');
        // Auto-clear the error after 5 seconds
        setTimeout(() => setDeleteError(null), 5000);
      }
    }
  };

  const handleModalSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setModalLoading(true);
    setModalError(null);
    
    try {
      if (editingInstitution) {
        await updateInstitution(editingInstitution.id, formData);
      } else {
        await createInstitution(formData);
      }
      setIsModalOpen(false);
      await loadInstitutions();
    } catch (err: any) {
        setModalError(err.message || 'Failed to save institution.');
    } finally {
        setModalLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Bank Manager</h1>
      </div>

      {deleteError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded relative" role="alert">
          <strong className="font-bold">Error: </strong>
          <span className="block sm:inline">{deleteError}</span>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle>Supported Institutions</CardTitle>
            <CardDescription>Manage the banks available for connection.</CardDescription>
          </div>
          <Button onClick={handleAddClick} size="sm">
            + Add Bank
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500 py-4">Loading institutions...</p>
          ) : error ? (
            <p className="text-sm text-destructive py-4">{error}</p>
          ) : institutions.length === 0 ? (
            <p className="text-sm text-slate-500 py-4">No institutions found. Add one to get started.</p>
          ) : (
            <div className="relative w-full overflow-auto mt-4">
              <table className="w-full caption-bottom text-sm">
                <thead className="[&_tr]:border-b">
                  <tr className="border-b transition-colors hover:bg-slate-100/50 data-[state=selected]:bg-slate-100">
                    <th className="h-12 px-4 text-left align-middle font-medium text-slate-500">ID</th>
                    <th className="h-12 px-4 text-left align-middle font-medium text-slate-500">Institution Name</th>
                    <th className="h-12 px-4 text-right align-middle font-medium text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="[&_tr:last-child]:border-0">
                  {institutions.map((inst) => (
                    <tr key={inst.id} className="border-b transition-colors hover:bg-slate-100/50 data-[state=selected]:bg-slate-100">
                      <td className="p-4 align-middle text-slate-500">{inst.id}</td>
                      <td className="p-4 align-middle font-medium">{inst.name}</td>
                      <td className="p-4 align-middle text-right space-x-2 flex justify-end">
                        <Button variant="ghost" size="sm" className="text-blue-600" onClick={() => handleEditClick(inst)}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => handleDelete(inst.id)}>
                          Delete
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Inline Modal (Alternatively could be its own file like FamilyMemberModal) */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <Card className="w-full max-w-sm mx-auto">
            <CardHeader>
              <CardTitle>{editingInstitution ? 'Edit' : 'Add'} Institution</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleModalSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Institution Name</Label>
                  <Input 
                    id="name" 
                    name="name" 
                    value={formData.name} 
                    onChange={(e) => setFormData({ name: e.target.value })} 
                    required 
                    autoFocus
                  />
                </div>
                {modalError && <p className="text-destructive text-sm">{modalError}</p>}
                <div className="flex justify-end space-x-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)} disabled={modalLoading}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={modalLoading || !formData.name.trim()}>
                    {modalLoading ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
};