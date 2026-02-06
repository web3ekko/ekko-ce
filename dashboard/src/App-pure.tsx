/**
 * Pure React App Component - No external dependencies
 */

import React from 'react'

console.log('App-pure.tsx loading...')

function App() {
  console.log('Pure App component rendering...')
  
  const [count, setCount] = React.useState(0)
  
  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>🎉 Pure React Test</h1>
      <p>✅ React is working!</p>
      <p>✅ State management is working!</p>
      
      <div style={{ marginTop: '20px' }}>
        <p>Counter: {count}</p>
        <button 
          onClick={() => setCount(count + 1)}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: '#007bff', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer',
            marginRight: '10px'
          }}
        >
          Increment
        </button>
        <button 
          onClick={() => setCount(0)}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: '#dc3545', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Reset
        </button>
      </div>
      
      <div style={{ marginTop: '20px' }}>
        <h3>If you can see this and the buttons work, React is fully functional!</h3>
      </div>
    </div>
  )
}

console.log('App-pure.tsx loaded, exporting App...')

export default App
