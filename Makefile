.PHONY: test lint

test:
	PYTHONPATH=src python3.12 -m unittest discover -s tests -v

lint:
	python3.12 -m compileall -q src tests
