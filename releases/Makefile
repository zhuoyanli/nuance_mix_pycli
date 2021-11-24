wheel:
	# clean up existing wheel file(s)
	@rm -rf dist/* build/*
	# build wheelfile
	@python setup.py bdist_wheel

update: wheel
	@# get the wheel file
	$(eval WHEEL = $(shell ls -1 dist/*whl | head))
	@# run pip install --upgrade --force-resinstall <wheel_file>
	@python -m pip install -U --force-reinstall $(WHEEL)

