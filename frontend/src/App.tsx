import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { OnboardingForm } from './components/OnboardingForm';
import { LoginForm } from './components/LoginForm';
import { Dashboard } from './components/Dashboard';
import { AuthProvider } from './context/AuthContext';

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50 flex flex-col">
          <Navbar />
          <main className="flex-grow p-4 md:p-8 w-full max-w-7xl mx-auto flex flex-col">
            <Routes>
              <Route path="/" element={<div className="mt-20 text-center"><h2>Welcome to your Ledger</h2></div>} />
              <Route path="/register" element={<OnboardingForm />} />
              <Route path="/login" element={<LoginForm />} />
              <Route path="/dashboard" element={<Dashboard />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;