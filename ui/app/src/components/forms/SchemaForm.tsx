import { useMemo } from 'react';
import { SettingsSchema } from './types';
import { FormGroup } from './FormGroup';
import { validateField } from './validation';

export interface SchemaFormProps {
  schema: SettingsSchema;
  values: Record<string, any>;
  onChange: (name: string, value: any) => void;
  level?: 'basic' | 'advanced' | 'expert';
}

export function SchemaForm({ schema, values, onChange, level = 'basic' }: SchemaFormProps) {
  const { groupedFields, errors } = useMemo(() => {
    const groups: Record<string, Array<{ name: string; property: any }>> = {};
    const fieldErrors: Record<string, string> = {};

    // Group fields by their group property and filter by level
    const levelOrder = { basic: 0, advanced: 1, expert: 2 };
    Object.entries(schema.properties).forEach(([name, property]) => {
      // Skip fields that are above the current level in the hierarchy
      if (
        property['x-level'] &&
        levelOrder[property['x-level']] > levelOrder[level]
      ) {
        return;
      }

      const groupName = property.group || 'General';
      if (!groups[groupName]) {
        groups[groupName] = [];
      }
      groups[groupName].push({ name, property });

      // Validate field
      const error = validateField(values[name], property);
      if (error) {
        fieldErrors[name] = error;
      }
    });

    return { groupedFields: groups, errors: fieldErrors };
  }, [schema, values, level]);

  // Sort groups by their order if defined
  const sortedGroupNames = Object.keys(groupedFields).sort((a, b) => {
    const orderA = schema['x-groups']?.[a]?.order ?? 999;
    const orderB = schema['x-groups']?.[b]?.order ?? 999;
    return orderA - orderB;
  });

  return (
    <div className="schema-form">
      {sortedGroupNames.map((groupName) => {
        const groupConfig = schema['x-groups']?.[groupName] || {
          title: groupName,
          order: 999
        };

        return (
          <FormGroup
            key={groupName}
            group={groupConfig}
            fields={groupedFields[groupName]}
            values={values}
            onChange={onChange}
            errors={errors}
          />
        );
      })}
    </div>
  );
}