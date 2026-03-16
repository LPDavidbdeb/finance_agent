import React from 'react';
import { ChartOfAccounts } from './components/ChartOfAccounts';

function App() {
  return (
    <div className="container mx-auto p-4 max-w-4xl font-sans">
      <header className="mb-8">
        <h1 className="text-3xl font-extrabold text-gray-800">
          Personal Finance App
        </h1>
        <p className="text-gray-600">Golden Reference Data Viewer</p>
      </header>

      <main>
        <ChartOfAccounts />
      </main>
    </div>
  );
}

export default App;