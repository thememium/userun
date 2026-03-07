# Changelog

## v0.1.4 (2026-03-07)

[Compare changes](https://github.com/thememium/userun/compare/v0.1.3...v0.1.4)

### 🤖 CI

- **publish.yml**: add workflow to publish package on release ([5edde7b](https://github.com/thememium/userun/commit/5edde7b5d926db6702d76df292690ebbf8e04719))

### Contributors

- Edward Boswell <thememium@gmail.com>

## v0.1.3 (2026-03-07)

[Compare changes](https://github.com/thememium/userun/compare/v0.1.2...v0.1.3)

### 🤖 CI

- **publish.yml**: add workflow to publish package on release ([5edde7b](https://github.com/thememium/userun/commit/5edde7b5d926db6702d76df292690ebbf8e04719))

### Contributors

- Edward Boswell <thememium@gmail.com>

## v0.1.2 (2026-03-07)

[Compare changes](https://github.com/thememium/userun/compare/v0.1.1...v0.1.2)

### 🩹 Fixes

- **poe**: update dev task to run correct entry point ([cc713c7](https://github.com/thememium/userun/commit/cc713c771caf2a8fe5ba6f8ba0f2609a6715b469))

### 📖 Documentation

- **readme**: replace text logo with image logo ([9248cc8](https://github.com/thememium/userun/commit/9248cc8f0a89525f2e5d171284aa1b3827b52f42))
- add dark‑background logo image for documentation ([c124a00](https://github.com/thememium/userun/commit/c124a002ca743e65296d1d1a3dbe0f2b17a21b2d))
- **readme**: add comprehensive project README ([03b5268](https://github.com/thememium/userun/commit/03b5268d98dabd9aeef5b93dce9e1ff0522f5ab9))

### 🏡 Chore

- **userun/cli**: delete obsolete command.py.j2 template ([2481ae6](https://github.com/thememium/userun/commit/2481ae6523b8c54190f041ecb510f517db256905))

### Contributors

- Edward Boswell <thememium@gmail.com>

## v0.1.1 (2026-03-07)

### 🚀 Enhancements

- **concurrent_command**: add configurable shell option and refactor subprocess execution ([734f22f](https://github.com/thememium/userun/commit/734f22fae95fb2e920cc98cd97cdc11bd706a025))
- **cli**: hide make command by default ([f0b9c1a](https://github.com/thememium/userun/commit/f0b9c1a31743e100b5d20f4f021191c72dd1f6d1))
- **pyproject**: add concurrent-demo script and tidy dependencies list ([703f18d](https://github.com/thememium/userun/commit/703f18d6dd4f736d68fdb10e906703c80256565b))
- **concurrent_command**: add subprocess-color flag and strip ANSI when disabled ([a39dac4](https://github.com/thememium/userun/commit/a39dac41ecaf49fbe3fb39e8357919e458a73b34))
- **concurrent_command**: add customizable prefixes, color support, and kill‑others option ([a155dce](https://github.com/thememium/userun/commit/a155dcebf90d82f69aa49dfa3a09a7cf7e2eb92e))
- **cli**: add concurrent command to run multiple commands in parallel ([1e26605](https://github.com/thememium/userun/commit/1e26605c9d1ea0e902137b93605ece5db3159977))
- **pyproject.toml**: add asyncio dependency and configure deptry ignores ([3f87e35](https://github.com/thememium/userun/commit/3f87e3547e2071ea58cba54ae9ba6e6d12f982ff))
- **userun/cli**: hide inspire command by default ([a5bb9e9](https://github.com/thememium/userun/commit/a5bb9e9041e6e61bbee2e949f857ff679d46c9a5))
- **userun**: add CLI scaffolding and initial entry point ([763d040](https://github.com/thememium/userun/commit/763d040cd89c751a3c7024ba2e7b951a22b2ef2e))

### 💅 Refactors

- **concurrent_command**: extract shell handling into helper methods and simplify defaults ([782252c](https://github.com/thememium/userun/commit/782252c7440d7491abc6b3ce4bfdb40aa5844264))

### ✅ Tests

- **concurrent_command**: add tests for bash fallback and shell‑argument parsing ([8e31e95](https://github.com/thememium/userun/commit/8e31e95ae2e10f191c26109339d47e5bf80c8089))
- **concurrent_command**: add tests for subprocess color handling ([2a5d917](https://github.com/thememium/userun/commit/2a5d917bac62c336ccef1245636a702e2f877256))
- **concurrent_command**: add test for name prefixes and no-color output ([92aff0c](https://github.com/thememium/userun/commit/92aff0c3058fd78329d8ed537f99eb4c9e5c6aa2))
- **concurrent_command**: add tests for ConcurrentCommand execution flow ([bc2f6a6](https://github.com/thememium/userun/commit/bc2f6a6a2063a84c8894258c87995333dcb2131d))

### Contributors

- Edward Boswell <thememium@gmail.com>
