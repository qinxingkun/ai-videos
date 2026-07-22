import test from 'node:test'
import assert from 'node:assert/strict'
import {
  RES_480P,
  RES_720P,
  detectWanPreset,
  snapWanDimension,
  validateWanResolution
} from './frameUtils.js'

test('detectWanPreset recognizes standard presets', () => {
  assert.equal(detectWanPreset(RES_480P.width, RES_480P.height), '480p')
  assert.equal(detectWanPreset(RES_720P.width, RES_720P.height), '720p')
  assert.equal(detectWanPreset(960, 544), 'custom')
})

test('snapWanDimension rounds to multiples of 16', () => {
  assert.equal(snapWanDimension(833), 832)
  assert.equal(snapWanDimension(1281), 1280)
})

test('validateWanResolution enforces step 16', () => {
  assert.equal(validateWanResolution(832, 480).ok, true)
  assert.equal(validateWanResolution(833, 480).ok, false)
})
