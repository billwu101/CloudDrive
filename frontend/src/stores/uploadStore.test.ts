import { afterEach, describe, expect, it, vi } from 'vitest'

import { SETTLE_DELAY_MS, useUploadStore } from './uploadStore'

function makeFile(name = 'test.txt', size = 100): File {
  return new File(['x'.repeat(size)], name, { type: 'text/plain' })
}

afterEach(() => {
  useUploadStore.setState({ tasks: [] })
})

describe('addTasks', () => {
  it('creates one task per file', () => {
    const files = [makeFile('a.txt'), makeFile('b.txt')]
    useUploadStore.getState().addTasks(files)
    expect(useUploadStore.getState().tasks).toHaveLength(2)
    expect(useUploadStore.getState().tasks[0].status).toBe('pending')
    expect(useUploadStore.getState().tasks[0].progress).toBe(0)
  })

  it('returns the created tasks', () => {
    const tasks = useUploadStore.getState().addTasks([makeFile()])
    expect(tasks).toHaveLength(1)
    expect(tasks[0].file.name).toBe('test.txt')
  })

  it('attaches parentId when provided', () => {
    useUploadStore.getState().addTasks([makeFile()], 'folder-1')
    expect(useUploadStore.getState().tasks[0].parentId).toBe('folder-1')
  })
})

describe('updateProgress', () => {
  it('updates progress for the correct task', () => {
    useUploadStore.getState().addTasks([makeFile(), makeFile('b.txt')])
    const { tasks } = useUploadStore.getState()
    useUploadStore.getState().updateProgress(tasks[0].id, 42)
    expect(useUploadStore.getState().tasks[0].progress).toBe(42)
    expect(useUploadStore.getState().tasks[1].progress).toBe(0)
  })
})

describe('markCompleted', () => {
  it('sets status to completed and progress to 100', () => {
    useUploadStore.getState().addTasks([makeFile()])
    const id = useUploadStore.getState().tasks[0].id
    useUploadStore.getState().markCompleted(id)
    const t = useUploadStore.getState().tasks[0]
    expect(t.status).toBe('completed')
    expect(t.progress).toBe(100)
  })
})

describe('markFailed', () => {
  it('sets status to failed with error message', () => {
    useUploadStore.getState().addTasks([makeFile()])
    const id = useUploadStore.getState().tasks[0].id
    useUploadStore.getState().markFailed(id, 'Network error')
    const t = useUploadStore.getState().tasks[0]
    expect(t.status).toBe('failed')
    expect(t.error).toBe('Network error')
  })
})

describe('cancelTask', () => {
  it('sets status to canceled and aborts the controller', () => {
    useUploadStore.getState().addTasks([makeFile()])
    const task = useUploadStore.getState().tasks[0]
    useUploadStore.getState().cancelTask(task.id)
    expect(useUploadStore.getState().tasks[0].status).toBe('canceled')
    expect(task.controller.signal.aborted).toBe(true)
  })
})

describe('removeTask', () => {
  it('removes the task from the list', () => {
    useUploadStore.getState().addTasks([makeFile()])
    const id = useUploadStore.getState().tasks[0].id
    useUploadStore.getState().removeTask(id)
    expect(useUploadStore.getState().tasks).toHaveLength(0)
  })
})

describe('clearCompleted', () => {
  it('removes only completed and canceled tasks', () => {
    useUploadStore.getState().addTasks([makeFile('a.txt'), makeFile('b.txt'), makeFile('c.txt')])
    const [a, b, c] = useUploadStore.getState().tasks
    useUploadStore.getState().markCompleted(a.id)
    useUploadStore.getState().cancelTask(b.id)
    useUploadStore.getState().markFailed(c.id, 'err')
    useUploadStore.getState().clearCompleted()
    const remaining = useUploadStore.getState().tasks
    expect(remaining).toHaveLength(1)
    expect(remaining[0].id).toBe(c.id)
  })
})

describe('settleBatch', () => {
  const store = () => useUploadStore.getState()

  function addBatch(names: string[]) {
    return store()
      .addTasks(names.map((n) => makeFile(n)))
      .map((t) => t.id)
  }

  it('keeps everything until the delay has elapsed', () => {
    vi.useFakeTimers()
    const [a] = addBatch(['a.txt'])
    store().markCompleted(a)

    store().settleBatch([a])
    vi.advanceTimersByTime(SETTLE_DELAY_MS - 1)
    expect(store().tasks).toHaveLength(1)

    vi.advanceTimersByTime(1)
    expect(store().tasks).toHaveLength(0)
    vi.useRealTimers()
  })

  it('removes only the completed tasks, leaving every other status', () => {
    vi.useFakeTimers()
    const ids = addBatch(['ok.txt', 'bad.txt', 'stopped.txt', 'held.txt'])
    const [ok, bad, stopped, held] = ids
    store().markCompleted(ok)
    store().markFailed(bad, 'Network error')
    store().cancelTask(stopped)
    store().markPaused(held)

    store().settleBatch(ids)
    vi.advanceTimersByTime(SETTLE_DELAY_MS)

    expect(store().tasks.map((t) => t.id)).toEqual([bad, stopped, held])
    vi.useRealTimers()
  })

  it('leaves another round untouched, including its successes', () => {
    vi.useFakeTimers()
    const [first] = addBatch(['first.txt'])
    const [second] = addBatch(['second.txt'])
    store().markCompleted(first)
    store().markCompleted(second)

    store().settleBatch([first])
    vi.advanceTimersByTime(SETTLE_DELAY_MS)

    expect(store().tasks.map((t) => t.id)).toEqual([second])
    vi.useRealTimers()
  })

  it('does not disturb an earlier round’s failure', () => {
    vi.useFakeTimers()
    const [old] = addBatch(['old.txt'])
    store().markFailed(old, 'Quota exceeded')
    const [fresh] = addBatch(['fresh.txt'])
    store().markCompleted(fresh)

    store().settleBatch([fresh])
    vi.advanceTimersByTime(SETTLE_DELAY_MS)

    expect(store().tasks.map((t) => t.id)).toEqual([old])
    vi.useRealTimers()
  })

  it('tolerates ids removed before the timer fires', () => {
    vi.useFakeTimers()
    const [a] = addBatch(['a.txt'])
    store().markCompleted(a)

    store().settleBatch([a])
    store().removeTask(a)
    expect(() => vi.advanceTimersByTime(SETTLE_DELAY_MS)).not.toThrow()
    expect(store().tasks).toHaveLength(0)
    vi.useRealTimers()
  })
})
