.PHONY: fmt check

fmt: format check

format:
	ruff format packages/tigen/src packages/zero/src

check:
	ruff check packages/tigen/src packages/zero/src --fix
	ty check packages/tigen/src packages/zero/src

test:
	pytest
run:
	python run.py

bench:
	python -m perf.bench_ecs -n 10000 -t 100

bench-full:
	python -m perf.bench_ecs --full