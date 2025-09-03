import React from 'react';
import './ServiceSelector.css';

const ServiceSelector = ({ currentService, setCurrentService, supportedServices = [] }) => {
  // Add loading state handling
  if (!supportedServices || supportedServices.length === 0) {
    return (
      <div className="service-selector">
        <h3>🔧 Select Signing Service</h3>
        <div className="service-loading">
          Loading services...
        </div>
      </div>
    );
  }

  return (
    <div className="service-selector">
      <h3>🔧 Select Signing Service</h3>
      <div className="service-buttons">
        {supportedServices.map((service) => (
          <button
            key={service}
            className={`service-button ${currentService === service ? 'active' : ''}`}
            onClick={() => setCurrentService(service)}
          >
            {getServiceIcon(service)} {getServiceName(service)}
          </button>
        ))}
      </div>
    </div>
  );
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

export default ServiceSelector;
