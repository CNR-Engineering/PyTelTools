# make doc
# make test
#
# Required dependencies
# - doc: doxygen
# - venv: virtualenv

doc:
	doxygen doxygen.config

venv:
	virtualenv venv --python=python3
	source venv/bin/activate && pip install -r requirements.txt --upgrade

clean:
	rm -rf doc venv

.PHONY: doc venv
