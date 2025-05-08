import type {NavigationTree} from '@/@types/navigation';
import {
  IconDashboard, 
  IconWallet, 
  IconBell, 
  IconExchange, 
  IconSettings,
  IconChartBar,
  IconServer
} from '@tabler/icons-react';

const navigationConfig: NavigationTree[] = [
  {
    key: 'dashboard',
    path: '/dashboard',
    title: 'Dashboard',
    translateKey: '',
    icon: IconDashboard,
    authority: [],
    subMenu: []
  },
  {
    key: 'wallets',
    path: '/wallets',
    title: 'Wallets',
    translateKey: '',
    icon: IconWallet,
    authority: [],
    subMenu: []
  },
  {
    key: 'alerts',
    path: '/alerts',
    title: 'Alerts',
    translateKey: '',
    icon: IconBell,
    authority: [],
    subMenu: []
  },
  {
    key: 'transactions',
    path: '/transactions',
    title: 'Transactions',
    translateKey: '',
    icon: IconExchange,
    authority: [],
    subMenu: []
  },
  {
    key: 'analytics',
    path: '/analytics',
    title: 'Analytics',
    translateKey: '',
    icon: IconChartBar,
    authority: [],
    subMenu: []
  },
  {
    key: 'nodes',
    path: '/nodes',
    title: 'Nodes',
    translateKey: '',
    icon: IconServer,
    authority: [],
    subMenu: []
  },
  {
    key: 'settings',
    path: '/settings',
    title: 'Settings',
    translateKey: '',
    icon: IconSettings,
    authority: [],
    subMenu: []
  },
];

export default navigationConfig;
