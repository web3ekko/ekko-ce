import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  ChartBarIcon, 
  WalletIcon, 
  BellIcon, 
  BoltIcon, 
  UserGroupIcon
} from '@heroicons/react/24/outline';
import { Select, SelectItem } from '@tremor/react';
import useStore from '../store/store';

const Layout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedBlockchain, setSelectedBlockchain } = useStore();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const blockchains = [
    { value: 'ETH', name: 'Ethereum' },
    { value: 'AVAX', name: 'Avalanche' },
    { value: 'MATIC', name: 'Polygon' },
    { value: 'BTC', name: 'Bitcoin' }
  ];

  const navigation = [
    { name: 'Dashboard', href: '/', icon: ChartBarIcon },
    { name: 'Wallets', href: '/wallets', icon: WalletIcon },
    { name: 'Alerts', href: '/alerts', icon: BellIcon },
    { name: 'Workflows', href: '/workflows', icon: BoltIcon },
    { name: 'AI Agents', href: '/agents', icon: UserGroupIcon },
  ];

  // Function to determine if a nav item is active
  const isActive = (path) => {
    return location.pathname === path;
  };

  const handleBlockchainChange = (value) => {
    setSelectedBlockchain(value);
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Sidebar for desktop */}
      <div className="hidden md:fixed md:inset-y-0 md:flex md:w-64 md:flex-col">
        <div className="flex min-h-0 flex-1 flex-col border-r border-gray-200 bg-white">
          <div className="flex flex-1 flex-col overflow-y-auto pt-5 pb-4">
            <div className="flex flex-shrink-0 items-center px-4">
              <span className="text-2xl font-bold text-ekko-primary flex items-center">
                ⚡ Ekko
              </span>
            </div>

            {/* Blockchain Selector */}
            <div className="mt-6 px-4">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Select Blockchain
              </h3>
              <div className="mt-2">
                <Select
                  value={selectedBlockchain}
                  onValueChange={handleBlockchainChange}
                >
                  {blockchains.map((blockchain) => (
                    <SelectItem key={blockchain.value} value={blockchain.value}>
                      {blockchain.name}
                    </SelectItem>
                  ))}
                </Select>
              </div>
            </div>

            <div className="mt-6">
              <h3 className="px-4 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Navigation
              </h3>

              <nav className="mt-2 flex-1 space-y-1 px-2">
                {navigation.map((item) => (
                  <button
                    key={item.name}
                    onClick={() => navigate(item.href)}
                    className={`${
                      isActive(item.href)
                        ? 'bg-ekko-primary text-white'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    } group flex items-center w-full px-2 py-2 text-sm font-medium rounded-md`}
                  >
                    <item.icon
                      className={`${
                        isActive(item.href) ? 'text-white' : 'text-gray-400 group-hover:text-gray-500'
                      } mr-3 h-5 w-5 flex-shrink-0`}
                      aria-hidden="true"
                    />
                    {item.name}
                  </button>
                ))}
              </nav>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile menu button */}
      <div className="sticky top-0 z-10 bg-white md:hidden flex items-center justify-between p-4 border-b border-gray-200">
        <span className="text-xl font-bold text-ekko-primary flex items-center">
          ⚡ Ekko
        </span>
        <button
          type="button"
          className="inline-flex items-center justify-center rounded-md p-2 text-gray-400 hover:bg-gray-100 hover:text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-ekko-primary"
          onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
        >
          <span className="sr-only">Open main menu</span>
          <svg
            className="h-6 w-6"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d={isMobileMenuOpen ? "M6 18L18 6M6 6l12 12" : "M4 6h16M4 12h16M4 18h16"}
            />
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {isMobileMenuOpen && (
        <div className="md:hidden">
          <div className="space-y-1 px-2 pb-3 pt-2">
            <div className="px-4 py-2">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Select Blockchain
              </h3>
              <div className="mt-2">
                <Select
                  value={selectedBlockchain}
                  onValueChange={handleBlockchainChange}
                >
                  {blockchains.map((blockchain) => (
                    <SelectItem key={blockchain.value} value={blockchain.value}>
                      {blockchain.name}
                    </SelectItem>
                  ))}
                </Select>
              </div>
            </div>

            {navigation.map((item) => (
              <button
                key={item.name}
                onClick={() => {
                  navigate(item.href);
                  setIsMobileMenuOpen(false);
                }}
                className={`${
                  isActive(item.href)
                    ? 'bg-ekko-primary text-white'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                } group flex w-full items-center rounded-md px-3 py-2 text-base font-medium`}
              >
                <item.icon
                  className={`${
                    isActive(item.href) ? 'text-white' : 'text-gray-400 group-hover:text-gray-500'
                  } mr-4 h-6 w-6 flex-shrink-0`}
                  aria-hidden="true"
                />
                {item.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex flex-1 flex-col md:pl-64">
        <main className="flex-1">
          <div className="py-6">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 md:px-8">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default Layout;
