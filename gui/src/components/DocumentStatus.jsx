// src/components/DocumentStatus.js
import React, { useState, useEffect } from 'react';

function DocumentStatus({ baseUrl, currentService, lastDocumentId }) {
  const [documentId, setDocumentId] = useState('');
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (lastDocumentId) {
      setDocumentId(lastDocumentId);
    }
  }, [lastDocumentId]);

  const handleGetStatus = async (e) => {
    e.preventDefault();

    const idToUse = documentId || lastDocumentId;
    if (!idToUse) {
      setError('No document ID provided and no previous document available');
      return;
    }

    setLoading(true);
    setError(null);
    setStatus(null);

    try {
      const response = await fetch(`${baseUrl}/api/${currentService}/documents/${idToUse}/status`);

      if (response.ok) {
        const data = await response.json();
        setStatus(data);
      } else {
        const errorData = await response.json();
        setError(`Error ${response.status}: ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      setError(`Network error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    const idToUse = documentId || lastDocumentId;
    if (!idToUse) {
      setError('No document ID available for download');
      return;
    }

    try {
      const response = await fetch(`${baseUrl}/api/${currentService}/documents/${idToUse}/download`);

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `signed_document_${idToUse}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const errorData = await response.json();
        setError(`Download failed: ${response.status} - ${errorData.detail || 'Unknown error'}`);
      }
    } catch (err) {
      setError(`Download error: ${err.message}`);
    }
  };

  return (
    <div className="document-status">
      <h2>📊 Document Status</h2>

      <form onSubmit={handleGetStatus}>
        <div className="form-group">
          <label>📄 Document ID:</label>
          <input
            type="text"
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            placeholder={lastDocumentId ? `Current: ${lastDocumentId}` : "Enter document ID"}
          />
          <small>Leave empty to use last document ID</small>
        </div>

        <button type="submit" disabled={loading}>
          {loading ? '⏳ Getting Status...' : '📊 Get Status'}
        </button>
      </form>

      {error && (
        <div className="error">
          ❌ {error}
        </div>
      )}

      {status && (
        <div className="status-result">
          <h3>📄 Document Information</h3>
          <div className="status-info">
            <p><strong>📄 Document ID:</strong> {status.document_id}</p>
            <p><strong>🔧 Service:</strong> {status.service}</p>
            <p><strong>📊 Status:</strong> <span className={`status-badge ${status.status}`}>{status.status}</span></p>
            <p><strong>✍️ Signed:</strong> {status.signed ? '✅ Yes' : '❌ No'}</p>
          </div>

          {status.signers && status.signers.length > 0 && (
            <div className="signers-info">
              <h4>👥 Signers:</h4>
              <div className="signers-list">
                {status.signers.map((signer, index) => (
                  <div key={index} className="signer-item">
                    <div className="signer-header">
                      <span className="signer-number">{index + 1}.</span>
                      <span className="signer-name">{signer.name || 'Unknown'}</span>
                      <span className="signer-email">({signer.email || 'Unknown'})</span>
                    </div>
                    <div className="signer-status">
                      <strong>Status:</strong>
                      <span className={`status-badge ${signer.signed ? 'signed' : 'pending'}`}>
                        {signer.signed ? '✅ Signed' : '⏳ Pending'}
                      </span>
                    </div>
                    {signer.signed_at && (
                      <div className="signed-at">
                        <strong>Signed at:</strong> {new Date(signer.signed_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="actions">
            <button
              onClick={handleDownload}
              className="download-btn"
              disabled={!status.signed}
            >
              📥 Download Document
            </button>
            {!status.signed && (
              <small>Download available after all parties have signed</small>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default DocumentStatus;
