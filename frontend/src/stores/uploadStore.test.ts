import { afterEach, describe, expect, it } from 'vitest'

import { useUploadStore } from './uploadStore'

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
