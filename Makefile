.PHONY: dev test deploy release samples

dev:          ## run locally at http://127.0.0.1:8099 against dev/media (dry run)
	dev/run-local.sh

test:         ## run the test suite
	.venv/bin/python -m pytest -q

deploy:       ## push working copy to HA as a local "Frame Art (dev)" add-on (HA_SSH=root@host)
	dev/deploy-ha.sh

release:      ## make release V=2.0.1
	dev/release.sh $(V)

samples:
	.venv/bin/python dev/make_samples.py dev/media
