# SPDX-License-Identifier: GPL-3.0-or-later
# The TypeScript client (docs/clients.md): build with the locked toolchain, test on clients/fixtures/codec.json.
.PHONY: build test clean
build: node_modules/.package-lock.json
	npx tsc -p tsconfig.json
node_modules/.package-lock.json: package.json package-lock.json
	npm ci --no-audit --no-fund
test: build
	node --test "dist/test/*.test.js"
clean:
	rm -rf dist node_modules
