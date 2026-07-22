import test from 'node:test'
import assert from 'node:assert/strict'
import { isDurationOnlyFailure } from './orchestrator.js'

test('isDurationOnlyFailure detects pure duration QA failures', () => {
  assert.equal(isDurationOnlyFailure(['duration 9.56s > 6.0s']), true)
  assert.equal(
    isDurationOnlyFailure(['duration 9.56s > 6.0s（≈153 frames @ 16.00fps；expected 81@16）']),
    true
  )
  assert.equal(isDurationOnlyFailure(['duration 9.56s > 6.0s', 'width 640 != 1280']), false)
  assert.equal(isDurationOnlyFailure([]), false)
})
