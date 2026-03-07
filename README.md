<a name="readme-top"></a>

<div align="center">
  <a href="https://github.com/thememium/userun">
    <img src="https://raw.githubusercontent.com/thememium/userun/refs/heads/master/docs/images/userun-logo-dark-bg.png" alt="useRun" width="407" height="162">
  </a>

  <p align="center">
    <a href="#table-of-contents"><strong>Explore the Documentation »</strong></a>
    <br />
    <a href="https://github.com/thememium/userun/issues">Report Bug</a>
    ·
    <a href="https://github.com/thememium/userun/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->

<a name="table-of-contents"></a>

<details>
  <summary>Table of Contents</summary>
  <ol>
    <li><a href="#about">About</a></li>
    <li><a href="#quick-start">Quick Start</a></li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#development">Development</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
  </ol>
</details>

<!-- ABOUT -->

## About

userun is a Python command runner for concurrent runs. It gives you:

- **Parallel execution** - Run multiple commands at the same time
- **Named prefixes** - Label output with names and optional colors
- **Custom prefixes** - Format prefixes with index, name, or label
- **Failure handling** - Stop remaining commands on first failure
- **Shell control** - Choose the shell and ANSI color passthrough

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- QUICK START -->

## Quick Start

### Install userun with uv (recommended)

```sh
uv add userun
```

### Install with pip (alternative)

```sh
pip install userun
```

### Run commands concurrently

```sh
userun concurrent -n server,lint,test "python3 -m http.server 8000" "uv run poe lint" "uv run poe test"
```

Each command runs in parallel and output is prefixed with its name.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- USAGE -->

## Usage

### Run Commands Concurrently

```sh
userun concurrent "echo one" "echo two"
```

### Named and Colored Prefixes

```sh
userun concurrent -n api,web -c blue,green "uv run api" "uv run web"
```

### Custom Prefix Format

```sh
userun concurrent -p "[{label}]" "make build" "make test"
```

### Stop Others on Failure

```sh
userun concurrent --kill-others "make build" "make test"
```

### Shell Selection

```sh
userun concurrent --shell "bash -lc" "echo $SHELL" "echo hi"
```

### Disable Prefixes or Colors

```sh
userun concurrent --no-prefix --no-color "make build" "make lint"
userun concurrent --no-subprocess-color "uv run pytest" "uv run ruff check ."
```

### Available Commands

```
concurrent (conc)  Run multiple commands concurrently
help               Show help
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- DEVELOPMENT -->

## Development

Common tasks:

```sh
uv run poe clean-full
uv run poe test
uv run poe lint
uv run poe format
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- CONTRIBUTING -->

## Contributing

Quick workflow:

1. Fork and branch: `git checkout -b feature/name`
2. Make changes
3. Run checks: `uv run poe clean-full`
4. Commit and push
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->

## License

License information has not been added yet.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---

<div align="center">
  <p>
    <sub>Built by <a href="https://github.com/thememium">thememium</a></sub>
  </p>
</div>
