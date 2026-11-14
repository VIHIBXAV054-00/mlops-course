# 7. heti labor: válaszok

CI-futás: a GitHubra pusholás után beillesztendő.
CT-futás: a kézi GitHub Actions-futtatás után beillesztendő.
Sikertelen futás (opcionális 6. feladat): a saját GitHub-futtatás után beillesztendő.

## 1. feladat: Az autograder workflow

Az `autograde.yml` minden pushra, pull requestre és kézi indításra lefuttatja a laborok automatikus ellenőrzését. Egy `labs` nevű jobja van. Először ellenőrzi, hogy minden labor `uv.lock` fájlja összhangban van-e a `pyproject.toml`-lal (`uv lock --check`), majd végigmegy a `labs/*/starter` és `labs/*` projektek mappáin. Minden megtalált Python-projektben `uv sync --locked --all-groups` és `uv run --frozen pytest -q` fut. A zárolt függőségek telepítése és a tesztfuttatás így minden labor saját könyvtárában történik.

A gyökérben levő workflow-k közül a `pnpm/action-setup@v4` elavult a rögzített verzió-pillanatkép szerint. Az `astral-sh/setup-uv` legújabb kiadásának főverziójához nincs azonos nevű főverziós tag: a v10-es kiadáshoz csak konkrét verziótag használható. A workflow ezért konkrét verzióra, például `v9.0.0`-ra hivatkozik, nem `@v10`-re.

## 5. feladat: Folyamatos tanítás

1. A CI pushra vagy pull requestre indul, tehát egy kódváltozást ellenőriz, és külön lint-, teszt- és pipeline-jobokat futtat. A CT időzítve vagy kézi indításra indul; újratanítja a modellt, majd ugyanazt a gate-et futtatja, de nem regisztrálja és nem telepíti a modellt. Mindkettő a Makefile céljait használja, újraépíti az adatot, közzéteszi a gate eredményét, és elmenti a bizonyítékokat. CI-nél van konkrét kóddiff és a változtatás áttekintője hagyhatta jóvá; ütemezett CT-nél nem feltétlenül történt kódváltozás vagy közvetlen emberi jóváhagyás a futás előtt. A kézi CT indítás indoklása rögzíthető, de ez nem egyenértékű a modell kiadásának jóváhagyásával.
2. A GO csak azt jelenti, hogy a modell megfelelt az előre beállított mérőszám- és csoportfeltételeknek. Nem bizonyítja önmagában a klinikai biztonságot, a jogszabályi megfelelést vagy az éles környezetre való felkészültséget. A kiadáshoz ezen felül emberi felülvizsgálat, kockázatértékelés, monitorozási és visszaállítási terv is kellhet.
3. A GitHub Actions ütemezett futásai késhetnek vagy kimaradhatnak, például nagy terhelésű időszakban; a workflow nem garantál pontos indítási időt, és külön riasztás nélkül a kimaradás észrevétlen maradhat.

## 6. feladat: Sikertelen build vizsgálata (opcionális)

Az alábbiak a feladatban várt sikertelen futás értelmezései; tényleges GitHub-futást ebben a munkakörnyezetben nem indítottam.

1. A `lint` és a `test` jobnak sikeresnek kell lennie, a `pipeline` job pedig a `make ci` lépésnél bukik el, mert az alacsonyabb `C` érték miatt a modell nem teljesíti a gate feltételeit. Ez azt mutatja, hogy a lint és a tesztek a kód, illetve a meglévő viselkedés helyességét ellenőrzik; a pipeline-job az újratanított modell elfogadhatóságát is ellenőrzi.
2. A hiba megjelenik a sikertelen `make ci` lépés kimenetében, a `pipeline` job összegzésében és a gate-összefoglaló táblázatban; a workflow `::error::` annotációt is kiír, a részletes jelentések pedig letölthetők az artifactból. Kollégának a job összefoglalóját és a gate-jelentést küldeném, mert ezek megmutatják a hibás feltételeket és a részleteket.
3. Az artifactfeltöltő lépés `if: always()` feltétellel fut. Ezért akkor is feltölti a `metrics/`, `reports/` és modellfájl bizonyítékait, ha a korábbi gate-lépés hibával leállította a pipeline-jobot.