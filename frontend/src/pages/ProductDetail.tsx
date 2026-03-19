import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Badge } from '../components/ui/badge';
import { 
  fetchFinancialProduct, 
  fetchProductStatements, 
  uploadStatement,
  deleteStatementImport,
  fetchStatementMonths,
  fetchStatementTransactions
} from '../api/client';
import { useAuth } from '../context/AuthContext';
import { StagedTransactionsTable } from '../components/StagedTransactionsTable';
import { useToast } from '../components/ui/use-toast';
import { Calendar, ChevronRight, FileText, Upload, Trash2, Loader2 } from 'lucide-react';

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
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [documentDate, setDocumentDate] = useState<string>('');
  
  // Staging Area State
  const [statements, setStatements] = useState<StatementImport[]>([]);
  const [stagedTransactionsRefresh, setStagedTransactionsRefresh] = useState(0);

  // Virtual Statement Navigator State
  const [months, setMonths] = useState<StatementMonth[]>([]);
  const [selectedMonth, setSelectedMonth] = useState<StatementMonth | null>(null);
  const [monthTransactions, setMonthTransactions] = useState<any[]>([]);
  const [loadingTransactions, setLoadingTransactions] = useState(false);

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
  }, [id, isAuthenticated, navigate]);

  useEffect(() => {
    if (id && selectedMonth) {
      loadMonthTransactions(Number(id), selectedMonth.month);
    }
  }, [id, selectedMonth]);

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
      if (data.length > 0 && !selectedMonth) {
        setSelectedMonth(data[0]);
      }
    } catch (err) {
      console.error("Failed to fetch statement months", err);
    }
  };

  const loadMonthTransactions = async (productId: number, monthStr: string) => {
    setLoadingTransactions(true);
    try {
      const [year, month] = monthStr.split('-').map(Number);
      const data = await fetchStatementTransactions(productId, year, month);
      setMonthTransactions(data);
    } catch (err) {
      console.error("Failed to fetch month transactions", err);
    } finally {
      setLoadingTransactions(false);
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
      if (id) {
        await loadStatements(Number(id));
        await loadMonths(Number(id));
        setStagedTransactionsRefresh(prev => prev + 1);
      }
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

    setUploadMessage(null);
    try {
      setUploading(true);
      await uploadStatement(Number(id), file, documentDate);
      setUploadMessage('Statement uploaded to staging area successfully.');
      setDocumentDate('');
      await loadStatements(Number(id));
      await loadMonths(Number(id));
      setStagedTransactionsRefresh((prev) => prev + 1);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed.';
      setUploadMessage(errorMessage);
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

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
          <Button onClick={handleUploadClick} disabled={uploading} className="flex-1 md:flex-none">
            {uploading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Upload className="h-4 w-4 mr-2" />}
            Upload Statement
          </Button>
          <input ref={fileInputRef} type="file" accept="application/pdf" className="hidden" onChange={handleFileSelected} />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
        {/* Left Column: Sidebar Navigator */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="shadow-sm">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-sm font-bold flex items-center gap-2">
                <Calendar className="h-4 w-4 text-blue-600" />
                Virtual Statements
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <nav className="flex flex-col">
                {months.length === 0 && (
                  <div className="p-6 text-center text-slate-400 text-sm">
                    No transactions recorded yet.
                  </div>
                )}
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
                    <span>{m.display_name}</span>
                    <Badge variant={selectedMonth?.month === m.month ? "default" : "secondary"} className="text-[10px]">
                      {m.transaction_count}
                    </Badge>
                  </button>
                ))}
              </nav>
            </CardContent>
          </Card>

          <Card className="shadow-sm bg-slate-50 border-dashed border-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-xs uppercase tracking-wider text-slate-500">Quick Upload Settings</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="doc-date" className="text-[11px] font-bold">Statement Date</Label>
                <Input 
                  id="doc-date"
                  type="date" 
                  size={1} 
                  className="h-8 text-xs" 
                  value={documentDate}
                  onChange={(e) => setDocumentDate(e.target.value)}
                />
              </div>
              {uploadMessage && (
                <p className="text-[10px] text-slate-600 italic bg-white p-2 rounded border border-slate-200">
                  {uploadMessage}
                </p>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: Statement Detail View & Staging Area */}
        <div className="lg:col-span-3 space-y-8">
          {/* Main Statement View */}
          <Card className="shadow-md overflow-hidden">
            <CardHeader className="bg-slate-900 text-white flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-xl">
                  {selectedMonth ? `Statement: ${selectedMonth.display_name}` : "Monthly Activity"}
                </CardTitle>
                <CardDescription className="text-slate-400">
                  {selectedMonth ? `${selectedMonth.transaction_count} transactions recorded` : "Select a month to view history"}
                </CardDescription>
              </div>
              {selectedMonth && <FileText className="h-8 w-8 text-blue-400 opacity-50" />}
            </CardHeader>
            <CardContent className="p-0">
              {loadingTransactions ? (
                <div className="p-12 text-center text-slate-500 flex flex-col items-center gap-2">
                  <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                  <p>Fetching ledger records...</p>
                </div>
              ) : selectedMonth ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                      <tr>
                        <th className="px-6 py-3 text-left font-semibold text-slate-700">Date</th>
                        <th className="px-6 py-3 text-left font-semibold text-slate-700">Description</th>
                        <th className="px-6 py-3 text-left font-semibold text-slate-700">Category</th>
                        <th className="px-6 py-3 text-right font-semibold text-slate-700">Amount</th>
                        <th className="px-6 py-3 text-center font-semibold text-slate-700">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {monthTransactions.length === 0 && (
                        <tr>
                          <td colSpan={5} className="px-6 py-12 text-center text-slate-400 italic">
                            No transactions found for this period.
                          </td>
                        </tr>
                      )}
                      {monthTransactions.map((tx) => (
                        <tr key={tx.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="px-6 py-4 text-slate-600 whitespace-nowrap font-mono text-xs">
                            {new Date(tx.bank_date).toLocaleDateString(undefined, { day: '2-digit', month: 'short' })}
                          </td>
                          <td className="px-6 py-4">
                            <div className="font-medium text-slate-900">{tx.clean_description || tx.raw_description}</div>
                            {tx.clean_description && <div className="text-[10px] text-slate-400">{tx.raw_description}</div>}
                          </td>
                          <td className="px-6 py-4">
                            {tx.predicted_account_name ? (
                              <Badge variant="secondary" className="bg-green-50 text-green-700 border-green-100 font-normal">
                                {tx.predicted_account_name}
                              </Badge>
                            ) : (
                              <span className="text-slate-400">---</span>
                            )}
                          </td>
                          <td className={`px-6 py-4 text-right font-mono font-semibold ${tx.amount < 0 ? 'text-red-600' : 'text-slate-900'}`}>
                            ${Math.abs(tx.amount).toFixed(2)}
                          </td>
                          <td className="px-6 py-4 text-center">
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${
                              tx.status === 'RECONCILED' ? 'bg-blue-100 text-blue-700' : 'bg-orange-100 text-orange-700'
                            }`}>
                              {tx.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-20 text-center text-slate-400 space-y-4">
                  <div className="bg-slate-100 w-16 h-16 rounded-full flex items-center justify-center mx-auto">
                    <ChevronRight className="h-8 w-8" />
                  </div>
                  <p>Select a statement period from the navigator to view details.</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Staging Area & Unprocessed Transactions */}
          <div className="space-y-6">
            <div className="flex items-center gap-2 px-1">
              <div className="h-px bg-slate-200 flex-1"></div>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest px-2">Review Queue</span>
              <div className="h-px bg-slate-200 flex-1"></div>
            </div>

            <StagedTransactionsTable productId={Number(id!)} refreshTrigger={stagedTransactionsRefresh} />

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
        </div>
      </div>
    </div>
  );
};
