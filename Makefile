.PHONY: install dev test lint analyze portfolio monitor

install:
	pip install -e .

dev:
	pip install -e ".[all]"

test:
	pytest tests/ -v --cov=maiupbit --cov-report=term-missing

lint:
	ruff check maiupbit/ scripts/ tests/

analyze:
	python -m maiupbit analyze KRW-BTC

portfolio:
	python -m maiupbit portfolio

monitor:
	python scripts/monitor.py

report:
	python scripts/daily_report.py

train:
	python scripts/train_model.py
