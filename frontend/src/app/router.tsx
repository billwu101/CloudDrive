import { createBrowserRouter, Navigate } from 'react-router-dom'

import { DrivePage } from '@/pages/DrivePage'
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { RecentPage } from '@/pages/RecentPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { SearchPage } from '@/pages/SearchPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { SharedPage } from '@/pages/SharedPage'
import { ShareTokenPage } from '@/pages/ShareTokenPage'
import { StarredPage } from '@/pages/StarredPage'
import { TrashPage } from '@/pages/TrashPage'

import { ProtectedLayout } from './ProtectedLayout'
import { RedirectIfAuth } from './RedirectIfAuth'
import { RequireAuth } from './RequireAuth'

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
          { path: '/drive', element: <DrivePage /> },
          { path: '/drive/folder/:folderId', element: <DrivePage /> },
          { path: '/recent', element: <RecentPage /> },
          { path: '/starred', element: <StarredPage /> },
          { path: '/shared', element: <SharedPage /> },
          { path: '/trash', element: <TrashPage /> },
          { path: '/search', element: <SearchPage /> },
          { path: '/settings', element: <SettingsPage /> },
        ],
      },
    ],
  },

  { path: '*', element: <NotFoundPage /> },
])
