import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { fetchFinancialProduct } from '../api/client';
import { useAuth } from '../context/AuthContext';

export const ProductDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [product, setProduct] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    
    if (id) {
      loadProductData(Number(id));
    }
  }, [id, isAuthenticated, navigate]);

  const loadProductData = async (productId: number) => {
    try {
      setLoading(true);
      setError(null);
      
      const productData = await fetchFinancialProduct(productId);
      setProduct(productData);
    } catch (err: any) {
      if (err.message === "Unauthorized") {
        navigate('/login');
      } else {
        setError(err.message || "Failed to load product details.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center text-slate-500">Loading product...</div>;
  }

  if (error || !product) {
    return (
      <div className="p-8 text-center">
        <p className="text-destructive mb-4">{error || "Product not found."}</p>
        <Button onClick={() => navigate(-1)} variant="outline">Go Back</Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto w-full">
      {/* Header Section */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">
            {product.account_name}
          </h1>
          <p className="text-slate-500 mt-1 flex items-center space-x-2">
            <span>{product.institution_name}</span>
            <span>•</span>
            <span className="inline-flex items-center rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-800">
              {product.product_type}
            </span>
            {product.account_number && (
              <>
                <span>•</span>
                <span className="font-mono text-sm">...{product.account_number.slice(-4)}</span>
              </>
            )}
          </p>
        </div>
        <div className="space-x-2">
          {product.owner_id && (
            <Button onClick={() => navigate(`/dashboard/member/${product.owner_id}`)} variant="outline">
              Back to Profile
            </Button>
          )}
          {!product.owner_id && (
            <Button onClick={() => navigate('/dashboard')} variant="outline">
              Back to Dashboard
            </Button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Statement Upload</CardTitle>
            <CardDescription>
              Upload your PDF statements here to automatically extract and reconcile transactions.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-slate-300 rounded-lg p-12 text-center hover:bg-slate-50 transition-colors cursor-pointer">
               <div className="flex flex-col items-center justify-center space-y-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinelinejoin="round" className="text-slate-400"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" x2="12" y1="3" y2="15"></line></svg>
                  <p className="text-sm font-medium text-slate-700">Click to upload or drag and drop</p>
                  <p className="text-xs text-slate-500">PDF statements only (Max 10MB)</p>
               </div>
            </div>
            <p className="text-sm text-slate-500 mt-4 text-center italic">
              Note: AI Extraction pipeline will process the uploaded PDF.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};