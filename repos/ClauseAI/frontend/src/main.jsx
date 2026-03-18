import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import { createLogger } from './utils/logger'
import './styles/clauseTheme.css'
import './styles/primitives.css'

const logger = createLogger('bootstrap')

window.addEventListener('error', (event) => {
    logger.error('Unhandled window error', {
        message: event.message,
        filename: event.filename,
        line: event.lineno,
        column: event.colno,
        error: event.error
    })
})

window.addEventListener('unhandledrejection', (event) => {
    logger.error('Unhandled promise rejection', { reason: event.reason })
})

ReactDOM.createRoot(document.getElementById('root')).render(
    <App />
)
