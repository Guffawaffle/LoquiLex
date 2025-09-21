import React from 'react';
import { FormGroupProps } from './types';
import { FieldRenderer } from './FieldRenderer';

export function FormGroup({ group, fields, values, onChange, errors }: FormGroupProps) {
  return (
    <div className="form-group-section">
      <div className="form-group-header">
        <h3 className="form-group-title">{group.title}</h3>
        {group.description && (
          <p className="form-group-description">{group.description}</p>
        )}
      </div>
      <div className="form-group-fields">
        {fields.map(({ name, property }) => (
          <FieldRenderer
            key={name}
            name={name}
            property={property}
            value={values[name]}
            onChange={(value) => onChange(name, value)}
            error={errors?.[name]}
          />
        ))}
      </div>
    </div>
  );
}