import { useState, useEffect, DragEvent } from "react";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { ChevronRight, ChevronDown, Trash2 } from "lucide-react";
import { fetchAccountTree, deleteAccount, moveAccount } from "../api/client";

type Account = {
  id: number;
  name: string;
  account_type: string;
  parent: number | null;
  children: Account[];
};

type AccountNodeProps = {
  account: Account;
  level?: number;
  onMove?: (draggedId: number, targetId: number) => void;
  onDelete?: (id: number) => void;
  onSelect?: (account: Account) => void;
  isSelectMode?: boolean;
};

const AccountNode = ({ account, level = 0, onMove, onDelete, onSelect, isSelectMode }: AccountNodeProps) => {
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
          <span className={`truncate select-none px-1 rounded transition-all ${
            isSelectMode 
              ? "hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 font-medium cursor-pointer" 
              : ""
          }`}>
            {account.name} 
          </span>
        </div>

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

      {isOpen && hasChildren && (
        <div className="flex flex-col w-full">
          {account.children.map((child) => (
            <AccountNode 
              key={child.id} 
              account={child} 
              level={level + 1} 
              onMove={onMove} 
              onDelete={onDelete} 
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
    } catch (err: any) {
      console.error("Failed to move node", err);
      alert("Failed to move account: " + err.message);
    }
  };

  const handleDelete = async (id: number) => {
    if (isSelectMode) return;
    if (!window.confirm("Are you sure you want to delete this account AND all its sub-accounts?")) return;
    try {
      await deleteAccount(id);
      await loadTree();
    } catch (err: any) {
      console.error("Failed to delete node", err);
      alert("Failed to delete account: " + err.message);
    }
  };

  if (loading) return <div className="text-center p-4">Loading Ledger...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;

  const balanceSheetAccounts = accounts.filter(a => ['ASSET', 'LIABILITY', 'EQUITY'].includes(a.account_type));
  const incomeStatementAccounts = accounts.filter(a => ['REVENUE', 'EXPENSE'].includes(a.account_type));

  const content = (
    <div className="space-y-8 w-full max-w-4xl mx-auto">

      {/* Balance Sheet Group */}
      <Card className={`${isSelectMode ? 'shadow-none border-none' : 'shadow-md border-slate-200 dark:border-slate-800'}`}>
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
      <Card className={`${isSelectMode ? 'shadow-none border-none' : 'shadow-md border-slate-200 dark:border-slate-800'}`}>
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

  return content;
}