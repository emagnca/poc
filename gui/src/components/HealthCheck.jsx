// src/components/HealthCheck.js
import React, { useState, useEffect } from 'react';

function HealthCheck({ baseUrl }) {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    // Check health on component mount
    checkHealth();
  }, []);

  useEffect(() => {
    let interval;
    if (autoRefresh) {
      interval = setInterval(checkHealth, 30000); // Refresh every 30 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${baseUrl}/api/health`);

      if (response.ok) {
        const data = await response.json();
        setHealth(data);
      } else {
        setError(`API Health Check Failed: ${response.status}`);
        setHealth(null);
      }
    } catch (err) {
      setError(`Network error: ${err.message}`);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'ok':
        return '#28a745'; // Green
      case 'warning':
        return '#ffc107'; // Yellow
      case 'error':
      case 'unhealthy':
        return '#dc3545'; // Red
      default:
        return '#6c757d'; // Gray
    }
  };

  return (
    <div className="health-check">
      <h2>🏥 API Health Check</h2>

      <div className="health-controls">
        <button onClick={checkHealth} disabled={loading}>
          {loading ? '⏳ Checking...' : '🔄 Check Health'}
        </button>

        <label className="auto-refresh">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          🔄 Auto-refresh (30s)
        </label>
      </div>

      {error && (
        <div className="error">
          ❌ {error}
        </div>
      )}

      {health && (
        <div className="health-result">
          <div className="health-status">
            <h3>
              <span
                className="status-indicator"
                style={{ color: getStatusColor(health.status) }}
              >
                ●
              </span>
              API Status: {health.status}
            </h3>
            <p><strong>🔧 Service:</strong> {health.service}</p>
            {health.timestamp && (
              <p><strong>🕐 Last Check:</strong> {new Date(health.timestamp).toLocaleString()}</p>
            )}
          </div>

          {health.details && (
            <div className="health-details">
              <h4>📋 Details:</h4>
              <pre>{JSON.stringify(health.details, null, 2)}</pre>
            </div>
          )}

          {health.version && (
            <div className="version-info">
              <p><strong>📦 Version:</strong> {health.version}</p>
            </div>
          )}

          {health.uptime && (
            <div className="uptime-info">
              <p><strong>⏱️ Uptime:</strong> {health.uptime}</p>
            </div>
          )}
        </div>
      )}

      <div className="health-info">
        <h4>ℹ️ About Health Check</h4>
        <ul>
          <li>🟢 <strong>Healthy/OK:</strong> All systems operational</li>
          <li>🔴 <strong>Error/Unhealthy:</strong> Critical issues</li>
          <li>⚫ <strong>Unknown:</strong> Unable to determine status</li>
        </ul>
      </div>
    </div>
  );
}

export default HealthCheck;
