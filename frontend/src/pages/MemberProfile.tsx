import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { fetchFamilyMember, fetchMemberProducts } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const MemberProfile: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [member, setMember] = useState<any | null>(null);
  const [products, setProducts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    
    if (id) {
      loadProfileData(Number(id));
    }
  }, [id, isAuthenticated, navigate]);

  const loadProfileData = async (memberId: number) => {
    try {
      setLoading(true);
      setError(null);
      
      // Fetch both member details and their products in parallel
      const [memberData, productsData] = await Promise.all([
        fetchFamilyMember(memberId),
        fetchMemberProducts(memberId)
      ]);
      
      setMember(memberData);
      setProducts(productsData);
    } catch (err: any) {
      if (err.message === "Unauthorized") {
        navigate('/login');
      } else {
        setError(err.message || "Failed to load member profile.");
      }
    } finally {
      setLoading(false);
    }
  };

  // Group products by their accounting post
  const groupedProducts = products.reduce((acc: any, product: any) => {
    const post = product.accounting_post || 'Uncategorized';
    if (!acc[post]) {
      acc[post] = [];
    }
    acc[post].push(product);
    return acc;
  }, {});

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading profile...</div>;
  }

  if (error || !member) {
    return (
      <div className="p-8 text-center">
        <p className="text-destructive mb-4">{error || "Member not found."}</p>
        <Button onClick={() => navigate('/dashboard')} variant="outline">Return to Dashboard</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      {/* Header Section */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            {member.first_name} {member.last_name}
          </h1>
          <p className="text-slate-500 mt-1 flex items-center space-x-2">
            <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold">
              {member.role}
            </span>
            <span>•</span>
            <span>{member.current_age} years old</span>
          </p>
        </div>
        <Button onClick={() => navigate('/dashboard')} variant="outline">
          Back to Dashboard
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        
        {/* Left Column: Milestones */}
        <div className="md:col-span-1 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Financial Milestones</CardTitle>
              <CardDescription>Key dates for planning</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-4">
                {Object.entries(member.financial_milestones || {}).map(([key, dateValue]) => {
                  // Format the key to be readable (e.g., "resp_grant_deadline" -> "RESP Grant Deadline")
                  const formattedLabel = key.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
                  
                  return (
                    <li key={key} className="flex flex-col">
                      <span className="text-sm font-medium text-slate-700">{formattedLabel}</span>
                      <span className="text-sm text-slate-500">{String(dateValue)}</span>
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Financial Products */}
        <div className="md:col-span-2 space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div>
                <CardTitle className="text-lg">Financial Products</CardTitle>
                <CardDescription>Grouped by accounting category.</CardDescription>
              </div>
              <Button size="sm" onClick={() => navigate('/dashboard')} variant="secondary">
                Manage
              </Button>
            </CardHeader>
            <CardContent>
              {products.length === 0 ? (
                <p className="text-sm text-slate-500 py-4 text-center border-2 border-dashed rounded-md my-4">
                  No financial products linked yet.
                </p>
              ) : (
                <div className="space-y-8 mt-4">
                  {Object.entries(groupedProducts).map(([postName, items]: [string, any]) => (
                    <div key={postName}>
                      <h3 className="text-md font-semibold text-slate-800 mb-3 border-b pb-1">
                        {postName}
                      </h3>
                      <div className="relative w-full overflow-auto">
                        <table className="w-full caption-bottom text-sm">
                          <thead className="[&_tr]:border-b">
                            <tr className="border-b transition-colors hover:bg-slate-100/50">
                              <th className="h-10 px-4 text-left align-middle font-medium text-slate-500">Institution</th>
                              <th className="h-10 px-4 text-left align-middle font-medium text-slate-500">Type</th>
                              <th className="h-10 px-4 text-left align-middle font-medium text-slate-500">Account Name</th>
                              <th className="h-10 px-4 text-left align-middle font-medium text-slate-500">Number</th>
                            </tr>
                          </thead>
                          <tbody className="[&_tr:last-child]:border-0">
                            {items.map((product: any) => (
                              <tr key={product.id} className="border-b transition-colors hover:bg-slate-100/50">
                                <td className="p-4 align-middle font-medium">{product.institution_name}</td>
                                <td className="p-4 align-middle">
                                  <span className="inline-flex items-center rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-800">
                                    {product.product_type}
                                  </span>
                                </td>
                                <td className="p-4 align-middle">
                                  <Link to={`/dashboard/product/${product.id}`} className="text-blue-600 hover:underline">
                                    {product.account_name}
                                  </Link>
                                </td>
                                <td className="p-4 align-middle font-mono text-slate-500">
                                  {product.account_number ? `...${product.account_number.slice(-4)}` : '-'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};