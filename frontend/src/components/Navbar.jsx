import './Navbar.css'
import { NavLink } from 'react-router-dom'

function Navbar() {
  return (
    <nav className="navbar">

      <div className="navbar-brand">
        <h2>QueueLess</h2>
        <span>Smart Queue Management</span>
      </div>

      <div className="navbar-links">
        <NavLink to="/">Home</NavLink>
        <NavLink to="/hospitals">Find Hospitals</NavLink>
        <NavLink to="/my-queue">My Queue</NavLink>
        <NavLink to="/profile">Profile</NavLink>
      </div>

    </nav>
  )
}

export default Navbar