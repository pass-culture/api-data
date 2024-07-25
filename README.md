# api-data

# Linter and precommit install

## Prerequisites

### Pyenv and `Python 3.9`

- Install [pyenv](https://github.com/pyenv/pyenv) to manage your Python versions and virtual environments:

  ```bash
  curl -sSL https://pyenv.run | bash
  ```

  - If you are on MacOS and experiencing errors on python install with pyenv, follow this [comment](https://github.com/pyenv/pyenv/issues/1740#issuecomment-738749988)
  - Add these lines to your `~/.bashrc` or `~/.zshrc` to be able to activate `pyenv virtualenv`:

      ```bash
      eval "$(pyenv init -)"
      eval "$(pyenv virtualenv-init -)"
      eval "$(pyenv init --path)"
      ```

  - Restart your shell

- Install the right version of `Python` with `pyenv`:

  ```bash
  pyenv install 3.9
  ```

### UV

UV is a tool that aims to replace pip and pip-tools for managing Python dependencies. It uses roughly the same API as pip-tools, but it is way faster since it is written in Rust.

- Install the latest version :

  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- Add the following line to your `~/.bashrc` or `~/.zshrc` to be able to use `uv`:

  ```bash
  . "$HOME/.cargo/env"
  ```

- Restart your shell

## Installation

### Python virtual environment, dependencies and git hooks (running before commit and push commands)

```bash
make install
```

### IAP Refresh Token

During the installation, you will be asked to connect to your Google Cloud account to generate an IAP **refresh_token**. This token is used to generate an **id_token**, which then allows to communicate with Applications deployed behind Google IAP (for instance the compliance API). The **refresh_token** is stored in your .bashrc or .zshrc under the variable 'IAP_REFRESH_TOKEN', since it can be used in different projects.

- This refresh token is used to generate an **id_token** to communicate with the IAP protected services.
  - The **id_token** is valid for 1 hour
  - The **refresh_token** is valid for several days.
- If you want to regenerate the refresh token, you can run the following command:

  ```bash
  make get_iap_refresh_token
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
