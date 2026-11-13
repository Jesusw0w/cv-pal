import { Resource, Signal, computed } from '@angular/core';

/**
 * A resource's value, or `fallback` while its request has failed.
 *
 * Reading `value()` on a failed resource throws, which takes the whole template down
 * with it — including the "could not load, try again" notice that was about to explain
 * the failure. Services expose this instead, and report the failure through `error`.
 */
export function valueOr<T, F>(resource: Resource<T>, fallback: F): Signal<T | F> {
  return computed(() => (resource.hasValue() ? resource.value() : fallback));
}
