# shapeledger-Handbuch

Beobachtete JSONL-Strukturen vergleichen, ohne skalare Beispielwerte zu speichern. Für Änderungen an Testdaten und Exporten. [English](../README.md) · [简体中文](README.zh-CN.md) · [Русский](README.ru.md)

## Schnellstart

Python 3.10+, zur Laufzeit nur die Standardbibliothek. Im Repository-Verzeichnis:

```sh
python -m shapeledger profile examples/baseline.jsonl > /tmp/baseline.shape.json
python -m shapeledger profile examples/candidate.jsonl > /tmp/candidate.shape.json
python -m shapeledger compare /tmp/baseline.shape.json /tmp/candidate.shape.json
python -m shapeledger compare /tmp/baseline.shape.json /tmp/candidate.shape.json --fail-on added_type --fail-on removed_path --fail-on missing_increase
```

Der letzte Befehl liefert für diese Beispiele Exitcode 1. `python -m pip install .` installiert den Befehl `shapeledger`. Der Build braucht setuptools, die Laufzeit keine Fremdbibliotheken. `profile -` liest stdin. Deterministisches JSON erscheint auf stdout. In eine neue Datei umleiten: Die Shell kann eine vorhandene Datei schon vor der Eingabeprüfung leeren. Das Programm gibt keine Teilprofile aus.

## Eingabe und Zählweise

Jede Zeile enthält genau einen strikten UTF-8-JSON-Wert; beliebige Wurzeltypen sind erlaubt. Leerzeilen, BOM, doppelte Schlüssel, NaN, Infinity, Float-Überlauf und beschädigte Datensätze werden abgelehnt. CRLF und eine letzte Zeile ohne Zeilenumbruch sind erlaubt. Fehler nennen die ungültige Datensatzzeile, ohne deren Inhalt auszugeben.

Version 1 enthält `version`, `records` und die sortierte Liste `nodes`. Ein Knoten enthält `path`, `types`, `opportunities`, `array_items`. Typen sind object, array, string, integer, number, boolean und null; `1` und `1.0` unterscheiden sich. Typisierte Pfade sehen so aus: `[["key","users"],["items"],["key","name"]]`. Punkte, Schrägstriche, Sterne, leere Schlüssel und der wörtliche Schlüssel `items` bleiben eindeutig.

- An der Wurzel entspricht die Anzahl der Möglichkeiten der Datensatzanzahl.
- Bei einem Objektschlüssel entspricht sie den beobachteten Objektinstanzen am Elternpfad, nicht allen Datensätzen oder Elterntypen.
- Bei Array-Elementen entspricht sie der gesamten Elementanzahl. Jedes Element einschließlich null zählt einmal.
- Fehlende Werte = Möglichkeiten minus Summe der Typzählungen. Null ist vorhanden und nicht fehlend.
- `array_items` summiert Array-Längen am Knoten. Leere Arrays erzeugen keinen Elementknoten. Felder von Objekten in Arrays verwenden nur diese Objektinstanzen als Nenner.
- Ohne Beobachtung gibt es keinen Knoten. Ein verschwundener Elternpfad wird als entfernter Pfad gemeldet, nicht als erfundene Nullquote.

Objektschlüssel und Strukturzählungen bleiben erhalten und können sensibel sein, besonders dynamische Schlüssel. Dies ist Datenminimierung, keine Anonymisierung. Skalare Werte werden vorübergehend im Speicher geparst, aber nicht ausgegeben. Fehlermeldungen enthalten keine Quelldaten oder Dateinamen.

## Vergleich und CI

Beide Profile werden vor dem Vergleich strikt validiert. Ereignisse sind `added_path`, `removed_path`, `added_type`, `missing_increase`, `null_increase`. Bei bestehenden Pfaden werden Quoten als exakte rationale Zahlen verglichen und etwa als `1/3` ausgegeben. Nullquoten verwenden Möglichkeiten als Nenner, nicht die Anzahl vorhandener Werte. Jede positive Erhöhung erzeugt ein Ereignis; Version 0.1 hat keine einstellbaren numerischen Schwellen. Entfernte Typen werden nicht gemeldet. Neue oder entfernte Pfade erzeugen nur Pfadereignisse, keine zusätzlichen Typ- oder Quotenereignisse.

Alle Ereignisse werden unabhängig von der CI-Politik ausgegeben. Mit wiederholtem `--fail-on KIND` wählen Sie Fehlerbedingungen. Ohne Auswahl ist der Vergleich rein informativ.

- Exitcode 0: gültige Eingabe, keine ausgewählte Bedingung erfüllt.
- Exitcode 1: mindestens eine ausgewählte Bedingung erfüllt.
- Exitcode 2: ungültige Eingabe/Profil, Limitüberschreitung, I/O- oder Aufruffehler.

## Grenzen

Streaming erfolgt pro Datensatz, nicht pro JSON-Token. Standard: 1 MiB pro Zeile einschließlich Zeilenumbruch (`--max-line-bytes`), höchstens 10.000 Knoten (`--max-nodes`), Pfadtiefe 64 (`--max-depth`, Wurzel 0). Knoten- und Tiefenlimits lassen sich nur senken. Alle Limits müssen positive ganze Zahlen sein. Speicherbedarf hängt von maximaler Zeile und gespeicherten Pfaden ab. Array-Elemente werden zusammengefasst, dynamische Schlüssel nicht normalisiert. Der Python-Parser kann tiefe Datensätze früher ablehnen. Jeder Profilvergleichseingang ist auf 32 MiB begrenzt; Felder, Version, Pfade, Zählungen und Elternbeziehungen werden geprüft.

Profile sind Beobachtungen, keine kryptografischen Nachweise oder vollständigen JSON Schemas. Keine Schemavalidierung, Verteilungsinferenz, Profilzusammenführung, Feldfilter oder Zahlenbereiche. Floats werden durch die Standardbibliothek geparst; ihre Genauigkeit beeinflusst die Typzählung nicht. Ausgaben benötigen Speicherplatz; eine geschlossene Pipe verursacht einen I/O-Fehler.

## Alternativen und Entwicklung

[GenSON](https://github.com/wolverdude/GenSON) erzeugt und vereinigt JSON Schemas. [DataProfiler](https://github.com/capitalone/DataProfiler) bietet umfassendere Statistik- und Entitätsprofile. shapeledger konzentriert sich auf Strukturzählungen, elternbezogene Fehlquoten und ausdrückliche CI-Ereignisse. Es ersetzt diese Projekte nicht und beansprucht keine neue Schemainferenz.

```sh
python -m unittest discover -s tests -v
python -m pip wheel --no-deps . -w dist
```

CI testet Python 3.10–3.13 und die Wheel-Installation. Beiträge brauchen Regressionstests; bei geänderter Semantik alle vier Sprachfassungen aktualisieren. Nur synthetische Beispiele verwenden, keine privaten Daten einchecken. Mögliche Erweiterungen: Profilzusammenführung, Pfadfilter, Budgets für dynamische Schlüssel. MIT-Lizenz.
