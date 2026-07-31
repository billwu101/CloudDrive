import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useUploadStore } from '@/stores/uploadStore'

import { UploadQueue } from './UploadQueue'

vi.mock('@/hooks/useUpload', () => ({
  useUploadControls: () => ({
    pause: vi.fn(),
    continueUpload: vi.fn(),
    cancel: vi.fn(),
    resumeWithFile: vi.fn(),
  }),
}))

vi.mock('@/lib/uploadPersistence', () => ({
  restoredTasksFromStorage: () => [],
}))

afterEach(() => {
  cleanup()
  useUploadStore.setState({ tasks: [] })
})

function seedFailedTask(name: string) {
  const [task] = useUploadStore.getState().addTasks([new File(['x'], name)])
  useUploadStore.getState().markFailed(task.id, 'Connection lost')
  return task.id
}

describe('UploadQueue', () => {
  it('renders nothing when the queue is empty', () => {
    const { container } = render(<UploadQueue onRetry={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('drops the old failed row when the user retries it (proposal §27.8)', async () => {
    const id = seedFailedTask('bad.txt')
    const onRetry = vi.fn()
    render(<UploadQueue onRetry={onRetry} />)

    await userEvent.click(screen.getByLabelText('Retry upload'))

    // The caller still gets the task (it needs the File to start a new round),
    // but the row it came from is gone — a retried failure is no longer the
    // current state of that file.
    expect(onRetry).toHaveBeenCalledTimes(1)
    expect(onRetry.mock.calls[0][0].id).toBe(id)
    expect(useUploadStore.getState().tasks).toHaveLength(0)
  })
})
