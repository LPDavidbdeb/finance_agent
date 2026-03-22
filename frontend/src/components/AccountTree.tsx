import React, { useState, useEffect, DragEvent } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { ChevronRight, ChevronDown, Trash2, Plus, Loader2 } from "lucide-react";
import { Link } from "react-router-dom";
import { fetchAccountTree, deleteAccount, moveAccount, createAccount } from "../api/client";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { useToast } from "./ui/use-toast";

type Account = {
  id: number;
  name: string;
  account_type: string;
  parent: number | null;
  children: Account[];
};

interface AddAccountModalProps {
  isOpen: boolean;
  onClose: () => void;
  parentAccount: Account | null;
  onSuccess: () => void;
}

const AddAccountModal: React.FC<AddAccountModalProps> = ({ isOpen, onClose, parentAccount, onSuccess }) => {
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setName("");
      setError(null);
    }
  }, [isOpen]);

  if (!isOpen || !parentAccount) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setLoading(true);
    setError(null);
    try {
      await createAccount({ name: name.trim(), parent_id: parentAccount.id });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to create account");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <Card className="w-full max-w-md mx-auto shadow-2xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="h-5 w-5 text-emerald-600" />
            Add Sub-Account
          </CardTitle>
          <CardDescription>
            Creating new category under <strong>{parentAccount.name}</strong>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="account-name">Category Name</Label>
              <Input
                id="account-name"
                placeholder="e.g. 'Gym Membership' or 'Dining Out'"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                required
              />
            </div>
            <div className="bg-slate-50 p-3 rounded-md border border-slate-100 space-y-1">
              <p className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">Type Inheritance</p>
              <p className="text-sm font-medium text-slate-600">{parentAccount.account_type}</p>
            </div>

            {error && <p className="text-destructive text-sm font-medium">{error}</p>}

            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" disabled={loading || !name.trim()}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Create Account
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
};

type AccountNodeProps = {
  account: Account;
  level?: number;
  onMove?: (draggedId: number, targetId: number) => void;
  onDelete?: (id: number) => void;
  onAddSub?: (parent: Account) => void;
  onSelect?: (account: Account) => void;
  isSelectMode?: boolean;
};

const AccountNode = ({ account, level = 0, onMove, onDelete, onAddSub, onSelect, isSelectMode }: AccountNodeProps) => {
  const [isOpen, setIsOpen] = useState(level < 1);
  const [isDragHover, setIsDragHover] = useState(false);
  const hasChildren = account.children && account.children.length > 0;

  const handleDragStart = (e: DragEvent<HTMLDivElement>) => {
    if (isSelectMode) return;
    e.dataTransfer.setData("accountId", account.id.toString());
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    if (isSelectMode) return;
    e.preventDefault(); // allow drop
    setIsDragHover(true);
  };

  const handleDragLeave = () => {
    setIsDragHover(false);
  };

  const handleDragDrop = (e: DragEvent<HTMLDivElement>) => {
    if (isSelectMode || !onMove) return;
    e.preventDefault();
    setIsDragHover(false);
    const draggedIdStr = e.dataTransfer.getData("accountId");
    if (!draggedIdStr) return;
    const draggedId = Number(draggedIdStr);

    if (draggedId !== account.id) {
      onMove(draggedId, account.id);
    }
  };

  const toggleExpand = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (hasChildren) {
      setIsOpen(!isOpen);
    }
  };

  const handleSelection = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isSelectMode && onSelect) {
      onSelect(account);
    } else if (hasChildren) {
      setIsOpen(!isOpen);
    }
  };

  return (
    <div className="w-full">
      <div 
        draggable={!isSelectMode}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDragDrop}
        className={`group flex items-center justify-between cursor-pointer py-1.5 pr-2 rounded-md transition-colors ${
          isDragHover ? "bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-400" : "hover:bg-slate-100 dark:hover:bg-slate-800"
        } ${
          level === 0 ? "mt-2 font-bold text-slate-800 dark:text-slate-100" : "mt-0.5 text-sm text-slate-700 dark:text-slate-300"
        }`}
        style={{ paddingLeft: `${level * 1.5}rem` }}
        onClick={handleSelection}
      >
        <div className="flex flex-1 items-center overflow-hidden">
          <div 
            className="w-6 flex justify-center items-center shrink-0 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-sm transition-colors"
            onClick={toggleExpand}
          >
            {hasChildren ? (
              isOpen ? 
                <ChevronDown className="w-4 h-4 text-slate-400" /> : 
                <ChevronRight className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-200 dark:text-slate-700 invisible" />
            )}
          </div>
          
          {isSelectMode ? (
            <span className="truncate select-none px-1 rounded hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 font-medium cursor-pointer transition-all">
              {account.name}
            </span>
          ) : (
            <Link 
              to={`/dashboard/accounts/${account.id}`}
              className="truncate select-none px-1 rounded hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-all"
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              {account.name}
            </Link>
          )}
        </div>

        <div className="flex items-center gap-1">
          {/* Add Sub-Account Button */}
          {!isSelectMode && onAddSub && (
            <button 
              onClick={(e) => { e.stopPropagation(); onAddSub(account); }}
              className="hidden group-hover:flex p-1 text-slate-400 hover:text-emerald-600 rounded transition-colors"
              title="Add Sub-Account"
            >
              <Plus className="w-4 h-4" />
            </button>
          )}

          {/* Delete Button (visible on group hover) */}
          {!isSelectMode && onDelete && (
            <button 
              onClick={(e) => { e.stopPropagation(); onDelete(account.id); }}
              className="hidden group-hover:flex p-1 text-slate-400 hover:text-red-500 rounded transition-colors"
              title="Delete Account"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {isOpen && hasChildren && (
        <div className="flex flex-col w-full">
          {account.children.map((child) => (
            <AccountNode 
              key={child.id} 
              account={child} 
              level={level + 1} 
              onMove={onMove} 
              onDelete={onDelete} 
              onAddSub={onAddSub}
              onSelect={onSelect}
              isSelectMode={isSelectMode}
            />
          ))}
        </div>
      )}
    </div>
  );
};

interface AccountTreeProps {
  onSelect?: (account: Account) => void;
  isSelectMode?: boolean;
}

export function AccountTree({ onSelect, isSelectMode = false }: AccountTreeProps) {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [selectedParent, setSelectedParent] = useState<Account | null>(null);
  
  const { toast } = useToast();

  const loadTree = async () => {
    try {
      const data = await fetchAccountTree();
      setAccounts(data);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTree();
  }, []);

  const handleMove = async (draggedId: number, targetParentId: number) => {
    if (isSelectMode) return;
    try {
      await moveAccount(draggedId, targetParentId);
      // Re-fetch to display the updated tree immediately
      await loadTree();
      toast({ title: "Account moved successfully" });
    } catch (err: any) {
      console.error("Failed to move node", err);
      toast({ 
        variant: "destructive", 
        title: "Move failed", 
        description: err.message 
      });
    }
  };

  const handleDelete = async (id: number) => {
    if (isSelectMode) return;
    if (!window.confirm("Are you sure you want to delete this account? Only empty leaf accounts can be removed.")) return;
    try {
      await deleteAccount(id);
      await loadTree();
      toast({ title: "Account deleted" });
    } catch (err: any) {
      console.error("Failed to delete node", err);
      toast({ 
        variant: "destructive", 
        title: "Delete failed", 
        description: err.message 
      });
    }
  };

  const handleAddSub = (parent: Account) => {
    setSelectedParent(parent);
    setIsAddModalOpen(true);
  };

  if (loading) return (
    <div className="flex flex-col items-center justify-center p-20 space-y-4">
      <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      <p className="text-slate-500 font-medium">Loading Ledger...</p>
    </div>
  );
  
  if (error) return (
    <div className="p-8 text-center bg-red-50 border border-red-100 rounded-xl max-w-2xl mx-auto">
      <p className="text-red-600 font-bold mb-2">Error loading tree</p>
      <p className="text-red-500 text-sm">{error}</p>
    </div>
  );

  const balanceSheetAccounts = accounts.filter(a => ['ASSET', 'LIABILITY', 'EQUITY'].includes(a.account_type));
  const incomeStatementAccounts = accounts.filter(a => ['REVENUE', 'EXPENSE'].includes(a.account_type));

  return (
    <div className="space-y-8 w-full max-w-4xl mx-auto pb-20">
      <AddAccountModal 
        isOpen={isAddModalOpen} 
        onClose={() => setIsAddModalOpen(false)} 
        parentAccount={selectedParent}
        onSuccess={loadTree}
      />

      {/* Balance Sheet Group */}
      <Card className={`${isSelectMode ? 'shadow-none border-none' : 'shadow-md border-slate-200 dark:border-slate-800 overflow-hidden'}`}>
        {!isSelectMode && (
          <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b border-slate-100 dark:border-slate-800 pb-4">
            <CardTitle className="text-2xl font-bold text-slate-800 dark:text-slate-100">
              Balance Sheet
            </CardTitle>
            <CardDescription>
              Your assets, liabilities, and net worth.
            </CardDescription>
          </CardHeader>
        )}
        <CardContent className={`${isSelectMode ? 'p-0' : 'p-6'}`}>
          {balanceSheetAccounts.length > 0 ? (
            <div className="flex flex-col w-full text-sm">
              {balanceSheetAccounts.map((rootAccount) => (
                <AccountNode 
                  key={rootAccount.id} 
                  account={rootAccount} 
                  level={0} 
                  onMove={handleMove} 
                  onDelete={handleDelete} 
                  onAddSub={handleAddSub}
                  onSelect={onSelect}
                  isSelectMode={isSelectMode}
                />
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No accounts found.</p>
          )}
        </CardContent>
      </Card>

      {/* Income Statement Group */}
      <Card className={`${isSelectMode ? 'shadow-none border-none' : 'shadow-md border-slate-200 dark:border-slate-800 overflow-hidden'}`}>
        {!isSelectMode && (
          <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b border-slate-100 dark:border-slate-800 pb-4">
            <CardTitle className="text-2xl font-bold text-slate-800 dark:text-slate-100">
              Income Statement
            </CardTitle>
            <CardDescription>
              Your revenue and expenses (Cash Flow).
            </CardDescription>
          </CardHeader>
        )}
        <CardContent className={`${isSelectMode ? 'p-0' : 'p-6'}`}>
          {incomeStatementAccounts.length > 0 ? (
            <div className="flex flex-col w-full text-sm">
              {incomeStatementAccounts.map((rootAccount) => (
                <AccountNode 
                  key={rootAccount.id} 
                  account={rootAccount} 
                  level={0} 
                  onMove={handleMove} 
                  onDelete={handleDelete} 
                  onAddSub={handleAddSub}
                  onSelect={onSelect}
                  isSelectMode={isSelectMode}
                />
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No accounts found.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
