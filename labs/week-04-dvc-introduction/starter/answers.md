# Válaszok

## 2. feladat

1. Git a `data/measurements.csv.dvc` kis pointerét, a `data/.gitignore` bejegyzését
   és az új `data/raw/batch_01.csv` fájlt kapja. A batch 19 034 bájt. Silo a
   461 soros, szintén 19 034 bájtos összefűzött CSV-t tárolja az MD5-hash címe
   alatt. Ez a DVC lényege: Gitben a kis verzióhivatkozás van, a nagyobb adat pedig
   a távoli tárhelyen; a pointer alapján később pontosan ugyanaz az adat tölthető le.
2. A függvény név szerint rendezi a batch-eket, összefűzéskor új indexet készít,
   kihagyja az indexet a CSV-ből, és LF sortörést ír. Így ugyanazokból a batch-ekből
   ugyanazok a bájtok készülnek. Például a batch-ek sorrendjének felcserélése
   megváltoztatná a fájlt és az MD5-öt.
3. A parancs: `dvc pull data/measurements.csv`. Működéséhez a megfelelő Git-commit
   pointerének kell kiválasztva lennie, és a hozzá tartozó objektumnak elérhetőnek
   kell lennie a beállított távoli tárhelyen érvényes hozzáféréssel.

## 4. feladat

1. A `git checkout <verzió1-commit> -- data/measurements.csv.dvc` a Gitben tárolt
   pointerfájlt cseréli le a verzió 1 pointerére. A `dvc checkout data/measurements.csv`
   ezután a DVC helyi cache-éből állítja vissza a CSV bájtjait. Az első parancs nem
   állítja vissza az adatot, a második nem választ Git-verziót: a Git nem kezeli a
   DVC adat-cache-t, a DVC pedig nem választ pointert a Git történetéből.
2. Ha a laptopon még soha nem volt letöltve az 1. verzió, a `dvc checkout` nem találja
   a szükséges bájtokat a helyi cache-ben, ezért hibával leáll. Előbb `dvc pull
   data/measurements.csv` kell, működő Silo-hozzáféréssel; ez letölti az adatot, amit
   utána a checkout vissza tud állítani.

## 5. feladat

1. Az `evaluate` szakasz függőségei:
   `models/model.pkl`, `models/mlflow_run_id.json`, `data/processed/test.csv`,
   `src/main.py`, valamint a `cli.py`, `pipeline.py`, `model.py`, `data.py`,
   `config.py` és `tracking.py` forrásfájlok a `src/week_04_dvc_introduction/`
   mappából. Ha például a `models/model.pkl` kimarad, a modell változása után a DVC
   nem feltétlenül indítja újra az értékelést. Ilyenkor a pipeline lefuthat a korábbi
   metrikákkal, tehát hibás vagy elavult eredményt adhat anélkül, hogy hibával megállna.
2. A két adathalmaz sorszáma azonos, de a soraik és értékeik nem: a batch-ekben érkező
   mérések nem ugyanazok, mint a kurzus eredeti `diabetes.csv` fájljában lévő
   rekordok. A sorszám csak a méretet mondja meg; a tartalmat és az egyes bájtokat
   nem. Ezért azonos sor-/rekordszám mellett a mérőszámok és a hash-ek eltérhetnek.

## 6. feladat

1. A DVC 32 karakteres MD5-e a fájl pontos bájtjait azonosítja; ezt adnám az
   auditornak, mert megmutatja, melyik pontos adatverzió tanította a modellt. Az
   MLflow 8 karakteres digestje az MLflow által naplózott táblázatos adathalmaz
   rövid azonosítója, nem a CSV bájtszintű hash-e. Ez MLflow-ban a dataset-inputok
   gyors azonosítására és összehasonlítására hasznos.
2. A `make runs-for-data` a
   `tags.dvc_md5 = '<aktuális pointer teljes MD5-e>'` szűrőt használja. Ezzel az
   kérdés az, hogy melyik MLflow-futás tanított az aktuális, pontos DVC-adatverzión.
   A 3. héten a fájlútvonal és a sorszám önmagában erre nem adott választ.
3. Az új **Data version** sor a DVC MD5-öt és az S3/Silo objektum URL-jét mutatja.
   Így az alias → modellverzió → MLflow-futás → adatverzió → tárolt bájtok lánc
   követhető. A lánc csak addig járható be, amíg a megnevezett objektum megvan a
   Silo-ban, és van hozzáférésünk.
