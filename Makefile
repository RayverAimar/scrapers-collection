.PHONY: install lint format

update-requirements:
	@echo "🔄 Updating requirements and installing dependencies..."
	make create-requirements && make install
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
	@echo "📦 Installing dependencies from requirements.txt..."
	pip install -r requirements.txt
	@echo "✅ Dependencies installed successfully"

scrape-reinfo:
	@echo "🌐 Starting REINFO scraper..."
	PYTHONPATH=. python scrapers/reinfo/reinfo_scraper.py
	@echo "✅ REINFO scraper completed"

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