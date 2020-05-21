ifndef CHARM_BUILD_DIR
    CHARM_BUILD_DIR=/tmp/builds
endif

help:
	@echo "This project supports the following targets"
	@echo ""
	@echo " make help - show this text"
	@echo " make submodules - make sure that the submodules are up-to-date"
	@echo " make lint - run flake8"
	@echo " make test - run the functional tests and lint"
	@echo " make functional - run the tests defined in the functional subdirectory"
	@echo " make release - build the charm"
	@echo " make clean - remove unneeded files"
	@echo ""

submodules:
	@echo "Cloning submodules"
	@git submodule update --init --recursive

lint:
	@mkdir -p report/lint/
	@echo "Running flake8"
	@tox -e lint

test: lint functional

functional: build
	@echo Executing with: CHARM_BUILD_DIR=$(CHARM_BUILD_DIR) tox -e func
	@CHARM_BUILD_DIR=$(CHARM_BUILD_DIR) tox -e func

build:
	@echo "Building charm to base directory $(CHARM_BUILD_DIR)"
	@-git describe --tags > ./repo-info
	@CHARM_LAYERS_DIR=./layers CHARM_INTERFACES_DIR=./interfaces TERM=linux \
		CHARM_BUILD_DIR=$(CHARM_BUILD_DIR) charm build . --force

release: clean build
	@echo "Charm is built at $(CHARM_BUILD_DIR)/prometheus-blackbox-exporter"

clean:
	@echo "Cleaning files"
	@if [ -d .tox ] ; then rm -r .tox ; fi
	@if [ -d .pytest_cache ] ; then rm -r .pytest_cache ; fi
	@find . -iname __pycache__ -exec rm -r {} +

# The targets below don't depend on a file
.PHONY: lint test functional build release clean help submodules
