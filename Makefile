STATIC_SRC_DIR=wagtail_localize/static_src

npm_deps:
	cd ${STATIC_SRC_DIR} && npm install

build: npm_deps
	cd ${STATIC_SRC_DIR} && npm run build

dev: npm_deps
	cd ${STATIC_SRC_DIR} && npm run start
