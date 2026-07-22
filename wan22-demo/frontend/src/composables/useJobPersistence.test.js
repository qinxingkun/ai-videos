import test from 'node:test'
import assert from 'node:assert/strict'

import {
  appendHistoryRecord,
  entryToVideoItems,
  loadHistory,
  mergeImportedVideos,
  parseFilenameTimestamp,
  saveHistory,
  sortAndTrimVideos,
  HISTORY_MAX_VIDEOS
} from './useJobPersistence.js'

test('parseFilenameTimestamp reads ComfyUI output filename', () => {
  const ts = parseFilenameTimestamp('wan2.2_t2v_high_noise_14B_fp8_scaled-20260717-1441_00001_.mp4')
  const d = new Date(ts)
  assert.equal(d.getFullYear(), 2026)
  assert.equal(d.getMonth(), 6)
  assert.equal(d.getDate(), 17)
  assert.equal(d.getHours(), 14)
  assert.equal(d.getMinutes(), 41)
})

test('entryToVideoItems flattens job record with finalVideo', () => {
  const items = entryToVideoItems({
    promptId: 'p1',
    mode: 'wan-t2v-5s',
    time: '14:41:00',
    createdAt: 1000,
    media: [{ filename: 'seg1.mp4', kind: 'video' }],
    finalVideo: { filename: 'final.mp4', kind: 'video' }
  }, 1000)
  assert.equal(items.length, 2)
  assert.equal(items[0].filename, 'final.mp4')
  assert.equal(items[0].label, '成片')
})

test('sortAndTrimVideos keeps newest and limits count', () => {
  const videos = Array.from({ length: 120 }, (_, i) => ({
    filename: `v${i}.mp4`,
    url: `/v${i}.mp4`,
    kind: 'video',
    createdAt: i
  }))
  const trimmed = sortAndTrimVideos(videos)
  assert.equal(trimmed.length, HISTORY_MAX_VIDEOS)
  assert.equal(trimmed[0].filename, 'v119.mp4')
  assert.equal(trimmed[trimmed.length - 1].filename, 'v20.mp4')
})

test('appendHistoryRecord prepends newer videos', () => {
  const existing = [{
    id: 'old-1',
    filename: 'old.mp4',
    url: '/old.mp4',
    kind: 'video',
    mode: 'wan-t2v-5s',
    time: '12:00:00',
    createdAt: 100
  }]
  const next = appendHistoryRecord({
    promptId: 'p2',
    mode: 'wan-t2v-5s',
    media: [{ filename: 'new.mp4', kind: 'video' }]
  }, existing)
  assert.equal(next[0].filename, 'new.mp4')
  assert.equal(next[1].filename, 'old.mp4')
})

test('mergeImportedVideos dedupes by filename and sorts newest first', () => {
  const existing = [{
    id: 'old-1',
    filename: 'old.mp4',
    url: '/old.mp4',
    kind: 'video',
    mode: 'wan-t2v-5s',
    time: '12:00:00',
    createdAt: 100
  }]
  const ts = parseFilenameTimestamp('wan2.2_t2v_foo-20260717-1430_00001_.mp4')
  const merged = mergeImportedVideos([
    {
      filename: 'wan2.2_t2v_foo-20260717-1430_00001_.mp4',
      subfolder: 'video',
      type: 'output',
      kind: 'video',
      createdAt: ts,
      mode: 'wan-t2v-import',
      label: 'ComfyUI 导入'
    },
    {
      filename: 'old.mp4',
      subfolder: 'video',
      type: 'output',
      kind: 'video',
      createdAt: 50,
      mode: 'wan-t2v-import'
    }
  ], existing)
  assert.equal(merged.length, 2)
  assert.equal(merged[0].filename, 'wan2.2_t2v_foo-20260717-1430_00001_.mp4')
  assert.equal(merged[1].filename, 'old.mp4')
  assert.equal(merged[1].createdAt, 100)
})

test('saveHistory and loadHistory round-trip flat list', () => {
  const storage = new Map()
  const original = globalThis.localStorage
  globalThis.localStorage = {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, val) => storage.set(key, val),
    removeItem: (key) => storage.delete(key)
  }
  try {
    saveHistory([
      { filename: 'a.mp4', url: '/a.mp4', kind: 'video', mode: 'wan-t2v-5s', createdAt: 2 },
      { filename: 'b.mp4', url: '/b.mp4', kind: 'video', mode: 'wan-t2v-5s', createdAt: 1 }
    ])
    const loaded = loadHistory()
    assert.equal(loaded.length, 2)
    assert.equal(loaded[0].filename, 'a.mp4')
  } finally {
    globalThis.localStorage = original
  }
})
