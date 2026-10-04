import './polyfills';

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import './i18n'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  // <StrictMode>
    <BrowserRouter basename={window.location.pathname.startsWith('/app') ? '/app' : undefined} future={{
      v7_startTransition: true, // ref: https://reactrouter.com/6.30.1/upgrading/future#v7_starttransition
      v7_relativeSplatPath: true
    }}>
      <App />
    </BrowserRouter>
  // </StrictMode>,
)
