import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import Login from './components/Login';
import DocumentSigning from './components/DocumentSigning';
import DocumentSearch from './components/DocumentSearch';
import './App.css';

const AppContent = () => {
  const { isAuthenticated, getAuthHeaders, user } = useAuth();
  const [activeTab, setActiveTab] = useState('signing');
  const [currentService, setCurrentService] = useState('scrive');
  const [supportedServices, setSupportedServices] = useState([]);
  const [lastDocumentId, setLastDocumentId] = useState(null);
  const [lastSigningUrl, setLastSigningUrl] = useState(null);
  const [loading, setLoading] = useState(false);

  const baseUrl = /*process.env.REACT_APP_API_URL ||*/ 'http://localhost:8000';

  // Fetch supported services when authenticated
  useEffect(() => {
    const fetchServices = async () => {
      if (!isAuthenticated) {
        setSupportedServices([]);
        return;
      }

      try {
        setLoading(true);
        const response = await fetch(`${baseUrl}/api/services`, {
          headers: getAuthHeaders(),
        });

        if (response.ok) {
          const data = await response.json();
          setSupportedServices(data.supported_services || []);
        } else {
          console.error('Failed to fetch services');
          // Set default services as fallback
          setSupportedServices(['scrive', 'docusign', 'selfsign']);
        }
      } catch (error) {
        console.error('Error fetching services:', error);
        // Set default services as fallback
        setSupportedServices(['scrive', 'docusign', 'selfsign']);
      } finally {
        setLoading(false);
      }
    };

    fetchServices();
  }, [isAuthenticated, baseUrl, getAuthHeaders]);

  // Reset current service if it's not in supported services
  useEffect(() => {
    if (supportedServices.length > 0 && !supportedServices.includes(currentService)) {
      setCurrentService(supportedServices[0]);
    }
  }, [supportedServices, currentService]);

  if (!isAuthenticated) {
    return <Login baseUrl={baseUrl} />;
  }

  if (loading) {
    return (
      <div className="loading-container">
        <div className="loading-spinner"></div>
        <p>Loading application...</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>📄 Document Signing Platform</h1>
          <div className="user-info">
            Welcome, {user?.full_name || user?.email}
          </div>
        </div>
        <div className="header-right">
          <button
            onClick={() => window.location.reload()}
            className="logout-button"
          >
            🔄 Refresh
          </button>
        </div>
      </header>

      <nav className="tab-navigation">
        <button
          className={activeTab === 'signing' ? 'active' : ''}
          onClick={() => setActiveTab('signing')}
        >
          ✍️ Sign Documents
        </button>
        <button
          className={activeTab === 'search' ? 'active' : ''}
          onClick={() => setActiveTab('search')}
        >
          🔍 Search Documents
        </button>
      </nav>

      <main className="app-main">
        {activeTab === 'signing' && (
          <DocumentSigning
            baseUrl={baseUrl}
            currentService={currentService}
            setCurrentService={setCurrentService}
            supportedServices={supportedServices}
            setLastDocumentId={setLastDocumentId}
            setLastSigningUrl={setLastSigningUrl}
          />
        )}

        {activeTab === 'search' && (
          <DocumentSearch
            baseUrl={baseUrl}
            currentService={currentService}
            setCurrentService={setCurrentService}
            supportedServices={supportedServices}
            setLastDocumentId={setLastDocumentId}
          />
        )}
      </main>
    </div>
  );
};

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
