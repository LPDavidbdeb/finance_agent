import React, { useState, useEffect } from 'react';
import { fetchTree } from '../api/client';

interface AccountNode {
  id: number;
  name: string;
  account_type: string;
  children: AccountNode[];
}

export const ChartOfAccounts: React.FC = () => {
  const [treeData, setTreeData] = useState<AccountNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const data = await fetchTree();
        setTreeData(data);
      } catch (err: any) {
        setError(err.message || 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const renderTree = (nodes: AccountNode[], depth = 0) => {
    return (
      <ul className={`pl-${depth > 0 ? 4 : 0}`}>
        {nodes.map((node) => (
          <li key={node.id} className="my-1">
            <div className="flex items-center">
              <span className="font-semibold">{node.name}</span>
              <span className="ml-2 text-xs text-gray-500">
                ({node.account_type})
              </span>
            </div>
            {node.children && node.children.length > 0 && (
              <div className="ml-4 border-l pl-2 border-gray-300">
                {renderTree(node.children, depth + 1)}
              </div>
            )}
          </li>
        ))}
      </ul>
    );
  };

  if (loading) {
    return <div className="p-4">Loading Chart of Accounts...</div>;
  }

  if (error) {
    return (
      <div className="p-4 text-red-500 bg-red-50 rounded">
        Error loading Chart of Accounts: {error}
      </div>
    );
  }

  return (
    <div className="p-4 bg-white rounded shadow-md">
      <h2 className="text-xl font-bold mb-4">Chart of Accounts</h2>
      {treeData.length > 0 ? (
        renderTree(treeData)
      ) : (
        <p>No accounts found.</p>
      )}
    </div>
  );
};