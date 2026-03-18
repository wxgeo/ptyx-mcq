project := "ptyx-mcq"

import "../justfiles/config.just"

default:
    just --list
    
doc:
    @cd ".." && just doc {{project}}
ruff:
    @cd ".." && just ruff {{project}}
mypy:
    @cd ".." && just mypy {{project}}
pytest:
    @cd ".." && just pytest {{project}}
fix:
    @cd ".." && just fix {{project}}
test:
    @cd ".." && just test {{project}}
push:
    @cd ".." && just push {{project}}
build:
    @cd ".." && just build {{project}}
release:
    @cd ".." && just release {{project}}

slow-test:
	{{uv}} run pytest -n auto --runslow tests/

single-processor-test:
	{{uv}} run pytest tests/


