import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { AuthProvider } from './context/AuthContext';
import { Loader2 } from 'lucide-react';

// Common components can stay static or be lazy if large
import { OnboardingForm } from './components/OnboardingForm';
import { LoginForm } from './components/LoginForm';

// Lazy-load all main pages
const Dashboard = lazy(() => import('./pages/Dashboard').then(module => ({ default: module.Dashboard })));
const FamilyManager = lazy(() => import('./pages/FamilyManager').then(module => ({ default: module.FamilyManager })));
const MemberProfile = lazy(() => import('./pages/MemberProfile').then(module => ({ default: module.MemberProfile })));
const ProductDetail = lazy(() => import('./pages/ProductDetail').then(module => ({ default: module.ProductDetail })));
const MerchantManager = lazy(() => import('./pages/MerchantManager').then(module => ({ default: module.MerchantManager })));
const MerchantDetail = lazy(() => import('./pages/MerchantDetail').then(module => ({ default: module.MerchantDetail })));
const AccountDetail = lazy(() => import('./pages/AccountDetail').then(module => ({ default: module.AccountDetail })));
const DimensionDetail = lazy(() => import('./pages/DimensionDetail').then(module => ({ default: module.DimensionDetail })));
const StatementDetail = lazy(() => import('./pages/StatementDetail').then(module => ({ default: module.StatementDetail })));
const MaintenancePage = lazy(() => import('./pages/MaintenancePage').then(module => ({ default: module.MaintenancePage })));
const SimulationPage = lazy(() => import('./pages/SimulationPage').then(module => ({ default: module.SimulationPage })));

// Lazy-load complex shared components
const InstitutionManager = lazy(() => import('./components/InstitutionManager').then(module => ({ default: module.InstitutionManager })));
const AccountTree = lazy(() => import('./components/AccountTree').then(module => ({ default: module.AccountTree })));

const PageLoader = () => (
  <div className="flex flex-col items-center justify-center min-h-[400px] space-y-4">
    <Loader2 className="h-12 w-12 animate-spin text-blue-600" />
    <p className="text-slate-500 font-medium italic animate-pulse">Loading experience...</p>
  </div>
);

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50 flex flex-col">
          <Navbar />
          <main className="flex-grow p-4 md:p-8 w-full max-w-7xl mx-auto flex flex-col">
            <Suspense fallback={<PageLoader />}>
              <Routes>
                <Route path="/" element={<div className="mt-20 text-center"><h2>Welcome to your Ledger</h2></div>} />
                <Route path="/register" element={<OnboardingForm />} />
                <Route path="/login" element={<LoginForm />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/dashboard/family" element={<FamilyManager />} />
                <Route path="/dashboard/member/:id" element={<MemberProfile />} />
                <Route path="/dashboard/product/:id" element={<ProductDetail />} />
                <Route path="/dashboard/merchants" element={<MerchantManager />} />
                <Route path="/dashboard/merchants/:id" element={<MerchantDetail />} />
                <Route path="/dashboard/accounts/:id" element={<AccountDetail />} />
                <Route path="/dashboard/dimension/:slug" element={<DimensionDetail />} />
                <Route path="/dashboard/statements/:id" element={<StatementDetail />} />
                <Route path="/dashboard/simulate" element={<SimulationPage />} />
                <Route path="/maintenance" element={<MaintenancePage />} />
                <Route path="/settings/banks" element={<InstitutionManager />} />
                <Route path="/ledger" element={<AccountTree />} />
              </Routes>
            </Suspense>
          </main>
        </div>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
