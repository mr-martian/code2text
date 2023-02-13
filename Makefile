build-all:
	python3 setup.py build
test:
	python3 -m unittest discover
install-local:
	pip3 install .
