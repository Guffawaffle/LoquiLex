/**
 * Bounded Queue Implementation
 * 
 * Provides a thread-safe bounded queue with configurable drop strategies
 * for handling overflow conditions.
 */

import type { BoundedQueueConfig } from '../types'

export class BoundedQueue<T> {
  private readonly config: BoundedQueueConfig
  private items: T[] = []
  private droppedCount = 0

  constructor(config: BoundedQueueConfig) {
    this.config = config
  }

  /**
   * Add an item to the queue
   */
  enqueue(item: T): boolean {
    if (this.items.length < this.config.maxSize) {
      this.items.push(item)
      return true
    }

    // Handle overflow based on drop strategy
    switch (this.config.dropStrategy) {
      case 'oldest':
        const dropped = this.items.shift()
        this.items.push(item)
        if (dropped !== undefined) {
          this.droppedCount++
          this.config.onDrop?.(dropped)
        }
        return true

      case 'newest':
        this.droppedCount++
        this.config.onDrop?.(item)
        return false

      case 'reject':
        return false

      default:
        throw new Error(`Unknown drop strategy: ${this.config.dropStrategy}`)
    }
  }

  /**
   * Remove and return the next item from the queue
   */
  dequeue(): T | undefined {
    return this.items.shift()
  }

  /**
   * Peek at the next item without removing it
   */
  peek(): T | undefined {
    return this.items[0]
  }

  /**
   * Get the current size of the queue
   */
  size(): number {
    return this.items.length
  }

  /**
   * Check if the queue is empty
   */
  isEmpty(): boolean {
    return this.items.length === 0
  }

  /**
   * Check if the queue is full
   */
  isFull(): boolean {
    return this.items.length >= this.config.maxSize
  }

  /**
   * Clear all items from the queue
   */
  clear(): void {
    this.items.length = 0
  }

  /**
   * Drain all items from the queue
   */
  drain(): T[] {
    const result = [...this.items]
    this.items.length = 0
    return result
  }

  /**
   * Get queue statistics
   */
  getStats() {
    return {
      size: this.items.length,
      maxSize: this.config.maxSize,
      droppedCount: this.droppedCount,
      isFull: this.isFull(),
      isEmpty: this.isEmpty()
    }
  }

  /**
   * Reset the dropped count
   */
  resetDroppedCount(): number {
    const count = this.droppedCount
    this.droppedCount = 0
    return count
  }

  /**
   * Iterate over all items without removing them
   */
  *[Symbol.iterator](): Iterator<T> {
    for (const item of this.items) {
      yield item
    }
  }

  /**
   * Convert to array (copy)
   */
  toArray(): T[] {
    return [...this.items]
  }
}

/**
 * Create a bounded queue with sensible defaults
 */
export function createBoundedQueue<T>(
  config: Partial<BoundedQueueConfig> = {}
): BoundedQueue<T> {
  const defaultConfig: BoundedQueueConfig = {
    maxSize: 100,
    dropStrategy: 'oldest'
  }
  
  return new BoundedQueue<T>({ ...defaultConfig, ...config })
}

/**
 * A specialized bounded queue for WebSocket messages
 */
export class MessageBuffer<T> extends BoundedQueue<T> {
  private totalBytes = 0
  private maxBytes: number

  constructor(config: BoundedQueueConfig & { maxBytes?: number }) {
    super(config)
    this.maxBytes = config.maxBytes ?? 1024 * 1024 // 1MB default
  }

  enqueue(item: T): boolean {
    const itemSize = this.estimateSize(item)
    
    // Check byte limit
    if (this.totalBytes + itemSize > this.maxBytes && !this.isEmpty()) {
      // Try to make room by dropping old messages
      while (!this.isEmpty() && this.totalBytes + itemSize > this.maxBytes) {
        const dropped = this.dequeue()
        if (dropped !== undefined) {
          this.totalBytes -= this.estimateSize(dropped)
        }
      }
    }
    
    const success = super.enqueue(item)
    if (success) {
      this.totalBytes += itemSize
    }
    
    return success
  }

  dequeue(): T | undefined {
    const item = super.dequeue()
    if (item !== undefined) {
      this.totalBytes -= this.estimateSize(item)
    }
    return item
  }

  clear(): void {
    super.clear()
    this.totalBytes = 0
  }

  getStats() {
    return {
      ...super.getStats(),
      totalBytes: this.totalBytes,
      maxBytes: this.maxBytes
    }
  }

  private estimateSize(item: T): number {
    // Simple estimation - could be more sophisticated
    try {
      return JSON.stringify(item).length * 2 // Rough UTF-16 estimation
    } catch {
      return 100 // Fallback size
    }
  }
}