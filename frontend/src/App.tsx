import { Cloud } from 'lucide-react'

function App() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-slate-950">
      <section className="w-full max-w-md border border-slate-200 bg-white p-8 shadow-sm">
        <div className="mb-8 flex size-11 items-center justify-center bg-blue-600 text-white">
          <Cloud aria-hidden="true" className="size-6" />
        </div>
        <h1 className="text-3xl font-semibold">Cloud Drive</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600">
          The application workspace is ready.
        </p>
        <div className="mt-8 flex items-center gap-3 border-t border-slate-200 pt-5 text-sm">
          <span aria-hidden="true" className="size-2 bg-emerald-500" />
          <span>Frontend online</span>
        </div>
      </section>
    </main>
  )
}

export default App
