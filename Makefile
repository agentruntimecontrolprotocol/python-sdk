.PHONY: diagrams build clean publish test

DIAGRAMS := arch-overview session-lifecycle job-lifecycle capability-negotiation heartbeat-ack result-chunk-progress
DIAGRAM_DIR := docs/diagrams

diagrams:
	@command -v dot >/dev/null 2>&1 || { echo "error: graphviz 'dot' not found in PATH; install with 'brew install graphviz'"; exit 1; }
	@for name in $(DIAGRAMS); do \
		echo "rendering $$name-light.svg"; \
		dot -Tsvg $(DIAGRAM_DIR)/$$name-light.dot -o $(DIAGRAM_DIR)/$$name-light.svg; \
		echo "rendering $$name-dark.svg"; \
		dot -Tsvg $(DIAGRAM_DIR)/$$name-dark.dot  -o $(DIAGRAM_DIR)/$$name-dark.svg; \
	done

clean:
	rm -rf dist build *.egg-info

build: clean
	uv build

# Publish to PyPI. Reads credentials from ~/.pypirc ([pypi] section) by
# default; override with UV_PUBLISH_TOKEN if you'd rather not touch the
# rc file. Run `make build` first or this target will fail.
publish: build
	uv publish

# Run the test suite with coverage. Equivalent to:
#   pip install -e .[test,all]
#   pytest --cov --cov-branch --cov-report=xml
# but uses `uv run` so the lockfile is honored.
test:
	uv run pytest --cov --cov-branch --cov-report=xml
