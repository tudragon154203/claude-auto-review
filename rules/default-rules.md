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

## Error Handling

- Do not silently swallow exceptions.
- Prefer specific errors with enough context to debug without exposing secrets.
- Await promises or intentionally handle async failures.
