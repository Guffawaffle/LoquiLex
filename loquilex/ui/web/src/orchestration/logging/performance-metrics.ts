/**
 * Performance metrics collection for UI orchestrator
 */

import { StructuredLogger } from './structured-logger'

export enum MetricType {
  LATENCY = 'latency',
  THROUGHPUT = 'throughput',
  COUNTER = 'counter',
  GAUGE = 'gauge'
}

export interface MetricValue {
  timestamp: number
  value: number
  metadata?: Record<string, any>
}

export interface MetricStats {
  count: number
  sum: number
  min?: number
  max?: number
  avg?: number
  p50?: number
  p95?: number
  p99?: number
  recent_avg?: number
}

export interface PerformanceThreshold {
  warning?: number
  critical?: number
}

/**
 * Performance metrics collector for browser environment
 */
export class PerformanceMetrics {
  private logger?: StructuredLogger
  private component: string
  private window_size: number
  
  // Metric storage
  private metrics: Map<string, MetricValue[]> = new Map()
  private counters: Map<string, number> = new Map()
  private gauges: Map<string, number> = new Map()
  
  // Timing contexts
  private active_timers: Map<string, number> = new Map()
  
  // Performance thresholds
  private thresholds: Map<string, PerformanceThreshold> = new Map()

  constructor(config: {
    logger?: StructuredLogger
    component?: string
    window_size?: number
  } = {}) {
    this.logger = config.logger
    this.component = config.component || 'ui_orchestrator'
    this.window_size = config.window_size || 1000
  }

  /**
   * Record latency measurement
   */
  recordLatency(name: string, duration_ms: number, metadata: Record<string, any> = {}): void {
    this.addMeasurement(name, duration_ms, MetricType.LATENCY, metadata)
  }

  /**
   * Record throughput measurement
   */
  recordThroughput(name: string, count: number, metadata: Record<string, any> = {}): void {
    this.addMeasurement(name, count, MetricType.THROUGHPUT, metadata)
  }

  /**
   * Increment a counter
   */
  incrementCounter(name: string, value: number = 1): void {
    const current = this.counters.get(name) || 0
    this.counters.set(name, current + value)

    if (this.logger) {
      this.logger.debug(`Counter incremented: ${name}`, {
        metric_type: MetricType.COUNTER,
        metric_name: name,
        counter_value: current + value,
        increment: value
      })
    }
  }

  /**
   * Set gauge value
   */
  setGauge(name: string, value: number): void {
    this.gauges.set(name, value)

    if (this.logger) {
      this.logger.debug(`Gauge updated: ${name}`, {
        metric_type: MetricType.GAUGE,
        metric_name: name,
        gauge_value: value
      })
    }
  }

  /**
   * Start timing a measurement
   */
  startTimer(name: string): void {
    this.active_timers.set(name, performance.now())
  }

  /**
   * End timing and record latency
   */
  endTimer(name: string, metadata: Record<string, any> = {}): number {
    const start_time = this.active_timers.get(name)
    if (start_time === undefined) {
      throw new Error(`Timer '${name}' was not started`)
    }

    this.active_timers.delete(name)
    const duration_ms = performance.now() - start_time

    this.recordLatency(name, duration_ms, metadata)
    return duration_ms
  }

  /**
   * Measure WebSocket performance
   */
  measureWebSocketLatency(name: string, sent_timestamp: number): void {
    const latency = performance.now() - sent_timestamp
    this.recordLatency(`websocket_${name}`, latency, {
      connection_type: 'websocket',
      message_type: name
    })
  }

  /**
   * Measure HTTP request performance
   */
  measureHttpLatency(name: string, method: string, status: number, duration: number): void {
    this.recordLatency(`http_${name}`, duration, {
      connection_type: 'http',
      method,
      status,
      success: status >= 200 && status < 400
    })
  }

  /**
   * Measure UI rendering performance
   */
  measureRenderTime(component: string, duration: number): void {
    this.recordLatency(`render_${component}`, duration, {
      metric_category: 'ui_performance',
      component
    })
  }

  /**
   * Add measurement to storage
   */
  private addMeasurement(
    name: string,
    value: number,
    metric_type: MetricType,
    metadata: Record<string, any>
  ): void {
    if (!this.metrics.has(name)) {
      this.metrics.set(name, [])
    }

    const measurements = this.metrics.get(name)!
    const measurement: MetricValue = {
      timestamp: Date.now(),
      value,
      metadata
    }

    measurements.push(measurement)

    // Keep only recent measurements
    if (measurements.length > this.window_size) {
      measurements.shift()
    }

    // Check thresholds
    this.checkThresholds(name, value, metric_type)

    if (this.logger) {
      this.logger.debug(`Metric recorded: ${name}`, {
        metric_type,
        metric_name: name,
        metric_value: value,
        ...metadata
      })
    }
  }

  /**
   * Get statistical summary for a metric
   */
  getStats(name: string): MetricStats | null {
    const measurements = this.metrics.get(name)
    if (!measurements || measurements.length === 0) {
      return null
    }

    const values = measurements.map(m => m.value)
    const sorted_values = [...values].sort((a, b) => a - b)
    const n = sorted_values.length

    const stats: MetricStats = {
      count: n,
      sum: values.reduce((a, b) => a + b, 0),
      min: sorted_values[0],
      max: sorted_values[n - 1],
      avg: values.reduce((a, b) => a + b, 0) / n
    }

    // Percentiles
    if (n > 0) {
      stats.p50 = sorted_values[Math.floor(n * 0.5)]
      stats.p95 = sorted_values[Math.floor(n * 0.95)]
      stats.p99 = sorted_values[Math.floor(n * 0.99)]
    }

    // Recent average (last 10% of measurements)
    const recent_count = Math.max(1, Math.floor(n * 0.1))
    const recent_values = values.slice(-recent_count)
    stats.recent_avg = recent_values.reduce((a, b) => a + b, 0) / recent_values.length

    return stats
  }

  /**
   * Set performance threshold
   */
  setThreshold(name: string, threshold: PerformanceThreshold): void {
    this.thresholds.set(name, threshold)
  }

  /**
   * Check if value exceeds thresholds
   */
  private checkThresholds(name: string, value: number, metric_type: MetricType): void {
    const threshold = this.thresholds.get(name)
    if (!threshold || !this.logger) {
      return
    }

    if (threshold.critical !== undefined && value >= threshold.critical) {
      this.logger.critical(`Metric threshold exceeded (critical): ${name}`, {
        metric_name: name,
        metric_value: value,
        threshold_type: 'critical',
        threshold_value: threshold.critical,
        metric_type
      })
    } else if (threshold.warning !== undefined && value >= threshold.warning) {
      this.logger.warning(`Metric threshold exceeded (warning): ${name}`, {
        metric_name: name,
        metric_value: value,
        threshold_type: 'warning',
        threshold_value: threshold.warning,
        metric_type
      })
    }
  }

  /**
   * Get all metrics summary
   */
  getAllMetrics(): Record<string, any> {
    const result = {
      component: this.component,
      timestamp: Date.now(),
      counters: Object.fromEntries(this.counters),
      gauges: Object.fromEntries(this.gauges),
      metrics: {} as Record<string, any>
    }

    for (const [name] of this.metrics) {
      const stats = this.getStats(name)
      if (stats) {
        result.metrics[name] = {
          count: stats.count,
          avg: stats.avg,
          min: stats.min,
          max: stats.max,
          p50: stats.p50,
          p95: stats.p95,
          p99: stats.p99,
          recent_avg: stats.recent_avg
        }
      }
    }

    return result
  }

  /**
   * Log metrics summary
   */
  logSummary(): void {
    if (!this.logger) {
      return
    }

    const summary = this.getAllMetrics()
    this.logger.info('Performance metrics summary', summary)
  }

  /**
   * Reset all metrics
   */
  reset(): void {
    this.metrics.clear()
    this.counters.clear()
    this.gauges.clear()
    this.active_timers.clear()
  }
}

/**
 * Create performance metrics with WebSocket-specific presets
 */
export function createWebSocketMetrics(logger?: StructuredLogger): PerformanceMetrics {
  const metrics = new PerformanceMetrics({
    logger,
    component: 'websocket_client'
  })

  // Set WebSocket-specific thresholds
  metrics.setThreshold('websocket_message_latency', { warning: 100, critical: 500 })
  metrics.setThreshold('websocket_connect_time', { warning: 2000, critical: 10000 })
  metrics.setThreshold('websocket_reconnect_interval', { warning: 5000, critical: 30000 })

  return metrics
}

/**
 * Create performance metrics with HTTP-specific presets
 */
export function createHttpMetrics(logger?: StructuredLogger): PerformanceMetrics {
  const metrics = new PerformanceMetrics({
    logger,
    component: 'http_client'
  })

  // Set HTTP-specific thresholds
  metrics.setThreshold('http_request_latency', { warning: 1000, critical: 5000 })
  metrics.setThreshold('http_download_latency', { warning: 10000, critical: 60000 })

  return metrics
}