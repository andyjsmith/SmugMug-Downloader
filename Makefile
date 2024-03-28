# Configuration
VENV_NAME?=venv
PYTHON=${VENV_NAME}/bin/python

# Detect the Python executable name
ifdef $(shell which python3)
	PYTHON_EXE=python3
else
	PYTHON_EXE=python
endif

setup: venv

venv: $(VENV_NAME)/bin/activate

$(VENV_NAME)/bin/activate: requirements.txt
	test -d $(VENV_NAME) || $(PYTHON_EXE) -m venv $(VENV_NAME)
	${PYTHON} -m pip install -U pip
	${PYTHON} -m pip install -r requirements.txt
	touch $(VENV_NAME)/bin/activate

clean:
	rm -rf $(VENV_NAME)
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

.PHONY: setup clean