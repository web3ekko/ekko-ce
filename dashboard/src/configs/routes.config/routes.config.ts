import { lazy } from 'react'
import authRoute from './authRoute'
import type { Routes } from '@/@types/routes'

export const publicRoutes: Routes = [...authRoute]

export const protectedRoutes = [
  {
    key: 'dashboard',
    path: '/dashboard',
    component: lazy(() => import('@/pages/ekko/Dashboard')),
    authority: []
  },
  {
    key: 'wallets',
    path: '/wallets',
    component: lazy(() => import('@/pages/ekko/Wallets')),
    authority: []
  },
  {
    key: 'alerts',
    path: '/alerts',
    component: lazy(() => import('@/pages/ekko/Alerts')),
    authority: []
  },
  {
    key: 'transactions',
    path: '/transactions',
    component: lazy(() => import('@/pages/ekko/Transactions')),
    authority: []
  },
  {
    key: 'analytics',
    path: '/analytics',
    component: lazy(() => import('@/pages/ekko/Analytics')),
    authority: []
  },
  {
    key: 'nodes',
    path: '/nodes',
    component: lazy(() => import('@/pages/ekko/Nodes')),
    authority: []
  },
  {
    key: 'settings',
    path: '/settings',
    component: lazy(() => import('@/pages/ekko/Settings')),
    authority: []
  },
]
