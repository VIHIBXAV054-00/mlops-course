# Válaszok

## 2. feladat

1. Nem dobnám el és nem venném fel automatikusan a `notes` oszlopot a
   szerződésbe. Előbb egyeztetnék a klinika adatokért felelős csapatával, hogy ez az oszlop valóban a jövőbeni adatátadás része-e,
   és szükség van-e rá. Ha elfogadják, módosítanám a sémát és annak
   verzióját is. Addig elutasítanám a nem várt oszlopot, hogy az adatváltozás ne
   maradjon észrevétlen.

2. A négy hiba:
   - 3. sor, `glucose`: az érték `unknown`, ezért nem alakítható számmá.
   - 7. sor, `age`: az érték `250`, ami meghaladja a 120-as felső határt.
   - 23. sor, `bmi`: az érték `280.0`, ami meghaladja a 100-as felső határt.
   - Teljes táblára vonatkozó hiba: a `notes` oszlop nem szerepel a sémában.

   A `glucose=unknown` hiba több riportbejegyzést eredményez: az érték nem
   alakítható `float64` típussá, emiatt a típusellenőrzés is hibát jelez, és a
   számszerű alsó- és felsőhatár-ellenőrzések sem tudják összehasonlítani.

## 4. feladat

1. Kapu nélkül a hibás `age = 250` bekerül a `data/processed/train.csv` és
   `data/processed/test.csv` fájlokba, majd a modell tanítása és kiértékelése
   felhasználja ezeket. A train eredményéből `models/model.pkl` és egy MLflow
   run, az evaluate eredményéből `metrics/metrics.json` készül. Ezeket később
   a modellregisztráció és az élesítés használhatja. A kapuval a `validate`
   megírja a riportot, majd hibánál leáll, ezért a `prepare` és az utána
   következő szakaszok nem futnak le.
2. A kézzel indított `prepare` hibával leáll, ha nincs sikeres legutóbbi
   validációs riport. Ezt a `prepare` elején meghívott `_require_validated`
   ellenőrzi. A DVC-függőségi él csak a DVC által futtatott pipeline sorrendjét
   szabályozza; a közvetlen Python-hívást nem védi.
3. A `MAX_AGE` változása miatt a `validate` újrafut, mert a `schemas.py`
   függősége megváltozott. A jelenlegi adatok maximum életkora 81, ezért a
   120-ról 125-re emelés mellett a riport tartalma változatlan marad. Így a
   `prepare`, `train` és `evaluate` kihagyható, mert a riport kimenete és a
   feldolgozandó adatok nem változtak; a modellt nem kell újratanítani. A 120-ra
   visszaállítás ismét kiváltja a `validate` futását, de azonos sikeres riport
   esetén a további szakaszok továbbra is kihagyhatók.

## 6. feladat

Az `insulin: null` kérés átmegy a szerződésen, és a modell a tanítóadatokból
megtanult mediánnal tölti ki. Nem tartanám ezt automatikusan helyesnek úgy,
hogy a kérések 40%-ában hiányzik az érték: előbb megvizsgálnám, hogy ez
rendszeres vagy informatív hiányzás-e, és mérném a kitöltés hatását. A
hiányzó értékek elfogadásáról vagy elutasításáról a klinikai/adatgazdai
felelőssel és a terméktulajdonossal kell dönteni, nem kizárólag a fejlesztőnek.
