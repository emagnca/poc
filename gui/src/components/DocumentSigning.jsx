// src/components/DocumentSigning.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import ServiceSelector from './ServiceSelector';
import './DocumentSigning.css';

const DocumentSigning = ({
  baseUrl,
  currentService,
  setCurrentService,
  supportedServices,
  setLastDocumentId,
  setLastSigningUrl
}) => {
  const { getAuthHeaders, user } = useAuth();

  const [file, setFile] = useState(null);
  const [signers, setSigners] = useState([{ signer_name: '', signer_email: '', mode: 'DIRECT_SIGNING' }]);
  const [metadata, setMetadata] = useState({
    title: '',
    custom_fields: {}
  });
  const [customFields, setCustomFields] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  // Clear results when service changes
  useEffect(() => {
    setResult(null);
    setError('');
  }, [currentService]);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.type === 'application/pdf') {
      setFile(selectedFile);
      setError('');
    } else {
      setError('Please select a PDF file');
      setFile(null);
    }
  };

  const handleSignerChange = (index, field, value) => {
    const newSigners = [...signers];
    newSigners[index][field] = value;
    setSigners(newSigners);
  };

  const addSigner = () => {
    setSigners([...signers, { signer_name: '', signer_email: '', mode: 'DIRECT_SIGNING' }]);
  };

  const removeSigner = (index) => {
    if (signers.length > 1) {
      setSigners(signers.filter((_, i) => i !== index));
    }
  };

  const handleMetadataChange = (field, value) => {
    setMetadata({ ...metadata, [field]: value });
  };

  const addCustomField = () => {
    const newField = { key: '', value: '', id: Date.now() };
    setCustomFields([...customFields, newField]);
  };

  const removeCustomField = (id) => {
    setCustomFields(customFields.filter(field => field.id !== id));
    // Also remove from metadata
    const newCustomFields = { ...metadata.custom_fields };
    const fieldToRemove = customFields.find(f => f.id === id);
    if (fieldToRemove && fieldToRemove.key) {
      delete newCustomFields[fieldToRemove.key];
      setMetadata({ ...metadata, custom_fields: newCustomFields });
    }
  };

  const handleCustomFieldChange = (id, type, value) => {
    const newCustomFields = customFields.map(field =>
      field.id === id ? { ...field, [type]: value } : field
    );
    setCustomFields(newCustomFields);

    // Update metadata custom_fields
    const customFieldsObj = {};
    newCustomFields.forEach(field => {
      if (field.key && field.value) {
        customFieldsObj[field.key] = field.value;
      }
    });
    setMetadata({ ...metadata, custom_fields: customFieldsObj });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    if (signers.some(s => !s.signer_name || !s.signer_email)) {
      setError('Please fill in all signer information');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      // Prepare metadata
      const processedMetadata = {
        ...metadata,
        created_by: user?.email || 'unknown',
        created_at: new Date().toISOString(),
        service: currentService
      };

      const formData = new FormData();
      formData.append('document', file);
      formData.append('signers', JSON.stringify(signers));
      formData.append('metadata', JSON.stringify(processedMetadata));

      // Use unified endpoint for all services
      const response = await fetch(`${baseUrl}/api/${currentService}/sign`, {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
        },
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        setResult(data);
        setLastDocumentId(data.document_id);

        // For services with signing URLs, set the last signing URL
        if (data.signing_urls && data.signing_urls.length > 0 && data.signing_urls[0].signing_url) {
          setLastSigningUrl(data.signing_urls[0].signing_url);
        }
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Signing request failed');
      }
    } catch (error) {
      console.error('Signing error:', error);
      setError('Network error occurred');
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

  const getModeDescription = (mode) => {
    switch (mode) {
      case 'EMAIL_NOTIFICATION':
        return 'Signer will receive an email with signing instructions';
      case 'DIRECT_SIGNING':
        return 'Generate direct signing URL (no email sent)';
      default:
        return '';
    }
  };

  const isServiceCompleted = (service) => {
    return service === 'selfsign';
  };

  const getDownloadUrl = (service, documentId) => {
    if (service === 'selfsign') {
      return `${baseUrl}/api/selfsign/documents/${documentId}/download`;
    }
    // Add other service download URLs as needed
    return null;
  };

  const getDocumentUrl = (service, documentId) => {
    return `${baseUrl}/documents/${documentId}`;
  };

  return (
    <div className="document-signing">
      <h2>✍️ Sign Your Documents</h2>

      {/* Service Selector */}
      <ServiceSelector
        currentService={currentService}
        setCurrentService={setCurrentService}
        supportedServices={supportedServices}
      />

      <form onSubmit={handleSubmit} className="signing-form">
        {/* File Upload */}
        <div className="form-group">
          <label htmlFor="document">📄 Select PDF Document:</label>
          <input
            type="file"
            id="document"
            accept=".pdf"
            onChange={handleFileChange}
            required
          />
          {file && <p className="file-info">Selected: {file.name}</p>}
        </div>

        {/* Signers */}
        <div className="signers-section">
          <h3>👥 Signers ({signers.length})</h3>
          {signers.map((signer, index) => (
            <div key={index} className="signer-group">
              <div className="signer-header">
                <h4>Signer {index + 1}</h4>
                {signers.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeSigner(index)}
                    className="remove-signer"
                  >
                    ❌ Remove
                  </button>
                )}
              </div>

              <div className="signer-fields">
                <div className="form-group">
                  <label>Full Name:</label>
                  <input
                    type="text"
                    value={signer.signer_name}
                    onChange={(e) => handleSignerChange(index, 'signer_name', e.target.value)}
                    placeholder="Enter full name"
                    required
                  />
                </div>

                <div className="form-group">
                  <label>Email Address:</label>
                  <input
                    type="email"
                    value={signer.signer_email}
                    onChange={(e) => handleSignerChange(index, 'signer_email', e.target.value)}
                    placeholder="Enter email address"
                    required
                  />
                </div>

                {/* Signing mode for all services */}
                <div className="form-group">
                  <label>Signing Mode:</label>
                  <select
                    value={signer.mode}
                    onChange={(e) => handleSignerChange(index, 'mode', e.target.value)}
                  >
                    <option value="DIRECT_SIGNING">📋 Direct Signing (URL)</option>
                    <option value="EMAIL_NOTIFICATION">📧 Email Notification</option>
                  </select>
                  <small className="mode-description">
                    {getModeDescription(signer.mode)}
                  </small>
                </div>
              </div>
            </div>
          ))}

          <button type="button" onClick={addSigner} className="add-signer">
            ➕ Add Another Signer
          </button>
        </div>

        {/* Metadata Section with Title and Custom Fields */}
        <div className="metadata-section">
          <h3>📋 Document Information & Metadata</h3>

          {/* Title Field */}
          <div className="form-group">
            <label>Title:</label>
            <input
              type="text"
              value={metadata.title}
              onChange={(e) => handleMetadataChange('title', e.target.value)}
              placeholder="Document title (optional)"
            />
          </div>

          {/* Custom Fields */}
          <div className="custom-fields-section">
            <div className="custom-fields-header">
              <h4>🏷️ Additional Metadata Fields</h4>
              <button type="button" onClick={addCustomField} className="add-custom-field">
                ➕ Add Metadata Field
              </button>
            </div>

            {customFields.length === 0 && (
              <p className="no-custom-fields">
                No additional metadata fields. Click "Add Metadata Field" to add custom information.
              </p>
            )}

            {customFields.map((field) => (
              <div key={field.id} className="custom-field">
                <div className="custom-field-inputs">
                  <input
                    type="text"
                    value={field.key}
                    onChange={(e) => handleCustomFieldChange(field.id, 'key', e.target.value)}
                    placeholder="Field name (e.g., Department, Project, Reference)"
                    className="custom-field-key"
                  />
                  <input
                    type="text"
                    value={field.value}
                    onChange={(e) => handleCustomFieldChange(field.id, 'value', e.target.value)}
                    placeholder="Field value"
                    className="custom-field-value"
                  />
                  <button
                    type="button"
                    onClick={() => removeCustomField(field.id)}
                    className="remove-custom-field"
                    title="Remove this field"
                  >
                    ❌
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Submit Button */}
        <button type="submit" disabled={loading} className="submit-button">
          {loading ? 'Processing...' : `${getServiceIcon(currentService)} Sign with ${getServiceName(currentService)}`}
        </button>
      </form>

      {/* Error Display */}
      {error && <div className="error-message">{error}</div>}

      {/* Results Display - Unified for all services */}
      {result && (
        <div className="result">
          <h3>✅ Document signing initiated with {getServiceName(currentService)}</h3>
          <p>📄 Document ID: {result.document_id}</p>

          {/* Show metadata in results */}
          {result.metadata && (result.metadata.title || Object.keys(result.metadata.custom_fields || {}).length > 0) && (
            <div className="result-metadata">
              <h4>📋 Document Metadata:</h4>
              <div className="metadata-display">
                {result.metadata.title && <p><strong>Title:</strong> {result.metadata.title}</p>}
                {result.metadata.custom_fields && Object.keys(result.metadata.custom_fields).length > 0 && (
                  <div className="custom-metadata">
                    <strong>Additional Fields:</strong>
                    <ul>
                      {Object.entries(result.metadata.custom_fields).map(([key, value]) => (
                        <li key={key}><strong>{key}:</strong> {value}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Service-specific result display */}
          {isServiceCompleted(currentService) ? (
            /* Completed services (like selfsign) */
            <div className="completed-service-result">
              <div className="success-message">
                {getServiceIcon(currentService)} <strong>Document signed successfully!</strong>
              </div>
              <p>✅ All signatures have been applied.</p>
              <p>📋 The document is ready for download and validation.</p>

              <div className="signers-completed">
                <h4>👥 Signed by ({result.signing_urls.length}):</h4>
                {result.signing_urls.map((signer, index) => (
                  <div key={index} className="signer-completed">
                    <div className="signer-info">
                      <span className="signer-details">
                        {index + 1}. {signer.signer_name} ({signer.signer_email})
                      </span>
                      <span className="completed-badge">✅ Completed</span>
                    </div>
                    {signer.signed_at && (
                      <small className="signed-time">
                        Signed at: {new Date(signer.signed_at).toLocaleString()}
                      </small>
                    )}
                  </div>
                ))}
              </div>

              <div className="service-actions">
                {getDownloadUrl(currentService, result.document_id) && (
                  <button
                    onClick={() => window.open(getDownloadUrl(currentService, result.document_id), '_blank')}
                    className="download-btn primary"
                  >
                    📥 Download Signed Document
                  </button>
                )}

                {signers.some(s => s.mode === 'DIRECT_SIGNING') && (
                  <button
                    onClick={() => window.open(getDocumentUrl(currentService, result.document_id), '_blank')}
                    className="view-document-btn secondary"
                  >
                    📄 View Document Details
                  </button>
                )}
              </div>
            </div>
          ) : (
            /* Pending services (like scrive, docusign) */
            <div className="pending-service-result">
              <div className="signing-urls">
                <h4>📝 Signing Information:</h4>
                {result.signing_urls.map((signer, index) => (
                  <div key={index} className="signer-url">
                    <div className="signer-info">
                      <strong>{signer.signer_name}</strong> ({signer.signer_email})
                      <span className="signing-mode">
                        {signer.mode === 'EMAIL_NOTIFICATION' ? '📧 Email sent' : '📋 Direct URL'}
                      </span>
                    </div>
                    {signer.signing_url ? (
                      <a
                        href={signer.signing_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="signing-link"
                      >
                        🔗 Sign Document
                      </a>
                    ) : (
                      <span className="no-url">
                        {signer.mode === 'EMAIL_NOTIFICATION' ?
                          '📧 Email notification sent to signer' :
                          'Signing URL not available'
                        }
                      </span>
                    )}
                  </div>
                ))}
              </div>

              <div className="next-steps">
                <h4>📋 Next Steps:</h4>
                <ol>
                  <li>
                    {signers.some(s => s.mode === 'EMAIL_NOTIFICATION') ?
                      'Signers will receive email notifications with signing instructions' :
                      'Share the signing links with the respective signers'
                    }
                  </li>
                  <li>Monitor signing progress in the "Search Documents" tab</li>
                  <li>Download the completed document once all signatures are collected</li>
                </ol>
              </div>
            </div>
          )}

          {/* Storage info */}
          {result.uploaded_to_storage === false && (
            <div className="storage-warning">
              ⚠️ Document saved locally only (external storage unavailable)
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DocumentSigning;
