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
    key: 'alertDetail',
    path: '/ekko/alerts/:id',
    component: lazy(() => import('@/pages/ekko/AlertDetail')),
    authority: []
  },
  {
    key: 'transactions',
    path: '/transactions',
    component: lazy(() => import('@/pages/ekko/Transactions')),
    authority: []
  },
  {
    key: 'workflows',
    path: '/workflows',
    component: lazy(() => import('@/pages/ekko/Workflows')),
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
