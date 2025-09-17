/**
 * Worker channel for orchestrating background tasks with progress tracking
 */
export class WorkerChannel extends EventTarget {
  private worker: Worker | null = null;
  private isInitialized = false;

  constructor() {
    super();
    this.initializeWorker();
  }

  private initializeWorker() {
    if (this.isInitialized) return;

    // TODO: Extract this to a separate worker file for better maintainability
    // The inline worker implementation creates a large, hard-to-maintain blob of JavaScript code within TypeScript.
    // Consider extracting this to a separate worker file or using a proper build process to bundle workers.
    // This would improve code organization, enable proper syntax highlighting, and make the worker code testable independently.
    const workerBlob = new Blob([
      // Import the worker script content - in a real implementation this would be
      // a separate file or bundled appropriately
      `
      // Inline worker implementation for demo purposes
      self.onmessage = function(e) {
        const { type, data } = e.data;

        switch (type) {
          case 'process_data':
            // Simulate processing work
            const result = processData(data);
            self.postMessage({ type: 'result', data: result });
            break;

          case 'ping':
            self.postMessage({ type: 'pong', timestamp: Date.now() });
            break;

          default:
            self.postMessage({ type: 'error', message: 'Unknown message type: ' + type });
        }
      };

      function processData(data) {
        // Simulate some processing work
        let result = 0;
        for (let i = 0; i < data.length; i++) {
          result += data[i] * data[i];
        }
        return result;
      }
      `
    ], { type: 'application/javascript' });

    this.worker = new Worker(URL.createObjectURL(workerBlob));
    this.worker.onmessage = this.handleWorkerMessage.bind(this);
    this.worker.onerror = this.handleWorkerError.bind(this);
    this.isInitialized = true;
  }

  private handleWorkerMessage(event: MessageEvent) {
    const { type, data } = event.data;
    this.dispatchEvent(new CustomEvent('message', { detail: { type, data } }));
  }

  private handleWorkerError(error: ErrorEvent) {
    this.dispatchEvent(new CustomEvent('error', { detail: error }));
  }

  public sendMessage(type: string, data?: any) {
    if (!this.worker) {
      throw new Error('Worker not initialized');
    }

    this.worker.postMessage({ type, data });
  }

  public terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
      this.isInitialized = false;
    }
  }

  public isReady(): boolean {
    return this.isInitialized && this.worker !== null;
  }
}