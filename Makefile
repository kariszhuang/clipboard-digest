.PHONY: venv freeze freeze-dev install install-dev run type clean update

# activate venv
VENV_ACTIVATE = source venv/bin/activate

# run your main script
run:
	. ./run_clipdigest.sh

# type-check with mypy
type:
	mypy .

# compile lockfiles
requirements.txt: requirements.in
	$(VENV_ACTIVATE) && pip-compile requirements.in

dev-requirements.txt: dev-requirements.in requirements.txt
	$(VENV_ACTIVATE) && pip-compile dev-requirements.in

freeze: requirements.txt
freeze-dev: dev-requirements.txt


install: requirements.txt
	pip install -r requirements.txt

install-dev: dev-requirements.txt
	pip install -r dev-requirements.txt

# remove venv and lockfiles
clean:
	rm -rf venv requirements.txt dev-requirements.txt
