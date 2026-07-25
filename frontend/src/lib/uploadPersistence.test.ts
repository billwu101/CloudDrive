import { beforeEach, describe, expect, it } from 'vitest'

import {
  forgetUpload,
  listPersistedUploads,
  rememberUpload,
  restoredTasksFromStorage,
} from './uploadPersistence'

beforeEach(() => localStorage.clear())

describe('uploadPersistence', () => {
  it('remembers a session and lists it back', () => {
    rememberUpload({ sessionId: 's1', fileName: 'a.mp4', size: 123, parentId: 'p1' })
    expect(listPersistedUploads()).toEqual([
      { sessionId: 's1', fileName: 'a.mp4', size: 123, parentId: 'p1' },
    ])
  })

  it('updates in place rather than duplicating the same session', () => {
    rememberUpload({ sessionId: 's1', fileName: 'a.mp4', size: 1 })
    rememberUpload({ sessionId: 's1', fileName: 'a.mp4', size: 2 })
    const all = listPersistedUploads()
    expect(all).toHaveLength(1)
    expect(all[0].size).toBe(2)
  })

  it('forgets a completed or cancelled session', () => {
    rememberUpload({ sessionId: 's1', fileName: 'a', size: 1 })
    rememberUpload({ sessionId: 's2', fileName: 'b', size: 1 })
    forgetUpload('s1')
    expect(listPersistedUploads().map((e) => e.sessionId)).toEqual(['s2'])
  })

  it('restores tasks that await their file (File cannot be persisted)', () => {
    rememberUpload({ sessionId: 's1', fileName: 'movie.mp4', size: 999, parentId: 'p1' })
    const [task] = restoredTasksFromStorage()
    expect(task.status).toBe('needs_file')
    expect(task.file).toBeNull()
    expect(task.fileName).toBe('movie.mp4')
    expect(task.sessionId).toBe('s1')
    expect(task.parentId).toBe('p1')
  })

  it('survives a corrupt storage value without throwing', () => {
    localStorage.setItem('clouddrive.uploads.v1', 'not json{')
    expect(listPersistedUploads()).toEqual([])
  })
})
