# Scrapers Collection

A collection of web scrapers for gathering various types of public information from different Peruvian government websites and databases.

## Features

- REINFO (Registro Integral de Formalización Minera) scraper
  - Scrapes information about registry for miners undergoing the formalization process.

## Prerequisites

- Python 3.11
- pip
- Make

## Installation

1. Clone the repository:
```bash
git clone https://github.com/RayverAimar/scrapers-collection.git
cd scrapers-collection/
```

2. Create and activate a virtual environment:
```bash
python -m venv env
source env/bin/activate
```

3. Install dependencies:
```bash
make install
```

4. Set up environment variables:
```bash
cp env.example .env
```

## Usage

The project includes several Makefile commands for common tasks:

- `make install`: Install project dependencies
- `make update-requirements`: Update and install requirements
- `make scrape-reinfo`: Run the REINFO scraper
- `make lint`: Run flake8 linter
- `make format`: Format code using black
- `make clean`: Clean up Python cache files

## Development

The project uses several development tools:
- `flake8` for linting
- `black` for code formatting
- `pre-commit` for git hooks
- `selenium` for web scraping
