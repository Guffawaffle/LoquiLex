/**
 * Unit tests for bounded queue utilities
 */

import { describe, it, expect, vi } from 'vitest'
import {
  BoundedQueue,
  createBoundedQueue,
  MessageBuffer
} from '../utils/bounded-queue'

describe('BoundedQueue', () => {
  it('should enqueue and dequeue items', () => {
    const queue = new BoundedQueue({ maxSize: 3, dropStrategy: 'oldest' })
    
    expect(queue.enqueue('a')).toBe(true)
    expect(queue.enqueue('b')).toBe(true)
    expect(queue.size()).toBe(2)
    
    expect(queue.dequeue()).toBe('a')
    expect(queue.dequeue()).toBe('b')
    expect(queue.size()).toBe(0)
  })

  it('should handle oldest drop strategy', () => {
    const onDrop = vi.fn()
    const queue = new BoundedQueue({ maxSize: 2, dropStrategy: 'oldest', onDrop })
    
    queue.enqueue('a')
    queue.enqueue('b')
    queue.enqueue('c') // Should drop 'a'
    
    expect(onDrop).toHaveBeenCalledWith('a')
    expect(queue.toArray()).toEqual(['b', 'c'])
    expect(queue.getStats().droppedCount).toBe(1)
  })

  it('should handle newest drop strategy', () => {
    const onDrop = vi.fn()
    const queue = new BoundedQueue({ maxSize: 2, dropStrategy: 'newest', onDrop })
    
    queue.enqueue('a')
    queue.enqueue('b')
    expect(queue.enqueue('c')).toBe(false) // Should drop 'c'
    
    expect(onDrop).toHaveBeenCalledWith('c')
    expect(queue.toArray()).toEqual(['a', 'b'])
    expect(queue.getStats().droppedCount).toBe(1)
  })

  it('should handle reject drop strategy', () => {
    const queue = new BoundedQueue({ maxSize: 2, dropStrategy: 'reject' })
    
    queue.enqueue('a')
    queue.enqueue('b')
    expect(queue.enqueue('c')).toBe(false) // Should reject
    
    expect(queue.toArray()).toEqual(['a', 'b'])
    expect(queue.getStats().droppedCount).toBe(0)
  })

  it('should support peek operation', () => {
    const queue = new BoundedQueue({ maxSize: 3, dropStrategy: 'oldest' })
    
    expect(queue.peek()).toBeUndefined()
    
    queue.enqueue('a')
    queue.enqueue('b')
    
    expect(queue.peek()).toBe('a')
    expect(queue.size()).toBe(2) // Peek doesn't remove
    
    queue.dequeue()
    expect(queue.peek()).toBe('b')
  })

  it('should support clear operation', () => {
    const queue = new BoundedQueue({ maxSize: 3, dropStrategy: 'oldest' })
    
    queue.enqueue('a')
    queue.enqueue('b')
    
    queue.clear()
    
    expect(queue.size()).toBe(0)
    expect(queue.isEmpty()).toBe(true)
  })

  it('should support drain operation', () => {
    const queue = new BoundedQueue({ maxSize: 3, dropStrategy: 'oldest' })
    
    queue.enqueue('a')
    queue.enqueue('b')
    
    const items = queue.drain()
    
    expect(items).toEqual(['a', 'b'])
    expect(queue.size()).toBe(0)
  })

  it('should provide accurate state checks', () => {
    const queue = new BoundedQueue({ maxSize: 2, dropStrategy: 'oldest' })
    
    expect(queue.isEmpty()).toBe(true)
    expect(queue.isFull()).toBe(false)
    
    queue.enqueue('a')
    expect(queue.isEmpty()).toBe(false)
    expect(queue.isFull()).toBe(false)
    
    queue.enqueue('b')
    expect(queue.isEmpty()).toBe(false)
    expect(queue.isFull()).toBe(true)
  })

  it('should be iterable', () => {
    const queue = new BoundedQueue({ maxSize: 3, dropStrategy: 'oldest' })
    
    queue.enqueue('a')
    queue.enqueue('b')
    queue.enqueue('c')
    
    const items = Array.from(queue)
    expect(items).toEqual(['a', 'b', 'c'])
  })

  it('should provide accurate stats', () => {
    const queue = new BoundedQueue({ maxSize: 2, dropStrategy: 'oldest' })
    
    queue.enqueue('a')
    queue.enqueue('b')
    queue.enqueue('c') // Drops 'a'
    
    const stats = queue.getStats()
    expect(stats.size).toBe(2)
    expect(stats.maxSize).toBe(2)
    expect(stats.droppedCount).toBe(1)
    expect(stats.isFull).toBe(true)
    expect(stats.isEmpty).toBe(false)
  })

  it('should reset dropped count', () => {
    const queue = new BoundedQueue({ maxSize: 1, dropStrategy: 'oldest' })
    
    queue.enqueue('a')
    queue.enqueue('b') // Drops 'a'
    
    expect(queue.resetDroppedCount()).toBe(1)
    expect(queue.getStats().droppedCount).toBe(0)
  })
})

describe('createBoundedQueue', () => {
  it('should create queue with default config', () => {
    const queue = createBoundedQueue<string>()
    
    const stats = queue.getStats()
    expect(stats.maxSize).toBe(100)
  })

  it('should create queue with custom config', () => {
    const queue = createBoundedQueue<string>({ maxSize: 50 })
    
    const stats = queue.getStats()
    expect(stats.maxSize).toBe(50)
  })
})

describe('MessageBuffer', () => {
  it('should extend BoundedQueue with byte limits', () => {
    const buffer = new MessageBuffer({ 
      maxSize: 10, 
      dropStrategy: 'oldest',
      maxBytes: 100 
    })
    
    // Add small messages
    buffer.enqueue({ data: 'small' })
    buffer.enqueue({ data: 'also small' })
    
    expect(buffer.size()).toBe(2)
  })

  it('should enforce byte limits', () => {
    const buffer = new MessageBuffer({ 
      maxSize: 100, 
      dropStrategy: 'oldest',
      maxBytes: 50 // Very small byte limit
    })
    
    // Add a message that might be too large
    buffer.enqueue({ data: 'a'.repeat(100) })
    
    const stats = buffer.getStats()
    expect(stats.totalBytes).toBeGreaterThan(0)
  })

  it('should track total bytes correctly', () => {
    const buffer = new MessageBuffer({ 
      maxSize: 10, 
      dropStrategy: 'oldest',
      maxBytes: 1000 
    })
    
    buffer.enqueue({ data: 'test' })
    const stats1 = buffer.getStats()
    expect(stats1.totalBytes).toBeGreaterThan(0)
    
    buffer.enqueue({ data: 'another test' })
    const stats2 = buffer.getStats()
    expect(stats2.totalBytes).toBeGreaterThan(stats1.totalBytes)
    
    buffer.dequeue()
    const stats3 = buffer.getStats()
    expect(stats3.totalBytes).toBeLessThan(stats2.totalBytes)
  })

  it('should clear bytes on clear', () => {
    const buffer = new MessageBuffer({ 
      maxSize: 10, 
      dropStrategy: 'oldest',
      maxBytes: 1000 
    })
    
    buffer.enqueue({ data: 'test' })
    expect(buffer.getStats().totalBytes).toBeGreaterThan(0)
    
    buffer.clear()
    expect(buffer.getStats().totalBytes).toBe(0)
  })

  it('should handle non-serializable items gracefully', () => {
    const buffer = new MessageBuffer({ 
      maxSize: 10, 
      dropStrategy: 'oldest',
      maxBytes: 1000 
    })
    
    // Create a circular reference that can't be JSON.stringified
    const circular: any = { data: 'test' }
    circular.self = circular
    
    // Should not throw
    expect(() => buffer.enqueue(circular)).not.toThrow()
    expect(buffer.size()).toBe(1)
  })

  it('should provide byte statistics', () => {
    const buffer = new MessageBuffer({ 
      maxSize: 10, 
      dropStrategy: 'oldest',
      maxBytes: 500 
    })
    
    buffer.enqueue({ data: 'test' })
    
    const stats = buffer.getStats()
    expect(stats.totalBytes).toBeGreaterThan(0)
    expect(stats.maxBytes).toBe(500)
    expect(stats.size).toBe(1)
  })
})