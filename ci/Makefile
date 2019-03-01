# Run the test suite in local container

BASE_OS ?= fedora\:rawhide  # Base image
DOCKER  ?= docker

run: Dockerfile
	$(DOCKER) build --rm --tag rpmrh:local-ci -f $< ..
	$(DOCKER) run rpmrh:local-ci

Dockerfile: Dockerfile.in
	sed -E 's|@BASE_OS@|$(BASE_OS)|' $< >$@

clean:
	$(DOCKER) image rm rpmrh:local-ci
	$(RM) Dockerfile
