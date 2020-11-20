npm_deps:
	npm install

build: npm_deps
	npm run build

dev: npm_deps
	npm run start

messages:
	node ./scripts/extract-translatable-strings.js
	cd wagtail_localize && python ../testmanage.py makemessages --locale=en
