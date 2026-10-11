import { useState } from 'react'
import { BrowserRouter, Routes, Route, useNavigate, Link } from 'react-router-dom'

import Navbar from './components/Navbar'
import Landing from './pages/Landing'
import Home from './pages/Home'
import QueueConfirmation from './pages/QueueConfirmation'
import MyQueue from './pages/MyQueue'
import Profile from './pages/Profile'
import StaffDashboard from './pages/StaffDashboard'
import AdminApprovals from './pages/AdminApprovals'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'

import './App.css'

const CURRENT_YEAR = new Date().getFullYear()

function AppContent() {
  const [queueTicket, setQueueTicket] = useState(null)
  const navigate = useNavigate()

  function handleJoinQueue(ticketOrHospital) {
    // If a real issued ticket object is passed from backend
    if (ticketOrHospital && (ticketOrHospital.ticket_number || ticketOrHospital.ticketId)) {
      const tokenNum = ticketOrHospital.ticket_number || ticketOrHospital.tokenNumber
      const pos = ticketOrHospital.queue_position !== undefined && ticketOrHospital.queue_position !== null
        ? ticketOrHospital.queue_position
        : (ticketOrHospital.position ?? 1)
      const wait = ticketOrHospital.estimated_wait_mins !== undefined && ticketOrHospital.estimated_wait_mins !== null
        ? ticketOrHospital.estimated_wait_mins
        : (ticketOrHospital.waitTime ?? 0)

      const realTicket = {
        id: ticketOrHospital.id,
        ticketId: ticketOrHospital.id,
        sessionId: ticketOrHospital.session_id || ticketOrHospital.sessionId,
        sessionName: ticketOrHospital.session_name || ticketOrHospital.sessionName,
        queueNumber: tokenNum,
        tokenNumber: tokenNum,
        status: ticketOrHospital.status || 'WAITING',
        position: pos,
        patientsAhead: ticketOrHospital.patients_ahead ?? 0,
        waitTime: wait,
        hospitalName: ticketOrHospital.hospital_name || ticketOrHospital.hospitalName || 'Hospital',
        doctorName: ticketOrHospital.doctor_name || ticketOrHospital.doctorName,
        location: ticketOrHospital.hospital_name ? `${ticketOrHospital.hospital_name}, Coimbatore` : 'Coimbatore',
      }

      try {
        sessionStorage.setItem('queueless_last_ticket', JSON.stringify(realTicket))
      } catch {
        // ignore storage errors
      }

      setQueueTicket(realTicket)
      navigate('/queue-confirmation', { state: { ticket: realTicket } })
      return
    }

    // Preserved fallback for mock demo booking
    if (queueTicket) {
      navigate('/my-queue')
      return
    }

    const queueCount = typeof ticketOrHospital?.queue === 'number' ? ticketOrHospital.queue : 12
    const newPosition = queueCount + 1

    const newTicket = {
      queueNumber: `Q-${String(newPosition).padStart(3, '0')}`,
      position: newPosition,
      waitTime: ticketOrHospital?.wait || ticketOrHospital?.avg_consultation_time_mins || 15,
      hospitalName: ticketOrHospital?.name || 'Hospital',
      location: ticketOrHospital?.location || `${ticketOrHospital?.address ? ticketOrHospital.address + ', ' : ''}${ticketOrHospital?.city || 'Coimbatore'}`,
    }

    setQueueTicket(newTicket)
    navigate('/queue-confirmation', { state: { ticket: newTicket } })
  }

  return (
    <div className="app-wrapper">
      <Navbar />

      <div className="main-content">
        <Routes>
          <Route
            path="/"
            element={<Landing />}
          />

          <Route
            path="/hospitals"
            element={<Home onJoin={handleJoinQueue} />}
          />

          <Route
            path="/queue-confirmation"
            element={
              <QueueConfirmation
                queue={queueTicket}
                onBack={() => navigate('/my-queue')}
              />
            }
          />

          <Route
            path="/my-queue"
            element={
              <MyQueue
                queue={queueTicket}
                onLeave={() => setQueueTicket(null)}
              />
            }
          />

          <Route
            path="/staff"
            element={<StaffDashboard />}
          />

          <Route
            path="/admin"
            element={<AdminApprovals />}
          />

          <Route
            path="/profile"
            element={<Profile />}
          />
        </Routes>
      </div>

      <footer className="app-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <h4>QueueLess</h4>
            <p>Smart OPD Appointment & Real-Time Hospital Queue Platform</p>
          </div>

          <div className="footer-links">
            <Link to="/">Home</Link>
            <Link to="/hospitals">Find Hospitals</Link>
            <Link to="/my-queue">My Queue</Link>
            <Link to="/staff">Staff Portal</Link>
            <Link to="/profile">Account</Link>
          </div>
        </div>
        <div className="footer-copy">
          © {CURRENT_YEAR} QueueLess Healthcare Systems. Dedicated to zero-wait outpatient care.
        </div>
      </footer>
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppContent />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}

export default App
