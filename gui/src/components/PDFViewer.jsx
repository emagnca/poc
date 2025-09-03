// src/components/PDFViewer.jsx
import React, { useEffect, useRef } from 'react';
import PDFObject from 'pdfobject';
import './PDFViewer.css';

const PDFViewer = ({ pdfUrl, onClose, documentId }) => {
  const pdfContainerRef = useRef(null);

  useEffect(() => {
    if (pdfUrl && pdfContainerRef.current) {
      // Clear any existing content
      pdfContainerRef.current.innerHTML = '';

      // Embed the PDF
      PDFObject.embed(pdfUrl, pdfContainerRef.current, {
        height: '100%',
        width: '100%',
        fallbackLink: '<p>Your browser does not support inline PDF viewing. <a href="[url]">Click here to download the PDF</a></p>'
      });
    }
  }, [pdfUrl]);

  return (
    <div className="pdf-viewer-overlay">
      <div className="pdf-viewer-container">
        <div className="pdf-viewer-header">
          <h3>📄 Document Viewer - {documentId}</h3>
          <div className="pdf-viewer-controls">
            <button
              onClick={() => window.open(pdfUrl, '_blank')}
              className="open-new-tab-btn"
              title="Open in new tab"
            >
              🔗 Open in New Tab
            </button>
            <button
              onClick={onClose}
              className="close-viewer-btn"
              title="Close viewer"
            >
              ❌ Close
            </button>
          </div>
        </div>
        <div
          ref={pdfContainerRef}
          className="pdf-viewer-content"
        />
      </div>
    </div>
  );
};

export default PDFViewer;

