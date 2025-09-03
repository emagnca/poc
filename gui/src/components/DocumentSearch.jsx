// src/components/DocumentSearch.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import './DocumentSearch.css';

const DocumentSearch = ({ baseUrl, supportedServices }) => {
  const { getAuthHeaders } = useAuth();

  const [searchType, setSearchType] = useState('document_id');
  const [searchValue, setSearchValue] = useState('');
  const [selectedService, setSelectedService] = useState('all');
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState('');
  const [showSearch, setShowSearch] = useState(false);

  // Load all documents on component mount
  useEffect(() => {
    loadAllDocuments();
  }, []);

  const loadAllDocuments = async () => {
    setLoading(true);
    setError('');

    try {
      // Use a new endpoint to get all user documents
      const response = await fetch(`${baseUrl}/api/documents/user`, {
        headers: {
          ...getAuthHeaders(),
        },
      });

      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents || []);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to load documents');
      }
    } catch (error) {
      console.error('Load documents error:', error);
      setError('Network error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();

    if (!searchValue.trim()) {
      setError('Please enter a search value');
      return;
    }

    setLoading(true);
    setError('');

    try {
      let endpoint;

      if (searchType === 'document_id') {
        // Use unified document details endpoint
        endpoint = `${baseUrl}/api/${selectedService}/documents/${searchValue}`;

        const response = await fetch(endpoint, {
          headers: {
            ...getAuthHeaders(),
          },
        });

        if (response.ok) {
          const data = await response.json();
          setDocuments([data]); // Show single document as array
        } else {
          const errorData = await response.json();
          setError(errorData.detail || 'Search failed');
          setDocuments([]);
        }
      } else {
        // For other search types, use search endpoint
        endpoint = `${baseUrl}/api/documents/search?type=${searchType}&value=${searchValue}${selectedService !== 'all' ? `&service=${selectedService}` : ''}`;

        const response = await fetch(endpoint, {
          headers: {
            ...getAuthHeaders(),
          },
        });

        if (response.ok) {
          const data = await response.json();
          setDocuments(data.documents || []);
        } else {
          const errorData = await response.json();
          setError(errorData.detail || 'Search failed');
          setDocuments([]);
        }
      }
    } catch (error) {
      console.error('Search error:', error);
      setError('Network error occurred');
      setDocuments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (documentId, service) => {
    try {
      // Use unified download endpoint
      const downloadUrl = `${baseUrl}/api/${service}/documents/${documentId}/download`;
      window.open(downloadUrl, '_blank');
    } catch (error) {
      console.error('Download error:', error);
      setError('Download failed');
    }
  };

  const refreshStatus = async (documentId, service) => {
    try {
      setLoading(true);
      // Use unified status endpoint
      const response = await fetch(`${baseUrl}/api/${service}/documents/${documentId}/status`, {
        headers: {
          ...getAuthHeaders(),
        },
      });

      if (response.ok) {
        const statusData = await response.json();
        // Update the specific document in the list
        setDocuments(prev => prev.map(doc =>
          doc.document_id === documentId
            ? { ...doc, status: statusData.status, signatures: statusData.database_signatures || doc.signatures }
            : doc
        ));
      } else {
        setError('Failed to refresh status');
      }
    } catch (error) {
      console.error('Status refresh error:', error);
      setError('Status refresh failed');
    } finally {
      setLoading(false);
    }
  };

  const getServiceIcon = (service) => {
    switch (service) {
      case 'scrive': return '📝';
      case 'docusign': return '📄';
      case 'selfsign': return '🔐';
      default: return '📋';
    }
  };

  const getServiceName = (service) => {
    switch (service) {
      case 'scrive': return 'Scrive';
      case 'docusign': return 'DocuSign';
      case 'selfsign': return 'Self-Sign';
      default: return service;
    }
  };

  const getStatusBadge = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return <span className="status-badge completed">✅ Completed</span>;
      case 'pending':
        return <span className="status-badge pending">⏳ Pending</span>;
      case 'in_progress':
        return <span className="status-badge in-progress">🔄 In Progress</span>;
      case 'cancelled':
        return <span className="status-badge cancelled">❌ Cancelled</span>;
      default:
        return <span className="status-badge unknown">❓ Unknown</span>;
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="document-search">
      <div className="search-header">
        <h2>📚 My Documents</h2>
        <div className="header-actions">
          <button
            onClick={() => setShowSearch(!showSearch)}
            className="toggle-search-btn"
          >
            {showSearch ? '📚 Show All' : '🔍 Search'}
          </button>
          <button
            onClick={loadAllDocuments}
            disabled={loading}
            className="refresh-all-btn"
          >
            🔄 Refresh
          </button>
        </div>
      </div>

      {showSearch && (
        <div className="search-form">
          <form onSubmit={handleSearch}>
            <div className="search-controls">
              <div className="form-group">
                <label>Service:</label>
                <select
                  value={selectedService}
                  onChange={(e) => setSelectedService(e.target.value)}
                >
                  <option value="all">🌐 All Services</option>
                  {supportedServices.map(service => (
                    <option key={service} value={service}>
                      {getServiceIcon(service)} {getServiceName(service)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Search by:</label>
                <select
                  value={searchType}
                  onChange={(e) => setSearchType(e.target.value)}
                >
                  <option value="document_id">Document ID</option>
                  <option value="signer_email">Signer Email</option>
                  <option value="title">Document Title</option>
                </select>
              </div>

              <div className="form-group">
                <label>Search value:</label>
                <input
                  type="text"
                  value={searchValue}
                  onChange={(e) => setSearchValue(e.target.value)}
                  placeholder={`Enter ${searchType.replace('_', ' ')}`}
                  required
                />
              </div>
            </div>

            <button type="submit" disabled={loading} className="search-button">
              {loading ? 'Searching...' : '🔍 Search'}
            </button>
          </form>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}

      {loading && !documents.length && (
        <div className="loading-message">
          🔄 Loading documents...
        </div>
      )}

      {documents.length === 0 && !loading && !error && (
        <div className="no-documents">
          📭 No documents found. Start by signing your first document!
        </div>
      )}

      {documents.length > 0 && (
        <div className="documents-list">
          <div className="documents-header">
            <h3>📄 Documents ({documents.length})</h3>
          </div>

          {documents.map((doc, index) => (
            <div key={doc.document_id || index} className="document-item">
              <div className="document-header">
                <div className="document-title">
                  <h4>{doc.metadata?.title || `Document ${doc.document_id?.slice(-8) || index + 1}`}</h4>
                  <span className="document-service">
                    {getServiceIcon(doc.service)} {getServiceName(doc.service)}
                  </span>
                </div>
                <div className="document-actions">
                  <button
                    onClick={() => handleDownload(doc.document_id, doc.service)}
                    className="download-btn"
                    title="Download document"
                  >
                    📥
                  </button>
                  <button
                    onClick={() => refreshStatus(doc.document_id, doc.service)}
                    className="refresh-btn"
                    disabled={loading}
                    title="Refresh status"
                  >
                    🔄
                  </button>
                </div>
              </div>

              <div className="document-info">
                <div className="info-row">
                  <strong>ID:</strong> {doc.document_id}
                </div>
                <div className="info-row">
                  <strong>Status:</strong> {getStatusBadge(doc.status)}
                </div>
                <div className="info-row">
                  <strong>Created:</strong> {formatDate(doc.created_at)}
                </div>
                {doc.completed_at && (
                  <div className="info-row">
                    <strong>Completed:</strong> {formatDate(doc.completed_at)}
                  </div>
                )}
              </div>

              {doc.signatures && doc.signatures.length > 0 && (
                <div className="signatures-summary">
                  <strong>👥 Signers:</strong>
                  <div className="signers-list">
                    {doc.signatures.map((signature, sigIndex) => (
                      <span key={sigIndex} className="signer-summary">
                        {signature.signer_name} {getStatusBadge(signature.status)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {doc.metadata?.custom_fields && Object.keys(doc.metadata.custom_fields).length > 0 && (
                <div className="document-metadata">
                  <strong>📋 Metadata:</strong>
                  <div className="metadata-summary">
                    {Object.entries(doc.metadata.custom_fields).slice(0, 3).map(([key, value]) => (
                      <span key={key} className="metadata-tag">
                        {key}: {value}
                      </span>
                    ))}
                    {Object.keys(doc.metadata.custom_fields).length > 3 && (
                      <span className="metadata-more">
                        +{Object.keys(doc.metadata.custom_fields).length - 3} more
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DocumentSearch;
