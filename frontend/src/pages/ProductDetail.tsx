import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import {
  fetchFinancialProduct,
  fetchProductStatements,
  uploadStatement,
  deleteStatementImport,
  fetchStatementMonths,
  fetchStatementTransactions,
  fetchStagedTransactions,
  fetchCeleryStatus,
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { TransactionListTable } from '../components/TransactionListTable';
import { useToast } from '../components/ui/use-toast';
import { Calendar, Upload, Trash2, Loader2, Inbox } from 'lucide-react';
import {
  TRANSACTION_ROUTING_BACKLOG_DESCRIPTION,
  TRANSACTION_ROUTING_BACKLOG_TITLE,
} from '../utils/transactionVocabulary';

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
  institution_id: number;
  product_type: string;
  account_number?: string;
  owner_id?: number;
};

type StatementMonth = {
  month: string;
  display_name: string;
  transaction_count: number;
};

export const ProductDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuth();
  const { toast } = useToast();

  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Upload State
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);

  // Staging Area State
  const [statements, setStatements] = useState<StatementImport[]>([]);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Virtual Statement Navigator State
  const [months, setMonths] = useState<StatementMonth[]>([]);
  const [selectedMonth, setSelectedMonth] = useState<StatementMonth | null>(null);

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }

    if (id) {
      const productId = Number(id);
      loadProductData(productId);
      loadStatements(productId);
      loadMonths(productId);
    }
  }, [id, isAuthenticated, navigate, refreshTrigger]);

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
      console.error("Failed to fetch statements", err);
    }
  };

  const loadMonths = async (productId: number) => {
    try {
      const data = await fetchStatementMonths(productId);
      setMonths(data);
    } catch (err) {
      console.error("Failed to fetch statement months", err);
    }
  };

  const handleDeleteStatement = async (importId: number) => {
    if (!window.confirm("Are you sure you want to delete this statement and all its staged transactions?")) {
      return;
    }

    try {
      await deleteStatementImport(importId);
      toast({
        title: "Statement deleted",
        description: "The statement and its staged transactions have been removed."
      });
      setRefreshTrigger(prev => prev + 1);
    } catch (err: any) {
      toast({
        title: "Error deleting statement",
        description: err.message || "An unexpected error occurred.",
        variant: "destructive"
      });
    }
  };

  const handleUploadClick = () => {
    if (uploading) return;
    fileInputRef.current?.click();
  };

  const handleFileSelected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !id) return;

    // Check Celery worker status before upload
    try {
      const status = await fetchCeleryStatus();
      if (!status.is_running) {
        const proceed = window.confirm(
          "Warning: The background worker (Celery) is currently offline. " +
          "If you upload now, the transaction extraction will not start until the worker is manually restarted. " +
          "\n\nDo you want to proceed anyway?"
        );
        if (!proceed) {
          event.target.value = '';
          return;
        }
      }
    } catch (err) {
      console.warn("Could not verify Celery status", err);
    }

    setUploading(true);
    try {
      await uploadStatement(Number(id), file);
      toast({ title: 'Statement uploaded', description: 'Extraction queued — check back shortly.' });
      setRefreshTrigger(prev => prev + 1);
    } catch (err: any) {
      toast({
        title: 'Upload failed',
        description: err.message || 'An unexpected error occurred.',
        variant: 'destructive',
      });
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const fetchBacklog = useCallback(() => {
    return fetchStagedTransactions(Number(id!));
  }, [id]);

  const fetchMonthTransactions = useCallback(() => {
    if (!selectedMonth) return Promise.resolve([]);
    const [year, month] = selectedMonth.month.split('-').map(Number);
    return fetchStatementTransactions(Number(id!), year, month);
  }, [id, selectedMonth]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
        <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
        <p className="text-slate-500 font-medium">Loading account details...</p>
      </div>
    );
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
    <div className="space-y-8 max-w-7xl mx-auto w-full pb-12">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-xl shadow-sm border border-slate-200">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">
              {product.account_name}
            </h1>
            <Badge variant="outline" className="bg-slate-50">
              {product.product_type}
            </Badge>
          </div>
          <p className="text-slate-500 mt-1 flex items-center space-x-2">
            <span className="font-medium text-slate-700">{product.institution_name}</span>
            {product.account_number && (
              <>
                <span>•</span>
                <span className="font-mono text-sm bg-slate-100 px-1.5 py-0.5 rounded">
                  ...{product.account_number.slice(-4)}
                </span>
              </>
            )}
          </p>
        </div>
        <div className="flex gap-2 w-full md:w-auto">
          {product.owner_id ? (
            <Button onClick={() => navigate(`/dashboard/member/${product.owner_id}`)} variant="outline" className="flex-1 md:flex-none">
              Back to Profile
            </Button>
          ) : (
            <Button onClick={() => navigate('/dashboard')} variant="outline" className="flex-1 md:flex-none">
              Back to Dashboard
            </Button>
          )}
          {selectedMonth === null && (
            <Button onClick={handleUploadClick} disabled={uploading} className="flex-1 md:flex-none">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
              Upload Statement
            </Button>
          )}
          <input ref={fileInputRef} type="file" accept="application/pdf" className="hidden" onChange={handleFileSelected} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Left Column: Sidebar Navigator */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-sm font-bold flex items-center gap-2 text-slate-900">
                Navigation
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <nav className="flex flex-col">
                <button
                  onClick={() => setSelectedMonth(null)}
                  className={`flex items-center gap-3 px-4 py-3 text-sm transition-colors border-l-4 ${
                    selectedMonth === null
                      ? "bg-blue-50 border-blue-600 text-blue-900 font-semibold"
                      : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <Inbox className="h-4 w-4" />
                  <span>Uploads & Backlog</span>
                </button>

                <div className="px-4 py-2 mt-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest bg-slate-50/50 border-y border-slate-100">
                  Virtual Statements
                </div>

                {months.map((m) => (
                  <button
                    key={m.month}
                    onClick={() => setSelectedMonth(m)}
                    className={`flex items-center justify-between px-4 py-3 text-sm transition-colors border-l-4 ${
                      selectedMonth?.month === m.month
                        ? "bg-blue-50 border-blue-600 text-blue-900 font-semibold"
                        : "border-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Calendar className="h-4 w-4 opacity-50" />
                      <span>{m.display_name}</span>
                    </div>
                    <Badge variant={selectedMonth?.month === m.month ? "default" : "secondary"} className="text-[10px]">
                      {m.transaction_count}
                    </Badge>
                  </button>
                ))}
              </nav>
            </CardContent>
          </Card>

        </div>

        {/* Right Column: Dynamic Content Area */}
        <div className="lg:col-span-3 space-y-8">
          {selectedMonth === null ? (
            <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">

              {/* Inbox Mode */}
              <div
                className="border-2 border-dashed border-slate-300 rounded-xl p-12 text-center bg-white hover:bg-slate-50 transition-colors cursor-pointer"
                onClick={handleUploadClick}
              >
                <div className="flex flex-col items-center justify-center space-y-3">
                  <div className="bg-blue-50 p-4 rounded-full">
                    <Upload className="h-8 w-8 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-slate-900">Upload PDF Statement</p>
                    <p className="text-sm text-slate-500">Extract and reconcile transactions into your ledger</p>
                  </div>
                  <Button variant="outline" size="sm" className="mt-2">Select File</Button>
                </div>
              </div>

              <TransactionListTable 
                productId={Number(id!)}
                institutionId={product?.institution_id}
                title={TRANSACTION_ROUTING_BACKLOG_TITLE}
                description={TRANSACTION_ROUTING_BACKLOG_DESCRIPTION}
                fetchFn={fetchBacklog}
                onDataChange={() => setRefreshTrigger(prev => prev + 1)}
                refreshTrigger={refreshTrigger}
              />

              <Card className="shadow-sm">
                <CardHeader className="pb-3 border-b border-slate-100 bg-slate-50/50">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <Upload className="h-4 w-4 text-slate-500" />
                    Import History
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-slate-50/50 text-slate-500 font-medium">
                        <tr>
                          <th className="px-4 py-2 text-left">Upload Date</th>
                          <th className="px-4 py-2 text-left">File Name</th>
                          <th className="px-4 py-2 text-center">Status</th>
                          <th className="px-4 py-2 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {statements.length === 0 && (
                          <tr>
                            <td colSpan={4} className="px-4 py-6 text-center text-slate-400 italic">No staged files found.</td>
                          </tr>
                        )}
                        {statements.map((statement) => (
                          <tr key={statement.id} className="hover:bg-slate-50/30">
                            <td className="px-4 py-3">{new Date(statement.upload_date).toLocaleDateString()}</td>
                            <td className="px-4 py-3 font-medium truncate max-w-[200px]">
                              {statement.file_url ? (
                                <a className="text-blue-600 hover:underline" href={statement.file_url} target="_blank" rel="noreferrer">
                                  {statement.file_name}
                                </a>
                              ) : statement.file_name}
                            </td>
                            <td className="px-4 py-3 text-center">
                              <span className={`px-2 py-0.5 rounded-full font-semibold ${
                                statement.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-600'
                              }`}>
                                {statement.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-red-400 hover:text-red-600" onClick={() => handleDeleteStatement(statement.id)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : (
            <div className="animate-in fade-in slide-in-from-right-2 duration-300">
              {/* Ledger Mode */}
              <TransactionListTable 
                productId={Number(id!)}
                institutionId={product?.institution_id}
                title={`Statement: ${selectedMonth.display_name}`}
                description={`A complete chronological view of all activity for ${selectedMonth.display_name}.`}
                fetchFn={fetchMonthTransactions}
                onDataChange={() => setRefreshTrigger(prev => prev + 1)}
                refreshTrigger={refreshTrigger}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
