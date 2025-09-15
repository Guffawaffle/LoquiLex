import React, { useState } from 'react'

export default function DualPanels() {
	const [showTimestamps, setShowTimestamps] = useState(false)
	return (
		<div style={{ display: 'flex', gap: '1rem' }}>
			<div
				data-testid="panel-source"
				style={{ flex: 1, border: '1px solid #ccc', padding: '0.5rem' }}
			>
				<h2 style={{ marginTop: 0 }}>Source</h2>
				<p>{showTimestamps ? '[00:00] Hello world (source)' : 'Hello world (source)'}</p>
			</div>
			<div
				data-testid="panel-target"
				style={{ flex: 1, border: '1px solid #ccc', padding: '0.5rem' }}
			>
				<h2 style={{ marginTop: 0 }}>Target</h2>
				<p>{showTimestamps ? '[00:00] 你好，世界 (target)' : '你好，世界 (target)'}</p>
			</div>
			<label style={{ alignSelf: 'flex-start' }}>
				<input
					type="checkbox"
					role="switch"
					aria-label="Timestamps"
					checked={showTimestamps}
					onChange={() => setShowTimestamps(v => !v)}
				/>{' '}
				<span>Timestamps</span>
			</label>
		</div>
	)
}
