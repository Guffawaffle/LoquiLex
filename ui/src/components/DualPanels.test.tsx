import { render, screen, fireEvent } from '@testing-library/react'
import DualPanels from './DualPanels'

describe('DualPanels', () => {
	it('renders source and target panels', () => {
		render(<DualPanels />)
		expect(screen.getByTestId('panel-source')).toBeInTheDocument()
		expect(screen.getByTestId('panel-target')).toBeInTheDocument()
	})

	it('toggles timestamps on/off', () => {
		render(<DualPanels />)
		const toggle = screen.getByRole('switch', { name: /timestamps/i })
		expect(toggle).toBeInTheDocument()
		fireEvent.click(toggle)
		// Assert a class/attribute change or visible timestamp token
	})
})
