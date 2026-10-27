import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AdminLayout } from './layouts/AdminLayout'
import { ClientLayout } from './layouts/ClientLayout'
import { ParticipantLayout } from './layouts/ParticipantLayout'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { OrganizationsPage } from './pages/OrganizationsPage'
import { AcademyHubPage } from './pages/AcademyHubPage'
import { LessonPlayerPage } from './pages/LessonPlayerPage'
import { LocationsPage } from './pages/LocationsPage'
import { MissionsPage } from './pages/MissionsPage'
import { NetworkPage } from './pages/NetworkPage'
import { ClientDashboardPage } from './pages/ClientDashboardPage'
import { OperationalPassportPage } from './pages/OperationalPassportPage'
import { StudentAcademyPage } from './pages/StudentAcademyPage'
import { ParticipantMissionsPage } from './pages/ParticipantMissionsPage'
import { NoAccessPage } from './pages/NoAccessPage'
import { InvitationAcceptPage } from './pages/InvitationAcceptPage'
import { AccountPage } from './pages/AccountPage'
import { RepresentativeSchoolsPage } from './pages/RepresentativeSchoolsPage'
import { InvitationsPage } from './pages/InvitationsPage'
import { ParticipantsPage } from './pages/ParticipantsPage'
import { queryClient } from './lib/queryClient'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Rotas Públicas */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/cadastro-colaborador" element={<Navigate to="/login" replace />} />
          <Route path="/convite/:token" element={<InvitationAcceptPage />} />
          <Route path="/convite-publico/:token" element={<InvitationAcceptPage />} />
          <Route path="/sem-acesso" element={<NoAccessPage />} />

          {/* Área 1: Administração (/admin) - Restrito a Administradores */}
          <Route element={<ProtectedRoute allowedRoles={['ADMIN']} />}>
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<DashboardPage />} />
              <Route path="organizations" element={<OrganizationsPage />} />
              <Route path="academy" element={<AcademyHubPage />} />
              <Route path="academy/course/:courseId/lesson/:lessonId" element={<LessonPlayerPage />} />
              <Route path="locations" element={<LocationsPage />} />
              <Route path="missions" element={<MissionsPage />} />
              <Route path="network" element={<NetworkPage />} />
              <Route path="invitations" element={<InvitationsPage />} />
              <Route path="participants" element={<ParticipantsPage />} />
            </Route>
          </Route>

          {/* Área 2: Cliente (/cliente) - Organizadoras e Bancas */}
          <Route element={<ProtectedRoute allowedRoles={['CLIENT', 'ADMIN']} />}>
            <Route path="/cliente" element={<ClientLayout />}>
              <Route index element={<ClientDashboardPage />} />
              <Route path="locations" element={<LocationsPage />} />
              <Route path="missions" element={<MissionsPage />} />
              <Route path="network" element={<NetworkPage />} />
              <Route path="invitations" element={<InvitationsPage />} />
              <Route path="participants" element={<ParticipantsPage />} />
            </Route>
          </Route>

          {/* Área 3: Participantes (/participante) - Colaboradores Operacionais */}
          <Route element={<ProtectedRoute allowedRoles={['PARTICIPANT', 'ADMIN']} />}>
            <Route path="/participante" element={<ParticipantLayout />}>
              <Route index element={<OperationalPassportPage />} />
              <Route path="academy" element={<StudentAcademyPage />} />
              <Route path="academy/course/:courseId/lesson/:lessonId" element={<LessonPlayerPage />} />
              <Route path="missions" element={<ParticipantMissionsPage />} />
              <Route path="escolas" element={<RepresentativeSchoolsPage />} />
              <Route path="conta" element={<AccountPage />} />
            </Route>
          </Route>

          {/* Fallback de Redirecionamento */}
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
