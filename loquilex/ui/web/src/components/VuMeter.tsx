import React from 'react'

export default function VuMeter({ rms, peak, clipPct }: { rms: number; peak: number; clipPct?: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(rms * 100)))
  const warn = (clipPct ?? 0) > 2
  return (
    <div className="w-72">
      <div className={`h-4 w-full rounded bg-slate-200 dark:bg-slate-800 overflow-hidden ring-1 ring-inset ${warn? 'ring-red-500':'ring-slate-300 dark:ring-slate-700'}`} aria-label="VU meter" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full" style={{ width: `${pct}%`, background: 'linear-gradient(90deg, #22c55e, #eab308, #ef4444)' }} />
      </div>
    </div>
  )
}
