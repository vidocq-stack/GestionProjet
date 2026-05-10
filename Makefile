.PHONY: graph check impact test clean validate help

help:
	@echo "Cibles disponibles :"
	@echo "  make graph                                   Reconstruit graph/inverted.json depuis data/*.json (verbose)"
	@echo "  make check                                   Dry-run : sort 1 si au moins un warning (orphelin, collision, schéma)"
	@echo "  make impact ARTIFACT=g:a [DEPTH=N|all]       Liste les repos impactés par un changement"
	@echo "  make test                                    Lance les tests unitaires Python"
	@echo "  make validate                                Vérifie que tous les data/*.json suivent le schéma"
	@echo "  make clean                                   Supprime graph/inverted.json"

graph:
	python3 scripts/build_inverted_graph.py --verbose

check:
	python3 scripts/build_inverted_graph.py --check

impact:
	@test -n "$(ARTIFACT)" || (echo "Usage: make impact ARTIFACT=io.vidocq.vauban:vauban-core [DEPTH=all|N]" && exit 1)
	python3 scripts/resolve_impact.py --graph graph/inverted.json --changed $(ARTIFACT) --depth $(or $(DEPTH),all)

test:
	cd scripts && python3 -m unittest discover -s tests

validate:
	python3 scripts/validate_data.py

clean:
	rm -f graph/inverted.json
