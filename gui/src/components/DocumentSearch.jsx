// src/components/DocumentSearch.jsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import ServiceSelector from './ServiceSelector';
import PDFViewer from './PDFViewer';
import './DocumentSearch.css';

const DocumentSearch = ({ baseUrl, currentService, setCurrentService, supportedServices, setLastDocumentId }) => {
  const { getAuthHeaders, user } = useAuth();

  const [searchCriteria, setSearchCriteria] = useState({
    document_id: '',
    signer_email: '',
    status: '',
    service: currentService,
  });

  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [pdfViewerData, setPdfViewerData] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [expandedMetadata, setExpandedMetadata] = useState(new Set());

  // Update service when currentService changes
  useEffect(() => {
    setSearchCriteria(prev => ({ ...prev, service: currentService }));
  }, [currentService]);

  // Function to toggle metadata expansion
  const toggleMetadata = (signatureId) => {
    setExpandedMetadata(prev => {
      const newSet = new Set(prev);
      if (newSet.has(signatureId)) {
        newSet.delete(signatureId);
      } else {
        newSet.add(signatureId);
      }
      return newSet;
    });
  };

  // Add sorting function
  const sortResults = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }

    const sortedResults = [...results].sort((a, b) => {
      let aValue = a[key];
      let bValue = b[key];

      // Handle different data types
      if (key === 'created_at') {
        aValue = new Date(aValue);
        bValue = new Date(bValue);
      } else if (typeof aValue === 'string') {
        aValue = aValue.toLowerCase();
        bValue = bValue.toLowerCase();
      }

      if (aValue < bValue) {
        return direction === 'asc' ? -1 : 1;
      }
      if (aValue > bValue) {
        return direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    setResults(sortedResults);
    setSortConfig({ key, direction });
  };

  // Add function to get sort indicator
  const getSortIndicator = (columnKey) => {
    if (sortConfig.key === columnKey) {
      return sortConfig.direction === 'asc' ? ' ↑' : ' ↓';
    }
    return ' ↕️';
  };

  const handleInputChange = (e) => {
    setSearchCriteria({
      ...searchCriteria,
      [e.target.name]: e.target.value,
    });
    setError('');
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setResults([]);
    setSortConfig({ key: null, direction: 'asc' }); // Reset sorting
    setExpandedMetadata(new Set()); // Reset expanded metadata

    try {
      // Build query parameters - automatically include current user as handler
      const queryParams = new URLSearchParams();

      // Always add current user as handler
      queryParams.append('handler', user.email);

      // Add other search criteria only if they have values
      Object.entries(searchCriteria).forEach(([key, value]) => {
        if (value && value.trim()) {
          queryParams.append(key, value.trim());
        }
      });

      const response = await fetch(`${baseUrl}/api/signatures/search?${queryParams}`, {
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const data = await response.json();
        setResults(data.signatures || []);
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Search failed');
      }
    } catch (error) {
      console.error('Search error:', error);
      setError('Network error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateStatus = async (documentId, service) => {
    try {
      setLoading(true);

      const response = await fetch(`${baseUrl}/api/${service}/documents/${documentId}/status`, {
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        const statusData = await response.json();

        // Update the specific signature in results with mapped status
        setResults(prevResults =>
          prevResults.map(signature => {
            if (signature.document_id === documentId && signature.service === service) {
              return {
                ...signature,
                status: statusData.status, // This should already be mapped by the server
                signed: statusData.signed || false,
                updated_at: new Date().toISOString(),
                // Preserve other fields
                last_status_check: new Date().toISOString()
              };
            }
            return signature;
          })
        );

        // Optional: Show success message
        console.log('Status updated:', statusData);

        // Optional: Show a brief success indicator
        setError(''); // Clear any previous errors

      } else {
        const errorData = await response.json();
        setError(`Failed to update status: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Update status error:', error);
      setError('Network error occurred while updating status');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSignature = async (signatureId) => {
    if (!window.confirm('Are you sure you want to delete this signature? This action cannot be undone.')) {
      return;
    }

    try {
      setLoading(true);

      const response = await fetch(`${baseUrl}/api/signatures/${signatureId}/delete`, {
        method: 'PUT',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
        },
      });

      if (response.ok) {
        // Remove the deleted signature from results
        setResults(prevResults =>
          prevResults.filter(signature => signature.id !== signatureId)
        );

        console.log('Signature deleted successfully');
      } else {
        const errorData = await response.json();
        setError(`Failed to delete signature: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Delete signature error:', error);
      setError('Network error occurred while deleting signature');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDocument = async (documentId, service) => {
    try {
      setLoading(true);

      const response = await fetch(`${baseUrl}/api/${service}/documents/${documentId}/download`, {
        headers: {
          ...getAuthHeaders(),
        },
      });

      if (response.ok) {
        // Create blob and URL for the PDF viewer
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);

        // Set PDF viewer data
        setPdfViewerData({
          url: url,
          documentId: documentId,
          service: service
        });

      } else {
        const errorData = await response.json();
        setError(`Failed to download document: ${errorData.detail}`);
      }
    } catch (error) {
      console.error('Download document error:', error);
      setError('Network error occurred while downloading document');
    } finally {
      setLoading(false);
    }
  };

  const closePdfViewer = () => {
    if (pdfViewerData?.url) {
      window.URL.revokeObjectURL(pdfViewerData.url);
    }
    setPdfViewerData(null);
  };

  const handleDocumentSelect = (documentId) => {
    setLastDocumentId(documentId);
  };

  return (
    <div className="document-search">
      <h2>🔍 Search Your Documents</h2>

      {/* Add ServiceSelector here */}
      <div className="service-selection">
        <ServiceSelector
          currentService={currentService}
          setCurrentService={setCurrentService}
          supportedServices={supportedServices}
        />
      </div>

      {/* Show current user info */}
      <div className="current-user-filter">
        <p><strong>Showing documents handled by:</strong> {user?.full_name} ({user?.email})</p>
      </div>

      <form onSubmit={handleSearch} className="search-form">
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="document_id">Document ID:</label>
            <input
              type="text"
              id="document_id"
              name="document_id"
              value={searchCriteria.document_id}
              onChange={handleInputChange}
              placeholder="Enter document ID"
            />
          </div>

          <div className="form-group">
            <label htmlFor="signer_email">Signer Email:</label>
            <input
              type="email"
              id="signer_email"
              name="signer_email"
              value={searchCriteria.signer_email}
              onChange={handleInputChange}
              placeholder="Enter signer email"
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="status">Status:</label>
            <select
              id="status"
              name="status"
              value={searchCriteria.status}
              onChange={handleInputChange}
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="sent">Sent</option>
              <option value="signed">Signed</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        <button type="submit" disabled={loading} className="search-button">
          {loading ? 'Searching...' : '🔍 Search My Documents'}
        </button>
      </form>

      {error && <div className="error-message">{error}</div>}

      {results.length > 0 && (
        <div className="search-results">
          <h3>Search Results ({results.length} found)</h3>
          <div className="results-table">
            <table>
              <thead>
                <tr>
                  <th
                    className="sortable-header"
                    onClick={() => sortResults('document_id')}
                    title="Click to sort by Document ID"
                  >
                    Document ID{getSortIndicator('document_id')}
                  </th>
                  <th
                    className="sortable-header"
                    onClick={() => sortResults('signer_email')}
                    title="Click to sort by Signer Email"
                  >
                    Signer{getSortIndicator('signer_email')}
                  </th>
                  <th
                    className="sortable-header"
                    onClick={() => sortResults('status')}
                    title="Click to sort by Status"
                  >
                    Status{getSortIndicator('status')}
                  </th>
                  <th
                    className="sortable-header"
                    onClick={() => sortResults('service')}
                    title="Click to sort by Service"
                  >
                    Service{getSortIndicator('service')}
                  </th>
                  <th>Metadata</th>
                  <th
                    className="sortable-header"
                    onClick={() => sortResults('created_at')}
                    title="Click to sort by Created Date"
                  >
                    Created{getSortIndicator('created_at')}
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((signature, index) => (
                  <tr key={index}>
                    <td>
                      <button
                        className="document-id-link"
                        onClick={() => handleDocumentSelect(signature.document_id)}
                      >
                        {signature.document_id}
                      </button>
                    </td>
                    <td>
                      <div>
                        <strong>{signature.signer_name}</strong>
                        <br />
                        <small>{signature.signer_email}</small>
                      </div>
                    </td>
                    <td>
                      <span className={`status-badge status-${signature.status}`}>
                        {signature.status}
                      </span>
                    </td>
                    <td>{signature.service}</td>
                    <td>
                      <div className="metadata-cell">
                        {signature.metadata && Object.keys(signature.metadata).length > 0 ? (
                          <div>
                            <button
                              className="metadata-toggle"
                              onClick={() => toggleMetadata(signature.id)}
                              title="Click to expand/collapse metadata"
                            >
                              📋 Metadata ({Object.keys(signature.metadata).length})
                              {expandedMetadata.has(signature.id) ? ' ▼' : ' ▶'}
                            </button>
                            {expandedMetadata.has(signature.id) && (
                              <div className="metadata-content expanded">
                                {Object.entries(signature.metadata).map(([key, value], idx) => (
                                  <div key={idx} className="metadata-item">
                                    <span className="metadata-key">{key}:</span>
                                    <span className="metadata-value">{String(value)}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="no-metadata">No metadata</span>
                        )}
                      </div>
                    </td>
                    <td>{new Date(signature.created_at).toLocaleDateString()}</td>
                    <td>
                      <div className="action-buttons">
                        {/* Show Sign button only if status is NOT signed, completed, or failed */}
                        {signature.signing_url &&
                         !['signed', 'completed', 'failed'].includes(signature.status.toLowerCase()) && (
                          <a
                            href={signature.signing_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="signing-link"
                          >
                            📝 Sign
                          </a>
                        )}

                        {/* Show Update button only if status is NOT completed */}
                        {signature.status.toLowerCase() !== 'completed' && (
                          <button
                            onClick={() => handleUpdateStatus(signature.document_id, signature.service)}
                            disabled={loading}
                            className="update-button"
                            title="Update status from service"
                          >
                            🔄 Update
                          </button>
                        )}

                        {/* View/Download button - always available */}
                        <button
                          onClick={() => handleViewDocument(signature.document_id, signature.service)}
                          disabled={loading}
                          className="view-button"
                          title="View/Download document"
                        >
                          👁️ View
                        </button>

                        {/* Delete button is always available */}
                        <button
                          onClick={() => handleDeleteSignature(signature.id)}
                          disabled={loading}
                          className="delete-button"
                          title="Delete signature"
                        >
                          🗑️ Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {results.length === 0 && !loading && !error && (
        <div className="no-results">
          <p>No documents found. Try adjusting your search criteria.</p>
        </div>
      )}

        {/* PDF Viewer Modal */}
        {pdfViewerData && (
          <PDFViewer
            pdfUrl={pdfViewerData.url}
            documentId={pdfViewerData.documentId}
            onClose={closePdfViewer}
          />
        )}

    </div>
  );
};

export default DocumentSearch;
