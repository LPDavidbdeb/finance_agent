import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { OnboardingForm } from './components/OnboardingForm';
import { LoginForm } from './components/LoginForm';
import { Dashboard } from './pages/Dashboard';
import { InstitutionManager } from './components/InstitutionManager';
import { MemberProfile } from './pages/MemberProfile';
import { ProductDetail } from './pages/ProductDetail';
import { MerchantManager } from './pages/MerchantManager';
import { MerchantDetail } from './pages/MerchantDetail';
import { AccountDetail } from './pages/AccountDetail';
import { AccountTree } from './components/AccountTree';
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
              <Route path="/dashboard/member/:id" element={<MemberProfile />} />
              <Route path="/dashboard/product/:id" element={<ProductDetail />} />
              <Route path="/dashboard/merchants" element={<MerchantManager />} />
              <Route path="/dashboard/merchants/:id" element={<MerchantDetail />} />
              <Route path="/dashboard/accounts/:id" element={<AccountDetail />} />
              <Route path="/settings/banks" element={<InstitutionManager />} />
              <Route path="/ledger" element={<AccountTree />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;