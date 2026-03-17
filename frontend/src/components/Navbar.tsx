import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext'; // <-- Import the hook

export const Navbar: React.FC = () => {
  const { isAuthenticated, logout } = useAuth(); // <-- Get the state and logout function
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <nav className="bg-slate-900 text-white p-4 shadow-md">
      <div className="max-w-7xl mx-auto flex justify-between items-center">
        <Link to="/" className="text-xl font-bold tracking-tight">Household Ledger</Link>
        
        <div className="space-x-4 flex items-center">
          {isAuthenticated ? (
            // WHAT TO SHOW WHEN LOGGED IN
            <>
              <Link to="/dashboard" className="hover:text-slate-300 transition-colors">Dashboard</Link>
              <Link to="/ledger" className="hover:text-slate-300 transition-colors">Ledger</Link>
              <Link to="/settings/banks" className="hover:text-slate-300 transition-colors">Manage Banks</Link>
              <button onClick={handleLogout} className="text-slate-300 hover:text-white transition-colors">
                Logout
              </button>
            </>
          ) : (
            // WHAT TO SHOW WHEN LOGGED OUT
            <>
              <Link to="/login" className="hover:text-slate-300 transition-colors">Log In</Link>
              <Link to="/register" className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-md font-medium transition-colors">
                Create Household
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};