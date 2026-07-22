import test from 'node:test'
import assert from 'node:assert/strict'
import {
  buildUtterancesFromShots,
  estimatedMasterMaxFrame,
  mergeUtterancesFromShots,
  normalizeCharacters,
  validateUtterances
} from './dubbing.js'
import { jobModeFor, isMultishotDubJob } from '../composables/useJobPersistence.js'

test('rejects overlapping utterances', () => {
  const result = validateUtterances([
    { id: 'u1', speakerId: 'a', text: '你好', startFrame: 0, endFrame: 40 },
    { id: 'u2', speakerId: 'b', text: '你好', startFrame: 39, endFrame: 80 }
  ], { maxFrame: 125, speakerIds: ['a', 'b'] })

  assert.equal(result.ok, false)
  assert.match(result.error, /重叠/)
})

test('accepts adjacent non-overlapping utterances', () => {
  const result = validateUtterances([
    { id: 'u1', speakerId: 'a', text: '你好', startFrame: 0, endFrame: 40 },
    { id: 'u2', speakerId: 'b', text: '你好', startFrame: 40, endFrame: 80 }
  ], { maxFrame: 125, speakerIds: ['a', 'b'] })

  assert.equal(result.ok, true)
})

test('normalizes character ids into stable speaker ids', () => {
  const characters = normalizeCharacters([
    { id: 'A', name: '陈默', voiceId: 'male.wav' },
    { name: '周晴', voiceId: 'female.wav' }
  ])

  assert.deepEqual(characters.map((item) => item.speakerId), ['A', 'speaker-2'])
})

test('converts shot dialogue lines into structured utterances', () => {
  const utterances = buildUtterancesFromShots(
    [{ dialogue: '陈默: "你好"\n周晴: 回应', startFrame: 10, endFrame: 90, lipSyncPolicy: 'preferred' }],
    [{ id: 'A', name: '陈默' }, { id: 'B', name: '周晴' }],
    { framesPerShot: 125 }
  )

  assert.equal(utterances.length, 2)
  assert.deepEqual(utterances.map((item) => item.speakerId), ['A', 'B'])
  assert.deepEqual(utterances.map((item) => [item.startFrame, item.endFrame]), [[10, 50], [50, 90]])
})

test('applies full-film frame offset across multi-shot dialogue', () => {
  const utterances = buildUtterancesFromShots(
    [
      { dialogue: '陈默: "第一镜"', startFrame: 0, endFrame: 125, lipSyncPolicy: 'required' },
      { dialogue: '周晴: "第二镜"', startFrame: 0, endFrame: 125, lipSyncPolicy: 'preferred' }
    ],
    [{ id: 'A', name: '陈默' }, { id: 'B', name: '周晴' }],
    { framesPerShot: 125 }
  )

  assert.equal(utterances.length, 2)
  assert.deepEqual(utterances.map((item) => [item.startFrame, item.endFrame]), [[0, 125], [125, 250]])
  const validation = validateUtterances(utterances, {
    maxFrame: estimatedMasterMaxFrame(2, 125),
    speakerIds: ['A', 'B']
  })
  assert.equal(validation.ok, true)
})

test('rejects multi-shot utterances that overflow master frame budget', () => {
  const result = validateUtterances([
    { id: 'u1', speakerId: 'A', text: '越界', startFrame: 200, endFrame: 260 }
  ], { maxFrame: estimatedMasterMaxFrame(2, 125), speakerIds: ['A'] })

  assert.equal(result.ok, false)
  assert.match(result.error, /帧范围无效/)
})

test('mergeUtterancesFromShots preserves manual frame edits by id', () => {
  const shots = [
    { dialogue: '陈默: "原句"', startFrame: 0, endFrame: 125 }
  ]
  const characters = [{ id: 'A', name: '陈默' }]
  const generated = buildUtterancesFromShots(shots, characters, { framesPerShot: 125 })
  const existing = [{
    ...generated[0],
    text: '手改台词',
    startFrame: 10,
    endFrame: 40,
    lipSyncPolicy: 'required'
  }]
  const merged = mergeUtterancesFromShots(existing, shots, characters, { framesPerShot: 125 })
  assert.equal(merged[0].text, '手改台词')
  assert.equal(merged[0].startFrame, 10)
  assert.equal(merged[0].endFrame, 40)
  assert.equal(merged[0].lipSyncPolicy, 'required')
})

test('jobModeFor distinguishes wan multishot dub modes', () => {
  assert.equal(jobModeFor({ engine: 'wan', mode: 't2v', kind: 'multishot-dub' }), 'wan-t2v-multishot-dub')
  assert.equal(jobModeFor({ engine: 'wan', mode: 'i2v', kind: 'multishot-dub' }), 'wan-i2v-multishot-dub')
  assert.equal(isMultishotDubJob({ mode: 'wan-t2v-multishot-dub' }), true)
})
