import { createBrowserRouter, Navigate } from 'react-router-dom'

import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { ShareTokenPage } from '@/pages/ShareTokenPage'

import { ProtectedLayout } from './ProtectedLayout'
import { RedirectIfAuth } from './RedirectIfAuth'
import { RequireAuth } from './RequireAuth'
import {
  LazyDrivePage,
  LazyRecentPage,
  LazySearchPage,
  LazySettingsPage,
  LazySharedPage,
  LazySkillsPage,
  LazyStarredPage,
  LazyTimeMachinePage,
  LazyTrashPage,
} from './LazyPages'

export const router = createBrowserRouter([
  // Public auth routes — redirect to /drive if already logged in
  {
    element: <RedirectIfAuth />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
    ],
  },

  // Public share-token route (no login required)
  { path: '/s/:shareToken', element: <ShareTokenPage /> },

  // Protected routes — redirect to /login if unauthenticated
  {
    element: <RequireAuth />,
    children: [
      {
        element: <ProtectedLayout />,
        children: [
          { index: true, element: <Navigate to="/drive" replace /> },
          { path: '/drive', element: <LazyDrivePage /> },
          { path: '/drive/folder/:folderId', element: <LazyDrivePage /> },
          { path: '/recent', element: <LazyRecentPage /> },
          { path: '/starred', element: <LazyStarredPage /> },
          { path: '/shared', element: <LazySharedPage /> },
          { path: '/skills', element: <LazySkillsPage /> },
          { path: '/time-machine', element: <LazyTimeMachinePage /> },
          { path: '/trash', element: <LazyTrashPage /> },
          { path: '/search', element: <LazySearchPage /> },
          { path: '/settings', element: <LazySettingsPage /> },
        ],
      },
    ],
  },

  { path: '*', element: <NotFoundPage /> },
])
