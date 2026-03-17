import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { OnboardingForm } from './components/OnboardingForm';
// If you have your AccountTree component, you can import it here later

function App() {
  return (
    <BrowserRouter>
      {/* The master layout container */}
      <div className="min-h-screen bg-gray-50 flex flex-col">
        
        {/* The Navigation Bar - Always visible */}
        <Navbar />

        {/* The Main Content Area - Swaps based on the URL */}
        <main className="flex-grow p-4 md:p-8 w-full max-w-7xl mx-auto flex flex-col">
          <Routes>
            
            {/* Route 1: The Home Page (URL: / ) 
              For now, we just put a placeholder message here.
            */}
            <Route 
              path="/" 
              element={
                <div className="flex flex-col items-center justify-center flex-grow text-center mt-20">
                  <h2 className="text-3xl font-semibold text-slate-800">Welcome to your Ledger</h2>
                  <p className="text-slate-600 mt-2">Get started by creating your household account.</p>
                </div>
              } 
            />
            
            {/* Route 2: The Registration Page (URL: /register ) 
              This is where your form lives now.
            */}
            <Route path="/register" element={<OnboardingForm />} />

          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;