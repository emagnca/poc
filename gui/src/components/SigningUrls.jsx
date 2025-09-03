// src/components/SigningUrls.js
import React, { useState, useEffect } from 'react';

function SigningUrls({ baseUrl, currentService, lastDocumentId }) {
  const [documentId, setDocumentId] = useState('');
  const [signingUrls, setSigningUrls] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (lastDocumentId) {
      setDocumentId(lastDocumentId);
    }
  }, [lastDocumentId]);

  const fetchSigningUrls = async (e) => {
    e.preventDefault();

    const idToUse = documentId || lastDocumentId;
    if (!idToUse) {
      setError('No document ID provided and no previous document available');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // First try to get document status which includes signing URLs
      const response = await fetch(`${baseUrl}/api/${currentService}/documents/${idToUse}/status`);

      if (response.ok) {
        const data = await response.json();
        // Transform status data to match signing URLs format
        if (data.signers) {
          const urlsData = {
            document_id: data.document_id,
            signing_urls: data.signers.map(signer => ({
              signer_email: signer.email,
              signer_name: signer.name,
              signing_url: signer.signing_url || null,
              mode: signer.mode || 'EMAIL_NOTIFICATION',
              signed: signer.signed || false
            }))
          };
          setSigningUrls(urlsData);
        } else {
          setError('No signer information available for this document');
        }
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

  const openSigningUrl = (url, signerEmail) => {
    if (url) {
      window.open(url, '_blank');
      console.log(`Opened signing URL for ${signerEmail}`);
    }
  };

  const copyUrl = (url) => {
    navigator.clipboard.writeText(url).then(() => {
      alert('Signing URL copied to clipboard!');
    }).catch(() => {
      alert('Failed to copy URL');
    });
  };

  const openAllUrls = () => {
    if (signingUrls && signingUrls.signing_urls) {
      signingUrls.signing_urls.forEach(signer => {
        if (signer.signing_url && !signer.signed) {
          setTimeout(() => {
            window.open(signer.signing_url, '_blank');
          }, 500); // Stagger opening to avoid popup blockers
        }
      });
    }
  };

  return (
    <div className="signing-urls">
      <h2>🔗 Signing URLs</h2>

      <form onSubmit={fetchSigningUrls}>
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
          {loading ? '⏳ Getting URLs...' : '🔗 Get Signing URLs'}
        </button>
      </form>

      {error && (
        <div className="error">
          ❌ {error}
        </div>
      )}

      {signingUrls && (
        <div className="urls-result">
          <h3>🔗 Available Signing URLs</h3>
          <p><strong>📄 Document ID:</strong> {signingUrls.document_id}</p>

          {signingUrls.signing_urls.filter(s => s.signing_url && !s.signed).length > 1 && (
            <div className="bulk-actions">
              <button
                onClick={openAllUrls}
                className="open-all-btn"
              >
                🌐 Open All Pending URLs
              </button>
            </div>
          )}

          <div className="signers-list">
            {signingUrls.signing_urls.map((signer, index) => (
              <div key={index} className="signer-url-item">
                <div className="signer-header">
                  <h4>
                    {signer.signer_name || signer.signer_email}
                    {signer.signed && <span className="signed-badge">✅ Signed</span>}
                  </h4>
                  <div className="signer-details">
                    <span className="signer-email">{signer.signer_email}</span>
                    <span className="signer-mode">{signer.mode}</span>
                  </div>
                </div>

                {signer.signing_url ? (
                  <div className="url-section">
                    <div className="url-actions">
                      <button
                        onClick={() => openSigningUrl(signer.signing_url, signer.signer_email)}
                        className="open-url-btn"
                        disabled={signer.signed}
                      >
                        🌐 {signer.signed ? 'Already Signed' : 'Open Signing Page'}
                      </button>
                      <button
                        onClick={() => copyUrl(signer.signing_url)}
                        className="copy-url-btn"
                      >
                        📋 Copy URL
                      </button>
                    </div>
                    <div className="url-preview">
                      <small>{signer.signing_url.substring(0, 80)}...</small>
                    </div>
                  </div>
                ) : (
                  <div className="no-url">
                    📧 Email notification - No direct URL available
                  </div>
                )}
              </div>
            ))}
          </div>

          {signingUrls.signing_urls.every(s => s.signed) && (
            <div className="all-signed">
              🎉 All signers have completed signing!
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SigningUrls;
