# api-data

## Linter and precommit install

### UV

UV is a tool that aims to replace pip and pip-tools for managing Python dependencies. It uses roughly the same API as pip-tools, but it is way faster since it is written in Rust. Moreover, it is able to install different versions of python.

- Install the latest version :

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- Restart your shell

### Python virtual environment, dependencies and git hooks (running before commit and push commands)

```bash
make install
```

### Troubleshooting

- If `make install` fails due to pre-commit not found, please run once more `make install`.

### Required : Install ggshield on your local machine if you don't already have it
Installation and usage of ggshield is documented in this [Notion page](https://www.notion.so/passcultureapp/Comment-utiliser-ggshield-254ad4e0ff98802a8d5cd6e737c60c4b?source=copy_link#142cb1c115cc4356bddc531d36d7448e)

- Linux:
```bash
curl -1sLf 'https://dl.cloudsmith.io/public/gitguardian/ggshield/setup.deb.sh' | sudo -E bash
```
- MacOs:
```bash
brew install ggshield
```

Then authenticate to ggshield:
```bash
ggshield auth login
```

## Formatting and static analysis

### Checking formatting and static analysis with `ruff`

To check code formatting and static analysis:

```bash
make ruff-check
```

You can also [integrate it to your IDE](https://docs.astral.sh/ruff/integrations/) to reformat
your code each time you save a file.

### Format code and apply auto-fixes with `ruff`

To format code, run static analysis and to apply auto-fixes:

```bash
make ruff-fix
```

## To run check micro service README

- [Recommendation documentation](apps/recommendation/README.md)

- [Compliance documentation](apps/fraud/compliance/api/README.md)
