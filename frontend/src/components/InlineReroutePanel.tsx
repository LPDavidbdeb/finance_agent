import React, { useState, useEffect, useRef } from 'react';
import { Button } from './ui/button';
import { Check, List, Loader2, Tag } from 'lucide-react';
import { rerouteJournalEntry } from '../api/client';

export interface FlatAccount {
  id: number;
  name: string;
  account_type: string;
  depth: number;
}

export interface RerouteMerchant {
  id: number;
  name: string;
  default_account_id?: number;
  default_account_name?: string;
}

interface InlineReroutePanelProps {
  entryId: number;
  flatAccounts: FlatAccount[];
  merchants: RerouteMerchant[];
  onSuccess: (updated: any) => void;
  onCancel: () => void;
}

export const InlineReroutePanel: React.FC<InlineReroutePanelProps> = ({
  entryId,
  flatAccounts,
  merchants,
  onSuccess,
  onCancel,
}) => {
  const [mode, setMode] = useState<'account' | 'merchant'>('account');
  const [search, setSearch] = useState('');
  const [selectedAccount, setSelectedAccount] = useState<FlatAccount | null>(null);
  const [selectedMerchant, setSelectedMerchant] = useState<RerouteMerchant | null>(null);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const filteredAccounts = flatAccounts.filter(a =>
    search.length > 0 && a.name.toLowerCase().includes(search.toLowerCase())
  );

  const filteredMerchants = merchants.filter(m =>
    search.length > 0 && m.name.toLowerCase().includes(search.toLowerCase())
  );

  const handleSave = async () => {
    if (!selectedAccount && !selectedMerchant) return;
    try {
      setSaving(true);
      const updated = await rerouteJournalEntry(
        entryId,
        selectedAccount?.id,
        selectedMerchant?.id,
      );
      onSuccess(updated);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2 mb-1">
        <button
          onClick={() => { setMode('account'); setSelectedMerchant(null); setSearch(''); }}
          className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${mode === 'account' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-500'}`}
        >
          Account
        </button>
        <button
          onClick={() => { setMode('merchant'); setSelectedAccount(null); setSearch(''); }}
          className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${mode === 'merchant' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-500'}`}
        >
          Merchant
        </button>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <div className="absolute left-3 top-2.5 text-slate-400">
            {mode === 'account' ? <List className="h-3.5 w-3.5" /> : <Tag className="h-3.5 w-3.5" />}
          </div>
          <input
            ref={inputRef}
            type="text"
            value={search}
            onChange={e => { setSearch(e.target.value); setSelectedAccount(null); setSelectedMerchant(null); }}
            placeholder={mode === 'account' ? 'Search accounts...' : 'Search merchants...'}
            className="w-full text-xs border border-slate-300 rounded-md pl-9 pr-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-400"
          />

          {mode === 'account' && search && !selectedAccount && filteredAccounts.length > 0 && (
            <div className="absolute z-20 top-full mt-1 w-full bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
              {filteredAccounts.map(acc => (
                <button
                  key={acc.id}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 flex items-center gap-2"
                  onClick={() => { setSelectedAccount(acc); setSearch(acc.name); }}
                >
                  <span className="text-slate-300">{'\u00a0'.repeat(acc.depth * 2)}</span>
                  <span className="font-medium text-slate-700 uppercase">{acc.name}</span>
                  <span className="text-slate-400 ml-auto">{acc.account_type}</span>
                </button>
              ))}
            </div>
          )}

          {mode === 'merchant' && search && !selectedMerchant && filteredMerchants.length > 0 && (
            <div className="absolute z-20 top-full mt-1 w-full bg-white border border-slate-200 rounded-md shadow-lg max-h-48 overflow-y-auto">
              {filteredMerchants.map(m => (
                <button
                  key={m.id}
                  className="w-full text-left px-3 py-2 text-xs hover:bg-blue-50 flex flex-col gap-0.5"
                  onClick={() => { setSelectedMerchant(m); setSearch(m.name); }}
                >
                  <span className="font-bold text-slate-700 uppercase">{m.name}</span>
                  {m.default_account_name && (
                    <span className="text-[9px] text-slate-400 uppercase italic">Default: {m.default_account_name}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        <Button
          size="sm"
          disabled={(!selectedAccount && !selectedMerchant) || saving}
          onClick={handleSave}
          className="text-xs h-7"
        >
          {saving
            ? <Loader2 className="h-3 w-3 animate-spin" />
            : <><Check className="h-3 w-3 mr-1" />Save</>
          }
        </Button>
        <button onClick={onCancel} className="text-slate-400 hover:text-slate-600 text-xs">
          Cancel
        </button>
      </div>

      {selectedAccount && (
        <p className="text-[10px] text-blue-600 mt-1 font-medium">
          Will move to account: <span className="font-black uppercase">{selectedAccount.name}</span>
        </p>
      )}
      {selectedMerchant && (
        <p className="text-[10px] text-purple-600 mt-1 font-medium">
          Assign to merchant <span className="font-black uppercase">{selectedMerchant.name}</span>
          {selectedMerchant.default_account_name && (
            <> and move to <span className="font-black uppercase">{selectedMerchant.default_account_name}</span></>
          )}
        </p>
      )}
    </div>
  );
};