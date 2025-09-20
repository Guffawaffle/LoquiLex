import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ModelSelect } from './components/ModelSelect';
import { DualPanelsView } from './components/DualPanelsView';
import { SettingsView } from './components/SettingsView';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<ModelSelect />} />
          <Route path="/settings" element={<SettingsView />} />
          <Route path="/session/:sessionId" element={<DualPanelsView />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;