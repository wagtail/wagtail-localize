# ----------------------------------------------------------------------------
# Self-Documented Makefile
# ref: http://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
# ----------------------------------------------------------------------------
.PHONY: help
.DEFAULT_GOAL := help

help:											## ⁉️  - Display help comments for each make command
	@grep -E '^[0-9a-zA-Z_-]+:.*? .*$$'  \
		$(MAKEFILE_LIST)  \
		| awk 'BEGIN { FS=":.*?## " }; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'  \
		| sort

npm_deps:  ## 🧰 - Install npm dependencies
	npm install

build: npm_deps  ## 🧰 - Build front-end assets
	npm run build

dev: npm_deps ## 🧰 - Build front-end assets and watch for changes in development mode
	npm run start

messages:  ## 🔨 - Make messages
	node ./scripts/extract-translatable-strings.js
	cd wagtail_localize && python ../testmanage.py makemessages --locale=en

fetch-translations:  ## 🔨 - Fetch new translations
	./scripts/fetch-translations.sh

compile-messages:  ## 🔨 - Compile messages
	cd wagtail_localize && python ../testmanage.py compilemessages

translations: build messages fetch-translations compile-messages  ## 🌍 - Prepare translations

clean:	## 🗑️  - Remove __pycache__ and test artifacts
	@echo "🗑️ - Removing __pycache__ and test artifacts"
	find . -name ".tox" -prune -o -type d -name  "__pycache__" -exec rm -r {} +

package-setup:
	@echo "📦 - Packaging for PyPI"
	flit build --setup-py

package: clean package-setup  ## 📦 - Package for PyPI

test:  ## 🧪 - Run test suite
	@echo "🧪 - Running test suite"
	tox
