import { describe, expect, it } from 'vitest'

import {
  formatBytes,
  MAX_UPLOAD_SIZE_BYTES,
  precheckBatch,
  runWithConcurrency,
  UPLOAD_CONCURRENCY,
  uploadErrorMessage,
} from './uploadLimits'

const MB = 1024 * 1024

describe('formatBytes', () => {
  it('scales to the largest fitting unit', () => {
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2 * 1024)).toBe('2.0 KB')
    expect(formatBytes(100 * MB)).toBe('100 MB')
    expect(formatBytes(1.93 * 1024 * MB)).toBe('1.9 GB')
  })
})

describe('precheckBatch', () => {
  it('rejects a file over the single-file limit', () => {
    const [verdict] = precheckBatch([MAX_UPLOAD_SIZE_BYTES + 1])
    expect(verdict?.code).toBe('FILE_TOO_LARGE')
    expect(verdict?.message).toContain('too large')
  })

  it('accepts a file exactly at the limit', () => {
    expect(precheckBatch([MAX_UPLOAD_SIZE_BYTES])).toEqual([null])
  })

  it('rejects a file that does not fit the remaining quota', () => {
    const [verdict] = precheckBatch([10 * MB], 5 * MB)
    expect(verdict?.code).toBe('QUOTA_EXCEEDED')
    expect(verdict?.message).toContain('storage space')
  })

  it('spends quota cumulatively across the batch', () => {
    // Each file fits on its own; together they exceed the 25 MB left.
    const verdicts = precheckBatch([10 * MB, 10 * MB, 10 * MB], 25 * MB)
    expect(verdicts[0]).toBeNull()
    expect(verdicts[1]).toBeNull()
    expect(verdicts[2]?.code).toBe('QUOTA_EXCEEDED')
  })

  it('does not spend quota on files already rejected for size', () => {
    const verdicts = precheckBatch([MAX_UPLOAD_SIZE_BYTES + 1, 10 * MB], 20 * MB)
    expect(verdicts[0]?.code).toBe('FILE_TOO_LARGE')
    expect(verdicts[1]).toBeNull()
  })

  it('checks only the size limit when the quota is unknown', () => {
    expect(precheckBatch([10 * MB, 20 * MB], undefined)).toEqual([null, null])
  })
})

describe('uploadErrorMessage', () => {
  it('distinguishes the three failure kinds instead of always saying network', () => {
    expect(uploadErrorMessage({ code: 'FILE_TOO_LARGE', message: 'x', status: 413 })).toContain(
      'too large',
    )
    expect(uploadErrorMessage({ code: 'QUOTA_EXCEEDED', message: 'x', status: 413 })).toContain(
      'storage space',
    )
    expect(uploadErrorMessage({ code: 'NETWORK_ERROR', message: 'x', status: 0 })).toContain(
      'Connection lost',
    )
  })

  it('treats a bare 413 (rejected by the proxy, no code) as too large', () => {
    expect(uploadErrorMessage({ code: 'UNKNOWN', message: 'Request failed', status: 413 })).toContain(
      'too large',
    )
  })

  it('falls back to the server message, then to a generic one', () => {
    expect(uploadErrorMessage({ code: 'NAME_CONFLICT', message: 'Name taken', status: 409 })).toBe(
      'Name taken',
    )
    expect(uploadErrorMessage(new Error('boom'))).toBe('Upload failed')
  })
})

describe('runWithConcurrency', () => {
  it('never runs more than the limit at once', async () => {
    let inFlight = 0
    let peak = 0
    const items = Array.from({ length: 10 }, (_, i) => i)

    await runWithConcurrency(items, UPLOAD_CONCURRENCY, async () => {
      inFlight += 1
      peak = Math.max(peak, inFlight)
      await new Promise((r) => setTimeout(r, 1))
      inFlight -= 1
    })

    expect(peak).toBe(UPLOAD_CONCURRENCY)
  })

  it('processes every item even when some fail', async () => {
    const seen: number[] = []
    await runWithConcurrency([1, 2, 3, 4], 2, async (n) => {
      seen.push(n)
      if (n % 2 === 0) throw new Error('nope')
    })
    expect(seen.sort()).toEqual([1, 2, 3, 4])
  })

  it('handles an empty batch without hanging', async () => {
    await expect(runWithConcurrency([], 3, async () => {})).resolves.toBeUndefined()
  })
})
