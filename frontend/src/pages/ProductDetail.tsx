import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { fetchFinancialProduct, fetchProductStatements, uploadStatement } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { StagedTransactionsTable } from '../components/StagedTransactionsTable';

type StatementImport = {
  id: number;
  upload_date: string;
  file_name: string;
  file_url?: string;
  processed_by_ai: boolean;
  processed_by_python: boolean;
  status: string;
};

type Product = {
  id: number;
  account_name: string;
  institution_name: string;
  product_type: string;
  account_number?: string;
  owner_id?: number;
};

export const ProductDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [statements, setStatements] = useState<StatementImport[]>([]);
  const [stagedTransactionsRefresh, setStagedTransactionsRefresh] = useState(0);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    if (id) {
      const productId = Number(id);
      loadProductData(productId);
      loadStatements(productId);
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

  const loadStatements = async (productId: number) => {
    try {
      const data = await fetchProductStatements(productId);
      setStatements(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch statements';
      if (errorMessage === 'Unauthorized') {
        navigate('/login');
      }
    }
  };

  const handleUploadClick = () => {
    if (uploading) return;
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !id) return;

    setUploadMessage(null);
    try {
      setUploading(true);
      await uploadStatement(Number(id), file);
      setUploadMessage('Statement uploaded to staging area successfully.');
      await loadStatements(Number(id));
      // Trigger StagedTransactionsTable to refresh
      setStagedTransactionsRefresh((prev) => prev + 1);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed.';
      if (errorMessage === 'Unauthorized') {
        navigate('/login');
      } else {
        setUploadMessage(errorMessage);
      }
    } finally {
      setUploading(false);
      event.target.value = '';
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
            <div
              className="border-2 border-dashed border-slate-300 rounded-lg p-12 text-center hover:bg-slate-50 transition-colors cursor-pointer"
              onClick={handleUploadClick}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={handleFileSelected}
              />
               <div className="flex flex-col items-center justify-center space-y-2">
                  <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-slate-400"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" x2="12" y1="3" y2="15"></line></svg>
                  <p className="text-sm font-medium text-slate-700">{uploading ? 'Uploading...' : 'Click to upload or drag and drop'}</p>
                  <p className="text-xs text-slate-500">PDF statements only (Max 10MB)</p>
               </div>
            </div>
            {uploadMessage && (
              <p className="text-sm mt-3 text-center text-slate-700">{uploadMessage}</p>
            )}
            <p className="text-sm text-slate-500 mt-4 text-center italic">
              Files are staged only. No AI extraction is triggered at upload time.
            </p>

            <div className="mt-6">
              <h3 className="text-sm font-semibold text-slate-800 mb-3">Staging Area</h3>
              <div className="overflow-x-auto border border-slate-200 rounded-md">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead className="bg-slate-50">
                    <tr>
                      <th className="px-4 py-2 text-left font-medium text-slate-600">Upload Date</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-600">File Name</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-600">Processed by AI</th>
                      <th className="px-4 py-2 text-left font-medium text-slate-600">Processed by Python</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {statements.length === 0 && (
                      <tr>
                        <td className="px-4 py-3 text-slate-500" colSpan={4}>No staged files yet.</td>
                      </tr>
                    )}
                    {statements.map((statement) => (
                      <tr key={statement.id}>
                        <td className="px-4 py-3 text-slate-700">{new Date(statement.upload_date).toLocaleString()}</td>
                        <td className="px-4 py-3 text-slate-700">
                          {statement.file_url ? (
                            <a className="text-blue-600 hover:underline" href={statement.file_url} target="_blank" rel="noreferrer">
                              {statement.file_name}
                            </a>
                          ) : statement.file_name}
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${statement.processed_by_ai ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-700'}`}>
                            {statement.processed_by_ai ? 'Yes' : 'No'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold ${statement.processed_by_python ? 'bg-green-100 text-green-800' : 'bg-slate-100 text-slate-700'}`}>
                            {statement.processed_by_python ? 'Yes' : 'No'}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </CardContent>
        </Card>

        <StagedTransactionsTable productId={Number(id!)} refreshTrigger={stagedTransactionsRefresh} />
      </div>
    </div>
  );
};