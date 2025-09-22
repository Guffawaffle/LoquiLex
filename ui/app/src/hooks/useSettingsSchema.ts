import { useState, useEffect } from 'react';
import { SettingsSchema } from '../components/forms';

export function useSettingsSchema() {
  const [schema, setSchema] = useState<SettingsSchema | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSchema = async () => {
      try {
        setLoading(true);
        setError(null);
        
        // Load schema from the static file
        // In a production app, this might be loaded from an API endpoint
        const response = await fetch('/dropoff/loquilex-ui-spec/05_SETTINGS_SCHEMA.json');
        if (!response.ok) {
          throw new Error('Failed to fetch schema');
        }
        
        const schemaData = await response.json();
        
        // Validate that the schema has the expected structure
        if (!schemaData || typeof schemaData !== 'object') {
          throw new Error('Invalid schema format');
        }
        
        if (!schemaData.properties || typeof schemaData.properties !== 'object') {
          throw new Error('Schema missing properties');
        }
        
        setSchema(schemaData as SettingsSchema);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load schema');
      } finally {
        setLoading(false);
      }
    };

    loadSchema();
  }, []);

  return { schema, loading, error };
}