{"status":"ok","model_version":"1","run_id":"fbfc41198cb44aa0a4d544907aa8f694","gate_verdict":"GO","schema_version":"1.0.0","model_source":"registry champion"}

1.
a) Elfogadta (pontozta): alapértelmezett kérés, glucose=0, glucose=-50, age=250 és bmi=336.
Visszautasította: extra oszlop (cholesterol), hiányzó oszlop (bmi), megváltozott oszlopsorrend.
Komponens a visszautasításoknál: scikit-learn SimpleImputer (_check_feature_names).
b)
- glucose=0 és glucose=-50: a glucose: Field(gt=0) szabály miatt.
- age=250 és bmi=336: az age: Field(le=120) és bmi: Field(le=100.0) szabályok miatt.
c) 
bemeneti adatvalidáció
monitorozása / naplózása.

3.
a) HTTP/JSON szerializáció, FastAPI routing, Pydantic típusvalidáció, DataFrame átalakítások.
b) Batch: Ügyfél-lemorzsolódás előrejelzése (minden adat előre rendelkezésre áll, a válaszidő nem sürgős).
Online: valós idejű csalásszűrés (egyesével érkező adatok, válaszidő számít).
Megkülönböztetés: az input elérhetőségének ideje és a válaszidő elvárása.
c) A késleltetéseknél a kiugró értékek nagyon leronthatják az átlagot. A p50 a tipikus kérést, a p95 a legrosszabb 5%-ot mutatja.

4.
a) Ez az image: a beépített modell miatt a pod a registry nélkül is elindul és kiszolgálja a forgalmat.
Registry-ből letölthető image: a modell letöltése sikertelen lesz és kiesést okoz.
