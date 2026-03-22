import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { 
  fetchFamilyMembers, 
  createFamilyMember, 
  updateFamilyMember, 
  deleteFamilyMember 
} from '../api/client';
import { FamilyMemberModal } from '../components/FamilyMemberModal';
import { AddProductModal } from '../components/AddProductModal';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, Users, CreditCard } from 'lucide-react';

export const FamilyManager: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modals State
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<any | null>(null);
  const [isProductModalOpen, setIsProductModalOpen] = useState(false);
  const [selectedMemberIdForProduct, setSelectedMemberIdForProduct] = useState<number | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    loadMembers();
  }, [isAuthenticated, navigate]);

  const loadMembers = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchFamilyMembers();
      setMembers(data);
    } catch (err: any) {
      if (err.message === "Unauthorized") {
         navigate('/login');
      } else {
         setError(err.message || 'Failed to load family members.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleMemberModalSubmit = async (formData: any) => {
    try {
      if (editingMember) {
        await updateFamilyMember(editingMember.id, formData);
      } else {
        await createFamilyMember(formData);
      }
      await loadMembers();
      setIsMemberModalOpen(false);
    } catch (err: any) {
      alert(err.message || 'Failed to save family member.');
    }
  };

  const handleDeleteMember = async (id: number) => {
    if (window.confirm("Are you sure you want to remove this family member?")) {
      try {
        await deleteFamilyMember(id);
        await loadMembers();
      } catch (err: any) {
        alert(err.message || 'Failed to delete member.');
      }
    }
  };

  if (loading && members.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="text-slate-500 font-medium">Loading household roster...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12 max-w-5xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Family Management</h1>
        <p className="text-slate-500 mt-1">Manage household members and their connected financial products.</p>
      </div>

      {error && (
        <Card className="bg-red-50 border-red-200">
          <CardContent className="pt-6">
            <p className="text-red-600 font-medium">{error}</p>
          </CardContent>
        </Card>
      )}

      <Card className="shadow-md">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b border-slate-100">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-600" />
              Household Roster
            </CardTitle>
            <CardDescription>Members of your financial family</CardDescription>
          </div>
          <Button onClick={() => { setEditingMember(null); setIsMemberModalOpen(true); }} size="sm">
            + Add Person
          </Button>
        </CardHeader>
        <CardContent className="pt-6">
          {members.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-slate-500 font-medium">No family members found.</p>
              <Button variant="link" onClick={() => setIsMemberModalOpen(true)}>Add your first person</Button>
            </div>
          ) : (
            <div className="relative w-full overflow-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-slate-500">
                    <th className="h-10 px-4 text-left font-medium">Name</th>
                    <th className="h-10 px-4 text-left font-medium">Role</th>
                    <th className="h-10 px-4 text-left font-medium">Age</th>
                    <th className="h-10 px-4 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {members.map((member) => (
                    <tr key={member.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="p-4 font-semibold text-slate-900">
                        <Link to={`/dashboard/member/${member.id}`} className="hover:text-blue-600 hover:underline">
                          {member.first_name} {member.last_name}
                        </Link>
                      </td>
                      <td className="p-4">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          member.role === 'PARENT' ? 'bg-blue-50 text-blue-700' : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {member.role}
                        </span>
                      </td>
                      <td className="p-4 text-slate-500 font-mono">{member.current_age} yrs</td>
                      <td className="p-4 text-right space-x-2">
                        <Button variant="outline" size="sm" onClick={() => { setSelectedMemberIdForProduct(member.id); setIsProductModalOpen(true); }}>
                          <CreditCard className="h-3.5 w-3.5 mr-1" />
                          Add Product
                        </Button>
                        <Button variant="ghost" size="sm" className="text-blue-600" onClick={() => { setEditingMember(member); setIsMemberModalOpen(true); }}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" className="text-red-500" onClick={() => handleDeleteMember(member.id)}>
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

      <FamilyMemberModal 
        isOpen={isMemberModalOpen}
        onClose={() => setIsMemberModalOpen(false)}
        onSubmit={handleMemberModalSubmit}
        initialData={editingMember}
      />
      
      <AddProductModal 
        isOpen={isProductModalOpen}
        onClose={() => setIsProductModalOpen(false)}
        memberId={selectedMemberIdForProduct}
        onSuccess={loadMembers}
      />
    </div>
  );
};
