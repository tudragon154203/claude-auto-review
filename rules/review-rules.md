# Claude Auto Review Rules

## Naming

- Use domain verbs, not generic handlers, in domain code.
- Avoid `helper`, `utils`, and `manager` names unless the surrounding domain makes their responsibility precise.
- Boolean variables should read as predicates, usually starting with `is`, `has`, `can`, `should`, or `needs`.

## Type Safety

- Avoid `any`; prefer `unknown`, explicit domain types, or narrow interfaces.
- Do not pass bare strings for security-sensitive IDs, tokens, emails, or account identifiers when a branded or structured type is practical.
- Validate external input at the system boundary before it reaches domain logic.

## Domain Logic

- Keep business rules out of transport handlers, UI event handlers, and persistence adapters.
- Use explicit exhaustive handling for closed sets of states.
- Avoid hidden default behavior that changes domain outcomes silently.

## Security

- Never use permissive fallback values for authentication, authorization, tenancy, or ownership checks.
- Do not log secrets, credentials, tokens, personal data, or raw authorization headers.
- Sanitize or parameterize user-controlled input before database, shell, or filesystem operations.
- Disallow path traversal in file/path inputs — validate, canonicalize, and restrict to intended directories.
- Prefer safe default behaviors that deny rather than permit when handling access, serialization, or deserialization.

## Error Handling

- Do not silently swallow exceptions.
- Prefer specific errors with enough context to debug without exposing secrets.
- Await promises or intentionally handle async failures.

## Concurrency / Thread Safety

- Avoid data races: shared mutable state must be protected by locks, atomics, or confined to a single thread/task.
- Design async APIs to avoid deadlocks — hold locks only for the minimum necessary time, avoid blocking calls inside async context managers.
- Validate thread affinity of resources (e.g. UI objects, DB connections) and document when they are not thread-safe.
- Prefer immutable data structures and message-passing patterns over shared mutable state.

## Resource Management

- Always acquire/initialize a resource in the same scope where it will be used; tie lifetimes together with `using`/`defer`/`try-with-resources`/RAII where practical.
- Release resources in the reverse order of acquisition to avoid circular dependencies.
- Track unique ownership explicitly (e.g. transfer ownership via move semantics or clear API contracts) rather than relying on shared ownership unless reference counting is intentional.
- Guard against leaks by ensuring every allocation/open has a matching release/close, even on error paths.

## SOLID Principles

- **Single Responsibility:** A class or module should have one reason to change. Reject god objects, catch-all utility classes, and functions that mix orchestration with domain logic.
- **Open/Closed:** Prefer extending behavior via new code (strategies, plugins, polymorphism) over modifying existing validated code. Flag hardcoded switch statements over closed sets that keep growing.
- **Liskov Substitution:** Subtypes must be substitutable for their base types. Reject derived classes that narrow preconditions, widen postconditions, or throw `NotImplementedError` for inherited methods.
- **Interface Segregation:** Clients should not depend on methods they do not use. Prefer small, focused interfaces over large monolithic ones that force consumers to depend on irrelevant capabilities.
- **Dependency Inversion:** High-level policy must not depend on low-level details; both should depend on abstractions. Flag direct instantiation of infrastructure (DB clients, HTTP callers, filesystem) inside domain or application logic.

## Testing Quality

- Unit tests must exercise the unit's full lifecycle: set up test fixture, exercise the unit, and tear down/clean up.
- Avoid brittle assertions — test outcomes, not implementation details. Do not assert on trivial "it did not throw" cases without verifying results.
- Test real error paths: assert on expected error types and messages, not generic catch-all.
- Prefer parameterized or matrix-style tests for closed sets of inputs; avoid copy-pasted test cases.

