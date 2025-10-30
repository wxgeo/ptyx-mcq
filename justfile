set shell := ["bash", "-cu"]

uv := "env -u VIRTUAL_ENV uv"

default:
    just --list
    
    
sync:
   {{uv}} run sync
   
doc:
    {{uv}} run make -C doc autodoc
    {{uv}} run make -C doc html
    
test:
    {{uv}} run ruff check ptyx_mcq tests
    {{uv}} run mypy ptyx_mcq tests
    {{uv}} run pytest -n auto tests

slow-test:
	{{uv}} run pytest -n auto --runslow tests/

single-processor-test:
	{{uv}} run pytest tests/

update-version:
    {{uv}} run semantic-release version
	
build: update-version
    {{uv}} build
    
publish: build
    {{uv}} publish
	
fix:
    {{uv}} run black .
    {{uv}} run ruff check --fix ptyx_mcq tests
    
lock:
    git commit uv.lock -m "dev: update uv.lock"
