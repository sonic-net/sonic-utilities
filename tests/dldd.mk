PYTHON ?= python3

.PHONY: coverage-gate
coverage-gate:
	$(PYTHON) -m coverage report \
		--include='config/dldd.py,show/dldd.py,utilities_common/dldd.py' \
		--fail-under=100
