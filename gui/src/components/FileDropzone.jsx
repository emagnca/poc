// src/components/FileDropzone.jsx
import React, { useState, useCallback } from 'react';
import './FileDropzone.css';

const FileDropzone = ({ onFileSelect, acceptedTypes = '.pdf,.doc,.docx' }) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      const file = files[0];
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const handleFileInput = useCallback((e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      onFileSelect(file);
    }
  }, [onFileSelect]);

  const removeFile = () => {
    setSelectedFile(null);
    onFileSelect(null);
  };

  return (
    <div className="file-dropzone-container">
      <div
        className={`file-dropzone ${isDragOver ? 'drag-over' : ''} ${selectedFile ? 'has-file' : ''}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {selectedFile ? (
          <div className="selected-file">
            <div className="file-info">
              <span className="file-name">{selectedFile.name}</span>
              <span className="file-size">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </span>
            </div>
            <button onClick={removeFile} className="remove-file-btn">
              ✕
            </button>
          </div>
        ) : (
          <div className="dropzone-content">
            <div className="upload-icon">📄</div>
            <p className="dropzone-text">
              Drag and drop your document here, or{' '}
              <label className="file-input-label">
                browse
                <input
                  type="file"
                  accept={acceptedTypes}
                  onChange={handleFileInput}
                  className="file-input"
                />
              </label>
            </p>
            <p className="file-types">Supported: PDF, DOC, DOCX</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default FileDropzone;
