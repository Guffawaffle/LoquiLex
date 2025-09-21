import React from 'react';
import { FormFieldProps } from './types';

export function FieldRenderer({ name, property, value, onChange, error }: FormFieldProps) {
  const fieldId = `field-${name}`;
  
  const renderField = () => {
    switch (property.type) {
      case 'string':
        if (property.enum) {
          return (
            <select
              id={fieldId}
              className="form-control"
              value={value || ''}
              onChange={(e) => onChange(e.target.value)}
            >
              {property.enum.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          );
        }
        return (
          <input
            id={fieldId}
            type="text"
            className="form-control"
            value={value || ''}
            onChange={(e) => onChange(e.target.value)}
            placeholder={property.default?.toString() || ''}
          />
        );
      
      case 'integer':
      case 'number':
        if (property.minimum !== undefined && property.maximum !== undefined) {
          return (
            <>
              <input
                id={fieldId}
                type="range"
                className="slider"
                min={property.minimum}
                max={property.maximum}
                value={value ?? property.default ?? property.minimum}
                onChange={(e) => onChange(parseInt(e.target.value))}
              />
              <div className="slider-labels">
                <span>{property.minimum} (Fast)</span>
                <span>{property.maximum} (Accurate)</span>
              </div>
            </>
          );
        }
        return (
          <input
            id={fieldId}
            type="number"
            className="form-control"
            value={value ?? property.default ?? ''}
            min={property.minimum}
            max={property.maximum}
            onChange={(e) => onChange(property.type === 'integer' ? parseInt(e.target.value) : parseFloat(e.target.value))}
          />
        );
      
      case 'boolean':
        return (
          <input
            id={fieldId}
            type="checkbox"
            checked={value ?? property.default ?? false}
            onChange={(e) => onChange(e.target.checked)}
            style={{ marginRight: '0.5rem' }}
          />
        );
      
      default:
        return (
          <input
            id={fieldId}
            type="text"
            className="form-control"
            value={value?.toString() || ''}
            onChange={(e) => onChange(e.target.value)}
          />
        );
    }
  };

  return (
    <div className="form-group">
      <label className="form-group__label" htmlFor={fieldId}>
        {property.type === 'boolean' && renderField()}
        {property.title || name}
        {property.type === 'integer' && property.minimum !== undefined && property.maximum !== undefined && 
          `: ${value ?? property.default ?? property.minimum} words`}
      </label>
      {property.description && (
        <p className="form-group__description">{property.description}</p>
      )}
      {property.type !== 'boolean' && property.type !== 'integer' && renderField()}
      {property.type === 'integer' && property.minimum !== undefined && property.maximum !== undefined && renderField()}
      {error && (
        <div className="form-error" style={{ color: 'var(--error)', fontSize: '0.875rem', marginTop: '0.25rem' }}>
          {error}
        </div>
      )}
    </div>
  );
}