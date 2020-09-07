npm_deps:
	npm install

build: npm_deps
	npm run build

dev: npm_deps
	npm run start
