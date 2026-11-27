# 6. heti labor: válaszok

## 2. feladat: A szelettábla értelmezése

1. A legalacsonyabb ROC AUC érték az `50+` korcsoporté: 0,6071, míg az összesített érték 0,8345, vagyis a különbség 0,2274. Ebben a csoportban mindössze 19 beteg van, ezért a becslés bizonytalan; a beállított támogatottsági szabály helyesen kihagyja ezt a csoportot, és nem tekinti a különbséget megbízható bizonyítéknak.
2. Ezt kivizsgálandó jelzésként érdemes kezelni, nem pedig a modell azonnali módosításának indokaként. Ellenőrizni kell az adatok minőségét és a hibás eseteket, majd a feltételezést nagyobb, reprezentatív csoporton vagy egy későbbi, független mintán is érvényesíteni, mielőtt módosítanánk a modellt vagy az alkalmazási szabályokat.
3. Az `under_normal` BMI-csoportban 30 beteg van, de csak egy pozitív eset. Az osztályozó egyetlen pozitív esetet sem jelez előre, ezért az F1 értéke 0,0000. Ennek ellenére a pozitív beteg kapta a legmagasabb előrejelzett valószínűséget, ezért a ROC AUC 1,0000: a rangsorolás tökéletes, de a rögzített döntési küszöb elmulasztja ezt az esetet. Egyetlen pozitív példa mellett egyik eredmény sem tekinthető megbízható becslésnek.

## 4. feladat: A gate mint pipeline-stage

1. A verdict az értékeléstől függ, az értékelés pedig az előkészített adatoktól. Ha a `prepare` a verdicttől függne, körkörös függőség jönne létre. Ezért a gate az utolsó DVC-stage, és NO-GO esetén nem nulla kilépési kóddal áll le. A `register` és a `promote` nem későbbi DVC-stage-ként, hanem a `require_go` segítségével olvassa be és ellenőrzi az eltárolt verdictet.
2. A `require_go` nélkül bárki közvetlenül regisztrálhatna egy elbukott vagy még nem is értékelt modellt. A gate jelentése ettől még meglenne, de a registry művelet megkerülné az ellenőrzést; a problémára csak a promóció, az élesítés vagy egy későbbi audit során derülhetne fény.
3. `C: 0.005` mellett az F1 0,1098-cal, 0,5243-ra csökken, miközben a ROC AUC 0,8427-re nő. Egyik mérőszám sem minden helyzetben a „helyes” választ adja: az F1 a küszöb mellett számított precizitást és recallt méri, a ROC AUC pedig a küszöbökön átívelő rangsorolási képességet. A prioritás attól függ, hogyan használjuk az előrejelzéseket, hol van a döntési küszöb, valamint milyen következménye van az elmulasztott eseteknek és a téves riasztásoknak. Az `acceptance.regression.primary_metric` egyértelművé teszi ezt a prioritást: a modell a kiválasztott mérőszámban legfeljebb `max_drop` mértékben romolhat, akkor is, ha egy másik mérőszáma javul.

## 5. feladat: Hibák vizsgálata csoportonként

1. Az életkori csoportok közötti selection-rate különbség 0,3030, de a selection rate önmagában nem bizonyít egyenlőtlen bánásmódot: az egyes korcsoportok alapgyakorisága eltérhet, és klinikailag nem feltétlenül az azonos kiválasztási arány a kívánatos. A gate ehelyett az életkori csoportok közötti TPR-különbséget korlátozza (ennek mért értéke 0,2059), amely azt mutatja, mennyire találja meg a modell a tényleges pozitív eseteket. Ezt a döntést a klinikai következmények és az érintettek véleménye alapján is felül kell vizsgálni.
2. Az inzulinadat hiánya az eltérő vizsgálati gyakorlattal vagy az ellátáshoz való hozzáféréssel is összefügghet, ezért ezen a tengelyen indokolt szigorúbb TPR-korlátot alkalmazni (0,20; a mért érték 0,1562). Az életkorra vonatkozó korlát megengedőbb (0,25), mert az életkor klinikailag értelmezhető csoportosítás, a jelenlegi értéket pedig viszonylag kis csoportokból becsüljük. Nagyobb, reprezentatív validációs minta, illetve az egyenlőtlen károkra utaló bizonyíték indokolhatná a korlát szigorítását.
3. Az etnikai csoportok szerinti teljesítményt is auditálnám, de az adatkészlet nem tartalmaz ilyen attribútumot. Ezt az adatot már a modell tanítása és értékelése előtt, jogszerűen, megfelelő hozzájárulással és adatvédelmi garanciák mellett, világos céllal és reprezentatív lefedettséggel kellett volna gyűjteni; utólag nem lehet megbízhatóan rekonstruálni.

## 6. feladat: A ratchet (opcionális)

A `baseline_from_registry` feloldja a beállított champion aliast, betölti a hozzá tartozó regisztrált modellt, majd az aktuális tesztadathalmazon értékeli ki, mielőtt rögzítené a baseline mérőszámait. Így az összehasonlítás az aktuális értékelési adatokhoz kötődik, nem egy másik adathalmazon mért, korábbi pontszámokat használja fel. A teljes, Dockerre épülő ratchet-folyamat ebben a munkakörnyezetben nem futott le.
