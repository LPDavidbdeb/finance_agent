import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { 
  fetchFamilyMembers, 
  createFamilyMember, 
  updateFamilyMember, 
  deleteFamilyMember,
  fetchSpendingEvolution,
  fetchSpendingByCategory,
  fetchAnnualStatements
} from '../api/client';
import { FamilyMemberModal } from '../components/FamilyMemberModal';
import { AddProductModal } from '../components/AddProductModal';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell
} from 'recharts';
import { Loader2, TrendingDown, TrendingUp, Wallet, Receipt, CreditCard, Users } from 'lucide-react';

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658', '#8dd1e1'];

export const Dashboard: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // Global Controls
  const currentYear = new Date().getFullYear();
  const [selectedYear, setSelectedYear] = useState(currentYear);
  const [selectedInterval, setSelectedInterval] = useState<'monthly' | 'bi-weekly'>('monthly');

  // Data State
  const [members, setMembers] = useState<any[]>([]);
  const [evolutionData, setEvolutionData] = useState<any[]>([]);
  const [categoryData, setCategoryData] = useState<any[]>([]);
  const [statements, setStatements] = useState<any>(null);
  
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
    loadAllData();
  }, [isAuthenticated, navigate, selectedYear, selectedInterval]);

  const loadAllData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const startDate = `${selectedYear}-01-01`;
      const endDate = `${selectedYear}-12-31`;

      const [membersData, evolution, categories, annual] = await Promise.all([
        fetchFamilyMembers(),
        fetchSpendingEvolution(startDate, endDate, selectedInterval),
        fetchSpendingByCategory(startDate, endDate),
        fetchAnnualStatements(selectedYear)
      ]);

      setMembers(membersData);
      setEvolutionData(evolution);
      setCategoryData(categories);
      setStatements(annual);
    } catch (err: any) {
      if (err.message === "Unauthorized") {
         navigate('/login');
      } else {
         setError(err.message || 'Failed to load dashboard data.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleMemberModalSubmit = async (formData: any) => {
    if (editingMember) {
      await updateFamilyMember(editingMember.id, formData);
    } else {
      await createFamilyMember(formData);
    }
    await loadAllData();
  };

  const handleDeleteMember = async (id: number) => {
    if (window.confirm("Are you sure you want to remove this family member?")) {
      try {
        await deleteFamilyMember(id);
        await loadAllData();
      } catch (err: any) {
        alert(err.message || 'Failed to delete member.');
      }
    }
  };

  if (loading && !statements) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="text-slate-500 font-medium">Building your command center...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Global Controls */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-4 rounded-lg shadow-sm border border-slate-200">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Financial Command Center</h1>
          <p className="text-sm text-slate-500">Real-time spending and net worth tracking</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex bg-slate-100 p-1 rounded-md">
            <button 
              className={`px-3 py-1 text-sm rounded ${selectedInterval === 'monthly' ? 'bg-white shadow-sm font-medium' : 'text-slate-600'}`}
              onClick={() => setSelectedInterval('monthly')}
            >
              Monthly
            </button>
            <button 
              className={`px-3 py-1 text-sm rounded ${selectedInterval === 'bi-weekly' ? 'bg-white shadow-sm font-medium' : 'text-slate-600'}`}
              onClick={() => setSelectedInterval('bi-weekly')}
            >
              Bi-Weekly
            </button>
          </div>
          <select 
            value={selectedYear}
            onChange={(e) => setSelectedYear(parseInt(e.target.value))}
            className="bg-white border border-slate-200 rounded-md px-3 py-1.5 text-sm font-medium focus:ring-2 focus:ring-blue-500 outline-none"
          >
            {[currentYear, currentYear - 1, currentYear - 2].map(y => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <Button onClick={loadAllData} variant="outline" size="sm" className="h-9">
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Card className="bg-red-50 border-red-200">
          <CardContent className="pt-6">
            <p className="text-red-600 font-medium">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Annual Summary Cards */}
      {statements && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          <Card className="bg-white border-l-4 border-l-green-500">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider">Revenue</CardDescription>
              <CardTitle className="text-xl flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-green-500" />
                ${statements.income_statement.revenue.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-white border-l-4 border-l-orange-500">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider">Expenses</CardDescription>
              <CardTitle className="text-xl flex items-center gap-2">
                <TrendingDown className="h-4 w-4 text-orange-500" />
                ${statements.income_statement.expenses.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-white border-l-4 border-l-blue-500">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider">Net Income</CardDescription>
              <CardTitle className={`text-xl ${statements.income_statement.net_income >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${statements.income_statement.net_income.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-white border-l-4 border-l-emerald-600">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider">Total Assets</CardDescription>
              <CardTitle className="text-xl flex items-center gap-2">
                <Wallet className="h-4 w-4 text-emerald-600" />
                ${statements.balance_sheet.assets.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-white border-l-4 border-l-red-500">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider">Liabilities</CardDescription>
              <CardTitle className="text-xl flex items-center gap-2 text-red-600">
                <Receipt className="h-4 w-4" />
                ${statements.balance_sheet.liabilities.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
          <Card className="bg-slate-900 text-white border-none shadow-lg transform scale-105 z-10">
            <CardHeader className="pb-2">
              <CardDescription className="text-xs uppercase font-bold tracking-wider text-slate-400">Net Worth</CardDescription>
              <CardTitle className="text-xl text-blue-400">
                ${statements.balance_sheet.equity.toLocaleString()}
              </CardTitle>
            </CardHeader>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Spending Evolution Chart */}
        <Card className="shadow-md overflow-hidden">
          <CardHeader className="bg-slate-50 border-b border-slate-100">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingDown className="h-5 w-5 text-orange-500" />
              Spending Evolution
            </CardTitle>
            <CardDescription>Chronological trend of expenses ({selectedInterval})</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[350px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={evolutionData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis 
                    dataKey="period" 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{fontSize: 12, fill: '#64748b'}}
                    dy={10}
                  />
                  <YAxis 
                    axisLine={false} 
                    tickLine={false} 
                    tick={{fontSize: 12, fill: '#64748b'}}
                    tickFormatter={(value) => `$${value}`}
                  />
                  <Tooltip 
                    cursor={{fill: '#f8fafc'}}
                    contentStyle={{borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)'}}
                    formatter={(value: any) => [`$${value.toLocaleString()}`, 'Expenses']}
                  />
                  <Bar dataKey="amount" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* CPI Category Breakdown Chart */}
        <Card className="shadow-md overflow-hidden">
          <CardHeader className="bg-slate-50 border-b border-slate-100">
            <CardTitle className="text-lg flex items-center gap-2">
              <PieChart className="h-5 w-5 text-blue-500" />
              Category Breakdown
            </CardTitle>
            <CardDescription>Proportion of spending across StatCan categories</CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="h-[350px] w-full flex items-center">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={categoryData}
                    cx="50%"
                    cy="50%"
                    innerRadius={80}
                    outerRadius={120}
                    paddingAngle={5}
                    dataKey="amount"
                    nameKey="category"
                  >
                    {categoryData.map((_entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value: any) => `$${value.toLocaleString()}`}
                  />
                  <Legend 
                    layout="vertical" 
                    align="right" 
                    verticalAlign="middle"
                    iconType="circle"
                    formatter={(value) => <span className="text-xs text-slate-600 font-medium">{value}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Household Roster Section */}
      <Card className="shadow-md">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4 border-b border-slate-100">
          <div>
            <CardTitle className="text-xl flex items-center gap-2">
              <Users className="h-5 w-5 text-blue-600" />
              Household Roster
            </CardTitle>
            <CardDescription>Manage your family members and their bank accounts</CardDescription>
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
        onSuccess={() => {}}
      />
    </div>
  );
};
