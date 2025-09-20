/**
 * Data redaction for sensitive information in UI logs
 */

export interface RedactionPattern {
  pattern: RegExp
  replacement: string | ((match: string, ...groups: string[]) => string)
}

/**
 * Redact sensitive information from UI logging data
 */
export class DataRedactor {
  private patterns: RedactionPattern[]
  private sensitive_fields: Set<string>

  constructor(customPatterns: RedactionPattern[] = []) {
    // Standard patterns for browser environment
    this.patterns = [
      // URLs with potential tokens
      {
        pattern: /(https?:\/\/[^\/]+\/)([^?&\s]+)?(\?[^&]*(?:token|key|secret|auth)[^&]*=[^&\s]*)/gi,
        replacement: '$1[REDACTED]$3'
      },

      // API keys and tokens
      {
        pattern: /(token|key|secret|password|auth)["']?\s*[=:]\s*["']?[\w-]{8,}/gi,
        replacement: '$1=[REDACTED]'
      },

      // File paths (browser-specific)
      {
        pattern: /blob:https?:\/\/[^\s]+/gi,
        replacement: 'blob:[REDACTED]'
      },

      // Local file paths
      {
        pattern: /file:\/\/[^\s]+/gi,
        replacement: 'file://[REDACTED]'
      },

      // WebSocket URLs with potential sensitive info
      {
        pattern: /(wss?:\/\/[^\/]+\/)([^?&\s]+)?(\?[^&]*(?:token|session|auth)[^&]*=[^&\s]*)/gi,
        replacement: '$1[REDACTED]$3'
      },

      ...customPatterns
    ]

    // Sensitive field names to redact entirely
    this.sensitive_fields = new Set([
      'password', 'token', 'secret', 'key', 'auth', 'credential',
      'api_key', 'access_token', 'refresh_token', 'auth_token',
      'session_token', 'csrf_token', 'bearer_token',
      'user_data', 'personal_info', 'email', 'phone', 'address'
    ])
  }

  /**
   * Redact sensitive information from a string
   */
  redactString(text: string): string {
    let result = text

    for (const { pattern, replacement } of this.patterns) {
      if (typeof replacement === 'string') {
        result = result.replace(pattern, replacement)
      } else {
        result = result.replace(pattern, replacement)
      }
    }

    return result
  }

  /**
   * Redact sensitive data from an object
   */
  redactObject(obj: Record<string, any>): Record<string, any> {
    const result: Record<string, any> = {}

    for (const [key, value] of Object.entries(obj)) {
      // Check if field name is sensitive
      if (this.sensitive_fields.has(key.toLowerCase())) {
        result[key] = '[REDACTED]'
        continue
      }

      // Recursively process nested data
      if (value && typeof value === 'object') {
        if (Array.isArray(value)) {
          result[key] = value.map(item =>
            item && typeof item === 'object'
              ? this.redactObject(item)
              : typeof item === 'string'
              ? this.redactString(item)
              : item
          )
        } else {
          result[key] = this.redactObject(value)
        }
      } else if (typeof value === 'string') {
        result[key] = this.redactString(value)
      } else {
        result[key] = value
      }
    }

    return result
  }

  /**
   * Add custom redaction pattern
   */
  addPattern(pattern: RedactionPattern): void {
    this.patterns.push(pattern)
  }

  /**
   * Add sensitive field name
   */
  addSensitiveField(fieldName: string): void {
    this.sensitive_fields.add(fieldName.toLowerCase())
  }
}