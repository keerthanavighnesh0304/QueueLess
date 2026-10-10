
import { useState } from 'react'
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom'

import Navbar from './components/Navbar'
import Home from './pages/Home'
import QueueConfirmation from './pages/QueueConfirmation'
import MyQueue from './pages/MyQueue'

import './App.css'

function AppContent() {
  const [queueTicket, setQueueTicket] = useState(null)
  const navigate = useNavigate()

  
function handleJoinQueue(hospital) {
  // Check whether the user already has an active queue
  if (queueTicket) {
    navigate('/my-queue')
    return
  }

  const newPosition = hospital.queue + 1

  const newTicket = {
    queueNumber: `Q-${String(newPosition).padStart(3, '0')}`,
    position: newPosition,
    waitTime: hospital.wait,
    hospitalName: hospital.name,
    location: hospital.location,
  }

  setQueueTicket(newTicket)

  // Navigate after creating the ticket
  navigate('/queue-confirmation')
}

  return (
    <>
      <Navbar />

      <Routes>
        <Route
          path="/"
          element={<Home onJoin={handleJoinQueue} />}
        />

        <Route
          path="/hospitals"
          element={<Home onJoin={handleJoinQueue} />}
        />

        <Route
          path="/queue-confirmation"
          element={
            queueTicket ? (
              <QueueConfirmation
                queue={queueTicket}
                onBack={() => navigate('/my-queue')}
              />
            ) : (
              <p>Please join a hospital queue first.</p>
            )
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
          path="/profile"
          element={<h1>Profile Page - Coming Soon</h1>}
        />
      </Routes>
    </>
  )
}

function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  )
}

export default App
