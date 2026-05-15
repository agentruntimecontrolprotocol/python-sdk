.PHONY: diagrams

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
