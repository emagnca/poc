// src/components/DocumentStatus.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import './DocumentStatus.css';

const DocumentStatus = ({ baseUrl, lastDocumentId, supportedServices }) => {
  const { getAuthHeaders } = useAuth();

  const [documentId, setDocumentId] = useState(lastDocumentId || '');
  const [selectedService, setSelectedService] = useState('selfsign');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Update document ID when lastDocumentId changes
  useEffect(() => {
    if (lastDocumentId) {
      setDocumentId(lastDocumentId);
    }
  }, [lastDocumentId]);

  // Auto-refresh functionality
  useEffect(() => {
    let interval;
    if (autoRefresh && documentId && status?.status !== 'completed') {
      interval = setInterval(() => {
        checkStatus();
      }, 10000); // Refresh every 10 seconds
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, documentId, status?.status]);

  const checkStatus = async () => {
    if (!documentId.trim()) {
      setError('Please enter a document ID');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Use unified status endpoint
      const response = await fetch(`${baseUrl}/api/${selectedService}/documents/${documentId}/status`, {
        headers: {
          ...getAuthHeaders(),
        },
      });

      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Status check failed');
        setStatus(null);
      }
    } catch (error) {
      console.error('Status check error:', error);
      setError('Network error occurred');
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    if (!documentId.trim()) {
      setError('Please enter a document ID');
      return;
    }

    try {
      // Use unified download endpoint
      const downloadUrl = `${baseUrl}/api/${selectedService}/documents/${documentId}/download`;
      window.open(downloadUrl, '_blank');
    } catch (error) {
      console.error('Download error:', error);
      setError('Download failed');
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

  const getStatusBadge = (statusValue) => {
    switch (statusValue?.toLowerCase()) {
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
    <div className="document-status">
      <h2>📊 Document Status</h2>

      <div className="status-form">
        <div className="form-controls">
          <div className="form-group">
            <label>Service:</label>
            <select
              value={selectedService}
              onChange={(e) => setSelectedService(e.target.value)}
            >
              {supportedServices.map(service => (
                <option key={service} value={service}>
                  {getServiceIcon(service)} {getServiceName(service)}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label>Document ID:</label>
            <input
              type="text"
              value={documentId}
              onChange={(e) => setDocumentId(e.target.value)}
              placeholder="Enter document ID"
            />
          </div>

          <div className="form-actions">
            <button
              type="button"
              onClick={checkStatus}
              disabled={loading}
              className="check-status-btn"
            >
              {loading ? 'Checking...' : '📊 Check Status'}
            </button>

            {status && (
              <button
                type="button"
                onClick={handleDownload}
                className="download-btn"
              >
                📥 Download
              </button>
            )}
          </div>
        </div>

        {status && status.status !== 'completed' && (
          <div className="auto-refresh">
            <label>
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
              />
              🔄 Auto-refresh every 10 seconds
            </label>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {status && (
        <div className="status-result">
          <div className="status-header">
            <h3>📄 Document Information</h3>
            {getStatusBadge(status.status)}
          </div>

          <div className="status-details">
            <div className="detail-row">
              <strong>Document ID:</strong> {status.document_id}
            </div>
            <div className="detail-row">
              <strong>Service:</strong> {getServiceIcon(status.service)} {getServiceName(status.service)}
            </div>
            <div className="detail-row">
              <strong>Status:</strong> {getStatusBadge(status.status)}
            </div>
            {status.metadata?.title && (
              <div className="detail-row">
                <strong>Title:</strong> {status.metadata.title}
              </div>
            )}
            <div className="detail-row">
              <strong>Created:</strong> {formatDate(status.created_at)}
            </div>
            {status.completed_at && (
              <div className="detail-row">
                <strong>Completed:</strong> {formatDate(status.completed_at)}
              </div>
            )}
            {status.file_size && (
              <div className="detail-row">
                <strong>File Size:</strong> {(status.file_size / 1024).toFixed(1)} KB
              </div>
            )}
          </div>

          {status.database_signatures && status.database_signatures.length > 0 && (
            <div className="signatures-section">
              <h4>👥 Signatures ({status.database_signatures.length})</h4>
              {status.database_signatures.map((signature, index) => (
                <div key={index} className="signature-item">
                  <div className="signature-header">
                    <strong>{signature.signer_name}</strong> ({signature.signer_email})
                    {getStatusBadge(signature.status)}
                  </div>
                  <div className="signature-details">
                    <small>Created: {formatDate(signature.created_at)}</small>
                    {signature.signed_at && (
                      <small>Signed: {formatDate(signature.signed_at)}</small>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {status.metadata?.custom_fields && Object.keys(status.metadata.custom_fields).length > 0 && (
            <div className="metadata-section">
              <h4>📋 Additional Metadata</h4>
              <div className="metadata-list">
                {Object.entries(status.metadata.custom_fields).map(([key, value]) => (
                  <div key={key} className="metadata-item">
                    <strong>{key}:</strong> {value}
                  </div>
                ))}
              </div>
            </div>
          )}

          {status.storage_url && (
            <div className="storage-info">
              <h4>☁️ Storage Information</h4>
              <div className="detail-row">
                <strong>Storage URL:</strong>
                <a href={status.storage_url} target="_blank" rel="noopener noreferrer">
                  🔗 View in Storage
                </a>
              </div>
            </div>
          )}

          {status.local_path && (
            <div className="local-info">
              <h4>💾 Local Storage</h4>
              <div className="detail-row">
                <strong>Local Path:</strong> {status.local_path}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DocumentStatus;
