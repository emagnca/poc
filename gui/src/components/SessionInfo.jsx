// src/components/SessionInfo.js
import React from 'react';

function SessionInfo({ currentService, baseUrl, lastDocumentId, lastSigningUrl }) {
  const openSigningUrl = () => {
    if (lastSigningUrl) {
      window.open(lastSigningUrl, '_blank');
    }
  };

  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text).then(() => {
      alert(`${label} copied to clipboard!`);
    }).catch(() => {
      alert('Failed to copy to clipboard');
    });
  };

  const clearSessionData = () => {
    if (window.confirm('Clear all session data? This will remove document IDs, URLs, and preferences.')) {
      localStorage.clear();
      sessionStorage.clear();
      window.location.reload();
    }
  };

  const exportSessionData = () => {
    const sessionData = {
      currentService,
      lastDocumentId,
      lastSigningUrl,
      timestamp: new Date().toISOString(),
      localStorage: { ...localStorage },
      sessionStorage: { ...sessionStorage }
    };

    const dataStr = JSON.stringify(sessionData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `session-data-${new Date().toISOString().split('T')[0]}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const testConnection = async () => {
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (response.ok) {
        alert('✅ Connection successful!');
      } else {
        alert(`❌ Connection failed: ${response.status}`);
      }
    } catch (error) {
      alert(`❌ Connection error: ${error.message}`);
    }
  };

  return (
    <div className="session-info">
      <h2>📋 Current Session Info</h2>

      <div className="info-grid">
        <div className="info-item">
          <label>🔧 Service:</label>
          <div className="info-value">
            <span className="service-badge">{currentService}</span>
          </div>
        </div>

        <div className="info-item">
          <label>🌐 Server:</label>
          <div className="info-value">
            <span>{baseUrl}</span>
            <button
              className="copy-btn"
              onClick={() => copyToClipboard(baseUrl, 'Server URL')}
              title="Copy to clipboard"
            >
              📋
            </button>
          </div>
        </div>

        <div className="info-item">
          <label>📄 Last Document ID:</label>
          <div className="info-value">
            {lastDocumentId ? (
              <>
                <span className="document-id">{lastDocumentId}</span>
                <button
                  className="copy-btn"
                  onClick={() => copyToClipboard(lastDocumentId, 'Document ID')}
                  title="Copy to clipboard"
                >
                  📋
                </button>
              </>
            ) : (
              <span className="no-value">None</span>
            )}
          </div>
        </div>

        <div className="info-item">
          <label>🔗 Last Signing URL:</label>
          <div className="info-value">
            {lastSigningUrl ? (
              <>
                <span className="signing-url">{lastSigningUrl.substring(0, 50)}...</span>
                <div className="url-actions">
                  <button
                    className="open-btn"
                    onClick={openSigningUrl}
                    title="Open signing URL"
                  >
                    🌐 Open
                  </button>
                  <button
                    className="copy-btn"
                    onClick={() => copyToClipboard(lastSigningUrl, 'Signing URL')}
                    title="Copy to clipboard"
                  >
                    📋
                  </button>
                </div>
              </>
            ) : (
              <span className="no-value">None</span>
            )}
          </div>
        </div>
      </div>

      <div className="session-actions">
        <h3>🔧 Quick Actions</h3>
        <div className="actions-grid">
          <button
            onClick={() => window.location.reload()}
            className="action-btn"
          >
            🔄 Refresh Page
          </button>

          <button
            onClick={clearSessionData}
            className="action-btn warning"
          >
            🗑️ Clear Session
          </button>

          <button
            onClick={testConnection}
            className="action-btn"
          >
            🔌 Test Connection
          </button>

          <button
            onClick={exportSessionData}
            className="action-btn"
          >
            📥 Export Session Data
          </button>

          {lastDocumentId && (
            <button
              onClick={() => copyToClipboard(
                `${baseUrl}/api/${currentService}/documents/${lastDocumentId}/status`,
                'Status URL'
              )}
              className="action-btn"
            >
              📋 Copy Status URL
            </button>
          )}

          {lastDocumentId && (
            <button
              onClick={() => copyToClipboard(
                `${baseUrl}/api/${currentService}/documents/${lastDocumentId}/download`,
                'Download URL'
              )}
              className="action-btn"
            >
              📥 Copy Download URL
            </button>
          )}

          {lastSigningUrl && (
            <button
              onClick={() => window.open(lastSigningUrl, '_blank')}
              className="action-btn primary"
            >
              🌐 Open Last Signing URL
            </button>
          )}
        </div>
      </div>

      <div className="api-endpoints">
        <h3>🔗 API Endpoints</h3>
        <div className="endpoints-list">
          <div className="endpoint-item">
            <span className="endpoint-label">Health Check:</span>
            <span className="endpoint-url">{baseUrl}/api/health</span>
            <button
              onClick={() => copyToClipboard(`${baseUrl}/api/health`, 'Health endpoint')}
              className="copy-btn small"
            >
              📋
            </button>
          </div>
          <div className="endpoint-item">
            <span className="endpoint-label">Services:</span>
            <span className="endpoint-url">{baseUrl}/api/services</span>
            <button
              onClick={() => copyToClipboard(`${baseUrl}/api/services`, 'Services endpoint')}
              className="copy-btn small"
            >
              📋
            </button>
          </div>
          <div className="endpoint-item">
            <span className="endpoint-label">Sign Document:</span>
            <span className="endpoint-url">{baseUrl}/api/{currentService}/sign</span>
            <button
              onClick={() => copyToClipboard(`${baseUrl}/api/${currentService}/sign`, 'Sign endpoint')}
              className="copy-btn small"
            >
              📋
            </button>
          </div>
          <div className="endpoint-item">
            <span className="endpoint-label">Search Documents:</span>
            <span className="endpoint-url">{baseUrl}/api/{currentService}/documents/search</span>
            <button
              onClick={() => copyToClipboard(`${baseUrl}/api/${currentService}/documents/search`, 'Search endpoint')}
              className="copy-btn small"
            >
              📋
            </button>
          </div>
        </div>
      </div>

      <div className="browser-info">
        <h3>🌐 Browser Information</h3>
        <div className="browser-details">
          <p><strong>User Agent:</strong> {navigator.userAgent}</p>
          <p><strong>Platform:</strong> {navigator.platform}</p>
          <p><strong>Language:</strong> {navigator.language}</p>
          <p><strong>Online:</strong> {navigator.onLine ? '✅ Yes' : '❌ No'}</p>
          <p><strong>Cookies Enabled:</strong> {navigator.cookieEnabled ? '✅ Yes' : '❌ No'}</p>
          <p><strong>Screen Resolution:</strong> {screen.width} x {screen.height}</p>
          <p><strong>Viewport Size:</strong> {window.innerWidth} x {window.innerHeight}</p>
          <p><strong>Time Zone:</strong> {Intl.DateTimeFormat().resolvedOptions().timeZone}</p>
        </div>
      </div>

      <div className="storage-info">
        <h3>💾 Storage Information</h3>
        <div className="storage-details">
          <div className="storage-section">
            <h4>Local Storage ({localStorage.length} items):</h4>
            {localStorage.length > 0 ? (
              <div className="storage-items">
                {Object.keys(localStorage).map(key => (
                  <div key={key} className="storage-item">
                    <span className="storage-key">{key}:</span>
                    <span className="storage-value">
                      {localStorage.getItem(key)?.substring(0, 50)}
                      {localStorage.getItem(key)?.length > 50 ? '...' : ''}
                    </span>
                    <button
                      onClick={() => copyToClipboard(localStorage.getItem(key), `LocalStorage ${key}`)}
                      className="copy-btn small"
                    >
                      📋
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p>No items in local storage</p>
            )}
          </div>

          <div className="storage-section">
            <h4>Session Storage ({sessionStorage.length} items):</h4>
            {sessionStorage.length > 0 ? (
              <div className="storage-items">
                {Object.keys(sessionStorage).map(key => (
                  <div key={key} className="storage-item">
                    <span className="storage-key">{key}:</span>
                    <span className="storage-value">
                      {sessionStorage.getItem(key)?.substring(0, 50)}
                      {sessionStorage.getItem(key)?.length > 50 ? '...' : ''}
                    </span>
                    <button
                      onClick={() => copyToClipboard(sessionStorage.getItem(key), `SessionStorage ${key}`)}
                      className="copy-btn small"
                    >
                      📋
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <p>No items in session storage</p>
            )}
          </div>
        </div>
      </div>

      <div className="performance-info">
        <h3>⚡ Performance Information</h3>
        <div className="performance-details">
          <p><strong>Page Load Time:</strong> {performance.now().toFixed(2)}ms</p>
          <p><strong>Memory Usage:</strong> {
            performance.memory ?
            `${(performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB` :
            'Not available'
          }</p>
          <p><strong>Connection:</strong> {
            navigator.connection ?
            `${navigator.connection.effectiveType} (${navigator.connection.downlink} Mbps)` :
            'Not available'
          }</p>
        </div>
      </div>
    </div>
  );
}

export default SessionInfo;
