import React, { lazy, Suspense } from 'react';
import useAuth from '@/utils/hooks/useAuth';
import useLocale from '@/utils/hooks/useLocale';
import LoadingScreen from '@/components/LoadingScreen/LoadingScreen';
import { IOSLayout } from './IOSLayout';
import Views from './Views';

export function Layout() {
  const { authenticated } = useAuth();

  useLocale();

  if (!authenticated) {
    const AuthLayout = lazy(() => import('./AuthLayout'));
    return (
      <Suspense
        fallback={
          <div className="flex flex-auto flex-col h-[100vh]">
            <LoadingScreen />
          </div>
        }
      >
        <AuthLayout />
      </Suspense>
    );
  }

  return (
    <IOSLayout>
      <Views />
    </IOSLayout>
  );
}
