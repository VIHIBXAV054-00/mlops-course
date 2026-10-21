# Válaszok

## 4. feladat

1. Sorrend F1, azonosságnál ROC AUC szerint:

	| Hely | Futás | F1 | ROC AUC |
	| ---: | --- | ---: | ---: |
	| 1 | `rf-n_estimators=300` | 0,6240 | 0,8172 |
	| 2 | `rf-n_estimators=100` | 0,6066 | 0,8161 |
	| 3 | `logreg-C=1.0` | 0,5785 | 0,8320 |
	| 4 | `logreg-C=10.0` | 0,5785 | 0,8318 |
	| 5 | `logreg-C=0.1` | 0,5714 | 0,8301 |
	| 6 | `logreg-C=0.01` | 0,5047 | 0,8208 |

	Nem ugyanaz a győztes: F1 szerint `rf-300`, ROC AUC szerint `logreg-C=1.0`. 
    
2. Nem élesíteném csak a legjobb teszt-F1 alapján. Az `rf-300` mátrixa `[[106, 19], [28, 39]]`, vagyis 28 beteg esetet tévesztett negatívnak. Külső validáció és elfogadott hibaküszöb is kell.
3. Az MLflow rögzítette többek között a `git_commit` taget, a paramétereket, a metrikákat és a modell artefaktumait.

## 6. feladat

1. Alias feloldása (`get_model_version_by_alias`) → verzió `run_id`-ja → futás lekérése (`get_run`) → paraméterek, metrikák, `git_commit` → a commit ellenőrzése Gitben (`git checkout <commit>`). A commitból a forráskódig vezető lépés nem az MLflow feladata.
2. Az alias átállítható másik verzióra a verzió módosítása nélkül, és több alias is mutathat ugyanarra a verzióra (`staging`, `champion`).
3. A `data/diabetes.csv` útvonal azt mutatja, melyik fájlból származnak a metrikák, de nem garantálja, hogy a fájl később változatlan marad. Ehhez verziózott adat vagy eltárolt adatpéldány és tartalom-hash szükséges.
