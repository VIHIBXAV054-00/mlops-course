# Válaszok

## 4. feladat

Az MLflow futások metaadatai (kísérletek, paraméterek, metrikák és tagek) a Postgresben vannak. A modellfájlok és más artefaktumok a MinIO objektumtárolóba kerülnek. A modell bináris fájl, ezért nem relációs adatok tárolására készült Postgresben: az objektumtároló nagy fájlokhoz és azok hatékony kiszolgálásához való.

## 5. feladat

A központi nyilvántartásban megőrizhetők és összehasonlíthatók a futások paraméterei, metrikái és modelljei. Így ellenőrizhető, hogy azonos adatokkal, kóddal és véletlenmaggal megismétlődött-e az eredmény; a futásokat mások is megtekinthetik a tracking URI-n keresztül. A Week 1 terminál-előzménye önmagában nem adott tartós, közösen lekérdezhető összehasonlítást.