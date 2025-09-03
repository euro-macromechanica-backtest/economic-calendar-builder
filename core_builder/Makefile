OUT ?= year_report_$(YEAR).md
CAL ?= calendar_$(YEAR).csv.gz
PY=python

run:
	$(PY) core.py run --year $(YEAR) --infile $(INFILE) $(OPTS)

validate:
	$(PY) core.py validate --year $(YEAR) --infile $(INFILE)

build:
	$(PY) core.py build --year $(YEAR) --infile $(INFILE) --outfile $(OUT)
check: build report

report:
	$(PY) core.py report --year $(YEAR) --calendar $(CAL) --outfile $(OUT)

bundle:
	$(PY) core.py bundle --year $(YEAR)
