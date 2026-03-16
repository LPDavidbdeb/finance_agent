import { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ChevronRight, ChevronDown } from "lucide-react";

type Account = {
  id: number;
  name: string;
  account_type: string;
  parent: number | null;
  children: Account[];
};

const AccountNode = ({ account }: { account: Account }) => {
  const [isOpen, setIsOpen] = useState(true);
  const hasChildren = account.children && account.children.length > 0;

  return (
    <div className="ml-4 mt-2">
      <div 
        className="flex items-center space-x-2 cursor-pointer hover:bg-slate-100 dark:hover:bg-slate-800 p-1 rounded-md transition-colors"
        onClick={() => setIsOpen(!isOpen)}
      >
        {hasChildren ? (
          isOpen ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />
        ) : (
          <span className="w-4 h-4 inline-block" /> // Placeholder to align leaf nodes
        )}
        <span className="font-medium text-slate-700 dark:text-slate-300">
          {account.name} 
        </span>
        <span className="text-xs px-2 py-0.5 rounded-full bg-slate-200 dark:bg-slate-700 text-slate-600 dark:text-slate-400">
          {account.account_type}
        </span>
      </div>
      
      {isOpen && hasChildren && (
        <div className="border-l border-slate-200 dark:border-slate-800 ml-2 pl-2">
          {account.children.map((child) => (
            <AccountNode key={child.id} account={child} />
          ))}
        </div>
      )}
    </div>
  );
};

export function AccountTree() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/api/accounts/tree")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch account tree");
        return res.json();
      })
      .then((data) => {
        setAccounts(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="text-center p-4">Loading Ledger...</div>;
  if (error) return <div className="text-red-500 p-4">Error: {error}</div>;

  return (
    <Card className="w-full max-w-2xl mx-auto shadow-sm">
      <CardHeader>
        <CardTitle>Chart of Accounts (Ledger)</CardTitle>
      </CardHeader>
      <CardContent>
        {accounts.length === 0 ? (
          <p className="text-slate-500">No accounts configured yet.</p>
        ) : (
          <div className="text-sm">
            {accounts.map((rootAccount) => (
              <AccountNode key={rootAccount.id} account={rootAccount} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
