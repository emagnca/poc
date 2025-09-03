// src/components/UserProfile.jsx
import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import './UserProfile.css';

const UserProfile = () => {
  const { user, logout } = useAuth();

  return (
    <div className="user-profile">
      <div className="user-info">
        <span className="user-name">👤 {user?.full_name}</span>
        <span className="user-email">{user?.email}</span>
      </div>
      <button onClick={logout} className="logout-button">
        🚪 Logout
      </button>
    </div>
  );
};

export default UserProfile;
