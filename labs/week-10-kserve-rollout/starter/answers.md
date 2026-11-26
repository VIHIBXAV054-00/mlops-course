2.
a)
- promote.when: "24 hours without a failed check or 5xx response"
  - Signal: HTTP 5xx státuszkódok és smoke test lefutások.
  - Döntési idő: 24 óra.
- rollback.when elem: "any smoke check fails"
  - Signal: Smoke test szintetikus ellenőrzései.
  - Döntési idő: másodpercek.
- True diagnosis: A valós diagnózis nem áll rendelkezésre még ilyenkor, az eredmények visszaérkezése több napba telik.

b)
- Páciensek száma: 30 (300 * 10%).
- v2 jobb e mint v1: Nem, ekkora adathalmazon és valós címkék nélkül nem mutatható ki statisztikai előny.
- Mit tud megmutatni: Technikai működőképességet, hibamentességet, késleltetést és extrém anomáliák hiányát valós forgalom mellett.

c)
- min_probability_spread: 0.1
- v3 elkapása: 0.1978-nál nagyobb érték, mivel a v3 spreadje 0.1978.
- v2 0.71 spread közeli érték kockázata: Normális szórás mellett tévesen elutasíthat jó modelleket is (false rejection).

3.
a)
- Miért tér el: Kis mintánál (200) a statisztikai mintavételi ingadozás miatt a mért érték eltér a várt aránytól.
- Kérések száma 1 százalékpont szignifikanciájához: Legalább 900 kérés kell (SE = sqrt(0.1*0.9/N) <= 0.01).

4.
a)
- Bukott ellenőrzések:
  - identity.gate.
  - behaviour.positive_is_positive.
- Sikeres ellenőrzések:
  - K8s readiness probe.
  - identity.health.
  - identity.version.
  - contract.illegal_rejected.
  - behaviour.negative_is_negative.
  - behaviour.not_a_constant.
  - protocol.v1_agrees.
- Egyetlen megtartandó ellenőrzés és indoklás:
  - identity.gate: Mert a teljes validációs adathalmazon mért minőségi döntést (metrikák, határértékek, fairness) vizsgál.

5.
a)
- Mit változtatott meg a rollback:
  - KServe/Knative: a 'canaryTrafficPercent'-et 0-ra állította, így a forgalom 100%-a azonnal visszaállt a stabil v1 revízióra.
- Mit NEM állított vissza:
  - A modell-tár állapotát (a v3 publikálva maradt a 'model-store/'-ban).
  - A registry állapotát.
  - A DVC fájlokat és a 'metrics/baseline.json'-t.
  - A v3 által adott válaszokat.

b)
- Rollback lépések:
  1. Forgalom azonnali nullázása a kanárin.
  2. Eredeti stabil manifest újraalkalmazása ('make rollback-reapply').
  3. Hibás modell visszavonása/törlése a modell-tárból és a registry-ből.
  4. A kanári futása alatt érkezett kérések ellenőrzése, téves predikciók korrekciója a downstream rendszerekben.
- Tesztelt és még nem tesztelt lépések:
  - Tesztelt: Az 1. lépés.
  - Nem tesztelt: A 2–4. lépések.
