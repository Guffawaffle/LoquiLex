import { SchemaProperty } from './types';

export function validateField(value: any, property: SchemaProperty): string | null {
  // Handle required validation (if needed in the future)
  if (value === undefined || value === null || value === '') {
    // For now, no fields are required, but we can add this logic later
    return null;
  }

  // Type validation
  switch (property.type) {
    case 'string':
      if (typeof value !== 'string') {
        return `Expected string, got ${typeof value}`;
      }
      if (property.enum && !property.enum.includes(value)) {
        return `Value must be one of: ${property.enum.join(', ')}`;
      }
      break;

    case 'integer':
      if (typeof value !== 'number' || isNaN(value)) {
        return 'Value must be a number';
      }
      if (!Number.isInteger(value)) {
        return 'Value must be an integer';
      }
      if (property.minimum !== undefined && value < property.minimum) {
        return `Value must be at least ${property.minimum}`;
      }
      if (property.maximum !== undefined && value > property.maximum) {
        return `Value must be at most ${property.maximum}`;
      }
      break;

    case 'number':
      if (typeof value !== 'number' || isNaN(value)) {
        return 'Value must be a number';
      }
      if (property.minimum !== undefined && value < property.minimum) {
        return `Value must be at least ${property.minimum}`;
      }
      if (property.maximum !== undefined && value > property.maximum) {
        return `Value must be at most ${property.maximum}`;
      }
      break;

    case 'boolean':
      if (typeof value !== 'boolean') {
        return `Expected boolean, got ${typeof value}`;
      }
      break;
  }

  return null;
}

export function validateSchema(values: Record<string, any>, schema: any): Record<string, string> {
  const errors: Record<string, string> = {};

  Object.entries(schema.properties).forEach(([name, property]) => {
    const error = validateField(values[name], property as SchemaProperty);
    if (error) {
      errors[name] = error;
    }
  });

  return errors;
}