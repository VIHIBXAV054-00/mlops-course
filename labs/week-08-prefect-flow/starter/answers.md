# 8. heti labor: válaszok

Ütemezett futás neve és végső állapota: `hilarious-bulldog` — `Completed`.

## Exercise 2 — DVC és Prefect

1. A Prefect ütemezett és kézzel indított futásokat kezel, elmenti a flow- és taskfutások állapotát, idejét és naplóit, valamint retry-kat kezel backoff-fal és jitterrel. Ezekkel meg lehet találni, mikor és hol hibázott egy futás, illetve átmeneti hálózati hibánál újrapróbálható a művelet. A DVC ezzel szemben a fájlfüggőségeket, a tartalmi hash-eket és a szakaszok eredményeit követi, ezért felismeri az elavult szakaszokat, és újrafelhasználja a gyorsítótárazott eredményeket.
2. Ha a DVC-szakaszokat külön Prefect-taskokra bontanánk, megkettőznénk a függőségi gráfot, és elveszíthetnénk a DVC tartalomhash-alapú gyorsítótárazását, illetve pontos inkrementális újrafuttatását. A két orchestrator eltérően ítélhetné meg, melyik szakasz elavult. Külön taskokra bontás akkor hasznos, ha a lépéseknek eltérő erőforrás-, retry-, párhuzamosítási vagy külső szolgáltatási követelménye van, és a DVC-függőségeket továbbra is egyértelműen megőrizzük.

## Exercise 5 — Ütemezett flow

1. Nem. A GO szükséges, de nem elégséges feltétele a kiadásnak: kell emberi felülvizsgálat, független validáció, kockázat- és fairness-ellenőrzés, fokozatos bevezetés, monitorozás és visszaállítási terv.
2. Sikertelen futásnál értesíteném a modellért felelős csapatot és az ügyeletest; az értesítés tartalmazza a futás azonosítóját, a hibás taskot, a paramétereket, az adatverziót és a hiba okát. Sikeres futásnál a gate eredménye és a modell nyilvántartási adatai menjenek a modellgazdáknak, de a GO önmagában ne indítson kiadást.
3. Az első hibáról jelzést küldenék a futás gazdájának; a második egymást követő hibánál eszkalálnám az ügyeletesnek vagy a csapatvezetőnek, és felfüggeszteném az automatikus újabb futásokat a kivizsgálásig.
4. Az olyan hibát továbbra is észrevétlenül hagyhatja a flow-n belüli értesítés, amely miatt a flow el sem indul: például leáll a Prefect szerver vagy a `.serve()` folyamat, illetve hibás a schedule. Ilyenkor nincs futás, amely értesítést küldhetne.
