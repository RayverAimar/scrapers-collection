.PHONY: install lint format

update-requirements:
	@echo "🔄 Updating requirements and installing dependencies..."
	make create-requirements && pip install -r requirements.txt
	@echo "✅ Requirements updated and installed successfully"

create-requirements:
	@echo "🔍 Checking if pip-tools is installed..."
	@if pip freeze | grep -q "^pip-tools=="; then \
		echo "✅ pip-tools is already installed"; \
	else \
		echo "📦 Installing pip-tools..."; \
		pip install pip-tools; \
		echo "✅ pip-tools installed successfully"; \
	fi
	@echo "📝 Generating requirements.txt from requirements.in..."
	pip-compile --output-file requirements.txt --strip-extras requirements.in
	@echo "✅ requirements.txt generated successfully"

install:
	make create-requirements
	@echo "📦 Installing dependencies from requirements.txt..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed successfully"
	@echo "📦 Installing pre-commit git hooks..."
	pre-commit install
	@echo "✅ Pre-commit git hooks installed successfully"

scrape-reinfo:
	@echo "🌐 Starting REINFO scraper..."
	PYTHONPATH=. python scrapers/reinfo/reinfo_scraper.py
	@echo "✅ REINFO scraper completed"

scrape-redjum:
	@echo "🌐 Starting REDJUM scraper..."
	@if [ -n "$(csv)" ]; then \
		echo "📄 Using CSV file: $(csv)"; \
	fi
	PYTHONPATH=. python scrapers/redjum/redjum_scraper.py $(if $(csv),--csv $(csv),)
	@echo "✅ REDJUM scraper completed"

lint:
	@echo "🔍 Running flake8 linter..."
	flake8 scrapers/
	@echo "✅ Linting completed"

format:
	@echo "🎨 Running black formatter..."
	black scrapers/
	@echo "✅ Formatting completed"

clean:
	@echo "🧹 Cleaning up Python cache files..."
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf *.pyc
	@echo "✅ Cleanup completed"