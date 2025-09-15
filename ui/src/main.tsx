import React from 'react'
import { createRoot } from 'react-dom/client'
import DualPanels from './components/DualPanels'

const container = document.getElementById('root')!
createRoot(container).render(<DualPanels />)
