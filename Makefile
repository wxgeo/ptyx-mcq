help:
	cat Makefile

doc: .
	poetry run make -C doc autodoc
	poetry run make -C doc html

tox:
	poetry run black .
	poetry run tox

version:
	poetry run semantic-release version

build: version
	poetry build

publish: build
	poetry publish

fix:
	poetry run black .
	poetry run ruff --fix ptyx_mcq tests

slow:
	poetry run pytest tests/ --runslow
