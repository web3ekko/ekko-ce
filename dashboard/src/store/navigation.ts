/**
 * Navigation Store
 * 
 * Global state management for navigation, breadcrumbs, and routing
 */

import { create } from 'zustand'
import { subscribeWithSelector } from 'zustand/middleware'

interface Breadcrumb {
  label: string
  path?: string
  icon?: React.ReactNode
}

interface NavigationItem {
  id: string
  label: string
  path: string
  icon?: React.ReactNode
  badge?: {
    value: string | number
    color?: string
  }
  children?: NavigationItem[]
  visible?: boolean
  permissions?: string[]
}

interface NavigationStore {
  // Current navigation state
  currentPath: string
  setCurrentPath: (path: string) => void
  
  // Breadcrumbs
  breadcrumbs: Breadcrumb[]
  setBreadcrumbs: (breadcrumbs: Breadcrumb[]) => void
  pushBreadcrumb: (breadcrumb: Breadcrumb) => void
  popBreadcrumb: () => void
  clearBreadcrumbs: () => void
  
  // Navigation history
  history: string[]
  pushHistory: (path: string) => void
  goBack: () => string | undefined
  goForward: () => string | undefined
  clearHistory: () => void
  
  // Navigation items
  navigationItems: NavigationItem[]
  setNavigationItems: (items: NavigationItem[]) => void
  updateNavigationItem: (id: string, updates: Partial<NavigationItem>) => void
  
  // Expanded sections (for collapsible navigation)
  expandedSections: Set<string>
  toggleSection: (sectionId: string) => void
  expandSection: (sectionId: string) => void
  collapseSection: (sectionId: string) => void
  collapseAllSections: () => void
  
  // Quick navigation / search
  recentPaths: string[]
  addRecentPath: (path: string) => void
  clearRecentPaths: () => void
  
  // Navigation state
  isNavigating: boolean
  setIsNavigating: (navigating: boolean) => void
  
  // Page metadata
  pageTitle: string
  setPageTitle: (title: string) => void
  pageDescription?: string
  setPageDescription: (description?: string) => void
  
  // Navigation helpers
  canGoBack: () => boolean
  canGoForward: () => boolean
  getCurrentNavigationItem: () => NavigationItem | undefined
  getNavigationPath: (itemId: string) => NavigationItem[]
  
  // Reset
  resetNavigationStore: () => void
}

const defaultNavigationItems: NavigationItem[] = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    path: '/dashboard',
    visible: true,
  },
  {
    id: 'alerts',
    label: 'Alerts',
    path: '/alerts',
    visible: true,
    badge: {
      value: 0,
      color: 'red',
    },
  },
  {
    id: 'wallets',
    label: 'Wallets',
    path: '/wallets',
    visible: true,
    children: [
      {
        id: 'wallet-groups',
        label: 'Wallet Groups',
        path: '/wallets/groups',
        visible: true,
      },
      {
        id: 'provider-wallets',
        label: 'Provider Wallets',
        path: '/wallets/providers',
        visible: true,
      },
    ],
  },
  {
    id: 'team',
    label: 'Team',
    path: '/team',
    visible: true,
  },
  {
    id: 'api',
    label: 'Developer API',
    path: '/api',
    visible: true,
  },
  {
    id: 'settings',
    label: 'Settings',
    path: '/settings',
    visible: true,
    children: [
      {
        id: 'settings-profile',
        label: 'Profile',
        path: '/settings/profile',
        visible: true,
      },
      {
        id: 'settings-security',
        label: 'Security',
        path: '/settings/security',
        visible: true,
      },
      {
        id: 'settings-billing',
        label: 'Billing',
        path: '/settings/billing',
        visible: true,
      },
    ],
  },
]

export const useNavigationStore = create<NavigationStore>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    currentPath: window.location.pathname,
    breadcrumbs: [],
    history: [window.location.pathname],
    navigationItems: defaultNavigationItems,
    expandedSections: new Set<string>(),
    recentPaths: [],
    isNavigating: false,
    pageTitle: 'Dashboard',
    pageDescription: undefined,
    
    // Actions
    setCurrentPath: (path) => {
      const state = get()
      if (path !== state.currentPath) {
        set((state) => ({
          currentPath: path,
          history: [...state.history, path].slice(-50), // Keep last 50 items
        }))
        
        // Add to recent paths
        get().addRecentPath(path)
      }
    },
    
    // Breadcrumb actions
    setBreadcrumbs: (breadcrumbs) => set({ breadcrumbs }),
    pushBreadcrumb: (breadcrumb) => set((state) => ({
      breadcrumbs: [...state.breadcrumbs, breadcrumb],
    })),
    popBreadcrumb: () => set((state) => ({
      breadcrumbs: state.breadcrumbs.slice(0, -1),
    })),
    clearBreadcrumbs: () => set({ breadcrumbs: [] }),
    
    // History actions
    pushHistory: (path) => set((state) => ({
      history: [...state.history, path].slice(-50),
    })),
    goBack: () => {
      const state = get()
      const currentIndex = state.history.indexOf(state.currentPath)
      if (currentIndex > 0) {
        const previousPath = state.history[currentIndex - 1]
        set({ currentPath: previousPath })
        return previousPath
      }
      return undefined
    },
    goForward: () => {
      const state = get()
      const currentIndex = state.history.indexOf(state.currentPath)
      if (currentIndex < state.history.length - 1) {
        const nextPath = state.history[currentIndex + 1]
        set({ currentPath: nextPath })
        return nextPath
      }
      return undefined
    },
    clearHistory: () => set({ history: [get().currentPath] }),
    
    // Navigation items actions
    setNavigationItems: (items) => set({ navigationItems: items }),
    updateNavigationItem: (id, updates) => set((state) => {
      const updateItem = (items: NavigationItem[]): NavigationItem[] => {
        return items.map((item) => {
          if (item.id === id) {
            return { ...item, ...updates }
          }
          if (item.children) {
            return { ...item, children: updateItem(item.children) }
          }
          return item
        })
      }
      return { navigationItems: updateItem(state.navigationItems) }
    }),
    
    // Expanded sections actions
    toggleSection: (sectionId) => set((state) => {
      const newExpanded = new Set(state.expandedSections)
      if (newExpanded.has(sectionId)) {
        newExpanded.delete(sectionId)
      } else {
        newExpanded.add(sectionId)
      }
      return { expandedSections: newExpanded }
    }),
    expandSection: (sectionId) => set((state) => {
      const newExpanded = new Set(state.expandedSections)
      newExpanded.add(sectionId)
      return { expandedSections: newExpanded }
    }),
    collapseSection: (sectionId) => set((state) => {
      const newExpanded = new Set(state.expandedSections)
      newExpanded.delete(sectionId)
      return { expandedSections: newExpanded }
    }),
    collapseAllSections: () => set({ expandedSections: new Set() }),
    
    // Recent paths actions
    addRecentPath: (path) => set((state) => {
      const filtered = state.recentPaths.filter((p) => p !== path)
      return { recentPaths: [path, ...filtered].slice(0, 10) }
    }),
    clearRecentPaths: () => set({ recentPaths: [] }),
    
    // Navigation state actions
    setIsNavigating: (navigating) => set({ isNavigating: navigating }),
    
    // Page metadata actions
    setPageTitle: (title) => set({ pageTitle: title }),
    setPageDescription: (description) => set({ pageDescription: description }),
    
    // Helper functions
    canGoBack: () => {
      const state = get()
      const currentIndex = state.history.indexOf(state.currentPath)
      return currentIndex > 0
    },
    canGoForward: () => {
      const state = get()
      const currentIndex = state.history.indexOf(state.currentPath)
      return currentIndex < state.history.length - 1
    },
    getCurrentNavigationItem: () => {
      const state = get()
      const findItem = (items: NavigationItem[]): NavigationItem | undefined => {
        for (const item of items) {
          if (item.path === state.currentPath) {
            return item
          }
          if (item.children) {
            const found = findItem(item.children)
            if (found) return found
          }
        }
        return undefined
      }
      return findItem(state.navigationItems)
    },
    getNavigationPath: (itemId) => {
      const findPath = (
        items: NavigationItem[],
        path: NavigationItem[] = []
      ): NavigationItem[] => {
        for (const item of items) {
          if (item.id === itemId) {
            return [...path, item]
          }
          if (item.children) {
            const found = findPath(item.children, [...path, item])
            if (found.length > path.length) return found
          }
        }
        return path
      }
      return findPath(get().navigationItems)
    },
    
    // Reset action
    resetNavigationStore: () => set({
      currentPath: '/',
      breadcrumbs: [],
      history: ['/'],
      navigationItems: defaultNavigationItems,
      expandedSections: new Set(),
      recentPaths: [],
      isNavigating: false,
      pageTitle: 'Dashboard',
      pageDescription: undefined,
    }),
  }))
)

// Selectors
export const selectCurrentPath = (state: NavigationStore) => state.currentPath
export const selectBreadcrumbs = (state: NavigationStore) => state.breadcrumbs
export const selectNavigationItems = (state: NavigationStore) => state.navigationItems
export const selectExpandedSections = (state: NavigationStore) => state.expandedSections
export const selectRecentPaths = (state: NavigationStore) => state.recentPaths
export const selectIsNavigating = (state: NavigationStore) => state.isNavigating
export const selectPageMetadata = (state: NavigationStore) => ({
  title: state.pageTitle,
  description: state.pageDescription,
})
