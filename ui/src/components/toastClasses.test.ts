import test from 'node:test'
import assert from 'node:assert/strict'
import { getToastViewportClass } from './toastClasses.ts'

test('getToastViewportClass moves toast below mock banner when mock mode is active', () => {
  const className = getToastViewportClass(true)

  assert.match(className, /\btop-12\b/)
  assert.doesNotMatch(className, /\btop-4\b/)
})

test('getToastViewportClass keeps default top offset when mock mode is inactive', () => {
  const className = getToastViewportClass(false)

  assert.match(className, /\btop-4\b/)
  assert.doesNotMatch(className, /\btop-12\b/)
})
