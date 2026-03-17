import React from 'react';
import { Link } from 'react-router-dom';

export const Navbar: React.FC = () => {
  return (
    <nav className="bg-slate-900 text-white p-4 shadow-md">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        
        {/* The brand logo/home link */}
        <Link to="/" className="text-xl font-bold tracking-tight">
          Household Ledger
        </Link>
        
        {/* The navigation links */}
        <div className="space-x-4 flex items-center">
          <Link to="/" className="hover:text-slate-300 transition-colors">
            Dashboard
          </Link>
          <Link 
            to="/register" 
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium transition-colors"
          >
            Create Household
          </Link>
        </div>
        
      </div>
    </nav>
  );
};