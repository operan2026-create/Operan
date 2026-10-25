import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminLayout } from './layouts/AdminLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { OrganizationsPage } from './pages/OrganizationsPage'
import { AcademyHubPage } from './pages/AcademyHubPage'
import { LessonPlayerPage } from './pages/LessonPlayerPage'
import { LocationsPage } from './pages/LocationsPage'
import { MissionsPage } from './pages/MissionsPage'
import { NetworkPage } from './pages/NetworkPage'
import { CollaboratorRegisterPage } from './pages/CollaboratorRegisterPage'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/cadastro-colaborador" element={<CollaboratorRegisterPage />} />

          {/* Admin Platform Routes */}
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="organizations" element={<OrganizationsPage />} />
            <Route path="academy" element={<AcademyHubPage />} />
            <Route path="academy/course/:courseId/lesson/:lessonId" element={<LessonPlayerPage />} />
            <Route path="locations" element={<LocationsPage />} />
            <Route path="missions" element={<MissionsPage />} />
            <Route path="network" element={<NetworkPage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
