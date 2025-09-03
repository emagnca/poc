// src/components/DocumentSigningForm.jsx
import React, { useState } from 'react';
import FileDropzone from './FileDropzone';

const DocumentSigningForm = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [signerName, setSignerName] = useState('');
  const [signerEmail, setSignerEmail] = useState('');
  const [provider, setProvider] = useState('docusign');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!selectedFile || !signerName || !signerEmail) {
      alert('Please fill in all fields and select a document');
      return;
    }

    setIsSubmitting(true);

    const formData = new FormData();
    formData.append('document', selectedFile);
    formData.append('signerName', signerName);
    formData.append('signerEmail', signerEmail);

    try {
      const response = await fetch(`http://localhost:8080/api/v1/documents/sign/${provider}`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const signingId = await response.text();
        alert(`Document sent for signing! Signing ID: ${signingId}`);
        // Reset form
        setSelectedFile(null);
        setSignerName('');
        setSignerEmail('');
      } else {
        throw new Error('Failed to initiate signing process');
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Error initiating signing process');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="document-signing-form">
      <h2>Document Signing</h2>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Select Document:</label>
          <FileDropzone
            onFileSelect={setSelectedFile}
            acceptedTypes=".pdf,.doc,.docx"
          />
        </div>

        <div className="form-group">
          <label htmlFor="signerName">Signer Name:</label>
          <input
            type="text"
            id="signerName"
            value={signerName}
            onChange={(e) => setSignerName(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="signerEmail">Signer Email:</label>
          <input
            type="email"
            id="signerEmail"
            value={signerEmail}
            onChange={(e) => setSignerEmail(e.target.value)}
            required
          />
        </div>

        <div className="form-group">
          <label htmlFor="provider">Signing Provider:</label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="docusign">DocuSign</option>
            <option value="scrive">Scrive</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={!selectedFile || isSubmitting}
          className="submit-btn"
        >
          {isSubmitting ? 'Sending...' : 'Send for Signing'}
        </button>
      </form>
    </div>
  );
};

export default DocumentSigningForm;
