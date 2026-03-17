import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { 
  fetchFamilyMembers, 
  createFamilyMember, 
  updateFamilyMember, 
  deleteFamilyMember 
} from '../api/client';
import { FamilyMemberModal } from './FamilyMemberModal';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const Dashboard: React.FC = () => {
  const [members, setMembers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingMember, setEditingMember] = useState<any | null>(null);

  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

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
      const data = await fetchFamilyMembers();
      setMembers(data);
    } catch (err: any) {
      if (err.message === "Unauthorized") {
         navigate('/login');
      } else {
         setError(err.message || 'Failed to load household roster.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleAddClick = () => {
    setEditingMember(null);
    setIsModalOpen(true);
  };

  const handleEditClick = (member: any) => {
    setEditingMember(member);
    setIsModalOpen(true);
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Are you sure you want to remove this family member?")) {
      try {
        await deleteFamilyMember(id);
        await loadMembers(); // Refresh list
      } catch (err: any) {
        alert(err.message || 'Failed to delete member.');
      }
    }
  };

  const handleModalSubmit = async (formData: any) => {
    if (editingMember) {
      await updateFamilyMember(editingMember.id, formData);
    } else {
      await createFamilyMember(formData);
    }
    await loadMembers(); // Refresh list after save
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">Dashboard</h1>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div>
            <CardTitle>Household Roster</CardTitle>
            <CardDescription>Manage the people in your financial plan.</CardDescription>
          </div>
          <Button onClick={handleAddClick} size="sm">
            + Add Person
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500 py-4">Loading roster...</p>
          ) : error ? (
            <p className="text-sm text-destructive py-4">{error}</p>
          ) : members.length === 0 ? (
            <p className="text-sm text-slate-500 py-4">No family members found. Add someone to get started.</p>
          ) : (
            <div className="relative w-full overflow-auto mt-4">
              <table className="w-full caption-bottom text-sm">
                <thead className="[&_tr]:border-b">
                  <tr className="border-b transition-colors hover:bg-slate-100/50 data-[state=selected]:bg-slate-100">
                    <th className="h-12 px-4 text-left align-middle font-medium text-slate-500">Name</th>
                    <th className="h-12 px-4 text-left align-middle font-medium text-slate-500">Role</th>
                    <th className="h-12 px-4 text-left align-middle font-medium text-slate-500">Age</th>
                    <th className="h-12 px-4 text-right align-middle font-medium text-slate-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="[&_tr:last-child]:border-0">
                  {members.map((member) => (
                    <tr key={member.id} className="border-b transition-colors hover:bg-slate-100/50 data-[state=selected]:bg-slate-100">
                      <td className="p-4 align-middle font-medium">{member.first_name} {member.last_name}</td>
                      <td className="p-4 align-middle">
                        <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
                          {member.role}
                        </span>
                      </td>
                      <td className="p-4 align-middle text-slate-500">{member.current_age} yrs</td>
                      <td className="p-4 align-middle text-right">
                        <Button variant="ghost" size="sm" className="mr-2 text-blue-600" onClick={() => handleEditClick(member)}>
                          Edit
                        </Button>
                        <Button variant="ghost" size="sm" className="text-destructive" onClick={() => handleDelete(member.id)}>
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
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSubmit={handleModalSubmit}
        initialData={editingMember}
      />
    </div>
  );
};