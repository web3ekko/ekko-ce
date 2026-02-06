/**
 * Minimal App Component for Debugging
 */

console.log('App-minimal.tsx loading...')

function App() {
  console.log('App component rendering...')
  
  // Test if React is working at all
  return (
    <div>
      <h1>Minimal Test</h1>
      <p>If you can see this, React is working!</p>
    </div>
  )
}

console.log('App-minimal.tsx loaded, exporting App...')

export default App
