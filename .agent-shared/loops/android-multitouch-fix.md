---
name: android-multitouch-fix
max_iterations: 2
stall_limit: 1
iteration_timeout: 1800
gate_timeout: 120
gates_every_iteration: false
plan_file: docs/EXECPLAN_2026-08-07_android-multitouch-state.md
implementation_log: docs/EXECPLAN_2026-08-07_android-multitouch-state_impl.md
gates:
  - git diff --check
  - test -s flutter/test/common/widgets/gestures_test.dart
---
# Fix Android multitouch state transitions with a minimal tested patch

Implement the protected plan test-first. Change only `flutter/lib/common/widgets/gestures.dart`,
`flutter/test/common/widgets/gestures_test.dart`, and the implementation log. Do not edit
`remote_input.dart`, REQS, the plan, harness configuration, dependencies, lockfiles, or Video.

The implementation must preserve the 200ms downward-transition debounce while ensuring repeated
updates for the same pending pointer-count target update the latest details without restarting the
deadline. A changed target, `onEnd`, `rejectGesture`, or `dispose` must not leave a stale callback
that can start a gesture after its pointers are gone. Treat 3 or more pointers consistently as the
three-finger state. Keep the diff small and explain any unrun Flutter checks in the implementation
log; do not download an SDK or add dependencies.

Before declaring `LOOP_STATUS: DONE`, inspect the final diff against the protected plan, record the
test cases and commands attempted in the implementation log, and ensure no files outside the
planned range were modified by this iteration.
