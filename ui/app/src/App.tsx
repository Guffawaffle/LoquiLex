import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ModelSelect } from './components/ModelSelect';
import { DualPanelsView } from './components/DualPanelsView';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<ModelSelect />} />
          <Route path="/session/:sessionId" element={<DualPanelsView />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;