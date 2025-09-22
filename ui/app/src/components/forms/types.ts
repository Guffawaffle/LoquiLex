export interface SchemaProperty {
  type: 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object';
  title?: string;
  description?: string;
  default?: any;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  group?: string;
  'x-level'?: 'basic' | 'advanced' | 'expert';
}

export interface SchemaGroup {
  title: string;
  description?: string;
  order: number;
}

export interface SettingsSchema {
  $schema?: string;
  title?: string;
  description?: string;
  type: 'object';
  properties: Record<string, SchemaProperty>;
  required?: string[];
  'x-groups'?: Record<string, SchemaGroup>;
}

export interface FormFieldProps {
  name: string;
  property: SchemaProperty;
  value: any;
  onChange: (value: any) => void;
  error?: string;
}

export interface FormGroupProps {
  group: SchemaGroup;
  fields: Array<{ name: string; property: SchemaProperty }>;
  values: Record<string, any>;
  onChange: (name: string, value: any) => void;
  errors?: Record<string, string>;
}