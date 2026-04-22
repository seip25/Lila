import React, { useState } from 'react'

export default function Counter({ start = 0 }) {
  const [count, setCount] = useState(start)

  return (
     <main className='container'>
     <article className="mt-8 max-w-sm">
      <h3>React Island: Counter</h3>
      <p>Current count: <strong>{count}</strong></p>
      <button 
        onClick={() => setCount(count + 1)} 
      >
        Increment
      </button>
    </article>
   </main>
  )
}
